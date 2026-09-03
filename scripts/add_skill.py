#!/usr/bin/env python3
"""Add a new skill to the repository using skill-creator."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def add_skill(repo_root: Path, skill_name: str) -> int:
    """Scaffold a new skill in the repository root."""
    scaffold_script = repo_root / "base-skills" / "skill-creator" / "scripts" / "scaffold.py"

    if not scaffold_script.exists():
        print(
            f"Error: scaffold script not found at {scaffold_script}",
            file=sys.stderr,
        )
        print(
            "Make sure the skill-creator skill is present in the repository.",
            file=sys.stderr,
        )
        return 1

    target_dir = repo_root / skill_name

    result = subprocess.run(
        [sys.executable, str(scaffold_script), skill_name, str(target_dir)],
        capture_output=False,
        text=True,
    )
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a new Agent Skill to the repository."
    )
    parser.add_argument("name", help="Skill name (kebab-case)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    sys.exit(add_skill(repo_root, args.name))


if __name__ == "__main__":
    main()
