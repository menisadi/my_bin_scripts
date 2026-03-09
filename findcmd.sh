#!/usr/bin/env bash
set -euo pipefail

TOOL="${1:?usage: $0 <tool> [target]}"
TARGET="${2:-apply}"

seen=""

extract_cmds() {
  # Heuristic parser for several CLI styles:
  # - Commands sections in help output
  # - "Installed commands (...):" lists (e.g. qsv --list)
  # - "It has N subcommands:" numbered lists (e.g. qsv apply -h)
  awk '
    BEGIN{insec=0; ininstalled=0; innumsub=0}
    {
      # Remove ANSI escape sequences commonly used for colored help output.
      line = $0
      gsub(/\033\[[0-9;]*[[:alpha:]]/, "", line)
      l = tolower(line)
    }
    l ~ /^[[:space:]]*(main[[:space:]]+commands|other[[:space:]]+commands|commands|available[[:space:]]+commands|subcommands)[[:space:]]*:?[[:space:]]*$/ {insec=1; ininstalled=0; innumsub=0; next}
    l ~ /^[[:space:]]*installed[[:space:]]+commands[[:space:]]*\([0-9]+\)[[:space:]]*:?[[:space:]]*$/ {ininstalled=1; insec=0; innumsub=0; next}
    l ~ /^[[:space:]]*it[[:space:]]+has[[:space:]]+[a-z0-9]+[[:space:]]+subcommands[[:space:]]*:?[[:space:]]*$/ {innumsub=1; insec=0; ininstalled=0; next}
    (insec || ininstalled || innumsub) && l ~ /^[[:space:]]*$/ {insec=0; ininstalled=0; innumsub=0}
    insec {
      # first token on the line
      if (match(line, /^[[:space:]]*[A-Za-z0-9][A-Za-z0-9_-]*/)) {
        token = substr(line, RSTART, RLENGTH)
        gsub(/^[[:space:]]+/, "", token)
        print token
      }
    }
    ininstalled {
      if (match(line, /^[[:space:]]*[A-Za-z0-9][A-Za-z0-9_-]*/)) {
        token = substr(line, RSTART, RLENGTH)
        gsub(/^[[:space:]]+/, "", token)
        print token
      }
    }
    innumsub {
      if (match(line, /^[[:space:]]*[0-9]+\.[[:space:]]*[A-Za-z0-9][A-Za-z0-9_-]*\*?/)) {
        token = substr(line, RSTART, RLENGTH)
        gsub(/^[[:space:]]*[0-9]+\.[[:space:]]*/, "", token)
        gsub(/\*$/, "", token)
        print token
      }
    }
  ' | sort -u
}

walk() {
  local path="$1"
  local key="|${path}|"
  [[ "$seen" == *"$key"* ]] && return
  seen="${seen}${key}"

  local help
  if ! help="$($TOOL $path --help 2>&1)"; then
    help=""
  fi

  local listout=""
  if [[ -z "$path" ]]; then
    listout="$($TOOL --list 2>&1 || true)"
  fi

  if echo "$help" | rg -q --fixed-strings "$TARGET"; then
    echo "MATCH: $TOOL $path  (help mentions '$TARGET')"
  fi

  local cmds
  cmds="$(
    {
      printf "%s\n" "$help"
      printf "%s\n" "$listout"
    } | extract_cmds || true
  )"
  while IFS= read -r c; do
    [[ -z "$c" ]] && continue
    if [[ "$c" == "$TARGET" ]]; then
      if [[ -z "$path" ]]; then
        echo "PATH:  $TOOL $c"
      else
        echo "PATH:  $TOOL $path $c"
      fi
    fi
    if [[ -z "$path" ]]; then
      walk "$c"
    else
      walk "$path $c"
    fi
  done <<< "$cmds"
}

walk ""
