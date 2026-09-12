---
name: video-note-generator
description: Extract structured notes from video URLs, primarily Bilibili, and output them as a single OKF document with embedded screenshots by default. Also supports an OKF v0.2 note bundle or a single PDF study handout. Probes online subtitles first, falls back to Whisper ASR and visual slide detection, then summarizes content into sections.
compatibility: Python 3.12+, macOS recommended, requires `playwright install chromium` and Whisper model download on first run
metadata:
  version: "0.8.0"
---

# video-note-generator

Generate structured notes from a video URL. By default this produces a **single OKF document with embedded screenshots**. You can also choose an **OKF v0.2 note bundle** or a **single PDF study handout**.

## Steps

0. One-time setup (skip if already done):

   ```bash
   python3.12 -m venv .venv && source .venv/bin/activate
   pip install -r ${KIMI_SKILL_DIR}/requirements.txt
   playwright install chromium   # required for the subtitle probe
   ```

   The Whisper model downloads automatically on first ASR use.

1. Run the main script from the skill directory:

   ```bash
   python3.12 ${KIMI_SKILL_DIR}/scripts/video_note_generator.py <url> [output]
   ```

   By default this produces a single OKF document. Add `--output-format pdf` for a PDF, or `--output-format okf` for an OKF note bundle.

2. Wait for it to finish — this can take a while (see "Runtime expectations" below). Intermediate artifacts go into a per-video topic directory `<temp-dir>/<title>/` (default `./tmp/<title>/`, where `<title>` is the video's display title):
   - `notes.json` — raw slide/time/content notes
   - `notes_summary.json` — structured section summaries
   - `notes_llm_prompt.md` — a prompt you can feed to an LLM for a better summary
   - `downloads/` — this video's yt-dlp download cache
   - `screenshots/` — pool of extracted video frames

   `downloads/` and `screenshots/` live inside the topic directory and are reused across runs of the same video.

   Final outputs still land in the working directory, named after `<title>`:
   - For `--output-format okf-doc` (default): `<title>_okf.md` + `<title>_okf_assets/` — single OKF markdown document with embedded screenshots
   - For `--output-format okf`: `<title>_notes/` — OKF v0.2 note bundle
   - For `--output-format pdf`: `<title>_study_notes.pdf` — the final study handout with screenshots

   If you provide an explicit `output` argument, the topic directory and all final outputs use that base name instead.

3. Report the result to the user: video title, number of raw slides, number of summary sections, and the chosen output path (OKF doc path, OKF bundle dir, or PDF path).

## Runtime expectations

- The script prints `[*]` progress lines (in Chinese) as it works. Do not interrupt it; ASR on a long video can take tens of minutes even after the download finishes.
- Phase 1 (subtitle probe) takes ~10–30 s. Phase 2 (download + Whisper ASR + visual slide detection) dominates the runtime and scales with video length.
- `./tmp/browser_data/` (Playwright browser session data, shared across videos) and a per-video topic directory `./tmp/<title>/` (intermediate JSON plus `downloads/` and `screenshots/`) are created under the working directory and reused across runs.

## Gotchas

- Screenshots require the video file. If Phase 1 grabs online subtitles, the video is never downloaded, so okf-doc/PDF outputs are text-only unless you re-run without subtitles (or delete the topic directory, default `./tmp/<title>/`, or its `notes.json`) so the ASR fallback downloads the video.
- Visual slide-change detection is tuned for slide/lecture-style videos; talking-head or vlog-style footage produces noisy section boundaries.
- Some sites detect headless browsers and return 412. If the subtitle probe and download both fail, retry with `--no-headless` (a browser window will open).
- OKF bundle mode (`--output-format okf`) requires the sibling `okf-note-taking` skill; the other formats do not. Re-running overwrites notes with the same slug instead of creating `-1` duplicates.
- The rule summarizer applies no built-in typo corrections by default (a global table can corrupt other videos' transcripts). Pass per-video fixes with `--corrections corrections.json` (see `references/asr-corrections.example.json`).

## Arguments

- `url` (positional, required): Video URL.
- `output` (positional, optional): Base name for the final output files and the temp topic directory. If omitted, the video's display title (as a safe filename slug) is used.
- `--output-format {okf,okf-doc,pdf}`: Final output format. Default `okf-doc`.
- `--temp-dir`: Root directory for all intermediate artifacts, relative to the working directory; each video gets its own topic subdirectory (`<temp-dir>/<base>/`). Default `./tmp`.
- `--reuse-existing`: Skip subtitle probing and ASR if the topic directory's `notes.json` already exists; regenerate summary and final output only.
- `--notes-dir`: OKF bundle mode only — bundle output directory, default `<output>_notes`.
- `--granularity {video,section}`: OKF bundle mode only — topic note granularity. Default `video` (one topic note for the whole video); use `section` to create one topic note per summary section.
- `--frame-selector-method {visual,ocr}`: PDF / okf-doc mode only — frame selection strategy, default `visual`. Install `easyocr` to use `ocr`.
- `--whisper-model`: Whisper model size, default `base`.
- `--corrections`: path to a JSON `{"typo": "fix"}` table applied to the ASR transcript before summarizing. Default: none. See `references/asr-corrections.example.json`.
- `--no-headless`: run the browser visibly; helps when sites block headless browsers (412 errors).

## LLM-enhanced summary

If the user asks for a higher-quality summary:

1. Run the script normally to create `<temp-dir>/<title>/notes.json` and `<temp-dir>/<title>/notes_llm_prompt.md` (default `./tmp/<title>/`).
2. Read `notes_llm_prompt.md` and use your LLM capability to produce a valid JSON array in the format shown in that file.
3. Write the JSON array to `notes_summary.json` in the same topic directory.
4. Re-run the script with `--reuse-existing` (and the same `--output-format`) to regenerate the final output from the new summary.

## How it works

- **Phase 1 — subtitle probe**: Use Playwright to intercept native CC / uploader subtitle JSON from the video page.
- **Phase 2 — fallback**: If no subtitle is found, download the video with `yt-dlp`, then run Whisper ASR and pHash visual slide-change detection in parallel, and align the text to slide timestamps.
- **Phase 3 — handout**: Summarize the notes into sections, then output in the chosen format:
  - **OKF**: Create an OKF v0.2 note bundle using the `okf-note-taking` skill helper. By default the whole video becomes a single topic note under `topics/`; use `--granularity section` to create one topic note per summary section. The video source always becomes a reference note under `references/`, and indexes/log are regenerated.
  - **OKF-doc**: Create a single OKF markdown file with YAML frontmatter. Each section is a level-2 heading and includes the time range, an embedded screenshot, key points, summary, and transcript excerpt.
  - **PDF**: Compose a PDF where each page shows the section title, key points, summary, and a screenshot selected from the video.

## Output reuse

Downloaded videos are cached per topic in `<temp-dir>/<base>/downloads/` relative to the working directory. Re-running the same URL reuses the cached video. Use `--reuse-existing` to also reuse `notes.json` in the topic directory.

In OKF bundle mode, re-running overwrites topic notes with the same slug in place (idempotent); it no longer creates `<slug>-1` duplicates.

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
