#!/usr/bin/env -S uv run
# /// script
# dependencies = ["rich"]
# ///

"""
logic_map_tui.py – interactive, foldable AST viewer
"""

from __future__ import annotations

import argparse
import ast
import inspect
import pathlib
import sys
from textwrap import dedent, shorten
from types import FunctionType, ModuleType
from typing import Union

from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Tree
from textual.widgets.tree import TreeNode

# ── helpers ──────────────────────────────────────────────────────────────
# Include the most common “logical” statement / handler nodes.
LOGICAL_NODES: tuple[type[ast.AST], ...] = (
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ExceptHandler,
) + ((ast.Match,) if hasattr(ast, "Match") else ())


def _expr(node: ast.AST, max_len: int = 60) -> str:
    """Return a one-liner representation of *node* suitable for a label."""
    try:
        code = ast.unparse(node)  # Py ≥ 3.9
    except AttributeError:  # Py ≤ 3.8
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
            ("for ", "magenta"), _expr(node.target), " in ", _expr(node.iter)
        )

    if isinstance(node, ast.AsyncFor):
        return Text.assemble(
            ("async for ", "magenta"), _expr(node.target), " in ", _expr(node.iter)
        )

    if isinstance(node, ast.While):
        return Text.assemble(("while ", "magenta"), _expr(node.test))

    if isinstance(node, ast.With):
        contexts = ", ".join(_expr(item.context_expr) for item in node.items)
        return Text.assemble(("with ", "magenta"), contexts)

    if isinstance(node, ast.AsyncWith):
        contexts = ", ".join(_expr(item.context_expr) for item in node.items)
        return Text.assemble(("async with ", "magenta"), contexts)

    if isinstance(node, ast.Try):
        return Text("try", style="magenta")

    if isinstance(node, ast.ExceptHandler):
        if node.type is None:
            return Text("except", style="magenta")
        return Text.assemble(("except ", "magenta"), _expr(node.type))

    if hasattr(ast, "Match") and isinstance(node, ast.Match):  # type: ignore[attr-defined]
        return Text.assemble(("match ", "magenta"), _expr(node.subject))

    return Text(type(node).__name__)


def _populate(tree_node: TreeNode, ast_node: ast.AST) -> None:
    """Recursively add logical AST nodes as children of *tree_node*."""
    for child in ast.iter_child_nodes(ast_node):
        if isinstance(child, LOGICAL_NODES):
            child_node = tree_node.add(_label(child))
            _populate(child_node, child)


_Target = Union[str, pathlib.Path, FunctionType, ModuleType]


def _to_source(obj: _Target) -> tuple[str, str]:
    """Return *(display_name, source_code)* from path / function / module."""
    if isinstance(obj, (str, pathlib.Path)):
        p = pathlib.Path(obj).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"No such file: {p}")
        return p.name, p.read_text(encoding="utf-8")

    if isinstance(obj, FunctionType):
        try:
            return obj.__name__, dedent(inspect.getsource(obj))
        except (OSError, TypeError) as err:
            raise ValueError(f"Cannot retrieve source for {obj}") from err

    if isinstance(obj, ModuleType):
        filename = getattr(obj, "__file__", None) or obj.__name__
        try:
            return pathlib.Path(filename).name, dedent(inspect.getsource(obj))
        except (OSError, TypeError) as err:
            raise ValueError(
                f"Cannot retrieve source for module {obj.__name__}"
            ) from err

    raise TypeError(f"Unsupported input type: {type(obj).__name__}")


# ── Textual application ──────────────────────────────────────────────────
class LogicMapApp(App):
    """Interactive, scrollable AST viewer."""

    CSS = """
    Screen { layout: vertical; }
    Tree   { height: 1fr; width: 1fr; }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, target: _Target):
        self._name, self._source = _to_source(target)
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()

        tree = Tree(f"[bold bright_blue]{self._name}")

        # Parse & populate
        try:
            parsed = ast.parse(self._source, filename=self._name or "<input>")
            _populate(tree.root, parsed)
        except SyntaxError as err:
            tree.root.add(Text(f"SyntaxError: {err}", style="red"))

        tree.root.expand()  # show first level automatically
        yield tree
        yield Footer()


# ── CLI glue ─────────────────────────────────────────────────────────────
def _parse_args(argv: list[str]) -> pathlib.Path:
    parser = argparse.ArgumentParser(
        prog="logic_map_tui",
        description="Interactive, foldable AST viewer for Python source files.",
    )
    parser.add_argument(
        "path",
        metavar="path/to/file.py",
        type=pathlib.Path,
        help="Python source file to inspect",
    )
    return parser.parse_args(argv).path


def main(argv: list[str] | None = None) -> None:
    argv = argv or sys.argv[1:]
    try:
        path: pathlib.Path = _parse_args(argv)
        LogicMapApp(path).run()
    except (FileNotFoundError, ValueError, TypeError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
