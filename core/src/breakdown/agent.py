from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from livekit import agents  # type: ignore[import-untyped]
from livekit.agents import Agent, AgentSession, RoomInputOptions  # type: ignore[import-untyped]
from livekit.rtc.rpc import RpcInvocationData  # type: ignore[import-untyped]

from breakdown.config import get_settings
from breakdown.indexer.store import create_store
from breakdown.providers.llm import create_llm
from breakdown.providers.tts import create_tts
from breakdown.rpc_handlers import (
    HandlerDeps,
    handle_ask,
    handle_explain,
    handle_next,
    handle_prev,
    handle_stop,
)
from breakdown.session import Session

# Bumped whenever the RPC method set or payload shapes change; see
# docs/protocol.md for the full history.
PROTOCOL_VERSION = 2


# Module-level function so livekit-agents can pickle it for worker subprocesses.
async def entrypoint(ctx: agents.JobContext) -> None:
    settings = get_settings()
    breakdown_dir = Path(os.environ.get("BREAKDOWN_DIR", ".breakdown"))
    workspace_root = breakdown_dir.parent
    store = create_store(settings.index_backend, breakdown_dir / "index")

    session = Session.load(breakdown_dir / "session.json") or Session(
        workspace_root=workspace_root
    )
    session_path = breakdown_dir / "session.json"

    llm = create_llm(settings)
    tts = create_tts(settings)
    agent_session = AgentSession(llm=llm, tts=tts)  # type: ignore[arg-type]

    deps = HandlerDeps(
        session=session,
        session_path=session_path,
        store=store,
        workspace_root=workspace_root,
        settings=settings,
        agent_session=agent_session,
        llm=llm,
    )

    def _register(
        method_name: str,
        handler: Callable[[str, HandlerDeps], Awaitable[str]],
    ) -> None:
        async def _wrapped(data: RpcInvocationData) -> str:
            return await handler(data.payload, deps)

        ctx.room.local_participant.register_rpc_method(method_name, _wrapped)  # type: ignore[attr-defined]

    # local_participant is only available once the room connection is live.
    await ctx.connect()  # type: ignore[attr-defined]

    _register("explain", handle_explain)
    _register("ask", handle_ask)
    _register("next", handle_next)
    _register("prev", handle_prev)
    _register("stop", handle_stop)

    await agent_session.start(  # type: ignore[attr-defined]
        agent=Agent(instructions="You are a helpful code explainer."),
        room=ctx.room,  # keyword-only in livekit-agents v1.6+
        room_input_options=RoomInputOptions(),
    )
