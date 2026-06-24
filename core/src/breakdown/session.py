from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


def _count_tokens(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # character-based approximation: ~4 chars per token
        return len(text) // 4


@dataclass
class Session:
    workspace_root: Path
    current_file: str = ""
    current_line: int = 0
    history: list[dict[str, str]] = field(default_factory=list)

    def add_turn(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})

    def token_count(self) -> int:
        return sum(_count_tokens(t["content"]) for t in self.history)

    def trim_to_budget(self, max_tokens: int) -> None:
        while self.token_count() > max_tokens and len(self.history) > 2:
            # remove oldest pair (user + assistant)
            self.history = self.history[2:]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        data = {
            "current_file": self.current_file,
            "current_line": self.current_line,
            "workspace_root": str(self.workspace_root),
            "history": self.history,
        }
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> Session | None:
        if not path.exists():
            return None
        try:
            data: dict[str, object] = json.loads(path.read_text())
            return cls(
                workspace_root=Path(str(data["workspace_root"])),
                current_file=str(data.get("current_file", "")),
                current_line=int(data.get("current_line", 0)),  # type: ignore[arg-type]
                history=list(data.get("history", [])),  # type: ignore[arg-type]
            )
        except Exception as e:
            logger.warning("Session file corrupt, ignoring: {}", e)
            return None
