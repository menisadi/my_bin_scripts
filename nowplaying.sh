#!/bin/bash
API_KEY="${LASTFM_API_KEY:?Set LASTFM_API_KEY}"
USER="${LASTFM_USERNAME:?Set LASTFM_USERNAME}"

json=$(curl -s "http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user=$USER&api_key=$API_KEY&format=json&limit=1")

artist=$(echo "$json" | jq -r '.recenttracks.track[0].artist["#text"]' | fribidi --nopad)
title=$(echo "$json" | jq -r '.recenttracks.track[0].name' | fribidi --nopad)
album=$(echo "$json" | jq -r '.recenttracks.track[0].album["#text"]' | fribidi --nopad)
nowplaying=$(echo "$json" | jq -r '.recenttracks.track[0]["@attr"].nowplaying // empty')

BOLD="\033[1m"
RESET="\033[0m"
COLOR="\033[36m" # cyan
ICON="▸ "

[ "$nowplaying" = "true" ] && echo -e "${ICON}${COLOR}Now Playing${RESET}"
echo -e "${BOLD}${COLOR}Title :${RESET} $title"
echo -e "${BOLD}${COLOR}Artist:${RESET} $artist"
echo -e "${BOLD}${COLOR}Album :${RESET} $album"
