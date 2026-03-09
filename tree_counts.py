#!/usr/bin/env -S uv run
import os

def tree(dir_path, prefix=''):
    entries = sorted(os.scandir(dir_path), key=lambda e: (not e.is_dir(), e.name))
    entries = [e for e in entries if not e.name.startswith('.')]
    for i, entry in enumerate(entries):
        is_last = (i == len(entries) - 1)
        connector = '└── ' if is_last else '├── '
        if entry.is_file():
            try:
                count = sum(1 for _ in open(entry.path, 'rb'))
            except:
                count = 0
            line = f'{prefix}{connector}{entry.name}'
            print(f'{line:<60} {count:>6} lines')
        else:
            print(f'{prefix}{connector}{entry.name}/')
            ext = '    ' if is_last else '│   '
            tree(entry.path, prefix + ext)

print('.')
tree('.')
