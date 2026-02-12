#!/usr/bin/env -S uv run
# /// script
# dependencies = ["rich", "python-chess"]
# ///
import argparse
import sys

import chess
import chess.pgn
import chess.engine
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from rich.panel import Panel
from rich.text import Text

console = Console()

# --- Lichess-ish ACPL knobs ---
LICHESS_START_CP_WHITE = 15  # Lichess uses +15cp as the starting eval for White
EVAL_CAP_CP = 1000  # Lichess caps evals to [-1000, +1000] and maps mates to +/-1000

# --- Your classification thresholds (in centipawns of loss) ---
INACCURACY_THRESHOLD = 50
MISTAKE_THRESHOLD = 100
BLUNDER_THRESHOLD = 300


def cp_to_gray_level(cp: int, cap_cp: int, steps: int) -> int:
    """
    Map centipawns (White POV) to a grayscale level 0..255.
    -cp cap => black (0), +cp cap => white (255), 0 => mid gray.
    Quantize to `steps` levels to cope with limited terminal palettes.
    """
    cap_cp = max(1, int(cap_cp))
    steps = int(steps)

    cp = clamp(cp, -cap_cp, cap_cp)
    t = (cp + cap_cp) / (2 * cap_cp)  # 0..1
    level = int(round(t * 255))

    if steps >= 2:
        step = 255 / (steps - 1)
        level = int(round(level / step) * step)

    return clamp(level, 0, 255)


def print_eval_bar(
    evals_white_cp: list[int],
    *,
    cap_cp: int = EVAL_CAP_CP,
    steps: int = 24,
    wrap_width: int | None = None,
    title: str = "Evaluation bar (White POV)",
    show_legend: bool = True,
):
    if not evals_white_cp:
        return

    usable_width = max(10, int(wrap_width)) if wrap_width else max(10, console.width - 2)
    block_char = " "
    lines: list[Text] = []

    cur = Text()
    for i, cp in enumerate(evals_white_cp, start=1):
        g = cp_to_gray_level(cp, cap_cp=cap_cp, steps=steps)
        cur.append(block_char, style=f"on rgb({g},{g},{g})")
        if (i % usable_width) == 0:
            lines.append(cur)
            cur = Text()
    if len(cur) > 0:
        lines.append(cur)

    if show_legend:
        legend = Text()
        legend.append(" Black ", style="on rgb(0,0,0)")
        legend.append("  ≈0  ", style="on rgb(128,128,128)")
        legend.append(" White ", style="on rgb(255,255,255)")
        console.print(Panel.fit(legend, title=title, padding=(0, 1)))

    for line in lines:
        console.print(line)
    console.print()


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


def analyze_game(
    pgn_path: str,
    stockfish_path: str,
    depth: int = 14,
    threads: int | None = None,
    hash_mb: int | None = None,
    collect_evals: bool = False,
):
    evals_white_cp: list[int] | None = [] if collect_evals else None

    try:
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    except Exception as e:
        console.print(
            f"[bold red]Error:[/bold red] Could not start Stockfish at {stockfish_path}. {e}"
        )
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
            return None, None, None

        total_plies = sum(1 for _ in game.mainline_moves())
        board = game.board()

        stats = {
            chess.WHITE: {
                "cpl_total": 0,
                "moves": 0,
                "inaccuracies": 0,
                "mistakes": 0,
                "blunders": 0,
            },
            chess.BLACK: {
                "cpl_total": 0,
                "moves": 0,
                "inaccuracies": 0,
                "mistakes": 0,
                "blunders": 0,
            },
        }

        # Header Panel
        header_info = (
            f"[bold white]{game.headers.get('White', 'Unknown')}[/bold white] vs "
            f"[bold white]{game.headers.get('Black', 'Unknown')}[/bold white]\n"
            f"[cyan]Result:[/cyan] [bold yellow]{game.headers.get('Result', '*')}[/bold yellow] | "
            f"[cyan]Depth:[/cyan] {depth}"
        )
        console.print(
            Panel(
                header_info, title="[bold blue]Chess Analysis[/bold blue]", expand=False
            )
        )

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

                if evals_white_cp is not None:
                    evals_white_cp.append(eval_white_cp)

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

        return stats, game.headers, evals_white_cp

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
    table.add_row(
        "Inaccuracies",
        f"[yellow]{w['inaccuracies']}[/yellow]",
        f"[yellow]{b['inaccuracies']}[/yellow]",
    )
    table.add_row(
        "Mistakes",
        f"[orange3]{w['mistakes']}[/orange3]",
        f"[orange3]{b['mistakes']}[/orange3]",
    )
    table.add_row(
        "Blunders",
        f"[bold red]{w['blunders']}[/bold red]",
        f"[bold red]{b['blunders']}[/bold red]",
    )

    console.print(table)
    console.print(
        f"\n[dim]Analysis completed for {w['moves'] + b['moves']} total plies.[/dim]\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze a PGN file using Stockfish (Lichess-ish ACPL)."
    )
    parser.add_argument("pgn", help="Path to the PGN file")
    parser.add_argument(
        "--engine", default="stockfish", help="Path to Stockfish binary"
    )
    parser.add_argument(
        "--depth", type=int, default=14, help="Analysis depth (higher = slower)"
    )
    parser.add_argument(
        "--threads", type=int, default=None, help="Stockfish Threads (optional)"
    )
    parser.add_argument(
        "--hash", type=int, default=None, help="Stockfish Hash in MB (optional)"
    )
    parser.add_argument(
        "--evalbar",
        action="store_true",
        help="Print a grayscale evaluation bar (one block per ply).",
    )
    parser.add_argument(
        "--evalbar-cap",
        type=int,
        default=400,
        help="Centipawn cap for mapping to grayscale (default: 400).",
    )
    parser.add_argument(
        "--evalbar-steps",
        type=int,
        default=24,
        help="Number of grayscale shades to use (default: 24).",
    )
    parser.add_argument(
        "--evalbar-wrap",
        type=int,
        default=0,
        help="Blocks per evalbar line before wrapping (default: 0 = fit terminal width).",
    )
    parser.add_argument(
        "--evalbar-legend",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show/hide the evaluation bar legend (default: on).",
    )

    args = parser.parse_args()

    results, headers, evals = analyze_game(
        args.pgn,
        args.engine,
        depth=args.depth,
        threads=args.threads,
        hash_mb=args.hash,
        collect_evals=args.evalbar,
    )

    if results:
        print_report(results, headers)
        if args.evalbar and evals:
            print_eval_bar(
                evals,
                cap_cp=args.evalbar_cap,
                steps=args.evalbar_steps,
                wrap_width=args.evalbar_wrap,
                show_legend=args.evalbar_legend,
            )
