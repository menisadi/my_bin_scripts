# bin — Bash Conventions

Personal `~/bin` scripts. Keep them small, readable, and portable across macOS and Linux/Termux.

## Script header
- Shebang: `#!/usr/bin/env bash` (never a hard-coded path).
- Start with `set -euo pipefail` and `IFS=$'\n\t'`.
- Know the `errexit` traps: it misbehaves with `read -rd ''`, in command
  substitutions, and around `&&` chains. Use `|| true` or a local `set +e`
  when needed rather than fighting it.

## Style
- Always brace and quote: `"${var}"`, not `$var`.
- Guard optional args under `nounset`: `"${1:-default}"` or `"${1:?message}"`.
- Prefer `printf` over `echo` when output contains data, escapes, or paths.
- Explicit names (`input_file`), not abbreviations (`f`). Underscore-prefix
  internal helper functions (`_warn`).
- Split logic across lines; avoid clever one-liners.

## Every script gets
- A `usage()` function and `-h`/`--help` handling that calls it.
- Errors to stderr: `_warn() { printf '%s\n' "$*" >&2; }` /
  `_die() { _warn "$@"; exit 1; }`.
- A portability note when using `date`, `sed`, etc. (see `since` for the
  GNU-vs-BSD `date` pattern).

## Before committing
- Run `shellcheck` on changed scripts; fix or justify warnings.
- Commits follow Conventional Commits (`feat:`, `fix:`, …).
