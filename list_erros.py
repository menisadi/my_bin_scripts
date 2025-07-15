#!/usr/bin/env python3
import re
import argparse
from pathlib import Path
import subprocess
from rich.console import Console
from rich.table import Table
from rich import box

LEVEL_ORDER = {"error": 3, "warning": 2, "information": 1}

console = Console()


def extract_python_files_from_dockerfile(dockerfile_path):
    py_files = []
    with open(dockerfile_path, "r") as f:
        buffer = ""
        for raw_line in f:
            line = raw_line.rstrip("\n")
            # if the line ends with a backslash, strip it and keep buffering
            if line.rstrip().endswith("\\"):
                buffer += line.rstrip()[:-1] + " "
                continue

            # last line of this logical command:
            buffer += line
            cmd = buffer.strip()

            # check if it’s a COPY or ADD
            if cmd.upper().startswith(("COPY ", "ADD ")):
                # split on any whitespace
                parts = re.split(r"\s+", cmd)
                # parts[0] = COPY/ADD, parts[-1] = destination
                sources = parts[1:-1]
                for src in sources:
                    if src.endswith(".py"):
                        py_files.append(src)

            # reset for next command
            buffer = ""

    return py_files


def count_ruff_issues(filepath):
    result = subprocess.run(["ruff", filepath], capture_output=True, text=True)
    return len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0


def count_pyright_issues(filepath, min_level):
    result = subprocess.run(["pyright", filepath], capture_output=True, text=True)
    count = 0
    for line in result.stdout.splitlines():
        match = re.match(r"^\s*.+:\d+:\d+ - (\w+)", line)
        if match:
            level = match.group(1).lower()
            if LEVEL_ORDER.get(level, 0) >= LEVEL_ORDER[min_level]:
                count += 1
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Count Python file issues from Dockerfile using ruff and/or pyright."
    )
    parser.add_argument("--dockerfile", default="Dockerfile")
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--min-level",
        choices=["error", "warning", "information"],
        default="error",
        help="Minimum diagnostic level to include from pyright.",
    )
    parser.add_argument(
        "--tool",
        choices=["ruff", "pyright", "both"],
        default="both",
        help="Which linter / type-checker to run.",
    )
    args = parser.parse_args()

    run_ruff = args.tool in ("ruff", "both")
    run_pyright = args.tool in ("pyright", "both")

    dockerfile_path = Path(args.dockerfile)
    project_root = Path(args.project_root)

    py_files = extract_python_files_from_dockerfile(dockerfile_path)
    py_files = [str(project_root / f) for f in py_files if (project_root / f).exists()]

    # ── table setup ───────────────────────────────────────
    table = Table(
        title=f"🧪 Lint Report (min-level: {args.min_level}, tool: {args.tool})",
        box=box.SIMPLE_HEAD,
        header_style="bold cyan",
    )
    table.add_column("File", style="white", no_wrap=True)
    if run_ruff:
        table.add_column("Ruff", justify="center")
    if run_pyright:
        table.add_column("Pyright", justify="center")

    # ── analysis loop ─────────────────────────────────────
    with console.status("[bold green]Analyzing files..."):
        for py_file in py_files:
            row = [py_file]

            if run_ruff:
                ruff_errors = count_ruff_issues(py_file)
                row.append(
                    f"[red]{ruff_errors}[/red]" if ruff_errors else "[green]0[/green]"
                )

            if run_pyright:
                pyright_errors = count_pyright_issues(py_file, args.min_level)
                row.append(
                    f"[red]{pyright_errors}[/red]"
                    if pyright_errors
                    else "[green]0[/green]"
                )

            table.add_row(*row)

    console.print()
    console.print(table)


if __name__ == "__main__":
    main()
