#!/usr/bin/env python3
"""Check Humanizer's package files without external dependencies."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

# Directories to skip when scanning the repo tree for stray package files.
IGNORED_DIR_NAMES = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def read_package_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise SystemExit(f"Cannot read {path.relative_to(ROOT)}: {error}")


def require_lf_line_endings(path: Path) -> None:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise SystemExit(f"Cannot read {path.relative_to(ROOT)}: {error}")
    if b"\r" in raw:
        raise SystemExit(
            f"Use LF line endings in {path.relative_to(ROOT)} (found CR or CRLF)"
        )


def is_ignored(relative_path: Path) -> bool:
    return any(part in IGNORED_DIR_NAMES for part in relative_path.parts[:-1])


SKILL_PATH = ROOT / "SKILL.md"
README_PATH = ROOT / "README.md"
PLUGIN_PATH = ROOT / ".claude-plugin" / "plugin.json"

SKILL = read_package_file(SKILL_PATH)
README = read_package_file(README_PATH)
try:
    PLUGIN = json.loads(read_package_file(PLUGIN_PATH))
except json.JSONDecodeError as error:
    raise SystemExit(f"Fix the JSON in .claude-plugin/plugin.json: {error}")

for path in (SKILL_PATH, README_PATH, PLUGIN_PATH):
    require_lf_line_endings(path)


def require_match(match: re.Match[str] | None, message: str) -> re.Match[str]:
    if match is None:
        raise SystemExit(message)
    return match


yaml_metadata = require_match(
    re.match(r"\A---\n(.*?)\n---\n", SKILL, re.DOTALL),
    "SKILL.md must begin with YAML metadata",
).group(1)

for unsupported_field in ("version:", "compatibility:", "allowed-tools:"):
    if re.search(rf"(?m)^{re.escape(unsupported_field)}", yaml_metadata):
        raise SystemExit(f"Remove unsupported YAML field: {unsupported_field[:-1]}")

for required_field in ("name:", "description:"):
    if not re.search(rf"(?m)^{re.escape(required_field)}", yaml_metadata):
        raise SystemExit(f"Add required YAML field: {required_field[:-1]}")

skill_version = require_match(
    re.search(r'(?m)^\s+version:\s*["\']?([0-9]+\.[0-9]+\.[0-9]+)["\']?\s*$', yaml_metadata),
    "Add metadata.version to SKILL.md as a three-part version",
).group(1)
readme_version = require_match(
    re.search(r"(?m)^- \*\*([0-9]+\.[0-9]+\.[0-9]+)\*\*", README),
    "Add a version entry to README.md",
).group(1)

package_versions = {skill_version, readme_version, str(PLUGIN.get("version", ""))}
if len(package_versions) != 1:
    raise SystemExit(
        f"Use one package version in all files: {sorted(package_versions)}"
    )

readme_changelog_versions = [
    tuple(int(part) for part in version.split("."))
    for version in re.findall(r"(?m)^- \*\*([0-9]+\.[0-9]+\.[0-9]+)\*\*", README)
]
if readme_changelog_versions != sorted(readme_changelog_versions, reverse=True):
    raise SystemExit("List README changelog versions newest first, oldest last")

skill_files = {
    path.relative_to(ROOT)
    for path in ROOT.rglob("SKILL.md")
    if not is_ignored(path.relative_to(ROOT))
}
if SKILL_PATH.is_symlink() or skill_files != {Path("SKILL.md")}:
    raise SystemExit("Keep one regular SKILL.md at the repo root")
if PLUGIN.get("skills") != ["./"]:
    raise SystemExit("Point the Claude plugin skill loader at the repo root")

pattern_numbers = [
    int(number)
    for number in re.findall(r"(?m)^### ([0-9]+)\. ", SKILL)
]
pattern_count = len(pattern_numbers)
if pattern_count == 0 or pattern_numbers != list(range(1, pattern_count + 1)):
    raise SystemExit(f"Number SKILL.md patterns from 1 upward without gaps: {pattern_numbers}")

readme_numbers = [
    int(number) for number in re.findall(r"(?m)^\| ([0-9]+) \|", README)
]
if sorted(readme_numbers) != pattern_numbers:
    raise SystemExit(
        f"List patterns 1 through {pattern_count} once each in the README tables: {sorted(readme_numbers)}"
    )
if f"## The {pattern_count} patterns" not in README:
    raise SystemExit(f"Title the README pattern section 'The {pattern_count} patterns'")

skill_line_count = len(SKILL.splitlines())
if skill_line_count > 400:
    raise SystemExit("Keep SKILL.md at 400 lines or fewer")
if skill_line_count > 360:
    print(f"Warning: SKILL.md is {skill_line_count}/400 lines and approaching the cap")

print(f"Humanizer package v{skill_version} is valid")
