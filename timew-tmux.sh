#!/usr/bin/env bash
# Print "tag  NN m" for the active Timewarrior interval.
# If nothing is running, print nothing (tmux will just leave the field blank).

# ➊ Bail out when there is no active timer
[[ "$(timew get dom.active 2>/dev/null)" != "1" ]] && exit 0

# ➋ First tag (adjust if you want all tags: dom.active.tag.1, .2, …)
tag=$(timew get dom.active.tag.1)

# ➌ ISO-8601 duration like PT1H12M33S  →  total minutes
iso=$(timew get dom.active.duration)
# shell-only parse; works for any H/M/S combo
[[ $iso =~ ^P([0-9]+D)?T([0-9]+H)?([0-9]+M)?([0-9]+S)?$ ]]
h=${BASH_REMATCH[2]%H}; h=${h:-0}
m=${BASH_REMATCH[3]%M}; m=${m:-0}
s=${BASH_REMATCH[4]%S}; s=${s:-0}
mins=$(( h*60 + m + (s+30)/60 ))      # round secs ≥30 up

printf '%s %dm\n' "$tag" "$mins"
