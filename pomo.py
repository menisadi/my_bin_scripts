#!/usr/bin/env -S uv run
import argparse
import time

DEFAULT_MINUTES = 25
DEFAULT_BAR_WIDTH = 30

def format_time(seconds_left: int) -> str:
    m, s = divmod(seconds_left, 60)
    return f"{m:02d}:{s:02d}"

def pomodoro(minutes: int, bar_width: int) -> None:
    total_seconds = minutes * 60
    start_time = time.time()

    try:
        while True:
            elapsed = int(time.time() - start_time)
            if elapsed > total_seconds:
                break

            remaining = total_seconds - elapsed
            progress = elapsed / total_seconds if total_seconds else 1
            filled = int(bar_width * progress)

            bar = "█" * filled + "░" * (bar_width - filled)
            timer_str = format_time(remaining)

            print(f"\r[{bar}] {timer_str}", end="", flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nTimer cancelled.")
        return

    print(f"\r[{'█' * bar_width}] 00:00  ✅ Done!")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple terminal Pomodoro timer.")
    parser.add_argument(
        "minutes",
        nargs="?",
        type=int,
        default=DEFAULT_MINUTES,
        help=f"Length of the timer in minutes (default: {DEFAULT_MINUTES})",
    )
    parser.add_argument(
        "-w", "--width",
        type=int,
        default=DEFAULT_BAR_WIDTH,
        help=f"Width of the progress bar (default: {DEFAULT_BAR_WIDTH})",
    )
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    print(f"Starting a {args.minutes}-minute pomodoro ")
    pomodoro(args.minutes, args.width)

if __name__ == "__main__":
    main()

