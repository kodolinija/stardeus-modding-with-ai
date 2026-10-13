"""Shared paths and small helpers."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "local"
MODS = ROOT / "mods"
TEMPLATES = ROOT / "templates"
TOOLS = ROOT / "tools"
PATHS_FILE = LOCAL / "paths.json"
APP_ID = "1380910"


class UserError(Exception):
    """A problem the user can fix. Printed without a traceback."""


def read_json(path: Path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def rel(path) -> str:
    """The path relative to the workspace when inside it, always with forward slashes."""
    p = Path(path)
    try:
        return p.absolute().relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def read_saved() -> dict:
    """What the last `setup` wrote, or an empty dict."""
    return read_json(PATHS_FILE) if PATHS_FILE.is_file() else {}


def load_paths(required: bool = True) -> dict | None:
    """Where the game is: from the last `setup`, or detected again when STARDEUS_GAME_DIR or
    STARDEUS_USER_DIR is set (so one command can look at another install without a new setup)."""
    if os.environ.get("STARDEUS_GAME_DIR") or os.environ.get("STARDEUS_USER_DIR"):
        from . import paths
        info = paths.detect()
        info["tools"] = read_saved().get("tools") or {}
        return info
    if PATHS_FILE.is_file():
        return read_json(PATHS_FILE)
    if required:
        raise UserError("This workspace is not set up yet. Run: tools/stardeus setup")
    return None
