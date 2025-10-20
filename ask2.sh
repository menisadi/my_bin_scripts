#!/usr/bin/env bash
set -euo pipefail

# Usage
if [ $# -eq 0 ]; then
  echo 'Usage: ask "your question in plain english"'
  exit 1
fi

QUERY="$*"

# Ask for a STRICT JSON response so we can parse it with jq.
PROMPT=$'You are a command-line assistant.\n\
Given the following request, reply with a SINGLE JSON object with EXACTLY one key "cmd".\n\
The value must be a single, executable bash command string.\n\
No explanations, no markdown, no code fences, no extra keys, no surrounding text.\n\
Example format: {"cmd":"echo \\"hello\\""}\n\
Request: '"${QUERY}"

# Call Ollama
RESPONSE="$(ollama run qwen2.5-coder:1.5b "$PROMPT" || true)"

# Extract the command with jq
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required to parse the model output." >&2
  exit 1
fi

# 1) Try parsing as-is
CMD="$(printf '%s' "$RESPONSE" | jq -r '.cmd' 2>/dev/null || true)"

# 2) If that failed, strip Markdown code fences and retry
if [ -z "${CMD:-}" ] || [ "$CMD" = "null" ]; then
  CLEANED="$(printf '%s' "$RESPONSE" \
    | sed -E 's/\r$//; /^\s*```[[:alnum:]_-]*\s*$/d')"
  CMD="$(printf '%s' "$CLEANED" | jq -r '.cmd' 2>/dev/null || true)"
fi

# 3) Final check
if [ -z "${CMD:-}" ] || [ "$CMD" = "null" ]; then
  echo "Failed to parse a command from model output."
  echo "Raw output was:"
  printf '%s\n' "$RESPONSE"
  exit 1
fi

echo "Proposed command:"
echo "  $CMD"
echo

# Simple post-action prompt
read -rp "Choose: [r]un / [c]opy / [x] cancel: " choice
case "${choice:-x}" in
  r|R)
    echo "Running..."
    # Use a login shell to respect PATH and aliases; remove if unnecessary.
    bash -lc "$CMD"
    ;;
  c|C)
    if command -v pbcopy >/dev/null 2>&1; then
      printf '%s' "$CMD" | pbcopy
      echo "Command copied to clipboard."
    else
      echo "pbcopy not found. (This is typically available on macOS.)"
    fi
    ;;
  x|X|*)
    echo "Cancelled."
    ;;
esac
