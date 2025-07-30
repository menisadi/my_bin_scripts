#!/usr/bin/env python3
"""
logic_map.py – pretty-prints the logical structure of a Python file.

Usage:
    python logic_map.py [options] path/to/module.py
    python -m logic_map [options] path/to/module.py      # if you `python -m pip install .`
    # Or from another script:
    from logic_map import show_logic_map; show_logic_map(fn_or_path, include_exits=True)
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import argparse
from textwrap import shorten  #  ← new
from types import FunctionType, ModuleType
from rich.console import Console
from rich.tree import Tree

#: base node types we want to show
BASE_LOGICAL_NODES = (
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

EXIT_NODES = (ast.Return, ast.Break, ast.Continue)
RAISE_NODES = (ast.Raise,)


def _expr(node: ast.AST, max_len: int = 60) -> str:
    """Return source for *node*, truncated nicely."""
    try:
        code = ast.unparse(node)  # Py ≥ 3.9
    except AttributeError:  # Py ≤ 3.8
        code = ast.dump(node, include_attributes=False)
    # collapse new-lines and over-long expressions
    return shorten(code.replace("\n", " "), width=max_len, placeholder=" … ")


#: quick palette
def _label(node: ast.AST, *, max_len: int = 60, show_lineno: bool = False) -> str:
    def with_lineno(text: str) -> str:
        if show_lineno and hasattr(node, "lineno"):
            return f"{text} [dim](L{getattr(node, 'lineno')})[/]"
        return text

    match node:
        # ── structural items ───────────────────────────────────────────────
        case ast.ClassDef(name=name):
            return with_lineno(f"[cyan]class[/] [bold]{name}")
        case ast.FunctionDef(name=name):
            return with_lineno(f"[green]def[/] [bold]{name}()")
        case ast.AsyncFunctionDef(name=name):
            return with_lineno(f"[green]async def[/] [bold]{name}()")

        # ── flow control, now with full conditions ─────────────────────────
        case ast.If(test=test):
            return with_lineno(f"[magenta]if[/] {_expr(test, max_len)}")
        case ast.For(target=target, iter=iter_):
            return with_lineno(
                f"[magenta]for[/] {_expr(target, max_len)} in {_expr(iter_, max_len)}"
            )
        case ast.While(test=test):
            return with_lineno(f"[magenta]while[/] {_expr(test, max_len)}")
        case ast.With(items=items):
            return with_lineno(
                f"[magenta]with[/] {_expr(items[0].context_expr, max_len)}"
            )
        case ast.Try():
            return with_lineno("[magenta]try[/]")
        case ast.Match(subject=subject):
            return with_lineno(f"[magenta]match[/] {_expr(subject, max_len)}")
        # ── exit points (opt-in) ───────────────────────────────────────────
        case ast.Return(value=value):
            if value is None:
                return with_lineno("[red]return[/]")
            return with_lineno(f"[red]return[/] {_expr(value, max_len)}")
        case ast.Break():
            return with_lineno("[red]break[/]")
        case ast.Continue():
            return with_lineno("[red]continue[/]")
        case ast.Raise(exc=exc, cause=cause):
            # "raise" or "raise exc" or "raise exc from cause"
            parts = []
            if exc is not None:
                parts.append(_expr(exc, max_len))
                if cause is not None:
                    parts.append(f"from {_expr(cause, max_len)}")
            tail = (" " + " ".join(parts)) if parts else ""
            return with_lineno(f"[red]raise[/]{tail}")
        case _:
            return with_lineno(type(node).__name__)


def _add_children(
    branch: Tree,
    node: ast.AST,
    nodes: tuple[type[ast.AST], ...],
    *,
    max_len: int,
    show_lineno: bool,
) -> None:
    """Recursively add logical children that belong to *node*."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, nodes):
            child_branch = branch.add(
                _label(child, max_len=max_len, show_lineno=show_lineno)
            )
            _add_children(
                child_branch, child, nodes, max_len=max_len, show_lineno=show_lineno
            )


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


def show_logic_map(
    target: str | pathlib.Path | FunctionType | ModuleType,
    *,
    include_exits: bool = False,
    include_raises: bool = False,
    show_lineno: bool = False,
    expr_width: int = 60,
) -> None:
    name, source = _to_source(target)
    root = ast.parse(source, filename=name)
    tree = Tree(f"[bold bright_blue]{name}", guide_style="bright_blue")
    nodes: tuple[type[ast.AST], ...] = BASE_LOGICAL_NODES
    if include_exits:
        nodes += EXIT_NODES
    if include_raises:
        nodes += RAISE_NODES
    _add_children(tree, root, nodes, max_len=expr_width, show_lineno=show_lineno)
    Console().print(tree)


# --- CLI -------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pretty-print the logical structure of a Python file."
    )
    parser.add_argument("path", help="path to a Python file")
    parser.add_argument(
        "-x",
        "--exits",
        action="store_true",
        help="include exit points: return/break/continue",
    )
    parser.add_argument(
        "-R", "--raises", action="store_true", help="include raise statements"
    )
    parser.add_argument(
        "-n", "--lineno", action="store_true", help="append line numbers like (L42)"
    )
    parser.add_argument(
        "-m",
        "--max-expr-len",
        type=int,
        default=60,
        help="truncate expressions to this width (default: 60)",
    )
    args = parser.parse_args()
    show_logic_map(
        args.path,
        include_exits=args.exits,
        include_raises=args.raises,
        show_lineno=args.lineno,
        expr_width=args.max_expr_len,
    )
