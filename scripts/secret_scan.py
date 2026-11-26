#!/usr/bin/env python3
"""Repository secret scanner using git grep and git ls-files.

Detects API keys, private keys, and tracked environment files.
Prints only file paths, line numbers, and pattern names (never matched secrets).
"""

import os
import subprocess
import sys

# High-risk credential regex patterns and descriptors
PATTERNS = [
    (r"sk-[A-Za-z0-9_-]{20,}", "OpenAI/Anthropic Secret Key"),
    (r"AIza[0-9A-Za-z_-]{35}", "Google API Key"),
    (r"gsk_[A-Za-z0-9_-]{20,}", "Groq API Key"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "Private Key Header"),
]

EXCLUDE_PATTERNS = [
    ":(exclude)scripts/secret_scan.py",
    ":(exclude)*uv.lock",
]


def scan_patterns(repo_root: str) -> list[str]:
    """Scan tracked files using git grep for known credential regex patterns."""
    findings: list[str] = []

    for pattern, name in PATTERNS:
        cmd = [
            "git",
            "grep",
            "-nIE",
            "-e",
            pattern,
            "--",
            ".",
            *EXCLUDE_PATTERNS,
        ]
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    file_path = parts[0]
                    line_num = parts[1]
                    norm_path = file_path.replace("\\", "/")
                    if norm_path.endswith("scripts/secret_scan.py") or norm_path.endswith("uv.lock"):
                        continue
                    findings.append(f"{file_path}:{line_num}: matched {name}")
        elif result.returncode not in (0, 1):
            # Non-zero and non-one indicates an unexpected git error
            err_msg = result.stderr.strip() or f"git grep exited with code {result.returncode}"
            print(f"Error executing git grep: {err_msg}", file=sys.stderr)
            sys.exit(2)

    return findings


def scan_tracked_env_files(repo_root: str) -> list[str]:
    """Verify that git ls-files does not track forbidden .env configuration files."""
    findings: list[str] = []
    cmd = ["git", "ls-files"]
    result = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        err_msg = result.stderr.strip() or f"git ls-files exited with code {result.returncode}"
        print(f"Error executing git ls-files: {err_msg}", file=sys.stderr)
        sys.exit(2)

    for line in result.stdout.splitlines():
        file_path = line.strip()
        if not file_path:
            continue
        base_name = os.path.basename(file_path)
        if base_name == ".env" or (base_name.startswith(".env.") and base_name != ".env.example"):
            findings.append(f"{file_path}: tracked environment file forbidden (only .env.example allowed)")

    return findings


def main() -> None:
    """Execute secret and environment file scans over current working directory."""
    repo_root = os.getcwd()
    findings = []
    findings.extend(scan_patterns(repo_root))
    findings.extend(scan_tracked_env_files(repo_root))

    if findings:
        for finding in sorted(findings):
            print(finding)
        sys.exit(1)

    print("secret scan: clean")
    sys.exit(0)


if __name__ == "__main__":
    main()
