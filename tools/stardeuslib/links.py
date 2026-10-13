"""Directory links between the workspace's mods/ and the game's Mods folder.

Windows gets a junction (no administrator rights or developer mode needed), other systems a
symlink. Removing a link never touches the folder it points to.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

from .util import UserError

_JUNCTION = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)
_SYMLINK = getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C)


def is_link(path: Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return getattr(st, "st_reparse_tag", 0) in (_JUNCTION, _SYMLINK)


def link_target(path: Path) -> Path | None:
    try:
        target = os.readlink(path)
    except OSError:
        return None
    for prefix in ("\\\\?\\", "\\??\\"):
        if target.startswith(prefix):
            target = target[len(prefix):]
    t = Path(target)
    if not t.is_absolute():
        t = path.parent / t
    return t


def same_path(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def create_dir_link(link: Path, target: Path) -> None:
    if os.path.lexists(link):
        raise UserError(f"{link} already exists")
    link.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target.resolve())],
            capture_output=True, text=True)
        if result.returncode != 0 or not is_link(link):
            msg = (result.stderr or result.stdout).strip()
            raise UserError(f"Could not create a junction at {link}: {msg}")
    else:
        os.symlink(target.resolve(), link, target_is_directory=True)


def remove_dir_link(link: Path) -> None:
    if not is_link(link):
        raise UserError(f"{link} is a real folder, not a link. Refusing to remove it.")
    if sys.platform.startswith("win"):
        os.rmdir(link)  # removes the junction or directory symlink itself
    else:
        os.unlink(link)
