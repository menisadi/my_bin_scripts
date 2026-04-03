# /// script
# dependencies = ["typer", "rich"]
# ///
"""Check if you've listened to an artist's full discography on Last.fm.

Usage:
    uv run discography_check.py "Artist Name"
    uv run discography_check.py --merge "רונה קינן" "Rona Kenan"
    uv run discography_check.py --albums-only "Caroline Polachek"

Requires env vars: LASTFM_API_KEY, LASTFM_USERNAME
"""

import os
import re
import json
import urllib.request
import urllib.parse
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(help="Check your Last.fm discography coverage for an artist.")
console = Console()

API_KEY = os.environ["LASTFM_API_KEY"]
DEFAULT_USERNAME = os.environ["LASTFM_USERNAME"]
BASE_URL = "https://ws.audioscrobbler.com/2.0/"


def lastfm_request(method: str, **params) -> dict:
    params.update({"method": method, "api_key": API_KEY, "format": "json"})
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def get_artist_info(artist: str, username: str) -> dict:
    data = lastfm_request("artist.getinfo", artist=artist, username=username)
    info = data.get("artist", {})
    stats = info.get("stats", {})
    return {
        "name": info.get("name", artist),
        "user_playcount": int(stats.get("userplaycount", 0)),
        "global_listeners": int(stats.get("listeners", 0)),
    }


def get_artist_albums(artist: str) -> list[dict]:
    albums = []
    page = 1
    while True:
        data = lastfm_request("artist.gettopalbums", artist=artist, limit=50, page=page)
        top = data.get("topalbums", {})
        batch = top.get("album", [])
        if not batch:
            break
        for a in batch:
            albums.append({"name": a["name"], "global_playcount": int(a.get("playcount", 0))})
        total_pages = int(top.get("@attr", {}).get("totalPages", 1))
        if page >= total_pages:
            break
        page += 1
    return albums


def get_user_album_info(artist: str, album: str, username: str) -> dict:
    data = lastfm_request("album.getinfo", artist=artist, album=album, username=username)
    if "error" in data:
        raise ValueError(f"API error {data['error']}: {data.get('message', '')}")
    album_data = data.get("album", {})
    tracks = album_data.get("tracks", {})
    if isinstance(tracks, dict):
        tracks = tracks.get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]
    track_details = []
    for t in tracks:
        track_details.append({
            "name": t.get("name", ""),
            "user_playcount": int(t.get("userplaycount", 0)) if "userplaycount" in t else 0,
        })
    tracks_heard = sum(1 for t in track_details if t["user_playcount"] > 0)
    return {
        "name": album_data.get("name", album),
        "user_playcount": int(album_data.get("userplaycount", 0)),
        "total_tracks": len(track_details),
        "tracks_heard": tracks_heard,
        "tracks": track_details,
    }


NORMALIZE_KEYWORDS = [
    "version",
    "remaster(?:ed)?",
    "deluxe",
    "edition",
    "expanded",
    "anniversary",
    "bonus",
    "explicit",
    "special",
    "collector",
    "re-?issue",
    "single",
    r"EP\b",
]


def normalize_album_name(name: str) -> str:
    kw = "(?:" + "|".join(NORMALIZE_KEYWORDS) + ")"
    # Remove " - <anything with keyword>..." at end
    norm = re.sub(rf'\s*[-–—]\s*.*?{kw}.*$', '', name, flags=re.IGNORECASE)
    # Remove (...keyword...) or [...keyword...]
    norm = re.sub(rf'\s*[(\[].*?{kw}.*?[)\]]', '', norm, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", norm).strip()


def matches_exclude(name: str, exclude: list[str]) -> bool:
    lower = name.lower()
    return any(word in lower for word in exclude)


def merge_album_versions(albums: list[dict]) -> list[dict]:
    """Merge albums that normalize to the same name, combining play counts."""
    merged = {}
    for a in albums:
        key = normalize_album_name(a["album"]).lower()
        if key not in merged:
            merged[key] = dict(a)
        else:
            existing = merged[key]
            existing["user_playcount"] += a["user_playcount"]
            existing["global_playcount"] += a["global_playcount"]
            if isinstance(a["total_tracks"], int) and a["tracks_heard"] > existing.get("tracks_heard", 0):
                existing["total_tracks"] = a["total_tracks"]
                existing["tracks_heard"] = a["tracks_heard"]
                existing["tracks"] = a["tracks"]
            # Prefer shorter name (usually the clean version)
            if len(a["album"]) < len(existing["album"]):
                existing["album"] = a["album"]
    return list(merged.values())


def check_artist(artist: str, progress: Progress, task_id, username: str, exclude: list[str] | None = None,
                  dedup: bool = True, min_threshold: int | None = None) -> dict:
    info = get_artist_info(artist, username)
    all_albums = get_artist_albums(artist)

    real_albums = [a for a in all_albums if not matches_exclude(a["name"], exclude)] if exclude else all_albums

    total_before_filter = len(real_albums)
    threshold = 0
    if real_albums:
        if min_threshold is not None:
            threshold = min_threshold
        else:
            max_pc = max(a["global_playcount"] for a in real_albums)
            threshold = max(1000, int(max_pc * 0.001))
        real_albums = [a for a in real_albums if a["global_playcount"] >= threshold]

    progress.update(task_id, total=len(real_albums), completed=0)
    results = []
    for i, album in enumerate(real_albums):
        try:
            album_info = get_user_album_info(artist, album["name"], username)
            results.append({
                "album": album_info["name"],
                "user_playcount": album_info["user_playcount"],
                "total_tracks": album_info["total_tracks"],
                "tracks_heard": album_info["tracks_heard"],
                "tracks": album_info["tracks"],
                "global_playcount": album["global_playcount"],
            })
        except Exception as e:
            console.print(f"  [dim]Warning: failed to fetch '{album['name']}': {e}[/dim]")
            results.append({
                "album": album["name"],
                "user_playcount": 0,
                "total_tracks": "?",
                "tracks_heard": 0,
                "tracks": [],
                "global_playcount": album["global_playcount"],
            })
        progress.update(task_id, completed=i + 1)

    albums_before_dedup = len(results)
    if dedup:
        results = merge_album_versions(results)

    return {
        "artist": info["name"],
        "user_total_scrobbles": info["user_playcount"],
        "albums": sorted(results, key=lambda x: -x["global_playcount"]),
        "stats": {
            "threshold": threshold,
            "filtered_out": total_before_filter - len(real_albums),
            "merged": albums_before_dedup - len(results),
        },
    }


def merge_results(results: list[dict]) -> list[dict]:
    """Merge multiple artist results into one, combining albums with the same name."""
    merged_albums = {}
    total_scrobbles = 0
    artist_names = []
    for r in results:
        artist_names.append(r["artist"])
        total_scrobbles += r["user_total_scrobbles"]
        for a in r["albums"]:
            key = normalize_album_name(a["album"]).lower()
            if key not in merged_albums:
                merged_albums[key] = dict(a)
            else:
                existing = merged_albums[key]
                existing["user_playcount"] += a["user_playcount"]
                existing["global_playcount"] += a["global_playcount"]
                # Merge track-level data: take the version with more tracks heard
                if isinstance(a["total_tracks"], int) and a["tracks_heard"] > existing["tracks_heard"]:
                    existing["total_tracks"] = a["total_tracks"]
                    existing["tracks_heard"] = a["tracks_heard"]
                    existing["tracks"] = a["tracks"]
    return [{
        "artist": " / ".join(artist_names),
        "user_total_scrobbles": total_scrobbles,
        "albums": sorted(merged_albums.values(), key=lambda x: -x["global_playcount"]),
    }]


def filter_albums_only(albums: list[dict]) -> list[dict]:
    return [a for a in albums if isinstance(a["total_tracks"], int) and a["total_tracks"] >= 4]


def album_status(a: dict) -> str:
    """Return status label for an album: Y (full), P (partial), N (unheard).

    Uses tracks_heard if available (per-track userplaycount from API).
    Falls back to comparing total scrobbles vs track count as a heuristic:
    if you've scrobbled fewer times than there are tracks, you likely haven't
    heard them all.
    """
    if a["user_playcount"] == 0:
        return "N"
    total = a["total_tracks"]
    heard = a["tracks_heard"]
    if isinstance(total, int) and total > 0:
        # If per-track data is available, use it
        if heard > 0 and heard < total:
            return "P"
        # If per-track data isn't populated, fall back to scrobble count heuristic
        if heard == 0 and a["user_playcount"] < total:
            return "P"
    return "Y"


def sort_albums(albums: list[dict], sort_by: str) -> list[dict]:
    sort_keys = {
        "popularity": lambda x: -x["global_playcount"],
        "status": lambda x: {"N": 2, "P": 1, "Y": 0}[album_status(x)],
        "tracks": lambda x: -(x["total_tracks"] if isinstance(x["total_tracks"], int) else 0),
        "plays": lambda x: -x["user_playcount"],
        "name": lambda x: x["album"].lower(),
    }
    return sorted(albums, key=sort_keys.get(sort_by, sort_keys["popularity"]))


def print_report(results: list[dict], albums_only: bool = False, show_summary: bool = True,
                 status_filter: list[str] | None = None, sort_by: str = "popularity",
                 verbosity: int = 0):
    for r in results:
        if verbosity >= 2:
            stats = r.get("stats", {})
            parts = [f"threshold: {stats.get('threshold', '?')}"]
            if stats.get("filtered_out"):
                parts.append(f"{stats['filtered_out']} albums below threshold")
            if stats.get("merged"):
                parts.append(f"{stats['merged']} versions merged")
            console.print(f"  [dim]{' | '.join(parts)}[/dim]")

        albums = filter_albums_only(r["albums"]) if albums_only else r["albums"]
        if status_filter:
            albums = [a for a in albums if album_status(a) in status_filter]
        albums = sort_albums(albums, sort_by)

        table = Table(
            title=f"{r['artist']}  [dim]({r['user_total_scrobbles']} scrobbles)[/dim]",
            title_style="bold",
            show_lines=False,
            padding=(0, 1),
        )
        table.add_column("", width=3, justify="center")
        table.add_column("Album", min_width=20)
        table.add_column("Tracks", justify="right", width=8)
        table.add_column("Plays", justify="right", width=6)

        for a in albums:
            status = album_status(a)
            total = a["total_tracks"]
            heard = a["tracks_heard"]

            status_colors = {"Y": "green", "P": "yellow", "N": "red"}
            color = status_colors[status]

            if status == "N":
                tracks_str = f"[dim]{total}[/dim]"
                plays_str = "[dim]-[/dim]"
                album_str = f"[dim]{a['album']}[/dim]"
            elif status == "P":
                if heard > 0:
                    tracks_str = f"[yellow]{heard}/{total}[/yellow]"
                else:
                    tracks_str = f"[yellow]{a['user_playcount']}/{total}[/yellow]"
                plays_str = f"[yellow]{a['user_playcount']}[/yellow]"
                album_str = a["album"]
            else:
                tracks_str = f"[green]{total}/{total}[/green]"
                plays_str = f"[green]{a['user_playcount']}[/green]"
                album_str = a["album"]

            table.add_row(f"[{color}]{status}[/{color}]", album_str, tracks_str, plays_str)

        console.print()
        console.print(table)

        if albums and all(album_status(a) == "Y" for a in albums):
            console.print("  [bold green]You've heard everything![/bold green]")

    # Summary
    if show_summary:
        all_albums = []
        for r in results:
            a = filter_albums_only(r["albums"]) if albums_only else r["albums"]
            all_albums.extend(a)

        full = sum(1 for a in all_albums if album_status(a) == "Y")
        partial = sum(1 for a in all_albums if album_status(a) == "P")
        missing = sum(1 for a in all_albums if album_status(a) == "N")

        summary_table = Table(title="Summary", title_style="bold", show_lines=False, padding=(0, 1))
        summary_table.add_column("", width=20)
        summary_table.add_column("Count", justify="right", width=6)
        summary_table.add_row("Total releases", str(len(all_albums)))
        summary_table.add_row("[green]Fully heard[/green]", f"[green]{full}[/green]")
        summary_table.add_row("[yellow]Partial[/yellow]", f"[yellow]{partial}[/yellow]")
        summary_table.add_row("[red]Not heard[/red]", f"[red]{missing}[/red]")

        console.print()
        console.print(summary_table)



VALID_STATUSES = {"Y", "P", "N"}
VALID_SORT_KEYS = ["popularity", "status", "tracks", "plays", "name"]


def parse_status_filter(values: list[str]) -> list[str]:
    statuses = [s.strip().upper() for s in values]
    for s in statuses:
        if s not in VALID_STATUSES:
            raise typer.BadParameter(f"Invalid status '{s}'. Must be Y, P, or N.")
    return statuses


@app.command()
def main(
    artists: list[str] = typer.Argument(
        help="Artist names to check"
    ),
    albums_only: bool = typer.Option(
        False, "--albums-only", "-a", help="Show only albums/EPs (4+ tracks)"
    ),
    no_summary: bool = typer.Option(
        False, "--no-summary", "-S", help="Hide the summary table"
    ),
    status: Optional[list[str]] = typer.Option(
        None, "--status", "-s", help="Filter by status: Y, P, N (e.g. -s N -s P)"
    ),
    sort: str = typer.Option(
        "popularity", "--sort", help=f"Sort albums by: {', '.join(VALID_SORT_KEYS)}"
    ),
    exclude: Optional[list[str]] = typer.Option(
        None, "--exclude", "-e", help="Exclude albums containing these words (e.g. -e remix -e live)"
    ),
    merge: bool = typer.Option(
        False, "--merge", "-m", help="Merge albums with the same name across artists"
    ),
    no_dedup: bool = typer.Option(
        False, "--no-dedup", help="Don't merge different versions of the same album"
    ),
    username: str = typer.Option(
        DEFAULT_USERNAME, "--user", "-u", help="Last.fm username (default: LASTFM_USERNAME env var)"
    ),
    min_threshold: Optional[int] = typer.Option(
        None, "--min-plays", "-p", help="Minimum global playcount to include an album (default: auto)"
    ),
    verbose: int = typer.Option(
        0, "--verbose", "-v", count=True, help="Increase verbosity (-v for info, -vv for details)"
    ),
):
    """Check if you've heard an artist's full discography on Last.fm."""
    exclude_lower = [w.lower() for w in exclude] if exclude else None
    status_filter = parse_status_filter(status) if status else None
    if sort not in VALID_SORT_KEYS:
        raise typer.BadParameter(f"Invalid sort key '{sort}'. Must be one of: {', '.join(VALID_SORT_KEYS)}")

    mode = "albums/EPs only" if albums_only else "all releases"
    panel_lines = [f"[bold]{', '.join(artists)}[/bold]"]
    if verbose >= 1:
        panel_lines.append(f"[dim]user: {username} | mode: {mode} | min-plays: {min_threshold or 'auto'}[/dim]")
    console.print(Panel("\n".join(panel_lines), title="Discography Check"))

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TextColumn("[dim]{task.completed}/{task.total} albums[/dim]"),
        console=console,
    ) as progress:
        for artist in artists:
            task_id = progress.add_task(f"Fetching {artist}...", total=None)
            results.append(check_artist(artist, progress, task_id, username=username,
                                        exclude=exclude_lower, dedup=not no_dedup,
                                        min_threshold=min_threshold))
            progress.update(task_id, description=f"[green]Done: {artist}[/green]")

    if merge:
        results = merge_results(results)

    print_report(results, albums_only=albums_only, show_summary=not no_summary,
                 status_filter=status_filter, sort_by=sort, verbosity=verbose)


if __name__ == "__main__":
    app()
