# danny-skills

Document processing skills for Claude Code.

## Skills

### remove-watermark

Remove light-colored text watermarks from white-background document images (exam papers, scanned documents). Pure local processing with Pillow + NumPy, no API key needed.

**Features:**
- 4-step workflow: Visual Analysis → Brightness Analysis → Remove → Verify
- Region mode for precise watermark targeting (zero damage to surrounding text)
- Full-image mode with text-aware two-pass processing
- Batch processing support

### image-to-pdf

Combine multiple image screenshots into a paginated A4 PDF with intelligent page breaks.

**Features:**
- Auto-trims whitespace borders
- Scales images to A4 printable width
- Smart page breaks at whitespace rows (never cuts through text)
- Multiple sort modes (natural, creation time, name)
- 300 DPI output ready for printing

## Installation

### Via npx skills

```bash
npx skills add wxttt/danny-skills
```

### Via Claude Code Marketplace

```
/plugin marketplace add wxttt/danny-skills
/plugin install document-skills@danny-skills
```

### Manual

Clone and copy the skill folders to `~/.claude/skills/`:

```bash
cp -r skills/remove-watermark ~/.claude/skills/
cp -r skills/image-to-pdf ~/.claude/skills/
```

## Dependencies

Both skills use `uv run` for automatic dependency management. Required Python packages:

- **remove-watermark**: `Pillow`, `numpy` (+ `scipy` for full-image mode)
- **image-to-pdf**: `Pillow`, `numpy`

No manual install needed — `uv run --with ...` handles it automatically.

## Usage Examples

```
# Natural language - Claude auto-triggers the right skill
帮我去掉 ./source 目录下图片的水印
把 ./images 里的截图拼成一个 PDF
Remove the watermark from this image and combine all pages into a printable PDF
```

## License

MIT
