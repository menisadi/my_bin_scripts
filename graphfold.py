#!/usr/bin/env python3
import re
import subprocess
import sys

cmd = ["git", "log", "--graph", "--oneline", "--decorate", "--all", *sys.argv[1:]]
log = subprocess.run(
    cmd, text=True, capture_output=True, check=True
).stdout.splitlines()

prev_prefix = None  # the “ASCII art” to the left of each SHA
skipped = False  # are we inside a fold?

for line in log:
    # Strip colour codes (they confuse string comparison)
    clean = re.sub(r"\x1b\\[[0-9;]*m", "", line)

    # Everything up to the first hex digit is the graph prefix
    m = re.match(r"([^0-9a-f]*)([0-9a-f])", clean)
    if not m:  # lines like "|/" or "\"
        print(line)
        prev_prefix, skipped = None, False
        continue

    prefix = m.group(1)
    if prefix == prev_prefix:
        skipped = True  # same branch line – fold it away
        continue
    if skipped:  # just ended a folded block
        print(f"{prev_prefix}…")  # keep graph connected
        skipped = False

    print(line)
    prev_prefix = prefix

# if the very last block was folded, close it
if skipped:
    print(f"{prev_prefix}…")
