---
name: skill-creator
description: Create, scaffold, and validate Agent Skills that follow the agentskills.io specification. Use when the user wants to create a new skill, check an existing skill for compliance, improve a skill description, or set up a skill directory with scripts, references, and assets.
---

# Skill Creator

This skill helps you create new Agent Skills, validate them against the agentskills.io specification, and improve their metadata and structure.

## When to use this skill

Activate this skill when the user asks for any of the following:

- "Create a new skill"
- "Scaffold a skill"
- "Validate this skill"
- "Check my SKILL.md"
- "Improve the description of my skill"
- "Why is my skill invalid?"
- "How should I structure a skill?"

## Workflow

### 1. Create a new skill

Run the scaffold script with the desired skill name and target directory:

```bash
python scripts/scaffold.py <skill-name> <target-directory>
```

Example from the repository root:

```bash
python base-skills/skill-creator/scripts/scaffold.py my-new-skill ./my-new-skill
```

If this skill lives in a skills collection repository, you can also use the root-level helper:

```bash
python scripts/add_skill.py my-new-skill
```

The script will:

- Validate the skill name format.
- Create the standard skill directory structure.
- Generate a `SKILL.md` template.
- Add an example directory tree in `assets/example_skill_tree.txt`.

After scaffolding, open the generated `SKILL.md` and fill in the `description` and body instructions.

### 2. Validate a skill

Run the validate script:

```bash
python scripts/validate.py <skill-directory>
```

This wraps `skills-ref validate` and reports any frontmatter or naming issues.

### 3. Check and improve the description

Run the description checker:

```bash
python scripts/check_description.py <skill-directory>
```

It checks length, specificity, and whether the description includes activation cues like "Use when".

## Skill directory structure

A standard skill looks like this:

```
my-skill/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
└── assets/           # Optional: templates, resources
```

Keep `SKILL.md` under 500 lines. Move detailed reference material to `references/` so agents can load it on demand.

## Writing a good SKILL.md

### Required frontmatter

```yaml
---
name: my-skill
description: What this skill does and when to use it.
---
```

- `name`: 1-64 characters, lowercase letters/digits/hyphens only, no leading/trailing/consecutive hyphens, must match the directory name.
- `description`: 1-1024 characters. Describe what the skill does **and** when to use it. Include specific keywords that help agents recognize relevant tasks.

### Good description example

```yaml
description: Extract text and tables from PDF files, fill PDF forms, and merge multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.
```

### Poor description example

```yaml
description: Helps with PDFs.
```

## Progressive disclosure

Agents load skills in three stages:

1. **Discovery**: Only `name` and `description` are loaded at startup.
2. **Activation**: The full `SKILL.md` body is loaded when a task matches the description.
3. **Execution**: Scripts, references, and assets are loaded only when needed.

Structure your skill to take advantage of this. Put the essential workflow in `SKILL.md` and detailed guides in `references/`.

## Keeping this skill up to date

The reference documents in `references/` are synced from the upstream agentskills/agentskills repository. To update them manually from the repository root:

```bash
python base-skills/skill-creator/scripts/sync_upstream.py --skill-root base-skills/skill-creator
```

A root-level GitHub Actions workflow (`.github/workflows/sync-upstream.yml`) also opens a pull request automatically when the upstream specification changes.

## References

- `references/specification.md` — Full Agent Skills format specification.
- `references/best-practices.md` — Recommendations for writing effective skills.
- `references/optimizing-descriptions.md` — How to write descriptions that agents use well.
