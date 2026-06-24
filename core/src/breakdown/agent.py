from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from loguru import logger
from livekit import agents  # type: ignore[import-untyped]
from livekit.agents import AgentSession, Agent, RoomInputOptions  # type: ignore[import-untyped]

from breakdown.config import Settings
from breakdown.indexer.store import VectorStore
from breakdown.providers.llm import create_llm
from breakdown.providers.tts import create_tts
from breakdown.providers.stt import create_stt
from breakdown.session import Session


def _room_name(workspace_root: Path) -> str:
    digest = hashlib.sha256(str(workspace_root.resolve()).encode()).hexdigest()[:12]
    return f"breakdown-{digest}"


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
        lines = abs_path.read_text(errors="replace").splitlines()
    except OSError:
        return [], ""

    half = settings.context_window_lines // 2
    start = max(0, line - 1 - half)
    end = min(len(lines), line - 1 + half)
    window = "\n".join(
        f"{i + 1}: {l}" for i, l in enumerate(lines[start:end], start=start)
    )

    try:
        from breakdown.indexer.embedder import create_embedder
        embedder = create_embedder(settings.embedding_provider, settings)
        query_emb = embedder.embed([lines[line - 1] if line <= len(lines) else ""])[0]
        chunks = store.search(query_emb, k=5)
        context = [c.text for c in chunks]
    except Exception as e:
        logger.warning("Context retrieval failed: {}", e)
        context = []

    return context, window


def create_agent(
    settings: Settings,
    store: VectorStore,
    breakdown_dir: Path,
) -> Any:
    async def entrypoint(ctx: agents.JobContext) -> None:
        workspace_root = breakdown_dir.parent
        session = Session.load(breakdown_dir / "session.json") or Session(
            workspace_root=workspace_root
        )
        session_path = breakdown_dir / "session.json"

        llm = create_llm(settings)
        tts = create_tts(settings)
        stt = create_stt(settings)

        agent_session = AgentSession(llm=llm, tts=tts, stt=stt)

        async def on_data(packet: Any) -> None:
            import json as _json
            try:
                msg = _json.loads(packet.data)
            except Exception:
                return

            msg_type: str = msg.get("type", "")

            if msg_type == "explain":
                session.current_file = msg.get("file", "")
                session.current_line = int(msg.get("line", 1))
                context, window = await _index_context(
                    store,
                    session.current_file,
                    session.current_line,
                    workspace_root,
                    settings,
                )
                system = _build_system_prompt(session, context, window)
                target_line = window.split("\n")[settings.context_window_lines // 2] if window else ""
                await agent_session.say(
                    f"Line {session.current_line}: {target_line}",
                    allow_interruptions=True,
                )
                session.add_turn("user", f"Explain line {session.current_line}: {target_line}")
                session.save(session_path)

            elif msg_type == "next":
                session.current_line += 1
                await ctx.room.local_participant.publish_data(
                    _json.dumps({"v": 1, "type": "position", "file": session.current_file, "line": session.current_line}).encode()
                )
                session.save(session_path)

            elif msg_type == "prev":
                session.current_line = max(1, session.current_line - 1)
                session.save(session_path)

            elif msg_type == "stop":
                await agent_session.aclose()

        ctx.room.on("data_received", on_data)
        await agent_session.start(
            ctx.room,
            agent=Agent(instructions="You are a helpful code explainer."),
            room_input_options=RoomInputOptions(),
        )

    return entrypoint
