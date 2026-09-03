# Agent Skills Collection

This repository contains a collection of [Agent Skills](https://agentskills.io) — portable, version-controlled folders that give AI agents specialized capabilities.

## Skills

| Skill | Description |
|---|---|
| [skill-creator](base-skills/skill-creator) | Create, scaffold, and validate other Agent Skills. |

## Quick start

### Add a new skill

```bash
python scripts/add_skill.py my-new-skill
```

This creates a new skill directory with a standard layout and a `SKILL.md` template.

### Validate all skills

```bash
python scripts/validate_all.py
```

This runs `skills-ref validate` against every top-level skill directory.

### Generate `<available_skills>` prompt block

```bash
python scripts/to_prompt.py
```

This generates the `<available_skills>` XML block recommended for Anthropic models, listing every skill in the repository.

## Repository structure

```
.
├── README.md
├── scripts/
│   ├── add_skill.py        # Scaffold a new skill
│   ├── validate_all.py     # Validate all skills
│   └── to_prompt.py        # Generate available_skills XML
├── .github/
│   └── workflows/
│       ├── validate-skills.yml   # CI validation
│       └── sync-upstream.yml     # Sync upstream spec for skill-creator
├── base-skills/            # Core skills
│   └── skill-creator/
│       ├── SKILL.md
│       ├── scripts/
│       ├── references/
│       └── assets/
└── knowledge-base-skills/  # Knowledge-base skills
```

## Keeping skill-creator up to date

The `skill-creator` skill includes reference documents synced from the upstream [agentskills/agentskills](https://github.com/agentskills/agentskills) repository.

To sync manually:

```bash
python base-skills/skill-creator/scripts/sync_upstream.py --skill-root base-skills/skill-creator
```

A GitHub Actions workflow also opens a pull request automatically every Monday when the upstream specification changes.

## License

Code in this repository is licensed under [Apache 2.0](LICENSE).
