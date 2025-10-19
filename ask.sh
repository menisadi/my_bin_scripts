#!/bin/bash

# Check if the user provided any input
if [ -z "$@" ]; then
    echo "Usage: ask \"your question in plain english\""
    exit 1
fi

# The user's query is all the arguments combined
QUERY="$@"

# We ask it to ONLY return the command.
PROMPT="Based on the following request, provide a single, executable bash command. Do not provide any explanation, preamble, or markdown formatting. Just the command. Request: ${QUERY}"

# Call the ollama CLI to get the command
ollama run qwen2.5-coder:3b "${PROMPT}"
