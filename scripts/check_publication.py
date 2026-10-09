#!/usr/bin/env python3
"""Conservative public-repository preflight for tracked and candidate files.

Does not contact services, read ignored files, print matching secret values, or
modify Git. This is a safety net, not a replacement for human release review.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 2_000_000

SENSITIVE_NAMES = {
    ".ds_store", "id_rsa", "id_ed25519", "pairing.json",
    "cookies.json", "cookies.txt", "storage-state.json", "storagestate.json",
    "credentials.json", "secrets.json", "notes.md",
}
SENSITIVE_FOLDERS = {
    ".git", ".venv", "node_modules", ".playwright-cli", "diagnostics",
    "__pycache__", ".local-system",
}
SENSITIVE_SUFFIXES = {".pem", ".p12", ".pfx", ".key", ".sqlite", ".db"}

# Deliberately narrow signatures, to avoid flagging documentation and
# synthetic short tokens. Report categories and file paths, never values.
SIGNATURES = {
    "private key": re.compile(rb"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----"),
    "GitHub credential": re.compile(rb"gh(?:p|o|u|s|r)_[A-Za-z0-9_]{25,}"),
    "OpenAI credential": re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{30,}"),
    "AWS credential": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "Playwright pairing credential": re.compile(
        rb"PLAYWRIGHT_MCP_EXTENSION_TOKEN\s*[:=]\s*['\"]?[A-Za-z0-9_-]{40,}"
    ),
    "developer home path": re.compile(rb"/(?:Users|home)/[A-Za-z0-9_.-]{2,}/"),
}


def path_issues(name: str) -> list[str]:
    path = PurePosixPath(name)
    parts = {part.lower() for part in path.parts}
    basename = path.name.lower()
    issues = []
    if parts & SENSITIVE_FOLDERS:
        issues.append("local runtime directory")
    if basename in SENSITIVE_NAMES or basename.startswith(".env"):
        # .env.example is intentionally public but must never contain a value.
        if basename != ".env.example":
            issues.append("private file name")
    if path.suffix.lower() in SENSITIVE_SUFFIXES:
        issues.append("private file extension")
    return issues


def content_issues(data: bytes) -> list[str]:
    if b"\x00" in data[:8192]:
        return []  # a binary asset, not a text source file
    return [category for category, signature in SIGNATURES.items()
            if signature.search(data)]


def candidates(root: Path = ROOT) -> list[str]:
    names = set()
    for mode in (["ls-files", "-z", "--cached"],
                 ["ls-files", "-z", "--others", "--exclude-standard"]):
        result = subprocess.run(["git", *mode], cwd=root, check=True,
                                capture_output=True)
        names.update(os.fsdecode(item) for item in result.stdout.split(b"\0") if item)
    return sorted(names)


def audit(root: Path = ROOT, names: list[str] | None = None) -> list[tuple[str, str]]:
    failures = []
    for name in names if names is not None else candidates(root):
        failures.extend((name, issue) for issue in path_issues(name))
        path = root / name
        if path.is_symlink():
            try:
                target = path.resolve(strict=True)
            except (OSError, RuntimeError):
                failures.append((name, "broken symbolic link"))
                continue
            if not target.is_relative_to(root.resolve()):
                failures.append((name, "symbolic link escapes repository"))
            continue
        if not path.is_file():
            # A tracked deletion is allowed during a release preparation.
            continue
        if path.stat().st_size > MAX_TEXT_BYTES:
            failures.append((name, "file too large for content check"))
            continue
        failures.extend((name, issue) for issue in content_issues(path.read_bytes()))
    return failures


def main() -> int:
    try:
        failures = audit()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Publication preflight could not inspect the repository: {type(exc).__name__}", file=sys.stderr)
        return 2
    if failures:
        for name, issue in failures:
            print(f"BLOCKED {name}: {issue}", file=sys.stderr)
        print(f"Preflight blocked: {len(failures)} issue(s); inspect locally without sharing credentials.",
              file=sys.stderr)
        return 1
    print("Publication preflight passed for tracked and non-ignored untracked files.")
    print("This does not review Git history, artifact provenance, or credentials outside known patterns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
