#!/usr/bin/env python3
"""
logic_map.py – pretty-prints the logical structure of a Python file.

Usage:
    python logic_map.py path/to/module.py
    python -m logic_map path/to/module.py      # if you `python -m pip install .`
    # Or from another script:
    from logic_map import show_logic_map; show_logic_map(fn_or_path)
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import sys
from textwrap import shorten  #  ← new
from types import FunctionType, ModuleType
from rich.console import Console
from rich.tree import Tree

#: node types we want to show
LOGICAL_NODES = (
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.If,
    ast.For,
    ast.While,
    ast.With,
    ast.Try,
    ast.Match,
)


def _expr(node: ast.AST, max_len: int = 60) -> str:
    """Return source for *node*, truncated nicely."""
    try:
        code = ast.unparse(node)  # Py ≥ 3.9
    except AttributeError:  # Py ≤ 3.8
        code = ast.dump(node, include_attributes=False)
    # collapse new-lines and over-long expressions
    return shorten(code.replace("\n", " "), width=max_len, placeholder=" … ")


#: quick palette
def _label(node: ast.AST) -> str:
    match node:
        # ── structural items ───────────────────────────────────────────────
        case ast.ClassDef(name=name):
            return f"[cyan]class[/] [bold]{name}"
        case ast.FunctionDef(name=name):
            return f"[green]def[/] [bold]{name}()"
        case ast.AsyncFunctionDef(name=name):
            return f"[green]async def[/] [bold]{name}()"

        # ── flow control, now with full conditions ─────────────────────────
        case ast.If(test=test):
            return f"[magenta]if[/] {_expr(test)}"
        case ast.For(target=target, iter=iter_):
            return f"[magenta]for[/] {_expr(target)} in {_expr(iter_)}"
        case ast.While(test=test):
            return f"[magenta]while[/] {_expr(test)}"
        case ast.With(items=items):
            return f"[magenta]with[/] {_expr(items[0].context_expr)}"
        case ast.Try():
            return "[magenta]try"
        case ast.Match(subject=subject):
            return f"[magenta]match[/] {_expr(subject)}"
        case _:
            return type(node).__name__


def _add_children(branch: Tree, node: ast.AST) -> None:
    """Recursively add logical children that belong to *node*."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, LOGICAL_NODES):
            child_branch = branch.add(_label(child))
            _add_children(child_branch, child)


def _to_source(obj: str | pathlib.Path | FunctionType | ModuleType) -> tuple[str, str]:
    """Return `(name, source_code)` for a file, module, or function."""
    if isinstance(obj, (pathlib.Path, str)):
        p = pathlib.Path(obj)
        return p.name, p.read_text(encoding="utf-8")
    if isinstance(obj, FunctionType):
        return obj.__name__, inspect.getsource(obj)
    if isinstance(obj, ModuleType):
        return getattr(obj, "__file__", obj.__name__), inspect.getsource(obj)
    raise TypeError("Unsupported input")


def show_logic_map(target: str | pathlib.Path | FunctionType | ModuleType) -> None:
    name, source = _to_source(target)
    root = ast.parse(source, filename=name)
    tree = Tree(f"[bold bright_blue]{name}", guide_style="bright_blue")
    _add_children(tree, root)
    Console().print(tree)


# --- CLI -------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python logic_map.py path/to/file.py")
    show_logic_map(sys.argv[1])
