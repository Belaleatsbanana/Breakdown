from __future__ import annotations

import json
from pathlib import Path

from livekit import agents  # type: ignore[import-untyped]
from livekit.agents import Agent, AgentSession, RoomInputOptions  # type: ignore[import-untyped]
from loguru import logger

from breakdown.config import Settings
from breakdown.indexer.store import VectorStore
from breakdown.providers.llm import create_llm
from breakdown.providers.stt import create_stt
from breakdown.providers.tts import create_tts
from breakdown.session import Session


def _build_system_prompt(session: Session, context_chunks: list[str], window: str) -> str:
    ctx = "\n\n---\n\n".join(context_chunks) if context_chunks else "No additional context."
    return (
        "You are Breakdown, a voice-driven code explainer. "
        "Explain code clearly and concisely as if speaking to the developer who wrote it. "
        "Be direct. Do not say 'certainly' or 'of course'. "
        "When asked about a specific line, explain what it does and why it matters in context.\n\n"
        f"Codebase context:\n{ctx}\n\n"
        f"Current code window:\n{window}"
    )


async def _index_context(
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


def create_agent(
    settings: Settings,
    store: VectorStore,
    breakdown_dir: Path,
) -> object:
    async def entrypoint(ctx: agents.JobContext) -> None:
        workspace_root = breakdown_dir.parent
        session = Session.load(breakdown_dir / "session.json") or Session(
            workspace_root=workspace_root
        )
        session_path = breakdown_dir / "session.json"

        llm = create_llm(settings)
        tts = create_tts(settings)
        stt = create_stt(settings)

        agent_session = AgentSession(llm=llm, tts=tts, stt=stt)  # type: ignore[arg-type]

        async def on_data(packet: object) -> None:
            try:
                msg: dict[str, object] = json.loads(getattr(packet, "data", b"{}"))
            except Exception:
                return

            msg_type: str = str(msg.get("type", ""))

            if msg_type == "explain":
                session.current_file = str(msg.get("file", ""))
                session.current_line = int(msg.get("line", 1))  # type: ignore[arg-type]
                context, window = await _index_context(
                    store,
                    session.current_file,
                    session.current_line,
                    workspace_root,
                    settings,
                )
                system = _build_system_prompt(session, context, window)
                session.add_turn("system", system)
                budget = int(settings.llm_context_window * settings.history_budget_pct)
                session.trim_to_budget(budget)
                mid = settings.context_window_lines // 2
                window_lines = window.split("\n")
                target_line = window_lines[mid] if window and mid < len(window_lines) else ""
                await agent_session.say(  # type: ignore[attr-defined]
                    f"Line {session.current_line}: {target_line}",
                    allow_interruptions=True,
                )
                session.add_turn("user", f"Explain line {session.current_line}: {target_line}")
                session.save(session_path)

            elif msg_type == "next":
                session.current_line += 1
                payload = json.dumps({
                    "v": 1,
                    "type": "position",
                    "file": session.current_file,
                    "line": session.current_line,
                }).encode()
                await ctx.room.local_participant.publish_data(payload)  # type: ignore[attr-defined]
                session.save(session_path)

            elif msg_type == "prev":
                session.current_line = max(1, session.current_line - 1)
                payload = json.dumps({
                    "v": 1,
                    "type": "position",
                    "file": session.current_file,
                    "line": session.current_line,
                }).encode()
                await ctx.room.local_participant.publish_data(payload)  # type: ignore[attr-defined]
                session.save(session_path)

            elif msg_type == "stop":
                await agent_session.aclose()  # type: ignore[attr-defined]

        ctx.room.on("data_received", on_data)  # type: ignore[attr-defined]
        await agent_session.start(  # type: ignore[attr-defined]
            ctx.room,
            agent=Agent(instructions="You are a helpful code explainer."),
            room_input_options=RoomInputOptions(),
        )

    return entrypoint
