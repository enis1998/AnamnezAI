#!/usr/bin/env python3
"""
AnamnezAI — UTF-8 Git Commit Helper
Solves Turkish/Arabic character encoding issues in PowerShell.
Usage: python commit.py "Commit message"
       python commit.py "Message" --no-push
"""
import sys
import os
import subprocess
import tempfile

def git_commit(message: str, push: bool = True):
    """Passes commit message to Git via temp file (UTF-8 encoding)."""
    repo_dir = os.path.dirname(os.path.abspath(__file__))

    # git add -A
    subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)

    # Write commit message to temp file (UTF-8)
    with tempfile.NamedTemporaryFile(
        mode='w', encoding='utf-8', suffix='.txt', delete=False
    ) as f:
        f.write(message)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["git", "commit", "-F", tmp_path],
            cwd=repo_dir, capture_output=True, text=True, encoding='utf-8'
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            return False
    finally:
        os.unlink(tmp_path)

    if push:
        result = subprocess.run(
            ["git", "push", "origin", "master"],
            cwd=repo_dir, capture_output=True, text=True, encoding='utf-8'
        )
        print(result.stdout)
        print(result.stderr)

    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python commit.py 'Commit message' [--no-push]")
        sys.exit(1)
    args = [a for a in sys.argv[1:] if a != '--no-push']
    message = " ".join(args)
    no_push = "--no-push" in sys.argv
    success = git_commit(message, push=not no_push)
    sys.exit(0 if success else 1)



