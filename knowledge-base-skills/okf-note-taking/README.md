# OKF Note-Taking Skill

A reusable [Kimi Code skill](https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html) and CLI helper for producing, linking, and maintaining learning notes as an [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/open-knowledge-format) v0.2 bundle.

It treats every note as an OKF **concept** (a markdown file with YAML frontmatter) inside a directory-based **bundle**, and automates the housekeeping that keeps the bundle organized and trustable.

---

## Features

- **One concept = one `.md` file** with required YAML frontmatter (`type`, `title`, `description`, `tags`, `status`, `generated`).
- **Bundle scaffolding** via `init` with `topics/`, `references/`, `computations/` and their indexes.
- **Concept creation** via `new` that auto-updates the nearest `index.md` and `log.md`.
- **Linking** via `link` to insert bundle-relative links in `# Related notes`.
- **Image attachment** via `attach` that copies media into `assets/` and optionally records it in frontmatter.
- **Index regeneration** via `index` to keep directory listings up to date.
- **Conformance checks** via `check` for frontmatter, footnotes, local images, and reserved filenames.
- **Git LFS setup** via `lfs-setup` to keep binary assets out of git history.

---

## Directory layout

```text
okf-note-taking/
  SKILL.md              # Skill entry point (YAML frontmatter + agent instructions)
  README.md             # This file
  README_CN.md          # Chinese version of this README
  pyproject.toml        # Python package metadata
  scripts/
    okf_notes.py        # CLI helper (init, new, link, attach, index, check, log, lfs-setup)
  references/
    WORKFLOW.md         # Detailed step-by-step workflows
    COMMANDS.md         # CLI command reference
    LFS.md              # Git LFS setup guide
    TEMPLATES.md        # Template usage guide
  assets/
    concept-template.md # OKF concept template
    index-template.md   # Directory index template
    log-template.md     # Update log template
```

A generated OKF bundle looks like:

```text
my-notes/
  .gitattributes        # Git LFS rules (optional)
  index.md              # Root listing; may declare okf_version: "0.2"
  log.md                # Update history
  topics/               # Thematic notes
    index.md
    backpropagation.md
  references/           # External-source mirrors
    index.md
  computations/         # Reproducible calculations
    index.md
  assets/               # Attached media
    topics/
      backpropagation/
        gradient-flow.png
```

---

## Module overview

| File / Directory | Purpose |
|------------------|---------|
| `SKILL.md` | Skill entry point. Contains trigger signals, core principles, standard layout, workflows, media conventions, and instructions for the agent. |
| `pyproject.toml` | Python packaging metadata. Declares dependencies and registers the `okf-notes` console script. |
| `scripts/okf_notes.py` | Core CLI helper. Implements all commands and utility functions for frontmatter handling, index updates, log entries, and Git LFS attributes. |
| `references/WORKFLOW.md` | Detailed workflows for initializing bundles, creating notes, linking, attaching images, regenerating indexes, checking conformance, and setting up Git LFS. |
| `references/COMMANDS.md` | Quick reference for every CLI subcommand and its options. |
| `references/LFS.md` | Guide for routing `assets/` through Git LFS, including generated `.gitattributes` content. |
| `references/TEMPLATES.md` | Documentation of frontmatter fields and how to use the bundled templates. |
| `assets/concept-template.md` | Template for a single OKF concept note. |
| `assets/index-template.md` | Template for a directory index page. |
| `assets/log-template.md` | Template for the update log page. |

---

## Installation

### As a Kimi Code skill

Copy or symlink this directory into your Kimi Code skills directory:

```bash
cp -r okf-note-taking ~/.kimi-code/skills/
```

Then invoke it:

```text
/skill:okf-note-taking create backpropagation
```

### As a Python CLI tool

```bash
cd okf-note-taking
pip install -e .
```

This installs the `okf-notes` command:

```bash
okf-notes --help
```

---

## Quick start

```bash
# 1. Initialize a new note bundle
okf-notes init my-learning-notes --name "My Learning Notes"
cd my-learning-notes

# 2. Create a concept note
okf-notes new topics/backpropagation.md \
    --title "Backpropagation" \
    --description "How gradients flow backward" \
    --tags ml neural-networks

# 3. Attach an image
okf-notes attach topics/backpropagation.md \
    --file ~/Downloads/gradient-flow.png \
    --caption "Gradient flow through a network" \
    --record

# 4. Link to another note
okf-notes link topics/backpropagation.md --to topics/neural-networks.md

# 5. Regenerate indexes and check
okf-notes index --regenerate
okf-notes check
```

---

## Documentation

- `SKILL.md` — core instructions for the agent.
- `references/WORKFLOW.md` — detailed workflows with input/output examples and boundary cases.
- `references/COMMANDS.md` — CLI command reference.
- `references/LFS.md` — Git LFS setup guide.
- `references/TEMPLATES.md` — template usage guide.
- `assets/` — ready-to-copy templates.

---

## Dependencies

- Python >= 3.11
- PyYAML >= 6.0

The core commands `init`, `new`, `log`, and `attach` only require the Python standard library when invoked directly via `python scripts/okf_notes.py`. Commands `link`, `index`, and `check` require PyYAML.

---

## License

Apache-2.0
