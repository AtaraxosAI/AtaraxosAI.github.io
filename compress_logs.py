#!/usr/bin/env python3
"""Compress raw per-move screenshots into small, web-legible AVIF frames.

The raw µStratego screenshots under ``Nortrom/logs/<date>/moveN.png`` are
3299x2800 RGBA PNGs at ~2.5 MB each (12 GB total). This flattens each onto
black, downscales to 1600 px wide, and re-encodes as AVIF — a ~20x size cut
(≈120 KB/img) that keeps even the tiny Belief-matrix numbers legible. AVIF wins
big here because the dashboards are synthetic UI (flat colors, sharp text, huge
black regions) rather than photos. Chroma is kept at full 4:4:4 resolution: the
plugin's 4:2:0 default halves color resolution, which measurably smears the
colored text (4x the RGB error on saturated pixels for these frames).

Frames are written game-numbered — ``Nortrom/frames/game{N}/move{K}.avif`` —
matching the rest of the site (Game{N}.mp4) and avoiding the spaces
and colons in the raw date-folder names, which are fragile in URLs and invalid
in filenames on some systems. A second tree, ``Nortrom/frames_cropped/``, holds
the same frames with the trailing black rows trimmed (same width, per-frame
height) for layouts where the mostly-black bottom wastes space. The originals
(needed to rebuild the videos) are left untouched. Re-runnable: existing
outputs are skipped.

    conda activate pytorch          # env with pillow + pillow-avif-plugin
    python compress_logs.py         # convert every game's frames
    python compress_logs.py --width 1400 --quality 45             # smaller

`build.py` imports the helpers here, so ``python build.py`` also builds frames.

Requires: Pillow and pillow-avif-plugin  (pip install pillow pillow-avif-plugin)
"""
import argparse
import csv
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

import pillow_avif  # noqa: F401  (registers the AVIF codec with Pillow)
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
NORTROM = os.path.join(ROOT, "Nortrom")
FRAMES_ROOT = os.path.join(NORTROM, "frames")
CROPPED_ROOT = os.path.join(NORTROM, "frames_cropped")

WIDTH = 1600      # px; keeps the tiny Belief numbers legible while cutting ~20x
QUALITY = 55      # AVIF quality 0-100
SPEED = 4         # AVIF speed 0-10 (lower = smaller + slower)
SUBSAMPLING = "4:4:4"  # full-res chroma; the 4:2:0 default smears colored text
CROP_THRESHOLD = 10    # channel value at or below this counts as black
CROP_MARGIN = 30       # px of black padding kept below the lowest content row


def list_frames(folder_abs):
    """Sorted [(move_number, png_abspath)] for a game's log folder."""
    out = []
    if not os.path.isdir(folder_abs):
        return out
    for name in os.listdir(folder_abs):
        m = re.fullmatch(r"move(\d+)\.png", name)
        if m:
            out.append((int(m.group(1)), os.path.join(folder_abs, name)))
    out.sort()
    return out


def frame_dst(game_num, move_num, frames_root=FRAMES_ROOT):
    return os.path.join(frames_root, f"game{game_num}", f"move{move_num}.avif")


def crop_black_bottom(rgb, threshold=CROP_THRESHOLD, margin=CROP_MARGIN):
    """Trim trailing all-black rows, keeping `margin` px of padding."""
    bbox = rgb.convert("L").point(lambda p: 255 if p > threshold else 0).getbbox()
    if bbox and bbox[3] + margin < rgb.height:
        rgb = rgb.crop((0, 0, rgb.width, bbox[3] + margin))
    return rgb


def png_to_avif(src, dst, width=WIDTH, quality=QUALITY, speed=SPEED,
                subsampling=SUBSAMPLING, crop=False):
    """Flatten onto black, drop alpha, downscale, and write AVIF."""
    img = Image.open(src)
    rgb = Image.new("RGB", img.size, (0, 0, 0))
    rgb.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
    if width < rgb.width:
        h = round(rgb.height * width / rgb.width)
        rgb = rgb.resize((width, h), Image.LANCZOS)
    if crop:
        rgb = crop_black_bottom(rgb)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    rgb.save(dst, "AVIF", quality=quality, speed=speed, subsampling=subsampling)


def _convert(job):
    src, dst, width, quality, speed, subsampling, crop = job
    try:
        png_to_avif(src, dst, width, quality, speed, subsampling, crop)
        return os.path.getsize(src), os.path.getsize(dst), None
    except Exception as e:  # keep the batch going; report at the end
        return 0, 0, f"{src}: {e}"


def game_folders(nortrom=NORTROM):
    """[(game_num, folder_abs)] from summary.csv (game -> log folder)."""
    games = []
    with open(os.path.join(nortrom, "summary.csv")) as f:
        for row in csv.DictReader(f):
            folder_rel = os.path.dirname(row["log"].strip())
            games.append((int(row["game"]), os.path.join(nortrom, folder_rel)))
    return games


def build_jobs(frames_root=FRAMES_ROOT, cropped_root=CROPPED_ROOT, width=WIDTH,
               quality=QUALITY, speed=SPEED, subsampling=SUBSAMPLING, force=False):
    jobs = []
    for num, folder in game_folders():
        for move, src in list_frames(folder):
            for root, crop in ((frames_root, False), (cropped_root, True)):
                dst = frame_dst(num, move, root)
                if force or not os.path.exists(dst):
                    jobs.append((src, dst, width, quality, speed, subsampling, crop))
    return jobs


def run(jobs, workers=None, quiet=False):
    total = len(jobs)
    if not total:
        if not quiet:
            print("frames: nothing to do (all exist; --force to redo)")
        return
    workers = workers or os.cpu_count()
    if not quiet:
        print(f"frames: {total} to convert on {workers} workers ...")
    src_b = dst_b = done = 0
    errors = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed([ex.submit(_convert, j) for j in jobs]):
            sb, db, err = fut.result()
            done += 1
            if err:
                errors.append(err)
            else:
                src_b += sb
                dst_b += db
            if not quiet and (done % 50 == 0 or done == total):
                print(f"\r  {done}/{total} ({done/total*100:4.0f}%)  "
                      f"{src_b/1e6:,.0f} MB -> {dst_b/1e6:,.1f} MB", end="", flush=True)
    if not quiet:
        ratio = src_b / dst_b if dst_b else 0
        avg = dst_b / max(1, total - len(errors)) / 1024
        print(f"\n  {src_b/1e6:,.0f} MB -> {dst_b/1e6:,.1f} MB "
              f"({ratio:.1f}x smaller, avg {avg:.0f} KB/img)")
        for e in errors[:10]:
            print("  ERR", e)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width", type=int, default=WIDTH)
    ap.add_argument("--quality", type=int, default=QUALITY)
    ap.add_argument("--speed", type=int, default=SPEED)
    ap.add_argument("--subsampling", default=SUBSAMPLING,
                    choices=["4:4:4", "4:2:2", "4:2:0", "4:0:0"])
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--force", action="store_true", help="re-encode even if output exists")
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(NORTROM, "logs")):
        sys.exit("no Nortrom/logs/ present locally — nothing to compress")
    jobs = build_jobs(width=args.width, quality=args.quality, speed=args.speed,
                      subsampling=args.subsampling, force=args.force)
    run(jobs, workers=args.workers)


if __name__ == "__main__":
    main()
