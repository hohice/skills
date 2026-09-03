#!/usr/bin/env python3
"""Validate all Agent Skills in the repository."""

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


def validate_all(repo_root: Path) -> int:
    """Run skills-ref validate against every discovered skill."""
    skills = find_skill_directories(repo_root)

    if not skills:
        print("No skills found in repository root.", file=sys.stderr)
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

    failures: list[Path] = []

    for skill_dir in skills:
        print(f"\n=== Validating {skill_dir.name} ===")
        result = subprocess.run(
            [executable, "validate", str(skill_dir)],
            capture_output=False,
            text=True,
        )
        if result.returncode != 0:
            failures.append(skill_dir)

    print("\n=== Validation summary ===")
    print(f"Total: {len(skills)}")
    print(f"Passed: {len(skills) - len(failures)}")
    print(f"Failed: {len(failures)}")

    if failures:
        print("\nFailed skills:")
        for skill_dir in failures:
            print(f"  - {skill_dir.name}")
        return 1

    print("\nAll skills are valid.")
    return 0


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    sys.exit(validate_all(repo_root))


if __name__ == "__main__":
    main()
