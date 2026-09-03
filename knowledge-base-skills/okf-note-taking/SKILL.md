---
name: okf-note-taking
description: Use this skill when the user wants to take learning notes, create or organize an OKF v0.2 knowledge bundle, link concepts, attach images, generate indexes, or check note conformance.
license: Apache-2.0
compatibility: Python >= 3.11 with PyYAML >= 6.0. Core commands also run with the standard library alone.
metadata:
  okf_version: "0.2"
  author: kimi-code-cli
---

# OKF Note-Taking

Help the user produce and maintain learning notes as an **Open Knowledge Format (OKF) v0.2** bundle: plain markdown files with YAML frontmatter, organized in a directory tree, linked by standard markdown links.

If invoked via slash command, e.g. `/skill:okf-note-taking create backpropagation`, treat `$action` as the intent and `$target` as the concept identifier.

Use the bundled CLI helper at `${KIMI_SKILL_DIR}/scripts/okf_notes.py` for file-system operations (creating files, copying images, regenerating indexes). For pure content generation, produce markdown directly.

---

## 1. Trigger signals

Use this skill when the user says things like:

- “Take a note about X.”
- “Create an OKF bundle / initialize my notes.”
- “Attach this image to my note.”
- “Link these two notes.”
- “Regenerate the index.”
- “Check my notes for format issues.”
- “Set up Git LFS.”

---

## 2. Core principles

1. **One note = one concept = one `.md` file.**
2. **Frontmatter is required and must contain `type`.** Also recommend `title`, `description`, `tags`, and `generated`.
3. **Links express relationships.** Prefer bundle-relative absolute paths `[text](/path/to/note.md)`.
4. **Indexes and logs are first-class.** Update `index.md` and `log.md` when creating or moving concepts.
5. **Images live inside the bundle under `assets/`.** Keep binaries portable; large files go through Git LFS.
6. **Be permissive.** Do not reject notes for missing optional fields, unknown types, broken links, or extra keys.
7. **Record provenance.** Write `generated` for every new note; add `sources` for external material and `verified` for human review.

---

## 3. Standard bundle layout

```text
notes/                          # bundle root
  .gitattributes                # optional LFS rules for assets/
  index.md                      # root listing; may declare okf_version: "0.2"
  log.md                        # update history
  topics/                       # thematic notes
    index.md
    backpropagation.md
  references/                   # external-source mirrors
    index.md
  computations/                 # reproducible calculations
    index.md
  assets/                       # attached media
    topics/
      backpropagation/
        gradient-flow.png
```

Reserved filenames (OKF §3.1): `index.md` and `log.md` must not be used as concept documents.

---

## 4. Quick start

```bash
# Initialize a bundle
python ${KIMI_SKILL_DIR}/scripts/okf_notes.py init my-notes --name "My Notes"
cd my-notes

# Create a note
python ${KIMI_SKILL_DIR}/scripts/okf_notes.py new topics/backpropagation.md \
    --title "Backpropagation" \
    --description "How gradients flow backward" \
    --tags ml neural-networks

# Attach an image
python ${KIMI_SKILL_DIR}/scripts/okf_notes.py attach topics/backpropagation.md \
    --file ~/Downloads/gradient-flow.png \
    --caption "Gradient flow" \
    --record

# Link notes
python ${KIMI_SKILL_DIR}/scripts/okf_notes.py link topics/backpropagation.md \
    --to topics/neural-networks.md

# Regenerate indexes and check
python ${KIMI_SKILL_DIR}/scripts/okf_notes.py index --regenerate
python ${KIMI_SKILL_DIR}/scripts/okf_notes.py check
```

---

## 5. Workflows

Each workflow is detailed in `references/WORKFLOW.md`. Summaries below:

### 5.1 Initialize a bundle

1. Choose a root directory.
2. Create root `index.md` with optional `okf_version: "0.2"`, root `log.md`, and subdirectories `topics/`, `references/`, `computations/` with their own `index.md`.
3. Create `.gitattributes` for Git LFS unless `--no-lfs`.
4. Report created paths.

### 5.2 Create a note

1. Identify title, topic, description, tags, sources.
2. Choose path: `topics/<slug>.md`, `references/<slug>.md`, or `computations/<slug>.md`.
3. Check for duplicates.
4. Write frontmatter and body with links.
5. Update `index.md` and `log.md`.

### 5.3 Link notes

Insert a bundle-relative link in `Related notes`, `Prerequisites`, or `See also`. Dangling links are allowed.

### 5.4 Attach an image

1. Copy image to `assets/<concept-path-without-.md>/<filename>`.
2. Insert relative markdown image reference in body.
3. With `--record`, append bundle-relative path `/assets/...` to frontmatter `assets`.

### 5.5 Regenerate indexes

Scan directories with concepts and generate `index.md` entries.

### 5.6 Check conformance

Report warnings for missing frontmatter, missing `type`, bad timestamps, unmatched footnotes, missing local images, or misuse of reserved filenames.

### 5.7 Set up Git LFS

Generate `.gitattributes` routing `assets/` media through Git LFS. See `references/LFS.md` for full steps.

---

## 6. Images and media

- Store images in `assets/<concept-relative-path-without-.md>/`.
- Use lowercase hyphenated filenames.
- Prefer `png`, `jpg`, `svg`, `webp`.
- Body references use relative paths; frontmatter `assets` uses bundle-relative absolute paths `/assets/...`.
- Record image provenance in `sources`.
- Always include alt text; add a text description below complex diagrams.

---

## 7. Templates

- Concept template: `assets/concept-template.md`
- Index template: `assets/index-template.md`
- Log template: `assets/log-template.md`
- Detailed template guide: `references/TEMPLATES.md`

---

## 8. Example interaction

**User:** Take a note on backpropagation.

**Agent:**
> I will create `topics/backpropagation.md` as an OKF concept and update the index and log.

```markdown
---
type: Note
title: Backpropagation
description: How gradients flow backward through a neural network.
tags: [ml, neural-networks, optimization]
status: draft
generated: { by: kimi-code-cli, at: 2026-08-26T14:00:00Z }
---

# Summary

Backpropagation computes gradients by applying the chain rule in reverse.

# Related notes

- [Neural Networks](/topics/neural-networks.md)
```

> Updated `topics/index.md` and `log.md`.

---

## 9. Companion CLI tool

The helper `scripts/okf_notes.py` provides: `init`, `lfs-setup`, `new`, `link`, `attach`, `index`, `check`, `log`.

For command details see `references/COMMANDS.md`.
