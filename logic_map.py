#!/usr/bin/env -S uv run
# /// script
# dependencies = ["rich"]
# ///
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
from textwrap import shorten
from typing import TypedDict
from types import FunctionType, ModuleType
from rich.console import Console  # pyright: ignore[reportMissingImports]
from rich.tree import Tree  # pyright: ignore[reportMissingImports]

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


class _Opts(TypedDict):
    """Rendering options threaded through the recursive helpers."""
    max_depth: int
    max_len: int
    show_lineno: bool
    include_calls: bool


def _with_lineno_text(text: str, lineno: int | None, show: bool) -> str:
    return f"{text} [dim](L{lineno})[/]" if show and lineno is not None else text


def _expr(node: ast.AST, max_len: int = 60) -> str:
    """Return source for *node*, truncated nicely."""
    try:
        code = ast.unparse(node)  # Py ≥ 3.9
    except AttributeError:  # Py ≤ 3.8
        code = ast.dump(node, include_attributes=False)
    return shorten(code.replace("\n", " "), width=max_len, placeholder=" … ")


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

        # ── flow control ───────────────────────────────────────────────────
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
            parts: list[str] = []
            if exc is not None:
                parts.append(_expr(exc, max_len))
                if cause is not None:
                    parts.append(f"from {_expr(cause, max_len)}")
            tail = (" " + " ".join(parts)) if parts else ""
            return with_lineno(f"[red]raise[/]{tail}")
        case _:
            return with_lineno(type(node).__name__)


def _docstring_label(body: list[ast.stmt], max_len: int) -> str | None:
    """Return a dimmed label for the docstring if the body starts with one."""
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        first_line = body[0].value.value.strip().split("\n")[0]
        return f"[dim italic]{shorten(first_line, width=max_len, placeholder=' …')}[/]"
    return None


def _call_label(stmt: ast.Expr, max_len: int, show_lineno: bool) -> str:
    """Return a label for a statement-level call expression."""
    text = f"[blue]→[/] {_expr(stmt.value, max_len)}"
    if show_lineno and hasattr(stmt, "lineno"):
        text += f" [dim](L{stmt.lineno})[/]"
    return text


def _add_stmt_list(
    branch: Tree,
    stmts: list[ast.stmt],
    nodes: tuple[type[ast.AST], ...],
    opts: _Opts,
    *,
    depth: int,
) -> None:
    for stmt in stmts:
        if isinstance(stmt, nodes):
            child_branch = branch.add(
                _label(stmt, max_len=opts["max_len"], show_lineno=opts["show_lineno"])
            )
            _add_children(child_branch, stmt, nodes, opts, depth=depth + 1)
        elif opts["include_calls"] and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            branch.add(_call_label(stmt, opts["max_len"], opts["show_lineno"]))
        else:
            _add_children(branch, stmt, nodes, opts, depth=depth)


def _add_children(
    branch: Tree,
    node: ast.AST,
    nodes: tuple[type[ast.AST], ...],
    opts: _Opts,
    *,
    depth: int,
) -> None:
    # Stop recursing once we've hit the depth limit
    if opts["max_depth"] and depth >= opts["max_depth"]:
        return

    # ── Function/class: docstring then body ────────────────────────────────
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        doc = _docstring_label(node.body, opts["max_len"])
        if doc:
            branch.add(doc)
        _add_stmt_list(branch, node.body, nodes, opts, depth=depth)
        return

    # ── Special handling for 'try' so we show except/else/finally ─────────
    if isinstance(node, ast.Try):
        _add_stmt_list(branch, node.body, nodes, opts, depth=depth)

        for h in node.handlers:
            exc = _expr(h.type, opts["max_len"]) if h.type is not None else ""
            name = f" as {h.name}" if getattr(h, "name", None) else ""
            label = "[magenta]except[/]" + (f" {exc}{name}" if exc or name else "")
            exc_branch = branch.add(
                _with_lineno_text(label, getattr(h, "lineno", None), opts["show_lineno"])
            )
            _add_stmt_list(exc_branch, h.body, nodes, opts, depth=depth)

        if node.orelse:
            ln = getattr(node.orelse[0], "lineno", None)
            else_branch = branch.add(_with_lineno_text("[magenta]else[/]", ln, opts["show_lineno"]))
            _add_stmt_list(else_branch, node.orelse, nodes, opts, depth=depth)

        if node.finalbody:
            ln = getattr(node.finalbody[0], "lineno", None)
            fin_branch = branch.add(_with_lineno_text("[magenta]finally[/]", ln, opts["show_lineno"]))
            _add_stmt_list(fin_branch, node.finalbody, nodes, opts, depth=depth)
        return

    # ── 'if' with explicit 'else' branch ──────────────────────────────────
    if isinstance(node, ast.If):
        _add_stmt_list(branch, node.body, nodes, opts, depth=depth)
        if node.orelse:
            ln = getattr(node.orelse[0], "lineno", None)
            else_branch = branch.add(_with_lineno_text("[magenta]else[/]", ln, opts["show_lineno"]))
            _add_stmt_list(else_branch, node.orelse, nodes, opts, depth=depth)
        return

    # ── Loop 'else' (runs when loop isn't broken) ─────────────────────────
    if isinstance(node, (ast.For, ast.While)):
        _add_stmt_list(branch, node.body, nodes, opts, depth=depth)
        if node.orelse:
            ln = getattr(node.orelse[0], "lineno", None)
            else_branch = branch.add(_with_lineno_text("[magenta]else[/]", ln, opts["show_lineno"]))
            _add_stmt_list(else_branch, node.orelse, nodes, opts, depth=depth)
        return

    # ── Generic descent ────────────────────────────────────────────────────
    for child in ast.iter_child_nodes(node):
        if isinstance(child, nodes):
            child_branch = branch.add(
                _label(child, max_len=opts["max_len"], show_lineno=opts["show_lineno"])
            )
            _add_children(child_branch, child, nodes, opts, depth=depth + 1)
        elif opts["include_calls"] and isinstance(child, ast.Expr) and isinstance(child.value, ast.Call):
            branch.add(_call_label(child, opts["max_len"], opts["show_lineno"]))
        else:
            _add_children(branch, child, nodes, opts, depth=depth)


def _to_source(obj: str | pathlib.Path | FunctionType | ModuleType) -> tuple[str, str]:
    """Return `(name, source_code)` for a file, module, or function."""
    if isinstance(obj, (pathlib.Path, str)):
        p = pathlib.Path(obj)
        return p.name, p.read_text(encoding="utf-8")
    if isinstance(obj, FunctionType):
        return obj.__name__, inspect.getsource(obj)
    # must be ModuleType
    filename: str = getattr(obj, "__file__", None) or obj.__name__
    return pathlib.Path(filename).name, inspect.getsource(obj)


def show_logic_map(
    target: str | pathlib.Path | FunctionType | ModuleType,
    *,
    include_exits: bool = False,
    include_raises: bool = False,
    include_calls: bool = False,
    show_lineno: bool = False,
    expr_width: int = 60,
    max_depth: int = 0,
) -> None:
    name, source = _to_source(target)
    root = ast.parse(source, filename=name)
    tree = Tree(f"[bold bright_blue]{name}", guide_style="bright_blue")
    nodes: tuple[type[ast.AST], ...] = BASE_LOGICAL_NODES
    if include_exits:
        nodes += EXIT_NODES
    if include_raises:
        nodes += RAISE_NODES
    opts: _Opts = {
        "max_depth": max_depth,
        "max_len": expr_width,
        "show_lineno": show_lineno,
        "include_calls": include_calls,
    }
    _add_children(tree, root, nodes, opts, depth=0)
    Console().print(tree)


# --- CLI -------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pretty-print the logical structure of a Python file."
    )
    parser.add_argument("path", help="path to a Python file")
    parser.add_argument(
        "-x", "--exits", action="store_true",
        help="include exit points: return/break/continue",
    )
    parser.add_argument(
        "-R", "--raises", action="store_true", help="include raise statements"
    )
    parser.add_argument(
        "-c", "--calls", action="store_true",
        help="include statement-level function calls (shown as → call)",
    )
    parser.add_argument(
        "-n", "--lineno", action="store_true", help="append line numbers like (L42)"
    )
    parser.add_argument(
        "-m", "--max-expr-len", type=int, default=60,
        help="truncate expressions to this width (default: 60)",
    )
    parser.add_argument(
        "-d", "--depth", type=int, default=0, metavar="N",
        help="limit tree to N levels deep (0 = unlimited)",
    )
    args = parser.parse_args()
    show_logic_map(
        args.path,
        include_exits=args.exits,
        include_raises=args.raises,
        include_calls=args.calls,
        show_lineno=args.lineno,
        expr_width=args.max_expr_len,
        max_depth=args.depth,
    )
