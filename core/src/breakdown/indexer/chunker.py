from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    file: str
    start_line: int
    end_line: int
    text: str
    type: str  # "function" | "class" | "import" | "variable" | "text"
    name: str


_AST_CHUNK_TYPES: dict[str, str] = {
    "function_definition": "function",
    "async_function_def": "function",
    "class_definition": "class",
    "import_statement": "import",
    "import_from_statement": "import",
    "expression_statement": "variable",
}


def chunk_tree(
    tree: object | None,
    source: bytes,
    file: str,
    window_lines: int,
) -> list[Chunk]:
    if tree is None:
        return _plain_text_chunks(source, file, window_lines)
    return _ast_chunks(tree, source, file)


def _ast_chunks(tree: object, source: bytes, file: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    lines = source.decode("utf-8", errors="replace").splitlines()

    def walk(node: object) -> None:
        node_type: str = getattr(node, "type", "")
        chunk_type = _AST_CHUNK_TYPES.get(node_type)
        if chunk_type:
            start: int = getattr(node, "start_point", (0,))[0] + 1
            end: int = getattr(node, "end_point", (0,))[0] + 1
            text = "\n".join(lines[start - 1 : end])
            name = _extract_name(node, lines)
            chunks.append(
                Chunk(
                    file=file,
                    start_line=start,
                    end_line=end,
                    text=text,
                    type=chunk_type,
                    name=name,
                )
            )
        else:
            for child in getattr(node, "children", []):
                walk(child)

    walk(getattr(tree, "root_node", tree))
    return chunks


def _extract_name(node: object, lines: list[str]) -> str:
    for child in getattr(node, "children", []):
        if getattr(child, "type", "") == "identifier":
            start = getattr(child, "start_point", (0, 0))
            line = lines[start[0]] if start[0] < len(lines) else ""
            return line[start[1] : getattr(child, "end_point", (0, len(line)))[1]]
    return ""


def _plain_text_chunks(source: bytes, file: str, window_lines: int) -> list[Chunk]:
    lines = source.decode("utf-8", errors="replace").splitlines()
    chunks: list[Chunk] = []
    for i in range(0, len(lines), window_lines):
        block = lines[i : i + window_lines]
        chunks.append(
            Chunk(
                file=file,
                start_line=i + 1,
                end_line=i + len(block),
                text="\n".join(block),
                type="text",
                name="",
            )
        )
    return chunks if chunks else [
        Chunk(file=file, start_line=1, end_line=1, text="", type="text", name="")
    ]
