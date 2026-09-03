# Video Note Generator Skill

A reusable [Kimi Code skill](https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html) and CLI helper that extracts structured study notes from a video URL (primarily Bilibili) and outputs them as:

1. A **single OKF document with embedded screenshots** (default).
2. An **OKF v0.2 note bundle**.
3. A **single PDF study handout**.

It uses a dual-track pipeline: first it tries a lightweight online subtitle probe; if that fails, it falls back to downloading the video and running Whisper ASR plus pHash visual slide-change detection in parallel. The extracted text is then summarized into sections and rendered in the chosen output format.

---

## Features

- **Dual-track extraction**: Playwright subtitle interception first, then `yt-dlp` + Whisper ASR + pHash slide detection as fallback.
- **Browser cookie auto-retry**: when Bilibili or other sites return 412, the tool tries Safari, Chrome, Edge, and Firefox cookies automatically.
- **Three output formats**:
  - `okf-doc` — single markdown file with OKF frontmatter, sections, screenshots, key points, summaries, and transcript excerpts.
  - `okf` — standard OKF v0.2 bundle with `topics/`, `references/`, and regenerated indexes/logs. By default the whole video becomes one topic note; use `--granularity section` to create one topic note per summary section.
  - `pdf` — printable study handout with one section per page and a smartly selected screenshot.
- **Configurable OKF granularity**: choose between a single topic note for the whole video (`video`, default) or one topic note per summary section (`section`).
- **Smart frame selection**: choose the best screenshot per section by visual change / brightness variance (`visual`) or by OCR text density (`ocr`).
- **LLM-enhanced summary workflow**: generate a prompt file, let an LLM produce better section summaries, then reuse existing intermediate results.
- **Caching**: downloaded videos are reused from `./downloads/`; intermediate JSON can be reused with `--reuse-existing`.

---

## Directory layout

```text
video-note-generator/
  SKILL.md                         # Skill entry point
  README.md                        # This file
  README_CN.md                     # Chinese version of this README
  requirements.txt                 # Python dependencies
  scripts/
    video_note_generator.py        # Main CLI and VideoNoteGenerator class
    frame_selector.py              # Smart screenshot selection strategies
    summarizers.py                 # Rule-based summarizer + LLM prompt builder
```

---

## Module overview

### `scripts/video_note_generator.py`

The main script. It defines `VideoNoteGenerator`, which orchestrates the full pipeline:

| Phase / Method | Purpose |
|----------------|---------|
| `_get_video_title` | Resolve the video title via `yt-dlp`, retrying with browser cookies if needed. |
| `_check_subtitle` / `_format_subtitle_notes` | Probe the video page with Playwright and intercept native/uploader subtitle JSON. |
| `_download_video` | Download the video with `yt-dlp`, reusing cached files and falling back to local cache on failure. |
| `_transcribe_audio` | Run OpenAI Whisper on the downloaded video. |
| `_detect_slide_changes` | Detect PPT/Keynote slide changes with perceptual hashing (pHash). |
| `_align_notes` | Align ASR segments to slide timestamps to produce structured notes. |
| `_summarize_notes` | Summarize raw notes into sections using the configured summarizer. |
| `_generate_okf_notes` | Produce an OKF v0.2 bundle by calling the `okf-note-taking` skill helper. Respects `--granularity` to emit either one topic note for the whole video or one topic note per section. |
| `_generate_okf_doc` | Produce a single OKF markdown document with embedded screenshots. |
| `_generate_study_pdf` | Produce a single PDF study handout using `fpdf2`. |
| `generate` | Unified entry point that runs all phases and returns output paths. |

### `scripts/frame_selector.py`

Responsible for picking the most informative screenshot for each section.

| Component | Purpose |
|-----------|---------|
| `BaseFrameSelector` | Abstract interface for frame selection. |
| `VisualChangeSelector` | Default strategy. Scores frames by pHash visual change and brightness variance; good for slides and tutorials. |
| `OCRFrameSelector` | Optional strategy. Scores frames by detected text count using EasyOCR; good for code demos and text-heavy slides. |
| `create_frame_selector` | Factory that creates the requested selector (`visual` or `ocr`). |

### `scripts/summarizers.py`

Transforms spoken ASR text into structured knowledge points.

| Component | Purpose |
|-----------|---------|
| `BaseSummarizer` | Abstract interface for summarizers. |
| `RuleBasedSummarizer` | Default rule-based summarizer that groups adjacent utterances, filters filler phrases, extracts section titles, and picks up to 3 key points per section. |
| `clean_asr_text` | Cleans common Chinese ASR mistakes using a built-in correction table. |
| `build_llm_summary_prompt` | Builds a prompt file that an LLM can use to produce higher-quality `{output}_summary.json`. |
| `create_summarizer` | Factory that creates the requested summarizer (`rule`). |

---

## Installation

### As a Kimi Code skill

Copy or symlink this directory into your Kimi Code skills directory:

```bash
cp -r video-note-generator ~/.kimi-code/skills/
```

Then invoke it through Kimi Code.

### As a Python CLI tool

```bash
cd video-note-generator
pip install -r requirements.txt
playwright install chromium
```

On first run, Whisper will automatically download the requested model.

---

## Quick start

```bash
# Default: single OKF document with embedded screenshots
python3.12 scripts/video_note_generator.py "https://www.bilibili.com/video/BVxxxxxx"

# OKF v0.2 note bundle — one topic note for the whole video (default)
python3.12 scripts/video_note_generator.py "https://www.bilibili.com/video/BVxxxxxx" --output-format okf

# OKF v0.2 note bundle — one topic note per summary section
python3.12 scripts/video_note_generator.py "https://www.bilibili.com/video/BVxxxxxx" --output-format okf --granularity section

# PDF study handout
python3.12 scripts/video_note_generator.py "https://www.bilibili.com/video/BVxxxxxx" --output-format pdf

# Reuse existing notes.json and regenerate outputs
python3.12 scripts/video_note_generator.py "https://www.bilibili.com/video/BVxxxxxx" --reuse-existing
```

---

## Output files

For a video titled `<title>` (or an explicit `output` base name):

| File / Directory | Description |
|------------------|-------------|
| `<title>.json` | Raw slide/time/content notes. |
| `<title>_summary.json` | Structured section summaries. |
| `<title>_llm_prompt.md` | Prompt you can feed to an LLM for a better summary. |
| `<title>_okf.md` + `<title>_okf_assets/` | Output for `--output-format okf-doc` (default). |
| `<title>_notes/` | Output for `--output-format okf`. Default layout has one topic note for the whole video; with `--granularity section` there is one topic note per summary section. |
| `<title>_study_notes.pdf` | Output for `--output-format pdf`. |

---

## LLM-enhanced summary workflow

1. Run the script normally to create `output.json` and `output_llm_prompt.md`.
2. Read `output_llm_prompt.md` and use your LLM to produce a valid JSON array in the format shown in that file.
3. Write the JSON array to `output_summary.json`.
4. Re-run the script with `--reuse-existing` (and the same `--output-format`) to regenerate the final output from the new summary.

---

## CLI arguments

| Argument | Description |
|----------|-------------|
| `url` | Video URL (required). |
| `output` | Output JSON path. Defaults to `<video-title>.json`. |
| `--output-format {okf,okf-doc,pdf}` | Final output format. Default `okf-doc`. |
| `--reuse-existing` | Skip subtitle probe and ASR if `output.json` exists; regenerate summary and final output only. |
| `--notes-dir` | OKF bundle mode only — custom bundle output directory. |
| `--granularity {video,section}` | OKF bundle mode only — topic note granularity. Default `video` (one topic note for the whole video); use `section` for one topic note per summary section. |
| `--frame-selector-method {visual,ocr}` | PDF / okf-doc mode only — frame selection strategy. Default `visual`. |
| `--whisper-model` | Whisper model size. Default `base`. |

---

## Dependencies

Required:

- Python >= 3.12 (macOS recommended)
- `openai-whisper`
- `imagehash`
- `Pillow`
- `moviepy`
- `yt-dlp`
- `playwright` (with Chromium installed)
- `PyYAML`
- `fpdf2`

Optional:

- `easyocr` — for `--frame-selector-method ocr`
- `openai` or another LLM client — for the LLM-enhanced summary workflow

---

## Relationship with `okf-note-taking`

When `--output-format okf` is selected, this skill reuses the `okf-note-taking` skill helper:

```text
../okf-note-taking/scripts/okf_notes.py
```

It calls `init`, `index --regenerate`, and `log` to create and maintain a standard OKF v0.2 bundle.

---

## License

Apache-2.0
