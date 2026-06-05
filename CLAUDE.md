# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Converts course videos into study material: extracts a plain-text transcription and a PDF of unique "slides" (diagrams, code screens) so a user can then ask Claude to produce an illustrated HTML study summary. The two scripts are meant to be run in parallel on the same video file.

## Dependencies

```bash
pip install faster-whisper opencv-python pillow
# also requires ffmpeg on PATH
```

## Running the scripts

Both scripts take the video path as the first positional argument and output a file with the same base name (`.txt` or `.pdf`) in the same directory.

```bash
# Transcription
python transcribir.py "video.mp4"
python transcribir.py "video.mp4" --modelo base --timestamps --idioma en

# Slides extraction
python slides.py "video.mp4"
python slides.py "video.mp4" --umbral 12 --calidad 70 --max-mb 20
```

## Architecture

The project is two independent single-file CLI scripts with no shared code:

- **`transcribir.py`** — loads a `faster-whisper` `WhisperModel` (CPU, int8), streams segments, writes a `.txt`. Imports are deferred inside `main()` so `--help` is instant.
- **`slides.py`** — opens the video with `cv2`, samples one frame every `--intervalo` seconds, compares consecutive frames by downscaling to 32×32 grayscale and taking the mean absolute difference (`cv2.absdiff`). Frames that differ by at least `--umbral` are kept. Kept frames are assembled into a PDF via Pillow, split into parts if the result would exceed `--max-mb` MB or `--max-paginas` pages (defaults tuned to Claude's upload limits: 30 MB / ~100 pages).

## Key design constraints

- PDF output must stay under **28 MB** and **95 pages** per file to fit within Claude's visual analysis limits. The `guardar_pdf` helper in `slides.py` enforces both limits simultaneously using a greedy chunking loop.
- The frame-comparison metric is intentionally coarse (32×32 mean diff) — fast and robust to minor video compression artifacts.
- `transcribir.py` uses `vad_filter=False` deliberately; enabling it can silently drop segments.
