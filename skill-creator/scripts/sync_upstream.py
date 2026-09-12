#!/usr/bin/env python3
"""Sync upstream Agent Skills specification documents into references/."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
import sys
from pathlib import Path

REPO = "agentskills/agentskills"
DEFAULT_REF = "main"
BASE_URL = f"https://raw.githubusercontent.com/{REPO}"

UPSTREAM_FILES = {
    "docs/specification.mdx": "references/specification.md",
    "docs/skill-creation/best-practices.mdx": "references/best-practices.md",
    "docs/skill-creation/optimizing-descriptions.mdx": "references/optimizing-descriptions.md",
}


def mdx_to_md(content: str) -> str:
    """Strip Mintlify-specific MDX syntax for plain Markdown consumption."""
    # Remove frontmatter.
    content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL, count=1)
    # Remove import statements.
    content = re.sub(r"^import .*?;\n", "", content, flags=re.MULTILINE)
    # Remove common Mintlify component tags while keeping their text content.
    for tag in ("Card", "CardGroup", "Note", "Tip", "Warning", "Accordion", "Tabs"):
        content = re.sub(rf"</?{tag}(\s+[^>]*)?>", "", content)
    # Remove param/prop attributes on component openings (e.g. <Card title="...">).
    content = re.sub(r"<(\w+)(\s+[^>]*)>", r"<\1>", content)
    return content.strip()


def sha256_hex(data: bytes) -> str:
    """Return sha256 hex digest of data."""
    return hashlib.sha256(data).hexdigest()


def fetch_file(repo_path: str, ref: str) -> bytes:
    """Fetch a file from the upstream repository."""
    url = f"{BASE_URL}/{ref}/{repo_path}"
    request = urllib.request.Request(url, headers={"User-Agent": "skill-creator-sync"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def load_lock(lock_path: Path) -> dict:
    """Load upstream.lock, or return a default structure."""
    if lock_path.exists():
        with lock_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "repo": REPO,
        "ref": DEFAULT_REF,
        "files": {},
    }


def save_lock(lock_path: Path, lock: dict) -> None:
    """Save upstream.lock with stable formatting."""
    with lock_path.open("w", encoding="utf-8") as f:
        json.dump(lock, f, indent=2, sort_keys=True)
        f.write("\n")


def sync(skill_root: Path, ref: str | None) -> int:
    """Sync upstream files into references/."""
    skill_root = skill_root.resolve()
    lock_path = skill_root / "upstream.lock"
    lock = load_lock(lock_path)

    if ref is None:
        ref = lock.get("ref", DEFAULT_REF)
    lock["repo"] = REPO
    lock["ref"] = ref

    updated_files: dict[str, str] = {}

    for upstream_path, local_rel_path in UPSTREAM_FILES.items():
        local_path = skill_root / local_rel_path
        print(f"Fetching {upstream_path} @ {ref} ...")

        try:
            raw = fetch_file(upstream_path, ref)
        except urllib.error.HTTPError as e:
            print(f"Error fetching {upstream_path}: {e.code} {e.reason}", file=sys.stderr)
            return 1
        except urllib.error.URLError as e:
            print(f"Error fetching {upstream_path}: {e.reason}", file=sys.stderr)
            return 1

        converted = mdx_to_md(raw.decode("utf-8"))
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(converted, encoding="utf-8")

        digest = sha256_hex(raw)
        updated_files[upstream_path] = digest
        print(f"  -> {local_path}")

    lock["files"] = updated_files
    save_lock(lock_path, lock)

    print(f"\nSynced {len(updated_files)} files. Lock written to {lock_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync upstream Agent Skills docs into references/."
    )
    parser.add_argument(
        "--ref",
        default=None,
        help="Upstream git ref to sync from (defaults to value in upstream.lock or main)",
    )
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=Path.cwd(),
        help="Root directory of this skill (defaults to current directory)",
    )
    args = parser.parse_args()

    sys.exit(sync(args.skill_root, args.ref))


if __name__ == "__main__":
    main()
