#!/usr/bin/env python3
"""
publish_to_pypi.py

Small helper script to build the package and upload it to PyPI or TestPyPI using twine.

Features:
- Builds sdist + wheel using `python -m build`.
- Uploads via `twine upload`.
- Supports `--repository` (pypi or testpypi), `--dry-run`, `--skip-build`, `--tag`.
- Reads TWINE_USERNAME and TWINE_PASSWORD from environment or falls back to prompting.

This script is intentionally minimal and focuses on safety: it will not push tags
unless `--tag` is supplied and it supports a dry-run mode so you can inspect commands.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_pyproject_version(pyproject: Path) -> str | None:
    """Try to read a version from pyproject.toml.

    Supports PEP621 [project] version and a fallback for Poetry [tool.poetry].
    Returns the version string or None if not found.
    """
    try:
        text = pyproject.read_text(encoding="utf-8")
    except Exception:
        return None

    # Quick and practical parsing - not a full TOML parse to avoid adding deps.
    for key in ("version",):
        # Look for a line like: version = "1.2.3"
        for line in text.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith(key) and "=" in line_stripped:
                # Grab content after '=' and strip quotes
                _, val = line_stripped.split("=", 1)
                return val.strip().strip('"\'')

    # Poetry style: [tool.poetry] section with version = "x.y"
    in_poetry = False
    for line in text.splitlines():
        if line.strip().startswith("[tool.poetry]"):
            in_poetry = True
            continue
        if in_poetry:
            if line.strip().startswith("version") and "=" in line:
                _, val = line.split("=", 1)
                return val.strip().strip('"\'')
            # If we hit another section, stop searching poetry section
            if line.strip().startswith("["):
                break

    return None


def run(cmd: list[str], env: dict | None = None, dry: bool = False) -> int:
    nice = " ".join(shlex.quote(p) for p in cmd)
    if dry:
        print("DRY RUN: ", nice)
        return 0
    print("Running:", nice)
    return subprocess.check_call(cmd, env=env or os.environ.copy())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and upload the package to PyPI or TestPyPI using twine."
    )

    parser.add_argument("--repository", choices=("pypi", "testpypi"), default="testpypi",
                        help="Which well-known repository to publish to (default: testpypi).")
    parser.add_argument("--repository-url", help="Custom repository URL (overrides --repository). Useful for private package indexes or aliases like 'vectalab'.")
    parser.add_argument("--skip-build", action="store_true", help="Skip the build step and only upload dist/.")
    parser.add_argument("--dry-run", action="store_true", help="Don't run commands; just show what would be executed.")
    parser.add_argument("--tag", action="store_true", help="Create a git tag for the version found in pyproject and push it after publishing.")
    parser.add_argument("--version", help="Explicit version to tag/use (overrides pyproject value for tagging).")
    parser.add_argument("--no-upload", action="store_true", help="Build but do not run twine upload (useful for CI checks)")
    args = parser.parse_args(argv)

    os.chdir(ROOT)

    pyproject = ROOT / "pyproject.toml"
    version = None
    if pyproject.exists():
        version = read_pyproject_version(pyproject)

    if args.version:
        version = args.version

    if not args.skip_build:
        print("[1/3] Building sdist and wheel using 'python -m build' ...")
        try:
            run([sys.executable, "-m", "build"], dry=args.dry_run)
        except subprocess.CalledProcessError as e:
            print("Build failed:", e)
            return 2

    # Twine repository URL
    # Determine which repository URL to use. --repository-url overrides the named --repository
    if args.repository_url:
        repository_url = args.repository_url
    else:
        repository_url = (
            "https://upload.pypi.org/legacy/" if args.repository == "pypi" else "https://test.pypi.org/legacy/"
        )

    dist_dir = ROOT / "dist"
    if not dist_dir.exists():
        print("No 'dist' directory found; nothing to upload. Run without --skip-build to create distributions.")
        return 3

    dists = sorted(str(p) for p in dist_dir.iterdir() if p.is_file())
    if not dists:
        print("No distribution files found in 'dist/'")
        return 4

    print(f"[2/3] Uploading {len(dists)} file(s) to {args.repository} ({repository_url})")

    twine_cmd = [sys.executable, "-m", "twine", "upload", "--repository-url", repository_url] + dists

    # Allow TWINE_USERNAME/TWINE_PASSWORD to be in environment; twine will pick them up automatically.
    env = os.environ.copy()

    if args.no_upload:
        print("--no-upload specified — skipping twine upload step")
    else:
        try:
            run(twine_cmd, env=env, dry=args.dry_run)
        except subprocess.CalledProcessError as e:
            print("Twine upload failed:", e)
            return 5

    if args.tag:
        if not version:
            print("Cannot create tag: no version found in pyproject.toml and --version not provided.")
            return 6

        tag_name = f"v{version}" if not str(version).startswith("v") else str(version)
        print(f"[3/3] Creating git tag {tag_name} and pushing to origin")

        try:
            run(["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"], dry=args.dry_run)
            run(["git", "push", "origin", tag_name], dry=args.dry_run)
        except subprocess.CalledProcessError as e:
            print("Git tag/push failed:", e)
            return 7

    print("Done — publishing sequence completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
