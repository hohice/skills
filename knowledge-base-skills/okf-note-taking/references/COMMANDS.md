# OKF Note-Taking CLI Reference

The CLI helper is implemented in `scripts/okf_notes.py`. After pip installation, use the `okf-notes` command; otherwise run `python scripts/okf_notes.py`.

---

## Installation

```bash
cd okf-note-taking
pip install -e .
```

---

## Commands

### `init`

Create an empty OKF bundle skeleton.

```bash
okf-notes init [directory] --name "My Notes"
okf-notes init [directory] --name "My Notes" --no-lfs
```

### `lfs-setup`

Create or update `.gitattributes` for Git LFS.

```bash
okf-notes lfs-setup [directory]
```

### `new`

Create a new concept note.

```bash
okf-notes new <path> --title "Title" --description "One-line summary" --tags tag1 tag2
```

### `link`

Add a bundle-relative link between notes.

```bash
okf-notes link <from> --to <target> [--text "Link text"]
```

### `attach`

Attach an image to a concept.

```bash
okf-notes attach <concept> --file <image> [--caption "Caption"] [--record]
```

### `index`

Generate or update `index.md` files.

```bash
okf-notes index [--regenerate]
```

### `check`

Check bundle conformance.

```bash
okf-notes check
```

### `log`

Append an entry to a `log.md`.

```bash
okf-notes log "Message" [--dir subdirectory] [--date YYYY-MM-DD]
```

---

## Dependencies

- Python >= 3.11
- PyYAML >= 6.0

Commands `init`, `new`, `log`, and `attach` (including `--record`) work with the standard library alone when invoked directly via `python scripts/okf_notes.py`. Commands `link`, `index`, and `check` require PyYAML.
