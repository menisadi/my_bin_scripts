---
name: notleko
description: Play a full game of chess against Stockfish using the notleko CLI, one move per invocation, with reasoning recorded as PGN comments.
---

Use the `notleko` CLI to play a full game against Stockfish.

## Arguments

Parse these from the invocation text (e.g. `/notleko elo=1800 reasoning=off`).
Both are optional; if omitted, use the defaults below.

- `elo=<number>` — Stockfish strength cap for `notleko engine --elo`.
  Default: `1500`.
- `reasoning=on|off` — whether to explain your moves. Default: `on`.
  - `on`: current behavior — every move includes `--reason`, and you add a
    `notleko comment` after each Stockfish reply (see below).
  - `off`: play silently — omit `--reason` on `notleko move`, and skip
    `notleko comment` entirely. Still use `notleko status --json` as needed
    to inspect the position; that's bookkeeping, not commentary.

First, get familiar with the commands:

```
notleko --help
notleko new --help
notleko move --help
notleko engine --help
notleko comment --help
```

Then play a full game where you are White and Stockfish is Black:

- Store the game in a file named `{yourname}_game_{YYYY-MM-DD}.pgn`. Pass this
  file to every command with the `--file` flag, placed AFTER the subcommand
  (e.g. `notleko new --file yourname_game_2026-08-04.pgn ...`).
- Start with `notleko new`, passing your name via `--name` and choosing White
  with `--color white`.
- Then repeat this loop until the game ends: play your move -> let Stockfish
  reply -> (if `reasoning=on`) comment on its reply.
  - Your move: `notleko move <uci>`, adding `--reason "..."` if
    `reasoning=on`. In every `--reason` cover, in order: (1) your read of the
    position, (2) the candidate moves you considered, (3) why you chose this
    one. A few sentences is plenty.
  - Stockfish's reply: `notleko engine --elo <elo> ...` — caps its strength
    to the requested Elo so the game is a real contest.
  - Your comment (only if `reasoning=on`): `notleko comment "..."` covering
    (1) what Stockfish's move does / its idea, and (2) how it changes your
    assessment. Don't rewrite existing comments — only add new ones.
- Use `notleko status --json` whenever you need to inspect the position,
  whose turn it is, or the list of legal moves.

Play the single game through to its end — checkmate, draw, or, if the
position is clearly lost, `notleko resign`.
