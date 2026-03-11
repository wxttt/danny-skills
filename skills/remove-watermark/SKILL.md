---
name: remove-watermark
description: Remove light-colored text watermarks from white-background document images (exam papers, scanned documents). No API key needed - pure local image processing. Use when the user wants to remove watermarks, clean up document screenshots, or remove light text overlays from images.
---

# Remove Watermark

Remove watermarks from white-background document images. Pure local processing, no API key needed.

## When to Use

Trigger this skill when the user wants to:

- Remove watermarks from document images or screenshots
- Clean up exam paper screenshots for printing
- Remove light text overlays (e.g., "公众号·xxx", website names)

## Workflow: 4-Step Process

The script path is `scripts/remove_watermark.py` relative to this SKILL.md.
Use `uv run --with Pillow --with numpy` (add `--with scipy` only when using `--region full`).

### Step 1: Visual Analysis (Claude reads the image)

Use the Read tool to look at a sample image. Identify:

- **Is there a watermark?** If no, skip processing.
- **Where is it?** (bottom-right corner, center, scattered across the image)
- **What type?** (light gray text, dark logo/stamp, colored)
- **Does it overlap with content text?**

Estimate the watermark region as approximate percentages: y0%, y1%, x0%, x1%.

### Step 2: Brightness Analysis (script analyzes the region)

Run the `analyze` subcommand on the watermark region to determine the right threshold:

```bash
uv run --with Pillow --with numpy python3 <skill-path>/scripts/remove_watermark.py analyze <image> --region "y0,y1,x0,x1"
```

Example: `analyze sample.jpg --region "94,100,60,100"`

This prints brightness distribution and a **suggested threshold**.

### Step 3: Remove Watermark

Use the suggested threshold and region from Steps 1-2:

```bash
# Region mode (preferred - zero damage to text outside the region)
uv run --with Pillow --with numpy python3 <skill-path>/scripts/remove_watermark.py remove <input> -o <output> --region "y0,y1,x0,x1" --threshold <N>

# Full mode (when watermark is scattered everywhere - needs scipy)
uv run --with Pillow --with numpy --with scipy python3 <skill-path>/scripts/remove_watermark.py remove <input> -o <output> --threshold <N>
```

**Region presets:** `bottom-right`, `bottom-left`, `top-right`, `top-left`, `bottom`, `top`, `right`, `left`, `center`, `full`

**Custom region:** `--region "y0,y1,x0,x1"` as percentages (e.g., `"94,100,60,100"` = bottom 6%, right 40%)

### Step 4: Verify Result

Use the Read tool to check the output image:
- Is the watermark gone?
- Is the text content intact?
- If not satisfactory, adjust threshold or region and re-run.

## Command Reference

### analyze

```
remove_watermark.py analyze <image> [--region REGION]
```

Prints brightness distribution and suggested threshold for a region.

### remove

```
remove_watermark.py remove <input...> [-o OUTPUT] [--region REGION] [--threshold N] [--enhance]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--region` | `full` | Region to process (preset name or `y0,y1,x0,x1`) |
| `--threshold` | `180` | Brightness cutoff for watermark pixels |
| `--enhance` | off | Boost text contrast after removal |
| `--preview` | off | Print stats without saving |

## Tips

- **Region mode is always preferred** over full mode when watermark is localized. It leaves all text perfectly intact.
- For dark watermarks (logo, stamps), use a **low threshold** (80-120) with a **tight region**.
- For light gray text watermarks, use a **higher threshold** (160-200).
- **Same batch**: if all images in a folder have the same watermark position, analyze one image and apply the same settings to all.
- Combine with **image-to-pdf** skill: remove watermarks first, then combine into PDF.
