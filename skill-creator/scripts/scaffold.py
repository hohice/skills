#!/usr/bin/env python3
"""Scaffold a new Agent Skill directory."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

MAX_NAME_LENGTH = 64


def validate_skill_name(name: str) -> list[str]:
    """Validate a skill name against the Agent Skills spec."""
    errors: list[str] = []
    normalized = unicodedata.normalize("NFKC", name).strip()

    if not normalized:
        errors.append("Skill name cannot be empty.")
        return errors

    if len(normalized) > MAX_NAME_LENGTH:
        errors.append(
            f"Skill name '{normalized}' exceeds {MAX_NAME_LENGTH} characters."
        )

    if normalized != normalized.lower():
        errors.append(f"Skill name '{normalized}' must be lowercase.")

    if normalized.startswith("-") or normalized.endswith("-"):
        errors.append("Skill name cannot start or end with a hyphen.")

    if "--" in normalized:
        errors.append("Skill name cannot contain consecutive hyphens.")

    if not all(c.isalnum() or c == "-" for c in normalized):
        errors.append(
            "Skill name can only contain lowercase letters, digits, and hyphens."
        )

    return errors


def skill_template(name: str) -> str:
    """Return a minimal SKILL.md template."""
    return f"""---
name: {name}
description: Describe what this skill does and when to use it. Include specific keywords and a "Use when" clause.
---

# {name}

## When to use this skill

Activate this skill when the user asks for ...

## Workflow

### 1. Step one

Describe the first step.

### 2. Step two

Describe the second step.

## References

- `references/REFERENCE.md` — detailed reference material.
"""


def example_tree() -> str:
    """Return an example skill directory tree."""
    return """\
my-skill/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
└── assets/           # Optional: templates, resources
"""


def scaffold(skill_name: str, target_dir: Path) -> None:
    """Create a new skill directory with standard layout."""
    errors = validate_skill_name(skill_name)
    if errors:
        print("Invalid skill name:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)

    normalized = unicodedata.normalize("NFKC", skill_name).strip()

    if target_dir.name != normalized:
        print(
            f"Warning: target directory name '{target_dir.name}' does not match "
            f"skill name '{normalized}'. Consider using {normalized}.",
            file=sys.stderr,
        )

    target_dir = target_dir.resolve()
    if target_dir.exists() and any(target_dir.iterdir()):
        print(
            f"Error: target directory {target_dir} already exists and is not empty.",
            file=sys.stderr,
        )
        sys.exit(1)

    scripts_dir = target_dir / "scripts"
    references_dir = target_dir / "references"
    assets_dir = target_dir / "assets"

    scripts_dir.mkdir(parents=True, exist_ok=True)
    references_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    (target_dir / "SKILL.md").write_text(skill_template(normalized), encoding="utf-8")
    (assets_dir / "example_skill_tree.txt").write_text(example_tree(), encoding="utf-8")
    (references_dir / "REFERENCE.md").write_text(
        "# Reference\n\nAdd detailed reference material here.\n",
        encoding="utf-8",
    )

    print(f"Created skill at {target_dir}")
    print("Next steps:")
    print(f"  1. Edit {target_dir / 'SKILL.md'}")
    print(f"  2. Add scripts to {scripts_dir}")
    print(f"  3. Add references to {references_dir}")
    print(f"  4. Run: python scripts/validate.py {target_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold a new Agent Skill directory."
    )
    parser.add_argument("name", help="Skill name (kebab-case)")
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target directory (defaults to ./<name>)",
    )
    args = parser.parse_args()

    target = Path(args.target) if args.target else Path.cwd() / args.name
    scaffold(args.name, target)


if __name__ == "__main__":
    main()
