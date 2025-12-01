#!/usr/bin/env bash
set -euo pipefail

usage() {
  local exit_code="${1:-1}"
  echo "Usage: tpm [-c|--continue] [-h|--help] MINUTES [TAGS...]"
  echo "  -c, --continue   Continue previous Timewarrior interval instead of starting a new one."
  echo "  -h, --help       Show this help message and exit."
  echo "  Example: tpm 25 coding"
  echo "  Example: tpm --continue 15"
  exit "$exit_code"
}

continue_flag=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--continue)
      continue_flag=true
      shift
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -lt 1 ]]; then
  usage
fi

minutes="$1"
shift  # remaining args are TAGS

if ! [[ "$minutes" =~ ^[0-9]+$ ]]; then
  echo "Error: MINUTES must be a positive integer." >&2
  usage
fi

if ! command -v timew >/dev/null 2>&1; then
  echo "Error: timew not found in PATH. Is Timewarrior installed?" >&2
  exit 1
fi

if "$continue_flag"; then
  echo "Running: timew continue"
  timew continue
else
  if [[ $# -gt 0 ]]; then
    echo "Running: timew start $*"
    timew start "$@"
  else
    echo "Running: timew start (no tags)"
    timew start
  fi
fi

echo "Starting pomodoro for ${minutes} minutes…"

# We rely on 'pom' being available in PATH
pom "$minutes" -w $(( $(tput cols) * 80 / 100 ))
