#!/usr/bin/env python
"""list_missing_docstrings.py

Walk a file or directory tree and report every Python function that does **not**
have a docstring.  The output is either written to *stdout* or, if the
``--report`` flag is supplied, to the given report file.

Each missing‑docstring function is reported on a single line in the form::

    path/to/file.py:lineno:function_name

Usage
-----

```bash
python list_missing_docstrings.py src/               # print to console
python list_missing_docstrings.py src/ -r missing.txt  # also save to a file
```
"""

import ast
import argparse
from pathlib import Path
from typing import Iterable, NamedTuple

__all__ = [
    "Target",
    "iter_python_files",
    "find_missing_docstrings",
    "main",
]


class Target(NamedTuple):
    """Information about a function that lacks a docstring."""

    filepath: Path
    lineno: int  # line number where the *def* appears (1‑based)
    name: str  # function name


def iter_python_files(path: Path) -> Iterable[Path]:
    """Yield every ``*.py`` file under *path* (recursively)."""
    if path.is_file() and path.suffix == ".py":
        yield path
    elif path.is_dir():
        yield from path.rglob("*.py")


def find_missing_docstrings(source: str, file_path: Path | None = None) -> list[Target]:
    """Return a list of :class:`Target` objects for functions without docstrings."""
    tree = ast.parse(source)
    targets: list[Target] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and ast.get_docstring(node) is None:
            targets.append(
                Target(
                    filepath=file_path or Path("<string>"),
                    lineno=node.lineno,
                    name=node.name,
                )
            )
    return targets


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="List Python functions that are missing a docstring.",
    )
    p.add_argument(
        "input_path",
        help="File or directory to scan recursively for *.py files",
    )
    p.add_argument(
        "-r",
        "--report",
        metavar="PATH",
        help="Write the results to this file instead of just printing.",
    )
    p.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        help="Suppress console output; use non‑zero exit status to signal problems.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.input_path).expanduser().resolve()

    py_files = list(iter_python_files(root))
    if not py_files:
        print("No *.py files found.")
        return

    missing: list[Target] = []
    for file in py_files:
        src_text = file.read_text(encoding="utf-8")
        missing.extend(find_missing_docstrings(src_text, file))

    if not missing:
        print("✨ No missing docstrings found.")
        return

    # Sort for deterministic output: by file, then line number
    missing.sort(key=lambda t: (t.filepath, t.lineno))

    lines = [f"{t.filepath.relative_to(root)}:{t.lineno}:{t.name}" for t in missing]

    # Write report file if requested
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(
            f"✅ Report written to {report_path} ({len(lines)} missing docstring(s))."
        )

    # Echo to stdout unless suppressed
    if not args.quiet:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
