#!/usr/bin/env -S uv run
import subprocess
import re
import sys
import argparse

def get_git_log():
    cmd = [
        "git", "log",
        "--graph",
        "--all",
        "--color=always",
        "--format=%h%C(auto)%d"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=False)
        return result.stdout.decode('utf-8', errors='replace').splitlines()
    except FileNotFoundError:
        print("Error: git not found.")
        sys.exit(1)

def extract_graph_prefix(line):
    # Regex to find a Git hash (boundary of 7+ hex chars)
    match = re.search(r'\b[0-9a-f]{7,40}\b', line)
    if match:
        return line[:match.start()]
    else:
        return line

def process_buffer(buffer, prefix, show_gap):
    if len(buffer) > 2:
        # Print the first line of the sequence
        print(buffer[0]) 
        
        # Only print the ellipsis/info line if the flag is passed
        if show_gap:
            # Clean ANSI codes to calculate indentation
            clean_prefix = re.sub(r'\x1b\[[0-9;]*m', '', prefix)
            indent = " " * len(clean_prefix)
            print(f"{indent}  ⋮  (hidden {len(buffer)-2} commits)")
        
        # Print the last line of the sequence
        print(buffer[-1]) 
    else:
        for b in buffer:
            print(b)

def main():
    # specific arguments for the script
    parser = argparse.ArgumentParser(description="Compress git log graph.")
    parser.add_argument("--show-gap", action="store_true", help="Print a spacer line with hidden commit count")
    args = parser.parse_args()

    lines = get_git_log()
    
    if not lines:
        return

    buffer = []
    last_prefix = None

    for line in lines:
        current_prefix = extract_graph_prefix(line)
        
        if current_prefix != last_prefix:
            if buffer:
                process_buffer(buffer, last_prefix, args.show_gap)
            buffer = [line]
            last_prefix = current_prefix
        else:
            buffer.append(line)
            
    if buffer:
        process_buffer(buffer, last_prefix, args.show_gap)

if __name__ == "__main__":
    main()
