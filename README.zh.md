# danny-skills

文档处理和创意动画 Skills，适用于 Claude Code 及其他 AI Agent。

## 包含的 Skills

### remove-watermark（去水印）

从白底文档图片（试卷、扫描件）中移除浅色文字水印。纯本地处理，不需要 API Key。

**特性：**
- 4 步工作流：视觉分析 → 亮度分析 → 去除 → 验证
- 区域模式精准定位水印（不损伤周围文字）
- 全图模式带文字感知的两遍处理
- 支持批量处理

### image-to-pdf（图片合成 PDF）

将多张截图合并为分页 A4 PDF，智能分页不切断文字。

**特性：**
- 自动裁剪白边
- 缩放至 A4 可打印宽度
- 在空白行处智能分页（不会切断文字）
- 多种排序方式（自然排序、创建时间、文件名）
- 300 DPI 输出，可直接打印

### particle-logo（粒子汇聚动画）

从任意 logo 或图片生成粒子汇聚动画视频。10,000 个粒子从随机位置散开后汇聚成 logo 形状，配合合成音乐。

**特性：**
- 1080p 60fps H.264 视频输出（6 秒）
- 自动检测背景色（透明 PNG、深色/浅色背景）
- 合成渐进式音乐 + "叮咚" 揭示音效
- 可自定义视频尺寸（横版、竖版、正方形）
- 需要 FFmpeg

## 安装

### 通过 npx skills

```bash
# 安装所有 skill
npx skills add wxttt/danny-skills -y

# 只安装单个 skill
npx skills add wxttt/danny-skills --skill remove-watermark
npx skills add wxttt/danny-skills --skill image-to-pdf
npx skills add wxttt/danny-skills --skill particle-logo

# 交互模式（选择要安装的 skill）
npx skills add wxttt/danny-skills
```

### 通过 Claude Code 插件市场

```
/plugin marketplace add wxttt/danny-skills
/plugin install document-skills@danny-skills
/plugin install creative-skills@danny-skills
```

### 手动安装

克隆仓库后，将 skill 目录复制到 `~/.claude/skills/`：

```bash
cp -r skills/remove-watermark ~/.claude/skills/
cp -r skills/image-to-pdf ~/.claude/skills/
cp -r skills/particle-logo ~/.claude/skills/
```

## 依赖

所有 skill 使用 `uv run` 自动管理依赖，所需 Python 包：

- **remove-watermark**：`Pillow`、`numpy`（全图模式额外需要 `scipy`）
- **image-to-pdf**：`Pillow`、`numpy`
- **particle-logo**：`Pillow`、`numpy`（+ 系统安装 `ffmpeg`）

无需手动安装 — `uv run --with ...` 会自动处理。

## 使用示例

```
# 自然语言调用，Claude 自动触发对应 skill
帮我去掉 ./source 目录下图片的水印
把 ./images 里的截图拼成一个 PDF
用这个 logo 生成一个粒子汇聚动画视频
先去水印，再合成 PDF 存到 dest.pdf
```

## License

MIT
