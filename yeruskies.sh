#!/usr/bin/env bash
set -euo pipefail

CITY="${1:-Yeruham}"
COLS="$(tput cols 2>/dev/null || echo 80)"

# ----- ANSI colors -----
if [[ -t 1 ]]; then
  RESET=$'\033[0m'
  BOLD=$'\033[1m'
  DIM=$'\033[2m'

  # Bright (high-intensity) colors: 90–97
  BR_BLACK=$'\033[90m'   # nice gray
  BR_RED=$'\033[91m'
  BR_GREEN=$'\033[92m'
  BR_YELLOW=$'\033[93m'
  BR_BLUE=$'\033[94m'
  BR_MAGENTA=$'\033[95m'
  BR_CYAN=$'\033[96m'
  BR_WHITE=$'\033[97m'
else
  RESET=""; BOLD=""; DIM=""
  BR_BLACK=""; BR_RED=""; BR_GREEN=""; BR_YELLOW=""; BR_BLUE=""; BR_MAGENTA=""; BR_CYAN=""; BR_WHITE=""
fi

# ----- Fetch and shape data for the LLM -----
json="$(
  curl -fsSL "https://wttr.in/${CITY}?format=j1" |
    jq -c '{
      city: "'"${CITY}"'",
      current: .current_condition[0] | {
        tempC: .temp_C,
        feelsLikeC: .FeelsLikeC,
        humidity: .humidity,
        windKmph: .windspeedKmph,
        windDir: .winddir16Point,
        desc: .weatherDesc[0].value
      },
      today: .weather[0] | {
        date: .date,
        maxC: .maxtempC,
        minC: .mintempC,
        uv: .uvIndex,
        sunrise: .astronomy[0].sunrise,
        sunset: .astronomy[0].sunset,
        # keep a little hourly texture, but not too big
        hourly: (.hourly | map({
          time: .time,
          chanceOfRain: .chanceofrain,
          precipMM: .precipMM,
          cloudCover: .cloudcover
        }))
      }
    }'
)"

prompt=$(
  cat <<'PROMPT'
You are a witty but helpful weather reporter.
Return EXACTLY 3 lines (no bullets, no extra lines):
Line 1: One short line about the key numbers (temps, wind, humidity, rain chance).
Line 2: A more verbal description of the vibe, friendly and humorous.
Line 3: Clothing suggestion for today (practical).
PROMPT
)

report="$(
  printf '%s\n\n%s\n' "$prompt" "$json" |
    mods --quiet --role short --word-wrap "$COLS"
)"

# ----- Pretty header -----
printf "%s%s☀  Weather for %s%s\n" "$BOLD" "$BR_CYAN" "$CITY" "$RESET"
printf "%s%s━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━%s\n" "$BR_BLACK" "" "$RESET"

line1="$(printf '%s\n' "$report" | sed -n '1p')"
line2="$(printf '%s\n' "$report" | sed -n '2p')"
line3="$(printf '%s\n' "$report" | sed -n '3p')"

# Highlight common numeric patterns
colorize_numbers() {
  sed -E \
    -e "s/([+-]?[0-9]+(\.[0-9]+)?) ?°?C/${BOLD}${BR_YELLOW}\1°C${RESET}/g" \
    -e "s/([0-9]+) ?km\/h/${BOLD}${BR_BLUE}\1 km\/h${RESET}/g" \
    -e "s/([0-9]+)%/${BOLD}${BR_GREEN}\1%${RESET}/g" \
    -e "s/([0-9]+(\.[0-9]+)?) ?mm/${BOLD}${BR_MAGENTA}\1 mm${RESET}/g"
}

printf "%s\n" "$(printf '%s' "$line1" | colorize_numbers)"
printf "%s%s%s\n" "${BOLD}${BR_MAGENTA}" "$line2" "$RESET"
printf "%s%s%s\n" "${BOLD}${BR_GREEN}" "$line3" "$RESET"

printf "%s%s━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━%s\n" "$BR_BLACK" "" "$RESET"
printf "%s%sData:%s wttr.in  %s(format=j1)%s\n" "$DIM" "$BR_BLACK" "$RESET" "$BR_BLACK" "$RESET"
