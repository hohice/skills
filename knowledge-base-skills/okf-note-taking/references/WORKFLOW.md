# OKF Note-Taking Workflows

This reference describes each workflow in detail. The concise version lives in `SKILL.md`.

---

## 1. Initialize a bundle

### Steps

1. Choose a root directory, e.g. `my-learning-notes/`.
2. Create the skeleton:
   - Root `index.md` with `okf_version: "0.2"` frontmatter.
   - Root `log.md` with an initialization entry.
   - Subdirectories `topics/`, `references/`, `computations/` with their own `index.md`.
3. Create `.gitattributes` to route `assets/` through Git LFS (unless `--no-lfs`).
4. Report created paths and suggest creating the first concept.

### Input / output example

Input: "Initialize a note bundle called ml-notes."

Output files:

```text
ml-notes/
  .gitattributes
  index.md
  log.md
  topics/index.md
  references/index.md
  computations/index.md
```

### Boundary cases

- If the directory already exists, reuse it and only create missing files.
- If `.gitattributes` already exists, append missing LFS rules instead of overwriting.

---

## 2. Create a new note

### Steps

1. Identify the concept: infer title, topic, description, tags, sources.
   - Path conventions:
     - `topics/<slug>.md` for thematic notes.
     - `references/<slug>.md` for external-source mirrors.
     - `computations/<slug>.md` for reproducible calculations.
   - Concept ID = file path without `.md`.
2. Check for duplicates by title, slug, or similar description.
3. Write the concept with frontmatter and body.
4. Insert bundle-relative links to related concepts.
5. Update the nearest `index.md`.
6. Append to the nearest `log.md`.
7. Report concept ID, path, links, and updated indexes/logs.

### Input / output example

Input: "Take a note on backpropagation."

Output: `topics/backpropagation.md`

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

### Boundary cases

- If the target path already exists, ask whether to update it instead of overwriting.
- If a related concept does not exist yet, create the link anyway (dangling link is allowed in OKF).

---

## 3. Link existing notes

### Steps

1. Read the source concept.
2. Confirm or create the target concept path.
3. Insert a bundle-relative link in `Related notes`, `Prerequisites`, or `See also`.
4. Update `log.md` only if the linking is part of a major reorganization.

### Boundary cases

- A link to a non-existent concept is valid; do not reject it.
- Avoid over-linking; each link should express a meaningful relationship.

---

## 4. Attach an image

### Steps

1. Confirm the concept file exists.
2. Copy the image to `assets/<concept-path-without-.md>/<filename>`.
3. Insert a relative-path markdown image reference in the body.
4. If `--record` is set, append the bundle-relative absolute path to the frontmatter `assets` field.
5. Suggest recording image provenance in `sources`.

### Input / output example

Input: "Attach gradient-flow.png to backpropagation.md and record it."

Body change:

```markdown
![Gradient flow](../assets/topics/backpropagation/gradient-flow.png)
```

Frontmatter change (with `--record`):

```yaml
assets:
  - /assets/topics/backpropagation/gradient-flow.png
```

### Boundary cases

- If the destination filename already exists, append a counter (`image-1.png`).
- External URL images should be downloaded into `assets/` when possible.

---

## 5. Regenerate indexes

### Steps

1. Find every directory containing at least one concept `.md`.
2. Ensure each has an `index.md`.
3. List concepts as `* [Title](filename.md) - description`.
4. List subdirectories as `* [Name](subdir/)`.

### Boundary cases

- Use `--regenerate` to overwrite existing `index.md` files; otherwise skip them.
- Root `index.md` is the only one that may contain `okf_version` frontmatter.

---

## 6. Check conformance

### Checks

1. Every non-reserved `.md` has parseable YAML frontmatter.
2. Every frontmatter has a non-empty `type`.
3. Timestamps are ISO 8601.
4. Footnote labels match `sources[].id` entries.
5. Local image references point to existing files.
6. Reserved filenames are not used as concept documents.

### Boundary cases

- All issues are reported as warnings, not fatal errors.
- External URL images are skipped.

---

## 7. Set up Git LFS

### Steps

1. Ensure `git lfs install` has been run.
2. Generate or update `.gitattributes` with LFS rules for `assets/`.
3. Advise committing `.gitattributes` before committing assets.

### Boundary cases

- Running `lfs-setup` multiple times is idempotent; duplicate rules are not added.
