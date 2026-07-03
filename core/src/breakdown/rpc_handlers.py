from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from livekit.agents import AgentSession  # type: ignore[import-untyped]
from livekit.agents import llm as lk_llm  # type: ignore[import-untyped]
from livekit.rtc.rpc import RpcError  # type: ignore[import-untyped]
from loguru import logger

from breakdown.config import Settings
from breakdown.indexer.store import VectorStore
from breakdown.session import Session

RPC_ERROR_PROVIDER_FAILURE = 2001
RPC_ERROR_EMPTY_QUESTION = 2002


@dataclass
class HandlerDeps:
    session: Session
    session_path: Path
    store: VectorStore
    workspace_root: Path
    settings: Settings
    agent_session: AgentSession  # type: ignore[type-arg]
    llm: object


def build_system_prompt(session: Session, context_chunks: list[str], window: str) -> str:
    ctx = "\n\n---\n\n".join(context_chunks) if context_chunks else "No additional context."
    return (
        "You are Breakdown, a voice-driven code explainer. "
        "Explain code clearly and concisely as if speaking to the developer who wrote it. "
        "Be direct. Do not say 'certainly' or 'of course'. "
        "When asked about a specific line, explain what it does and why it matters in context.\n\n"
        f"Codebase context:\n{ctx}\n\n"
        f"Current code window:\n{window}"
    )


async def index_context(
    store: VectorStore,
    file: str,
    line: int,
    workspace_root: Path,
    settings: Settings,
) -> tuple[list[str], str]:
    abs_path = workspace_root / file
    try:
        source_lines = abs_path.read_text(errors="replace").splitlines()
    except OSError:
        return [], ""

    half = settings.context_window_lines // 2
    start = max(0, line - 1 - half)
    end = min(len(source_lines), line - 1 + half)
    window = "\n".join(
        f"{i + 1}: {src}" for i, src in enumerate(source_lines[start:end], start=start)
    )

    try:
        from breakdown.indexer.embedder import create_embedder
        embedder = create_embedder(settings.embedding_provider, settings)
        query_emb = embedder.embed([source_lines[line - 1] if line <= len(source_lines) else ""])[0]
        chunks = store.search(query_emb, k=5)
        context = [c.text for c in chunks]
    except Exception as exc:
        logger.warning("Context retrieval failed: {}", exc)
        context = []

    return context, window


async def _generate_text(llm_plugin: object, system: str, question: str) -> str:
    chat_ctx = lk_llm.ChatContext()
    chat_ctx.add_message(role="system", content=system)
    chat_ctx.add_message(role="user", content=question)
    try:
        response = await llm_plugin.chat(chat_ctx=chat_ctx).collect()  # type: ignore[attr-defined]
    except Exception as exc:
        raise RpcError(RPC_ERROR_PROVIDER_FAILURE, f"LLM call failed: {exc}") from None
    return str(response.text)


def _last_system_prompt(session: Session) -> str:
    for turn in reversed(session.history):
        if turn["role"] == "system":
            return turn["content"]
    return (
        "You are Breakdown, a voice-driven code explainer. "
        "Answer clearly and concisely."
    )


async def handle_explain(payload: str, deps: HandlerDeps) -> str:
    data: dict[str, object] = json.loads(payload)
    file = str(data.get("file", ""))
    line = int(data.get("line", 1))  # type: ignore[arg-type]
    deps.session.current_file = file
    deps.session.current_line = line

    context, window = await index_context(
        deps.store, file, line, deps.workspace_root, deps.settings,
    )
    system = build_system_prompt(deps.session, context, window)
    deps.session.add_turn("system", system)
    budget = int(deps.settings.llm_context_window * deps.settings.history_budget_pct)
    deps.session.trim_to_budget(budget)

    question = f"Explain line {line} in {file}."
    deps.session.add_turn("user", question)

    text = await _generate_text(deps.llm, system, question)

    deps.session.add_turn("assistant", text)
    deps.session.save(deps.session_path)
    deps.agent_session.say(text, allow_interruptions=True)  # type: ignore[attr-defined]

    return json.dumps({"text": text, "file": file, "line": line})


async def handle_ask(payload: str, deps: HandlerDeps) -> str:
    data: dict[str, object] = json.loads(payload)
    text = str(data.get("text", ""))
    if not text:
        raise RpcError(RPC_ERROR_EMPTY_QUESTION, "Question text must not be empty")

    deps.session.add_turn("user", text)
    system = _last_system_prompt(deps.session)
    answer = await _generate_text(deps.llm, system, text)
    deps.session.add_turn("assistant", answer)
    deps.session.save(deps.session_path)
    deps.agent_session.say(answer, allow_interruptions=True)  # type: ignore[attr-defined]

    return json.dumps({"text": answer})


async def handle_next(payload: str, deps: HandlerDeps) -> str:
    deps.session.current_line += 1
    deps.session.save(deps.session_path)
    return json.dumps({"file": deps.session.current_file, "line": deps.session.current_line})


async def handle_prev(payload: str, deps: HandlerDeps) -> str:
    deps.session.current_line = max(1, deps.session.current_line - 1)
    deps.session.save(deps.session_path)
    return json.dumps({"file": deps.session.current_file, "line": deps.session.current_line})


async def handle_stop(payload: str, deps: HandlerDeps) -> str:
    await deps.agent_session.aclose()  # type: ignore[attr-defined]
    return json.dumps({"ok": True})
