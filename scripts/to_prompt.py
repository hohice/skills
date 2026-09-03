#!/usr/bin/env python3
"""Generate <available_skills> XML for all skills in the repository."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def find_skill_directories(repo_root: Path) -> list[Path]:
    """Return skill directories that contain a SKILL.md or skill.md file.

    Skills are organized under category directories (e.g. base-skills/,
    knowledge-base-skills/) rather than at the repository root.
    """
    skills: list[Path] = []
    non_category_dirs = {"scripts", ".github"}
    for category_dir in repo_root.iterdir():
        if not category_dir.is_dir():
            continue
        if category_dir.name.startswith(".") or category_dir.name in non_category_dirs:
            continue
        for item in category_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                if (item / "SKILL.md").exists() or (item / "skill.md").exists():
                    skills.append(item)
    return sorted(skills)


def to_prompt(repo_root: Path) -> int:
    """Run skills-ref to-prompt for all discovered skills."""
    skills = find_skill_directories(repo_root)

    if not skills:
        print("<available_skills>\n</available_skills>")
        return 0

    executable = shutil.which("skills-ref")
    if executable is None:
        print(
            "Error: skills-ref CLI not found on PATH.",
            file=sys.stderr,
        )
        print(
            "Install it from the upstream repository:",
            file=sys.stderr,
        )
        print(
            "  pip install git+https://github.com/agentskills/agentskills.git#subdirectory=skills-ref",
            file=sys.stderr,
        )
        return 1

    result = subprocess.run(
        [executable, "to-prompt"] + [str(skill) for skill in skills],
        capture_output=False,
        text=True,
    )
    return result.returncode


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    sys.exit(to_prompt(repo_root))


if __name__ == "__main__":
    main()
