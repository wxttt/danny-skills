---
name: particle-logo
description: Generate a particle convergence animation video from any logo or image. 10,000 particles scatter and converge into the logo shape with synthesized music that builds to a "ding" reveal. Supports any image (auto-detects background, transparent PNGs, dark/light backgrounds). Use when the user wants to create a particle animation, logo reveal video, or motion graphics from an image.
---

# Particle Logo Convergence

Generate a 1080p particle animation video from any logo or image. Pure local processing — Python + FFmpeg, no API key needed.

## When to Use

Trigger this skill when the user wants to:

- Create a particle animation or logo reveal video
- Turn a logo / image into a motion graphics clip
- Generate a short video with synthesized music from a static image

## Requirements

- **FFmpeg** must be installed (`brew install ffmpeg`)
- **Python deps**: numpy, Pillow (installed automatically via `uv run --with`)

## Workflow

### Step 1: Confirm inputs

Ask the user for (if not already provided):
- **Input image** — any PNG/JPG/WEBP; transparent-background PNGs work best
- **Output path** — e.g. `output.mp4`
- **Size** (optional) — defaults to auto-detect from image aspect ratio
- **Duration** (optional) — defaults to 6 seconds
- **Particles** (optional) — defaults to 10,000
- **Background color** (optional) — defaults to auto-detect

### Step 2: Run the script

```bash
uv run --with numpy --with Pillow python3 <skill-path>/scripts/particle_logo.py <input_image> <output.mp4> [--size WxH] [--duration N] [--particles N] [--fps 30|60] [--bg COLOR] [--no-audio]
```

The script path is `scripts/particle_logo.py` relative to this SKILL.md.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--size WxH` | auto | Video size (e.g. `1920x1080`, `1080x1920`, `1080`) |
| `--duration N` | 6.0 | Duration in seconds (range 3-30) |
| `--particles N` | 10000 | Particle count (range 1000-50000). More = finer detail but slower |
| `--fps 30\|60` | 60 | Frame rate. 30 = smaller file, 60 = smoother |
| `--bg COLOR` | auto | Background color: `auto` / `white` / `black` / `#RRGGBB` |
| `--no-audio` | off | Skip audio synthesis, output video only |

**Examples:**

```bash
# Auto size (preserves image aspect ratio)
uv run --with numpy --with Pillow python3 <skill-path>/scripts/particle_logo.py logo.png output.mp4

# Force specific size
uv run --with numpy --with Pillow python3 <skill-path>/scripts/particle_logo.py logo.png output.mp4 --size 1920x1080

# Custom duration and particles
uv run --with numpy --with Pillow python3 <skill-path>/scripts/particle_logo.py logo.png output.mp4 --duration 10 --particles 20000

# Fast preview (fewer particles, lower fps, no audio)
uv run --with numpy --with Pillow python3 <skill-path>/scripts/particle_logo.py logo.png output.mp4 --particles 3000 --fps 30 --no-audio

# Black background, portrait video
uv run --with numpy --with Pillow python3 <skill-path>/scripts/particle_logo.py logo.png output.mp4 --bg black --size 1080x1920
```

### Step 3: Verify output

Check that:
1. The output file exists and is > 1 MB (a near-zero file means all-black video)
2. The script printed a sensible `Auto BG color` and a non-zero `targets` count

If targets is 0 or the file is too small, see Troubleshooting below.

## Auto-Detection Behavior

| Image type | Background | Foreground mask |
|------------|------------|-----------------|
| Light background (white/gray) | Sampled from 4 corners | Otsu threshold on color distance |
| Dark background | Sampled from 4 corners | Otsu threshold on color distance |
| Transparent PNG (RGBA) | Forced to white | Alpha channel directly |

**Size auto-detection** (when `--size` is not given):
- Longest side ≤ 1920, shortest side ≤ 1080, original aspect ratio preserved
- 1:1 image → ~1080×1080, 16:9 → 1920×1080, 4:3 → 1440×1080

## Output Specs

| Property | Value |
|----------|-------|
| Duration | 6 seconds (configurable 3-30s via --duration) |
| FPS | 60 (or 30 via --fps) |
| Codec | H.264, CRF 18 |
| Audio | AAC 192k, synthesized build-up music (disable via --no-audio) |
| Particles | 10,000 (configurable 1k-50k via --particles) |
| Convergence | ~58% duration particle build → ding → logo reveal |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| File ~0.2 MB, all black | Particle color == background (e.g., black icon on transparent → black bg) | Should be auto-fixed; if not, check that the image has an alpha channel |
| `targets: 0` error | No foreground pixels detected | Image may have very low contrast; not currently supported |
| `ffmpeg: command not found` | FFmpeg not installed | `brew install ffmpeg` |
| Very slow (>5 min) | Too many target pixels (>500k) | Use a simpler/smaller logo |
