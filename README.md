# Ataraxos vs. Pim Niemeijer

A static showcase of the 20-game match between four-time Stratego world champion Pim Niemeijer and the Stratego AI Ataraxos.
Ataraxos won the series with 15 wins, 1 loss, and 4 draws.

## The move-by-move viewer

Each raw screenshot is a 3299×2800 PNG (~2.5 MB). For the web they are
recompressed to **AVIF at 1600 px wide, quality 55, 4:4:4 chroma** — about
**99 KB each, a ~20× cut** — which stays crisp enough to read the tiny
Belief-matrix numbers. AVIF is the right codec here because the dashboards are
synthetic UI (flat colors, sharp text, big black regions), not photos. Full-res
4:4:4 chroma matters for the same reason: the encoder's default 4:2:0
subsampling halves color resolution and visibly smears the colored text.

Two trees are generated, game-numbered to avoid the spaces/colons in the raw
date folders: `Nortrom/frames/game{N}/move{K}.avif` (full height) and
`Nortrom/frames_cropped/` (same width, trailing black bottom trimmed per
frame — **this is what the viewer shows**, rendered full-width with vertical
scroll). `assets/games.json` lists each game's move numbers, and the viewer
builds one URL at a time.

## How it stays light

- **Nothing heavy loads on startup.** The page fetches `assets/games.json`, then
  only the selected game's replay video (metadata first; it previews its own first
  frame via a `#t=0.1` media fragment). Other games' videos load only when picked.
- **Frames load on demand.** Opening a game loads only the current AVIF frame
  (plus a couple prefetched neighbors); the `src` is dropped on close. The whole
  sequence is never in memory at once.

## What is / isn't committed

| Path | Size | In repo? |
|------|------|----------|
| `Nortrom/frames_cropped/` (per-move AVIFs, bottom-cropped) | **~0.7 GB** | ⚠️ used by the viewer — see note |
| `Nortrom/frames/` (per-move AVIFs, full height) | **~0.6 GB** | full-height renders; not fetched by the site |
| `Nortrom/videos/` | 43 MB | ✅ per-game replay videos (shown in the right pane) |
| `Nortrom/logs/` (raw per-move PNGs) | **12 GB** | ❌ ignored via `.gitignore` |

**Heads up on repo size.** The two AVIF trees together are ~1.3 GB, over
GitHub's ~1 GB repo soft limit. Options: commit only `frames_cropped/` (the one
the site fetches), shrink further (`--width 1400 --quality 45`), or host the
frames on a CDN / object store and point the viewer there. The raw PNGs stay
excluded (~453 MB/game, far over GitHub's limits).

## Rebuilding metadata / frames

Regenerate everything from the logs (needs `Nortrom/logs/` present locally; uses
`pillow-avif-plugin` for the frames):

```sh
conda activate pytorch          # env with pillow + pillow-avif-plugin
python build.py                 # games.json + all frames (~2 min)
python build.py --no-frames     # metadata only (fast)
python build.py --workers 2     # limit frame encoding to 2 cores

# Just the frames, with size knobs:
python compress_logs.py --width 1400 --quality 45
```

## Deploy to GitHub Pages

```sh
git init
git add .
git commit -m "Nortrom game archive"
git branch -M main
git remote add origin git@github.com:<you>/<repo>.git
git push -u origin main
```

Then in the repo: **Settings → Pages → Source: Deploy from a branch → `main` / root**.
The site will be served at `https://<you>.github.io/<repo>/`.

## Local preview

```sh
python3 -m http.server 8000
# open http://localhost:8000
```

## Files

```
index.html               markup
assets/styles.css        dark + paper-light themes (toggle top-right, choice persisted)
assets/app.js            game rail + video pane + filters + move-by-move frame viewer
assets/games.json        generated per-game metadata (incl. frame lists)
Nortrom/frames/          generated per-move AVIFs, full height (game{N}/move{K}.avif)
Nortrom/frames_cropped/  same frames, black bottom trimmed — what the viewer loads
build.py                 regenerates games.json + frames
compress_logs.py         PNG→AVIF frame compressor (used by build.py; also standalone)
```
