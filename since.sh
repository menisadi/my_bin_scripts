#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 YYYY-MM-DDTHH:MM"
  echo "Example: $0 2025-10-31T23:00"
  exit 1
}

if [[ $# -ne 1 ]]; then usage; fi
INPUT="$1"

# Pick a date command: GNU date (Linux), gdate (macOS coreutils), or BSD date (macOS).
if date --version >/dev/null 2>&1; then
  D=date          # GNU date
elif command -v gdate >/dev/null 2>&1; then
  D=gdate         # GNU date via coreutils on macOS
else
  D=              # Fall back to BSD date
fi

to_epoch() {
  local ts="$1"
  if [[ -n "$D" ]]; then
    # GNU date accepts the ISO-like format directly.
    "$D" -d "$ts" +%s 2>/dev/null || return 1
  else
    # BSD date needs an explicit format string.
    date -j -f "%Y-%m-%dT%H:%M" "$ts" "+%s" 2>/dev/null || return 1
  fi
}

then_epoch=$(to_epoch "$INPUT") || {
  echo "Error: couldn't parse time '$INPUT'. Expected format YYYY-MM-DDTHH:MM (e.g., 2025-10-31T23:00)"
  exit 2
}

# Current time (epoch seconds), using whichever date we found.
if [[ -n "$D" ]]; then
  now=$("$D" +%s)
else
  now=$(date "+%s")
fi

delta=$(( now - then_epoch ))

# If the time is in the future, show "in ..." instead of "... ago".
if (( delta < 0 )); then
  delta=$(( -delta ))
  sign="-"
else
  sign=""
fi

days=$(( delta / 86400 ))
rem=$(( delta % 86400 ))
hours=$(( rem / 3600 ))
rem=$(( rem % 3600 ))
minutes=$(( rem / 60 ))
# seconds (computed but not shown, in case you want them later)
# seconds=$(( rem % 60 ))

if [[ "$sign" == "-" ]]; then
  printf "in %d days, %d hours, %d minutes\n" "$days" "$hours" "$minutes"
else
  printf "%d days, %d hours, %d minutes ago\n" "$days" "$hours" "$minutes"
fi
