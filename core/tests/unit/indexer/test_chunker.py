from __future__ import annotations

from breakdown.indexer.chunker import chunk_tree

# ---------------------------------------------------------------------------
# Minimal mock AST nodes for tests that need AST-level chunking.
# We build these directly rather than going through parse_file(), because the
# autouse mock in conftest.py returns a bare MockTree with no children, which
# would produce zero AST chunks and make the AST-dependent tests fail.
# ---------------------------------------------------------------------------


class _MockIdent:
    """Minimal identifier node."""

    def __init__(self, text: str, line: int, col: int = 0) -> None:
        self.type = "identifier"
        self.start_point = (line, col)
        self.end_point = (line, col + len(text))
        self.children: list[object] = []


class _MockNode:
    """Minimal AST node with a type, span, and optional identifier child."""

    def __init__(
        self,
        type_: str,
        start: int,
        end: int,
        name_text: str = "",
        name_col: int = 0,
        children: list[object] | None = None,
    ) -> None:
        self.type = type_
        self.start_point = (start, 0)
        self.end_point = (end, 0)
        self._name_text = name_text
        self.children: list[object] = children if children is not None else []
        if name_text:
            self.children.insert(0, _MockIdent(name_text, start, name_col))


class _MockRoot:
    """Module-level root node whose children are top-level statements."""

    def __init__(self, children: list[object]) -> None:
        self.type = "module"
        self.start_point = (0, 0)
        self.end_point = (100, 0)
        self.children = children


class _MockTree:
    """Minimal tree wrapper."""

    def __init__(self, root: _MockRoot) -> None:
        self.root_node = root


def _make_hello_tree() -> _MockTree:
    """Build a fake AST that mirrors core/tests/fixtures/sample_project/src/hello.py.

    hello.py (1-indexed lines):
        1: def greet(name: str) -> str:
        2:     return f"Hello, {name}"
        3:
        4:
        5: class Greeter:
        6:     def __init__(self, prefix: str) -> None:
        7:         self.prefix = prefix
        8:
        9:     def greet(self, name: str) -> str:
       10:         return f"{self.prefix}, {name}"
    """
    # "def greet(...)" -- identifier starts at col 4
    greet_fn = _MockNode("function_definition", start=0, end=1, name_text="greet", name_col=4)
    # "class Greeter:" -- identifier starts at col 6
    greeter_cls = _MockNode("class_definition", start=4, end=9, name_text="Greeter", name_col=6)
    root = _MockRoot(children=[greet_fn, greeter_cls])
    return _MockTree(root)


# hello.py source bytes (must match the fake AST line numbers above)
_HELLO_SOURCE: bytes = b"""\
def greet(name: str) -> str:
    return f"Hello, {name}"


class Greeter:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def greet(self, name: str) -> str:
        return f"{self.prefix}, {name}"
"""


def test_chunks_python_functions() -> None:
    tree = _make_hello_tree()
    chunks = chunk_tree(tree, _HELLO_SOURCE, "src/hello.py", window_lines=50)
    names = [c.name for c in chunks]
    assert "greet" in names


def test_chunks_python_class() -> None:
    tree = _make_hello_tree()
    chunks = chunk_tree(tree, _HELLO_SOURCE, "src/hello.py", window_lines=50)
    types = [c.type for c in chunks]
    assert "class" in types


def test_chunk_has_correct_file() -> None:
    tree = _make_hello_tree()
    chunks = chunk_tree(tree, _HELLO_SOURCE, "src/hello.py", window_lines=50)
    assert all(c.file == "src/hello.py" for c in chunks)


def test_fallback_plain_text_chunks_when_no_tree() -> None:
    """tree is None for unknown extensions; chunk_tree must fall back to text chunks."""
    # We test the plain-text path directly with synthetic source.
    source = b"line one\nline two\nline three\n"
    chunks = chunk_tree(None, source, "src/unknown.xyz", window_lines=50)
    assert len(chunks) >= 1
    assert chunks[0].type == "text"


def test_chunk_line_numbers_are_positive() -> None:
    tree = _make_hello_tree()
    chunks = chunk_tree(tree, _HELLO_SOURCE, "src/hello.py", window_lines=50)
    assert all(c.start_line >= 1 for c in chunks)
    assert all(c.end_line >= c.start_line for c in chunks)
