# Video Note Generator Skill

一个可复用的 [Kimi Code skill](https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html) 和 CLI 辅助工具，用于从视频 URL（主要是 Bilibili）提取结构化学习笔记，并输出为以下三种形式之一：

1. **带嵌入截图的单文件 OKF 文档**（默认）。
2. **OKF v0.2 笔记包**。
3. **单文件 PDF 学习讲义**。

它采用双轨流水线：首先尝试轻量级的在线字幕探测；如果失败，则回退到下载视频并并行运行 Whisper ASR 与 pHash 视觉翻页检测。提取的文本随后被总结成小节，并按所选格式输出。

---

## 功能特性

- **双轨提取**：先用 Playwright 拦截字幕，失败后使用 `yt-dlp` + Whisper ASR + pHash 翻页检测。
- **浏览器 Cookie 自动重试**：当 Bilibili 等站点返回 412 时，工具会自动尝试 Safari、Chrome、Edge 和 Firefox 的 Cookie。
- **三种输出格式**：
  - `okf-doc` — 单 markdown 文件，带 OKF frontmatter、小节、截图、要点、摘要和转写片段。
  - `okf` — 标准 OKF v0.2 笔记包，含 `topics/`、`references/`，并自动重建索引和日志。默认整视频生成一个主题文档；使用 `--granularity section` 可按每个摘要小节生成一个主题文档。
  - `pdf` — 可打印的学习讲义，每页一个小节并附带智能选图。
- **可配置的 OKF 粒度**：选择整视频一个主题文档（`video`，默认）或每个摘要小节一个主题文档（`section`）。
- **智能选图**：通过画面变化/亮度方差（`visual`）或 OCR 文字密度（`ocr`）为每个小节挑选最佳截图。
- **LLM 增强摘要工作流**：生成 prompt 文件，由 LLM 产出更优的小节摘要，再复用中间结果重新生成最终输出。
- **缓存机制**：已下载的视频从 `./downloads/` 复用；中间 JSON 可通过 `--reuse-existing` 复用。

---

## 目录结构

```text
video-note-generator/
  SKILL.md                         # Skill 入口
  README.md                        # 英文版说明
  README_CN.md                     # 中文版说明（本文件）
  requirements.txt                 # Python 依赖
  scripts/
    video_note_generator.py        # 主 CLI 与 VideoNoteGenerator 类
    frame_selector.py              # 智能截图选择策略
    summarizers.py                 # 基于规则的摘要器 + LLM prompt 生成器
```

---

## 模块说明

### `scripts/video_note_generator.py`

主脚本。它定义了 `VideoNoteGenerator` 类，负责编排完整流程：

| 阶段 / 方法 | 作用 |
|------------|------|
| `_get_video_title` | 通过 `yt-dlp` 获取视频标题，需要时自动使用浏览器 Cookie 重试。 |
| `_check_subtitle` / `_format_subtitle_notes` | 使用 Playwright 探测视频页并拦截原生/UP主字幕 JSON。 |
| `_download_video` | 使用 `yt-dlp` 下载视频，复用缓存文件，失败时回退到本地缓存。 |
| `_transcribe_audio` | 对下载的视频运行 OpenAI Whisper。 |
| `_detect_slide_changes` | 使用感知哈希（pHash）检测 PPT/Keynote 翻页节点。 |
| `_align_notes` | 将 ASR 片段按翻页时间对齐，生成结构化笔记。 |
| `_summarize_notes` | 使用配置的摘要器将原始笔记总结成小节。 |
| `_generate_okf_notes` | 调用 `okf-note-taking` skill helper 生成 OKF v0.2 笔记包。根据 `--granularity` 参数生成整视频一个主题文档，或每个小节一个主题文档。 |
| `_generate_okf_doc` | 生成带嵌入截图的单文件 OKF markdown 文档。 |
| `_generate_study_pdf` | 使用 `fpdf2` 生成单文件 PDF 学习讲义。 |
| `generate` | 统一入口，运行所有阶段并返回输出路径。 |

### `scripts/frame_selector.py`

负责为每个小节挑选最具信息量的截图。

| 组件 | 作用 |
|------|------|
| `BaseFrameSelector` | 帧选择器抽象接口。 |
| `VisualChangeSelector` | 默认策略。通过 pHash 画面变化和亮度方差评分；适合幻灯片和教程类视频。 |
| `OCRFrameSelector` | 可选策略。通过 EasyOCR 检测到的文字数量评分；适合代码演示和文字密集的幻灯片。 |
| `create_frame_selector` | 工厂函数，按名称创建选择器（`visual` 或 `ocr`）。 |

### `scripts/summarizers.py`

将口语化的 ASR 文本提炼成结构化知识点。

| 组件 | 作用 |
|------|------|
| `BaseSummarizer` | 摘要器抽象接口。 |
| `RuleBasedSummarizer` | 默认基于规则的摘要器。合并相邻语句、过滤口头禅、提取小节标题，并为每小节挑选最多 3 个要点。 |
| `clean_asr_text` | 使用内置修正表清理常见中文 ASR 口误。 |
| `build_llm_summary_prompt` | 构建 prompt 文件，供 LLM 生成更高质量的 `{output}_summary.json`。 |
| `create_summarizer` | 工厂函数，按名称创建摘要器（目前仅 `rule`）。 |

---

## 安装

### 作为 Kimi Code skill

复制或符号链接此目录到 Kimi Code skills 目录：

```bash
cp -r video-note-generator ~/.kimi-code/skills/
```

然后通过 Kimi Code 调用。

### 作为 Python CLI 工具

```bash
cd video-note-generator
pip install -r requirements.txt
playwright install chromium
```

首次运行时会自动下载所需的 Whisper 模型。

---

## 快速开始

```bash
# 默认：带嵌入截图的单文件 OKF 文档
python3.12 scripts/video_note_generator.py "https://www.bilibili.com/video/BVxxxxxx"

# OKF v0.2 笔记包 — 整视频一个主题文档（默认）
python3.12 scripts/video_note_generator.py "https://www.bilibili.com/video/BVxxxxxx" --output-format okf

# OKF v0.2 笔记包 — 每个摘要小节一个主题文档
python3.12 scripts/video_note_generator.py "https://www.bilibili.com/video/BVxxxxxx" --output-format okf --granularity section

# PDF 学习讲义
python3.12 scripts/video_note_generator.py "https://www.bilibili.com/video/BVxxxxxx" --output-format pdf

# 复用已有的 notes.json 并重新生成输出
python3.12 scripts/video_note_generator.py "https://www.bilibili.com/video/BVxxxxxx" --reuse-existing
```

---

## 输出文件

对于标题为 `<title>` 的视频（或显式指定的 `output` 基本名）：

| 文件 / 目录 | 说明 |
|------------|------|
| `<title>.json` | 原始 slide/时间/内容笔记。 |
| `<title>_summary.json` | 结构化小节摘要。 |
| `<title>_llm_prompt.md` | 可喂给 LLM 以生成更优摘要的 prompt。 |
| `<title>_okf.md` + `<title>_okf_assets/` | `--output-format okf-doc`（默认）的输出。 |
| `<title>_notes/` | `--output-format okf` 的输出。默认布局为整视频一个主题文档；使用 `--granularity section` 时为每个摘要小节一个主题文档。 |
| `<title>_study_notes.pdf` | `--output-format pdf` 的输出。 |

---

## LLM 增强摘要工作流

1. 正常运行脚本，生成 `output.json` 和 `output_llm_prompt.md`。
2. 读取 `output_llm_prompt.md`，使用你的 LLM 生成符合该文件所示格式的 JSON 数组。
3. 将 JSON 数组写入 `output_summary.json`。
4. 使用 `--reuse-existing`（和相同的 `--output-format`）重新运行脚本，以从新的摘要重新生成最终输出。

---

## CLI 参数

| 参数 | 说明 |
|------|------|
| `url` | 视频 URL（必需）。 |
| `output` | 输出 JSON 路径。默认为 `<video-title>.json`。 |
| `--output-format {okf,okf-doc,pdf}` | 最终输出格式。默认 `okf-doc`。 |
| `--reuse-existing` | 如果 `output.json` 已存在，跳过字幕探测和 ASR；仅重新生成摘要和最终输出。 |
| `--notes-dir` | 仅 OKF 笔记包模式 — 自定义 bundle 输出目录。 |
| `--granularity {video,section}` | 仅 OKF 笔记包模式 — 主题文档粒度。默认 `video`（整视频一个主题文档）；使用 `section` 可为每个摘要小节生成一个主题文档。 |
| `--frame-selector-method {visual,ocr}` | 仅 PDF / okf-doc 模式 — 选图策略。默认 `visual`。 |
| `--whisper-model` | Whisper 模型大小。默认 `base`。 |

---

## 依赖

必需：

- Python >= 3.12（推荐 macOS）
- `openai-whisper`
- `imagehash`
- `Pillow`
- `moviepy`
- `yt-dlp`
- `playwright`（需安装 Chromium）
- `PyYAML`
- `fpdf2`

可选：

- `easyocr` — 用于 `--frame-selector-method ocr`
- `openai` 或其他 LLM 客户端 — 用于 LLM 增强摘要工作流

---

## 与 `okf-note-taking` 的关系

当选择 `--output-format okf` 时，本 skill 会复用 `okf-note-taking` skill helper：

```text
../okf-note-taking/scripts/okf_notes.py
```

它会调用 `init`、`index --regenerate` 和 `log` 命令来创建并维护标准 OKF v0.2 笔记包。

---

## 许可证

Apache-2.0
