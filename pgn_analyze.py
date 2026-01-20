#!/usr/bin/env -S uv run
# /// script
# dependencies = ["rich"]
# ///
import argparse
import sys

import chess
import chess.pgn
import chess.engine
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

console = Console()

# --- Lichess-ish ACPL knobs ---
LICHESS_START_CP_WHITE = 15   # Lichess uses +15cp as the starting eval for White
EVAL_CAP_CP = 1000            # Lichess caps evals to [-1000, +1000] and maps mates to +/-1000

# --- Your classification thresholds (in centipawns of loss) ---
INACCURACY_THRESHOLD = 50
MISTAKE_THRESHOLD = 100
BLUNDER_THRESHOLD = 300


def clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))


def score_to_capped_cp(score: chess.engine.PovScore, pov: chess.Color) -> int:
    """
    Convert a python-chess score to a Lichess-ish centipawn integer:
    - mates mapped to +/-EVAL_CAP_CP via mate_score=EVAL_CAP_CP
    - clamped to [-EVAL_CAP_CP, +EVAL_CAP_CP]
    """
    raw = score.pov(pov).score(mate_score=EVAL_CAP_CP)
    if raw is None:
        return 0
    return clamp(raw, -EVAL_CAP_CP, EVAL_CAP_CP)


def analyze_game(pgn_path: str, stockfish_path: str, depth: int = 14, threads: int | None = None, hash_mb: int | None = None):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Could not start Stockfish at {stockfish_path}. {e}")
        sys.exit(1)

    try:
        # Optional engine tuning (safe if the option exists)
        opts = {}
        if threads is not None:
            opts["Threads"] = threads
        if hash_mb is not None:
            opts["Hash"] = hash_mb
        if opts:
            try:
                engine.configure(opts)
            except Exception:
                # If some options don't exist for this engine build, just ignore.
                pass

        with open(pgn_path, "r", encoding="utf-8", errors="replace") as pgn_file:
            game = chess.pgn.read_game(pgn_file)

        if not game:
            console.print("[bold red]Error:[/bold red] No game found in PGN file.")
            return None, None

        total_plies = sum(1 for _ in game.mainline_moves())
        board = game.board()

        stats = {
            chess.WHITE: {"cpl_total": 0, "moves": 0, "inaccuracies": 0, "mistakes": 0, "blunders": 0},
            chess.BLACK: {"cpl_total": 0, "moves": 0, "inaccuracies": 0, "mistakes": 0, "blunders": 0},
        }

        # Header Panel
        header_info = (
            f"[bold white]{game.headers.get('White', 'Unknown')}[/bold white] vs "
            f"[bold white]{game.headers.get('Black', 'Unknown')}[/bold white]\n"
            f"[cyan]Result:[/cyan] [bold yellow]{game.headers.get('Result', '*')}[/bold yellow] | "
            f"[cyan]Depth:[/cyan] {depth}"
        )
        console.print(Panel(header_info, title="[bold blue]Chess Analysis[/bold blue]", expand=False))

        # Lichess-style: use a sequence of evals (from White POV) AFTER each ply,
        # with a fixed starting eval of +15cp for White at ply 0.
        prev_eval_white_cp = LICHESS_START_CP_WHITE

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing moves...", total=total_plies)

            for move in game.mainline_moves():
                mover = board.turn  # who is playing this move
                board.push(move)

                info = engine.analyse(board, chess.engine.Limit(depth=depth))
                eval_white_cp = score_to_capped_cp(info["score"], pov=chess.WHITE)

                # Loss from mover POV:
                # - If White moved: loss = max(0, prev_white_eval - new_white_eval)
                # - If Black moved: loss = max(0, prev_black_eval - new_black_eval)
                #   but black_eval = -white_eval, so loss = max(0, (-prev) - (-new)) = max(0, new - prev)
                if mover == chess.WHITE:
                    loss = max(0, prev_eval_white_cp - eval_white_cp)
                else:
                    loss = max(0, eval_white_cp - prev_eval_white_cp)

                stats[mover]["cpl_total"] += loss
                stats[mover]["moves"] += 1

                if loss >= BLUNDER_THRESHOLD:
                    stats[mover]["blunders"] += 1
                elif loss >= MISTAKE_THRESHOLD:
                    stats[mover]["mistakes"] += 1
                elif loss >= INACCURACY_THRESHOLD:
                    stats[mover]["inaccuracies"] += 1

                prev_eval_white_cp = eval_white_cp
                progress.update(task, advance=1)

        return stats, game.headers

    finally:
        try:
            engine.quit()
        except Exception:
            pass


def print_report(stats, headers):
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Metric", style="dim", width=15)
    table.add_column("White", justify="center", width=10)
    table.add_column("Black", justify="center", width=10)

    w = stats[chess.WHITE]
    b = stats[chess.BLACK]

    w_avg_cpl = (w["cpl_total"] / w["moves"]) if w["moves"] else 0.0
    b_avg_cpl = (b["cpl_total"] / b["moves"]) if b["moves"] else 0.0

    table.add_row("Avg CPL", f"{w_avg_cpl:.1f}", f"{b_avg_cpl:.1f}")
    table.add_row("Inaccuracies", f"[yellow]{w['inaccuracies']}[/yellow]", f"[yellow]{b['inaccuracies']}[/yellow]")
    table.add_row("Mistakes", f"[orange3]{w['mistakes']}[/orange3]", f"[orange3]{b['mistakes']}[/orange3]")
    table.add_row("Blunders", f"[bold red]{w['blunders']}[/bold red]", f"[bold red]{b['blunders']}[/bold red]")

    console.print(table)
    console.print(f"\n[dim]Analysis completed for {w['moves'] + b['moves']} total plies.[/dim]\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a PGN file using Stockfish (Lichess-ish ACPL).")
    parser.add_argument("pgn", help="Path to the PGN file")
    parser.add_argument("--engine", default="stockfish", help="Path to Stockfish binary")
    parser.add_argument("--depth", type=int, default=14, help="Analysis depth (higher = slower)")
    parser.add_argument("--threads", type=int, default=None, help="Stockfish Threads (optional)")
    parser.add_argument("--hash", type=int, default=None, help="Stockfish Hash in MB (optional)")

    args = parser.parse_args()

    results, headers = analyze_game(
        args.pgn,
        args.engine,
        depth=args.depth,
        threads=args.threads,
        hash_mb=args.hash,
    )
    if results:
        print_report(results, headers)
