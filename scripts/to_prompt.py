#!/usr/bin/env python3
"""Generate <available_skills> XML for all skills in the repository."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def find_skill_directories(repo_root: Path) -> list[Path]:
    """Return skill directories that contain a SKILL.md or skill.md file.

    Skills live directly at the repository root, one directory per skill.
    """
    skills = [
        item
        for item in repo_root.iterdir()
        if item.is_dir()
        and not item.name.startswith(".")
        and ((item / "SKILL.md").exists() or (item / "skill.md").exists())
    ]
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
