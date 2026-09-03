---
name: video-note-generator
description: Extract structured notes from video URLs, primarily Bilibili, and output them as a single OKF document with embedded screenshots by default. Also supports an OKF v0.2 note bundle or a single PDF study handout. Probes online subtitles first, falls back to Whisper ASR and visual slide detection, then summarizes content into sections.
compatibility: Python 3.12+, macOS recommended, requires `playwright install chromium` and Whisper model download on first run
metadata:
  version: "0.6.0"
---

# video-note-generator

Generate structured notes from a video URL. By default this produces a **single OKF document with embedded screenshots**. You can also choose an **OKF v0.2 note bundle** or a **single PDF study handout**.

## Steps

1. Run the main script from the skill directory:

   ```bash
   python3.12 ${KIMI_SKILL_DIR}/scripts/video_note_generator.py <url> [output.json]
   ```

   By default this produces a single OKF document. Add `--output-format pdf` for a PDF, or `--output-format okf` for an OKF note bundle.

2. Wait for it to finish. It outputs files next to `<title>` (the video's display title):
   - `<title>.json` — raw slide/time/content notes
   - `<title>_summary.json` — structured section summaries
   - `<title>_llm_prompt.md` — a prompt you can feed to an LLM for a better summary
   - For `--output-format okf-doc` (default): `<title>_okf.md` + `<title>_okf_assets/` — single OKF markdown document with embedded screenshots
   - For `--output-format okf`: `<title>_notes/` — OKF v0.2 note bundle
   - For `--output-format pdf`: `<title>_study_notes.pdf` — the final study handout with screenshots

   If you provide an explicit `output` argument, all files use that base name instead.

3. Report the result to the user: video title, number of raw slides, number of summary sections, and the chosen output path (OKF doc path, OKF bundle dir, or PDF path).

## Arguments

- `url` (positional, required): Video URL.
- `output` (positional, optional): Output JSON path. If omitted, files are named after the video's display title.
- `--output-format {okf,okf-doc,pdf}`: Final output format. Default `okf-doc`.
- `--reuse-existing`: Skip subtitle probing and ASR if `output.json` already exists; regenerate summary and final output only.
- `--notes-dir`: OKF bundle mode only — bundle output directory, default `<output>_notes`.
- `--granularity {video,section}`: OKF bundle mode only — topic note granularity. Default `video` (one topic note for the whole video); use `section` to create one topic note per summary section.
- `--frame-selector-method {visual,ocr}`: PDF / okf-doc mode only — frame selection strategy, default `visual`. Install `easyocr` to use `ocr`.
- `--whisper-model`: Whisper model size, default `base`.

## LLM-enhanced summary

If the user asks for a higher-quality summary:

1. Run the script normally to create `output.json` and `output_llm_prompt.md`.
2. Read `output_llm_prompt.md` and use your LLM capability to produce a valid JSON array in the format shown in that file.
3. Write the JSON array to `output_summary.json`.
4. Re-run the script with `--reuse-existing` (and the same `--output-format`) to regenerate the final output from the new summary.

## How it works

- **Phase 1 — subtitle probe**: Use Playwright to intercept native CC / uploader subtitle JSON from the video page.
- **Phase 2 — fallback**: If no subtitle is found, download the video with `yt-dlp`, then run Whisper ASR and pHash visual slide-change detection in parallel, and align the text to slide timestamps.
- **Phase 3 — handout**: Summarize the notes into sections, then output in the chosen format:
  - **OKF**: Create an OKF v0.2 note bundle using the `okf-note-taking` skill helper. By default the whole video becomes a single topic note under `topics/`; use `--granularity section` to create one topic note per summary section. The video source always becomes a reference note under `references/`, and indexes/log are regenerated.
  - **OKF-doc**: Create a single OKF markdown file with YAML frontmatter. Each section is a level-2 heading and includes the time range, an embedded screenshot, key points, summary, and transcript excerpt.
  - **PDF**: Compose a PDF where each page shows the section title, key points, summary, and a screenshot selected from the video.

## Output reuse

Downloaded videos are cached in `./downloads/` relative to the working directory. Re-running the same URL reuses the cached video. Use `--reuse-existing` to also reuse `output.json`.

## OKF bundle layout (okf mode)

By default the OKF bundle contains **one topic note for the whole video**. Use `--granularity section` to split the video into one topic note per summary section.

### Default (`--granularity video`)

```text
<output>_notes/
  index.md
  log.md
  topics/
    index.md
    <video-slug>.md     # single note for the whole video
  references/
    index.md
    video-source.md     # source video reference
  computations/
    index.md
```

The single topic note contains an overall summary, top key points, a `# Sections` breakdown with per-section summaries and key points, the full transcript, source attribution, and a link to the reference note.

### With `--granularity section`

```text
<output>_notes/
  index.md
  log.md
  topics/
    index.md
    <section-slug>.md   # one per summary section
  references/
    index.md
    video-source.md     # source video reference
  computations/
    index.md
```

Each topic note includes YAML frontmatter (`type`, `title`, `description`, `tags`, `generated`, `sources`) and sections for Summary, Key points, Transcript, Source, and Related notes.

## OKF document layout (okf-doc mode)

```text
<output>_okf.md
<output>_okf_assets/
  section_001_0012.jpg
  section_002_0045.jpg
  ...
```

The single markdown file has OKF frontmatter and a human-readable flow: overall summary, then each section as a heading with its screenshot, key points, summary, and transcript.
