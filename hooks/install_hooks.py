#!/usr/bin/env python
"""Install git hooks for this repository."""

import shutil
import stat
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HOOKS_SRC = REPO_ROOT / "hooks"
HOOKS_DST = REPO_ROOT / ".git" / "hooks"


def install():
    hook_file = HOOKS_SRC / "pre-commit"
    dest = HOOKS_DST / "pre-commit"

    if not hook_file.exists():
        print(f"ERROR: Source hook not found: {hook_file}")
        return False

    shutil.copy2(hook_file, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
    print(f"Installed: {dest}")
    return True


if __name__ == "__main__":
    print("Installing git hooks...")
    if install():
        print("Done. Pre-commit hook will run unit tests on relevant changes.")
    else:
        print("Failed to install hooks.")
