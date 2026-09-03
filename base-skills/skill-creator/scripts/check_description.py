#!/usr/bin/env python3
"""Check the quality of a Skill's description."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MIN_DESCRIPTION_LENGTH = 30
MAX_DESCRIPTION_LENGTH = 1024


def find_skill_md(skill_dir: Path) -> Path | None:
    """Find SKILL.md or skill.md in the directory."""
    for name in ("SKILL.md", "skill.md"):
        path = skill_dir / name
        if path.exists():
            return path
    return None


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from SKILL.md content."""
    if not content.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter not properly closed with ---")

    frontmatter_str = parts[1]
    body = parts[2].strip()

    metadata: dict[str, str] = {}
    current_key: str | None = None
    for line in frontmatter_str.splitlines():
        stripped = line.rstrip()
        if not stripped:
            continue

        # Simple top-level key: value parser; does not support nested maps.
        if stripped.startswith(" ") and current_key is not None:
            # Continuation / list item — skip for this simple checker.
            continue

        if ":" in stripped:
            key, value = stripped.split(":", 1)
            current_key = key.strip()
            metadata[current_key] = value.strip().strip('"').strip("'")

    return metadata, body


def check_description(skill_dir: Path) -> int:
    """Check the skill description and print suggestions."""
    skill_dir = skill_dir.resolve()
    skill_md = find_skill_md(skill_dir)

    if skill_md is None:
        print(f"Error: SKILL.md not found in {skill_dir}", file=sys.stderr)
        return 1

    try:
        metadata, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    except ValueError as e:
        print(f"Error parsing frontmatter: {e}", file=sys.stderr)
        return 1

    description = metadata.get("description", "")
    name = metadata.get("name", "<unknown>")

    print(f"Checking description for skill: {name}")
    print(f"Description length: {len(description)} characters")

    suggestions: list[str] = []

    if not description:
        suggestions.append("Description is missing. It is a required field.")
    else:
        if len(description) < MIN_DESCRIPTION_LENGTH:
            suggestions.append(
                f"Description is short ({len(description)} chars). "
                f"Aim for at least {MIN_DESCRIPTION_LENGTH} characters to include "
                f"what the skill does and when to use it."
            )
        if len(description) > MAX_DESCRIPTION_LENGTH:
            suggestions.append(
                f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters. "
                f"Shorten it to fit the spec."
            )

        lower = description.lower()
        if "use when" not in lower and "activate" not in lower:
            suggestions.append(
                "Add a 'Use when ...' clause so agents know when to activate this skill."
            )

        # Check for vague words.
        vague_words = ["helps", "various", "things", "stuff", "etc"]
        found_vague = [w for w in vague_words if re.search(rf"\b{w}\b", lower)]
        if found_vague:
            suggestions.append(
                f"Description contains vague words ({', '.join(found_vague)}). "
                f"Use concrete actions and nouns instead."
            )

        # Check for concrete domain keywords.
        concrete_indicators = [
            "file", "files", "script", "scripts", "command", "run",
            "extract", "generate", "validate", "test", "pdf", "json", "yaml",
        ]
        if not any(indicator in lower for indicator in concrete_indicators):
            suggestions.append(
                "Description lacks concrete keywords (e.g., file types, tools, actions). "
                "Add specific terms agents can match against."
            )

    if suggestions:
        print("\nSuggestions:")
        for suggestion in suggestions:
            print(f"  - {suggestion}")
        return 1

    print("\nDescription looks good.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check the quality of a Skill's description."
    )
    parser.add_argument("skill_dir", type=Path, help="Path to the skill directory")
    args = parser.parse_args()

    sys.exit(check_description(args.skill_dir))


if __name__ == "__main__":
    main()
