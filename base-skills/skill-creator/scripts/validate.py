#!/usr/bin/env python3
"""Validate an Agent Skill directory using skills-ref."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def find_skills_ref() -> str | None:
    """Return the path to the skills-ref executable, or None if not found."""
    return shutil.which("skills-ref")


def validate(skill_dir: Path) -> int:
    """Run skills-ref validate against the given directory."""
    skill_dir = skill_dir.resolve()

    if not skill_dir.exists():
        print(f"Error: path does not exist: {skill_dir}", file=sys.stderr)
        return 1

    if not skill_dir.is_dir():
        print(f"Error: not a directory: {skill_dir}", file=sys.stderr)
        return 1

    executable = find_skills_ref()
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
        [executable, "validate", str(skill_dir)],
        capture_output=False,
        text=True,
    )
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an Agent Skill directory.")
    parser.add_argument("skill_dir", type=Path, help="Path to the skill directory")
    args = parser.parse_args()

    sys.exit(validate(args.skill_dir))


if __name__ == "__main__":
    main()
