from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from breakdown import __version__
from breakdown.config import get_settings

app = typer.Typer(help="Breakdown -- voice-driven AI code explainer", add_completion=False)
console = Console()


@app.command()
def version() -> None:
    """Print the current version."""
    console.print(__version__)


@app.command()
def index(
    path: Path = typer.Argument(Path("."), help="Workspace root to index"),
) -> None:
    """Index a codebase for context-aware explanations."""
    settings = get_settings()
    path = path.resolve()
    breakdown_dir = path / ".breakdown"
    breakdown_dir.mkdir(parents=True, exist_ok=True)

    from breakdown.indexer.chunker import chunk_tree
    from breakdown.indexer.embedder import create_embedder
    from breakdown.indexer.ignore import IgnoreFilter
    from breakdown.indexer.manifest import Manifest
    from breakdown.indexer.parser import parse_file
    from breakdown.indexer.registry import LanguageRegistry
    from breakdown.indexer.store import create_store

    ignore = IgnoreFilter(path)
    registry = LanguageRegistry()
    embedder = create_embedder(settings.embedding_provider, settings)
    store = create_store(settings.index_backend, breakdown_dir / "index")
    manifest = Manifest(breakdown_dir / "manifest.json")

    files = [
        f for f in path.rglob("*")
        if f.is_file() and not ignore.is_ignored(f)
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Indexing {len(files)} files...", total=len(files))
        for file in files:
            if not manifest.is_stale(file):
                progress.advance(task)
                continue
            tree, source = parse_file(file, registry)
            rel = str(file.relative_to(path))
            chunks = chunk_tree(tree, source, rel, settings.context_window_lines)
            if chunks:
                embeddings = embedder.embed([c.text for c in chunks])
                ids = store.add(chunks, embeddings)
                manifest.update(file, ids)
            progress.advance(task)

    manifest.save()
    store.close()
    console.print(f"[green]Index complete.[/green] {len(files)} files processed.")


@app.command()
def start(
    path: Path = typer.Argument(Path("."), help="Workspace root"),
) -> None:
    """Start the Breakdown agent and token server."""
    settings = get_settings()
    path = path.resolve()
    breakdown_dir = path / ".breakdown"
    breakdown_dir.mkdir(parents=True, exist_ok=True)

    _ensure_livekit(settings)

    from breakdown.indexer.store import create_store
    from breakdown.token_server import TokenServer

    token_server = TokenServer(settings=settings, breakdown_dir=breakdown_dir)
    token_server.start_background()

    store = create_store(settings.index_backend, breakdown_dir / "index")

    from livekit.agents import WorkerOptions  # type: ignore[import-untyped]
    from livekit.agents import cli as lk_cli

    from breakdown.agent import create_agent

    entrypoint = create_agent(settings, store, breakdown_dir)
    lk_cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_url,
        )
    )


def _ensure_livekit(settings: object) -> None:
    import os
    if getattr(settings, "livekit_url", ""):
        return
    logger.info("No LIVEKIT_URL set -- starting local LiveKit server via Docker")
    try:
        subprocess.run(
            ["docker", "compose", "-f", "deploy/docker-compose.livekit.yml", "up", "-d"],
            check=True,
            capture_output=True,
        )
        os.environ["LIVEKIT_URL"] = "ws://localhost:7880"
        os.environ.setdefault("LIVEKIT_API_KEY", "devkey")
        os.environ.setdefault("LIVEKIT_API_SECRET", "devsecret1234567890123456789012345678")
        logger.info("Local LiveKit server started on ws://localhost:7880")
    except subprocess.CalledProcessError as e:
        logger.error("Failed to start local LiveKit: {}", e.stderr.decode())
        raise typer.Exit(1)
    except FileNotFoundError:
        logger.error("Docker not found. Install Docker or set LIVEKIT_URL in .env")
        raise typer.Exit(1)
