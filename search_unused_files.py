#!/usr/bin/env python3
import os
import argparse
from pathlib import Path


def parse_dockerfile(dockerfile_path):
    copied_files = set()
    with open(dockerfile_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.upper().startswith("COPY"):
                parts = line.split()
                if len(parts) >= 2:
                    sources = parts[1:-1]
                    copied_files.update(sources)
    return copied_files


def get_all_files(base_dir, exclude_dirs=None, exclude_exts=None):
    base_dir = Path(base_dir)
    all_files = set()
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".") and (not exclude_dirs or d not in exclude_dirs)
        ]

        for file in files:
            if file.startswith("."):
                continue
            if exclude_exts and Path(file).suffix in exclude_exts:
                continue
            file_path = Path(root) / file
            relative_path = file_path.relative_to(base_dir)
            all_files.add(str(relative_path))
    return all_files


def main():
    parser = argparse.ArgumentParser(
        description="Find redundant files not used in Dockerfile COPY"
    )
    parser.add_argument("dockerfile", help="Path to Dockerfile")
    parser.add_argument("source_dir", help="Path to the source directory")
    parser.add_argument(
        "--exclude-dirs", nargs="*", default=[], help="Directories to exclude"
    )
    parser.add_argument(
        "--exclude-exts",
        nargs="*",
        default=[],
        help="File extensions to exclude (e.g. .log .tmp)",
    )

    args = parser.parse_args()

    copied = parse_dockerfile(args.dockerfile)
    actual = get_all_files(
        args.source_dir, exclude_dirs=args.exclude_dirs, exclude_exts=args.exclude_exts
    )

    copied_resolved = set()
    for path in copied:
        full_path = Path(args.source_dir) / path
        if full_path.is_dir():
            copied_resolved.update(
                str(p.relative_to(args.source_dir))
                for p in full_path.rglob("*")
                if p.is_file()
            )
        elif full_path.exists():
            copied_resolved.add(str(Path(path)))

    unused = actual - copied_resolved

    print("\nUnused files:")
    for f in sorted(unused):
        print(f)


if __name__ == "__main__":
    main()
