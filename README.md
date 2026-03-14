# danny-skills

Document processing and creative animation skills for Claude Code.

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

### particle-logo

Generate a particle convergence animation video from any logo or image. 10,000 particles scatter and converge into the logo shape with synthesized music.

**Features:**
- 1080p 60fps H.264 video output (6 seconds)
- Auto-detects background color (transparent PNG, light/dark backgrounds)
- Synthesized build-up music with "ding" reveal
- Customizable video size (landscape, portrait, square)
- Requires FFmpeg

## Installation

### Via npx skills

```bash
# Install all skills
npx skills add wxttt/danny-skills -y

# Install a single skill
npx skills add wxttt/danny-skills --skill remove-watermark
npx skills add wxttt/danny-skills --skill image-to-pdf
npx skills add wxttt/danny-skills --skill particle-logo

# Interactive mode (select which skills to install)
npx skills add wxttt/danny-skills
```

### Via Claude Code Marketplace

```
/plugin marketplace add wxttt/danny-skills
/plugin install document-skills@danny-skills
/plugin install creative-skills@danny-skills
```

### Manual

Clone and copy the skill folders to `~/.claude/skills/`:

```bash
cp -r skills/remove-watermark ~/.claude/skills/
cp -r skills/image-to-pdf ~/.claude/skills/
cp -r skills/particle-logo ~/.claude/skills/
```

## Dependencies

All skills use `uv run` for automatic dependency management. Required Python packages:

- **remove-watermark**: `Pillow`, `numpy` (+ `scipy` for full-image mode)
- **image-to-pdf**: `Pillow`, `numpy`
- **particle-logo**: `Pillow`, `numpy` (+ system `ffmpeg`)

No manual install needed — `uv run --with ...` handles it automatically.

## Usage Examples

```
# Natural language - Claude auto-triggers the right skill
帮我去掉 ./source 目录下图片的水印
把 ./images 里的截图拼成一个 PDF
用这个 logo 生成一个粒子汇聚动画视频
Create a particle animation from my logo
```

## License

MIT
