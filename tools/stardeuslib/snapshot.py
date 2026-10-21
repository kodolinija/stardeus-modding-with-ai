"""A read-only copy of the installed game's Core text files inside the workspace.

Agents read the game from here (no permission prompts, no sandbox limits), and after a game
update two snapshots show what changed. Graphics are not copied, only listed in graphics.txt.
"""
from __future__ import annotations

import difflib
import fnmatch
import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .links import is_link
from .util import LOCAL, UserError, read_json, write_json

GAME = LOCAL / "game"
TEXT_SUFFIXES = {".json", ".cs", ".csv", ".txt", ".md"}
COPY_DIRS = ["Definitions", "Config", "Scenarios", "Translations", "ReferenceSourceCode"]
COPY_FILES = ["ModInfo.json", "README.md"]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
KEEP = 3


def path_for(snapshot_id: str) -> Path:
    return GAME / snapshot_id


def is_complete(path: Path) -> bool:
    return (path / "meta.json").is_file()


def _copy_tree(src: Path, dst: Path) -> int:
    count = 0
    for dirpath, _, files in os.walk(src):
        rel = Path(dirpath).relative_to(src)
        for name in files:
            if Path(name).suffix.lower() not in TEXT_SUFFIXES:
                continue
            target = dst / rel / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(dirpath) / name, target)
            count += 1
    return count


def _graphics_index(graphics: Path) -> list[str]:
    ids = []
    for dirpath, _, files in os.walk(graphics):
        for name in files:
            p = Path(name)
            if p.suffix.lower() in IMAGE_SUFFIXES:
                rel = (Path(dirpath) / p.stem).relative_to(graphics).as_posix()
                ids.append(rel)
    return sorted(ids)


def _safe_rmtree(path: Path) -> None:
    if is_link(path):
        raise UserError(f"{path} is a link; refusing to delete through it")
    if path.exists():
        shutil.rmtree(path)


def make(info: dict, force: bool = False) -> tuple[Path, bool]:
    """Creates the snapshot for the installed build unless it exists. Returns (path, created)."""
    dest = path_for(info["snapshot_id"])
    if is_complete(dest) and not force:
        return dest, False
    core = Path(info["core_dir"])
    tmp = dest.with_name(dest.name + ".partial")
    _safe_rmtree(tmp)
    counts = {}
    for d in COPY_DIRS:
        if (core / d).is_dir():
            counts[d] = _copy_tree(core / d, tmp / "Core" / d)
    for f in COPY_FILES:
        if (core / f).is_file():
            (tmp / "Core").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(core / f, tmp / "Core" / f)
    # The mod versions this build refuses to load, next to the Mods folder in StreamingAssets
    disabled = core.parent.parent / "DisabledMods.json"
    if disabled.is_file():
        tmp.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(disabled, tmp / "DisabledMods.json")
    sprites = _graphics_index(core / "Graphics") if (core / "Graphics").is_dir() else []
    (tmp / "graphics.txt").write_text("\n".join(sprites) + "\n", encoding="utf-8")
    managed = Path(info["managed_dir"])
    dlls = sorted(p.name for p in managed.glob("*.dll")) if managed.is_dir() else []
    (tmp / "managed.txt").write_text("\n".join(dlls) + "\n", encoding="utf-8")
    write_json(tmp / "meta.json", {
        "snapshot_id": info["snapshot_id"],
        "game_version": info.get("game_version"),
        "build_id": (info.get("steam") or {}).get("build_id"),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": counts,
        "sprites": len(sprites),
    })
    _safe_rmtree(dest)
    os.replace(tmp, dest)
    prune(keep_id=info["snapshot_id"])
    return dest, True


def all_snapshots() -> list[tuple[Path, dict]]:
    if not GAME.is_dir():
        return []
    found = []
    for p in GAME.iterdir():
        if p.is_dir() and is_complete(p):
            found.append((p, read_json(p / "meta.json")))
    return sorted(found, key=lambda x: x[1].get("created", ""))


def prune(keep_id: str, keep: int = KEEP) -> None:
    snaps = all_snapshots()
    removable = [p for p, _ in snaps if p.name != keep_id]
    while len(removable) > keep - 1:
        _safe_rmtree(removable.pop(0))
    for p in GAME.glob("*.partial") if GAME.is_dir() else []:
        _safe_rmtree(p)


def current(paths: dict) -> Path:
    snap = path_for(paths["snapshot_id"])
    if not is_complete(snap):
        raise UserError("The game snapshot is missing. Run: tools/stardeus setup")
    return snap


def _files(root: Path) -> dict[str, Path]:
    out = {}
    base = root / "Core"
    for dirpath, _, files in os.walk(base):
        for name in files:
            full = Path(dirpath) / name
            out[full.relative_to(base).as_posix()] = full
    return out


def _digest(p: Path) -> str:
    return hashlib.sha1(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def diff(old: Path, new: Path, pattern: str | None = None) -> dict[str, list[str]]:
    a, b = _files(old), _files(new)
    if pattern:
        a = {k: v for k, v in a.items() if fnmatch.fnmatch(k, pattern)}
        b = {k: v for k, v in b.items() if fnmatch.fnmatch(k, pattern)}
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = sorted(k for k in set(a) & set(b) if _digest(a[k]) != _digest(b[k]))
    return {"added": added, "removed": removed, "changed": changed}


def unified(old: Path, new: Path, rel_path: str) -> str:
    def lines(root: Path) -> list[str]:
        p = root / "Core" / rel_path
        if not p.is_file():
            return []
        return p.read_text(encoding="utf-8-sig", errors="replace").splitlines(keepends=True)
    return "".join(difflib.unified_diff(lines(old), lines(new),
                                        f"{old.name}/{rel_path}", f"{new.name}/{rel_path}"))
