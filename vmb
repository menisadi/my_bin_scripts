#!/usr/bin/env zsh
# vibemark stats filtered to the current git branch

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  cat <<'EOF'
Usage: vmb [OPTIONS]

Flags:
  -h, --help          Show this help
  --root PATH         Repo root (default: cwd)
  --top INTEGER       Show top N remaining by LOC
  --all               Show all remaining files
  --no-table          Show only totals without a file table
EOF
  exit 0
fi

base=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null)
base=${base#origin/}
[[ -n "$base" ]] || base=main

changed_files=$(git diff "${base}...HEAD" --name-only)

if [[ -z "$changed_files" ]]; then
  echo "No changed files found on this branch." >&2
  exit 1
fi

csv=$(vibemark stats "$@" --all --include-done --format csv | tr -d '\r' | awk -F',' '
  NR==FNR { changed[$0]=1; next }
  FNR==1 { print; next }
  ($1 in changed) { print }
' <(printf '%s\n' "$changed_files") -)

if [[ $(printf '%s\n' "$csv" | wc -l) -le 1 ]]; then
  echo "No vibemark data for changed files." >&2
  exit 0
fi

printf '%s\n' "$csv" | awk -F',' 'NR>1 {r+=$3; t+=$4} END {printf "Branch total: %d/%d LOC read (%.1f%%)\n", r, t, (t>0 ? r/t*100 : 0)}'
printf '\n'
printf '%s\n' "$csv" | awk -F',' 'BEGIN{OFS=","} NR==1{print $0,"pct"; next} {printf "%s,%.0f%%\n", $0, ($4>0 ? ($3/$4)*100 : 0)}' | qsv table
