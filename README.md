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

## Rebuilding metadata / frames

Regenerate everything from the raw logs (needs a Python env with `pillow` and
`pillow-avif-plugin` installed):

```sh
python build.py                 # games.json + all frames (~2 min)
python build.py --no-frames     # metadata only (fast)
python build.py --workers 2     # limit frame encoding to 2 cores

# Just the frames, with size knobs:
python compress_logs.py --width 1400 --quality 45
```

## Local preview

```sh
python3 -m http.server 8000
```

## Files

```
index.html               markup
assets/styles.css        dark + paper-light themes (toggle top-right, choice persisted)
assets/app.js            game rail + video pane + filters + move-by-move frame viewer
assets/games.json        generated per-game metadata (incl. frame lists)
Nortrom/frames_cropped/  per-move AVIFs, black bottom trimmed — what the viewer loads
build.py                 regenerates games.json + frames
compress_logs.py         PNG→AVIF frame compressor (used by build.py; also standalone)
```
