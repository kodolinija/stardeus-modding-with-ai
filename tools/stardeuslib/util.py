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


def load_paths(required: bool = True) -> dict | None:
    """The result of the last `setup`, or None."""
    if PATHS_FILE.is_file():
        return read_json(PATHS_FILE)
    if required:
        raise UserError("This workspace is not set up yet. Run: tools/stardeus setup")
    return None
