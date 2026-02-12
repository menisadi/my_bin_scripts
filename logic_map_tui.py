#!/usr/bin/env -S uv run
# /// script
# dependencies = ["rich", "textual"]
# ///

"""
logic_map_tui.py – interactive, foldable AST viewer
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import sys
from textwrap import shorten
from types import FunctionType, ModuleType

from textual.app import App, ComposeResult
from textual.widgets import Tree, Header, Footer  # ← modern import path
from textual.widgets.tree import TreeNode
from rich.text import Text

# ── helpers ──────────────────────────────────────────────────────────────
# Build LOGICAL_NODES dynamically so the code also works on Python < 3.10,
# whose `ast` module has no Match node.
LOGICAL_NODES: tuple[type[ast.AST], ...] = (
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.If,
    ast.For,
    ast.While,
    ast.With,
    ast.Try,
) + ((ast.Match,) if hasattr(ast, "Match") else ())


def _expr(node: ast.AST, max_len: int = 60) -> str:
    """Return a one-line representation of *node* suitable for a label."""
    try:
        code = ast.unparse(node)  # Py ≥ 3.9
    except AttributeError:  # Py <= 3.8
        code = ast.dump(node, include_attributes=False)
    return shorten(code.replace("\n", " "), width=max_len, placeholder=" … ")


def _label(node: ast.AST) -> Text:
    """Return a colourised label for *node*."""
    if isinstance(node, ast.ClassDef):
        return Text.assemble(("class ", "cyan"), (node.name, "bold"))

    if isinstance(node, ast.FunctionDef):
        return Text.assemble(("def ", "green"), (f"{node.name}()", "bold"))

    if isinstance(node, ast.AsyncFunctionDef):
        return Text.assemble(("async def ", "green"), (f"{node.name}()", "bold"))

    if isinstance(node, ast.If):
        return Text.assemble(("if ", "magenta"), _expr(node.test))

    if isinstance(node, ast.For):
        return Text.assemble(
            ("for ", "magenta"),
            _expr(node.target),
            " in ",
            _expr(node.iter),
        )

    if isinstance(node, ast.While):
        return Text.assemble(("while ", "magenta"), _expr(node.test))

    if isinstance(node, ast.With):
        return Text.assemble(("with ", "magenta"), _expr(node.items[0].context_expr))

    if isinstance(node, ast.Try):
        return Text("try", style="magenta")

    # `ast.Match` only exists on Python ≥ 3.10
    if hasattr(ast, "Match") and isinstance(node, ast.Match):  # type: ignore[attr-defined]
        return Text.assemble(("match ", "magenta"), _expr(node.subject))

    return Text(type(node).__name__)


def _populate(tree_node: TreeNode, ast_node: ast.AST) -> None:
    """Recursively add logical AST nodes as children of *tree_node*."""
    for child in ast.iter_child_nodes(ast_node):
        if isinstance(child, LOGICAL_NODES):
            child_node = tree_node.add(_label(child))
            _populate(child_node, child)


def _to_source(obj) -> tuple[str, str]:
    """Return (display_name, source_code) for a file / function / module.

    The first element is used as the *filename* for ast.parse, so it **must**
    be a str or os.PathLike – never None.
    """
    if isinstance(obj, (str, pathlib.Path)):
        p = pathlib.Path(obj)
        return p.name, p.read_text(encoding="utf-8")

    if isinstance(obj, FunctionType):
        return obj.__name__, inspect.getsource(obj)

    if isinstance(obj, ModuleType):
        # __file__ may legitimately be None (built-ins, REPL code, etc.).
        # Fall back to the module’s qualified name so that `ast.parse`
        # always gets a real filename string.
        filename = getattr(obj, "__file__", None) or obj.__name__
        return pathlib.Path(filename).name, inspect.getsource(obj)

    raise TypeError(f"Unsupported input type: {type(obj).__name__}")


# ── Textual application ──────────────────────────────────────────────────
class LogicMapApp(App):
    """Interactive, scrollable AST viewer."""

    CSS = """
    Screen { layout: vertical; }
    Tree   { height: 1fr; width: 1fr; }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, target):
        self._name, self._source = _to_source(target)
        super().__init__()

    def compose(self) -> ComposeResult:  # noqa: D401 (simple verb is fine here)
        yield Header()

        tree = Tree(f"[bold bright_blue]{self._name}")
        _populate(
            tree.root,
            ast.parse(self._source, filename=self._name or "<input>"),
        )
        # In modern Textual the Tree already handles its own scrolling;
        # just yield it.  If you prefer an explicit scroll container:
        #   scroll = ScrollView()
        #   scroll.mount(tree)
        #   yield scroll
        yield tree
        yield Footer()


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python logic_map_tui.py path/to/file.py")
    LogicMapApp(sys.argv[1]).run()


if __name__ == "__main__":
    main()
