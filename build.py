#!/usr/bin/env python3
"""Build metadata (games.json) and per-move AVIF frames.

Reads Nortrom/summary.csv, derives per-game info from the GAME logs, and for the
move-by-move viewer compresses every raw screenshot into a small AVIF under
Nortrom/frames/game{N}/ (see compress_logs.py). Re-runnable; skips frames that
already exist.

    conda activate pytorch     # env with pillow + pillow-avif-plugin
    python build.py            # metadata + frames
    python build.py --no-frames    # skip the (slow, ~2 min) frame pass
"""
import argparse
import csv
import json
import os
import re

import compress_logs

ROOT = os.path.dirname(os.path.abspath(__file__))
NORTROM = os.path.join(ROOT, "Nortrom")
OUT_JSON = os.path.join(ROOT, "assets", "games.json")

def parse_date(log_path):
    """Folder name like 'logs/2025-07-08 12:17:08/GAME-...' -> date string."""
    m = re.search(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})", log_path)
    return f"{m.group(1)} {m.group(2)}" if m else ""


def count_plies(game_log_abs):
    """GAME log: line 1 = header, line 2 = setup, remaining lines = plies."""
    try:
        with open(game_log_abs, "r", errors="replace") as f:
            n = sum(1 for _ in f)
        return max(0, n - 2)
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-frames", action="store_true",
                    help="skip generating per-move AVIF frames (metadata only)")
    ap.add_argument("--workers", type=int, default=None,
                    help="parallel processes for frame encoding (default: all cores)")
    args = ap.parse_args()

    games = []
    with open(os.path.join(NORTROM, "summary.csv")) as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        num = int(row["game"])
        outcome = row["outcome"].strip().upper()
        log_rel = row["log"].strip()  # e.g. logs/2025-.../GAME-xxx.log
        folder_rel = os.path.dirname(log_rel)
        folder_abs = os.path.join(NORTROM, folder_rel)
        game_log_abs = os.path.join(NORTROM, log_rel)

        # Sorted move numbers for the frame viewer (may be sparse, e.g. one side's plies).
        frame_moves = [mv for mv, _ in compress_logs.list_frames(folder_abs)]

        games.append({
            "num": num,
            "outcome": outcome,
            "date": parse_date(log_rel),
            "plies": count_plies(game_log_abs),
            "video": f"Nortrom/videos/Game{num}.mp4",
            # Frame viewer: build `${framesDir}/move${n}.avif` for n in frames.
            # Uses the bottom-cropped tree — full-width rendering with no black
            # bars; the full-height originals stay under Nortrom/frames/.
            "framesDir": f"Nortrom/frames_cropped/game{num}" if frame_moves else None,
            "frames": frame_moves,
        })
        print(f"game {num:>2}  {outcome}  plies={games[-1]['plies']}  "
              f"frames={len(frame_moves)}")

    wins = sum(1 for g in games if g["outcome"] == "W")
    losses = sum(1 for g in games if g["outcome"] == "L")
    draws = sum(1 for g in games if g["outcome"] == "D")

    payload = {
        "player": "Nortrom",
        "record": {"wins": wins, "losses": losses, "draws": draws, "total": len(games)},
        # Game value on a [-1, +1] scale (win=+1, loss=-1, draw=0), matching summary.txt.
        "empiricalValue": round((wins - losses) / len(games), 3) if games else 0,
        "games": games,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nWrote {OUT_JSON}: {wins}W {losses}L {draws}D")

    # Per-move AVIF frames for the viewer (skips ones already built; ~2 min cold).
    if args.no_frames:
        print("skipped frame generation (--no-frames)")
    elif os.path.isdir(os.path.join(NORTROM, "logs")):
        compress_logs.run(compress_logs.build_jobs(), workers=args.workers)
    else:
        print("no Nortrom/logs/ present — skipping frames "
              "(the frame viewer needs Nortrom/frames/ deployed)")


if __name__ == "__main__":
    main()
