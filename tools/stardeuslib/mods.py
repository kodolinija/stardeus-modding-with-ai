"""Mods in the workspace: ModInfo, version folders and where the game finds each kind of content."""
from __future__ import annotations

import re
from pathlib import Path

from . import jsonc
from .util import MODS, UserError

# Fallback when the snapshot's Consts.cs cannot be read (Consts.ModDirLoadOrder)
DEFAULT_LOAD_ORDER = ["CommonPre", "0.15", "0.14", "0.13", "0.12", "0.11", "CommonPost", ""]
TOP_FOLDERS = ("Definitions", "Config", "Patches", "Graphics", "Sounds", "Translations", "Libraries")


def load_order(snapshot: Path | None) -> list[str]:
    """The folders a mod may use per game version, read from the installed game's code."""
    if snapshot:
        consts = snapshot / "Core/ReferenceSourceCode/Constants/Consts.cs"
        if consts.is_file():
            text = consts.read_text(encoding="utf-8-sig", errors="replace")
            m = re.search(r"ModDirLoadOrder\s*=\s*new\s+string\[\]\s*\{(.*?)\}", text, re.S)
            if m:
                body = re.sub(r"//[^\n]*", "", m.group(1))
                items = re.findall(r'"([^"]*)"', body)
                if items:
                    return items
    return list(DEFAULT_LOAD_ORDER)


class Mod:
    def __init__(self, folder: Path, order: list[str]):
        self.dir = folder
        self.order = order
        self.info: dict = {}
        self.info_error: str | None = None
        path = folder / "ModInfo.json"
        if path.is_file():
            try:
                data, _ = jsonc.load(path)
                if isinstance(data, dict):
                    self.info = data
                else:
                    self.info_error = "ModInfo.json must be a JSON object"
            except (jsonc.JsoncError, OSError) as e:
                self.info_error = str(e)
        else:
            self.info_error = "ModInfo.json is missing"

    @property
    def id(self) -> str:
        return str(self.info.get("Id") or self.dir.name)

    def candidates(self, rel: str) -> list[Path]:
        out = []
        for seg in self.order:
            p = self.dir / seg / rel if seg else self.dir / rel
            if p.is_dir():
                out.append(p)
        return out

    def content(self, rel: str) -> Path | None:
        """The folder the game reads for rel (for example "Definitions"): the first that exists."""
        found = self.candidates(rel)
        return found[0] if found else None

    def version_segment(self, file: Path) -> str:
        """"0.15" for mods/X/0.15/Definitions/a.json, "" for mods/X/Definitions/a.json."""
        parts = file.relative_to(self.dir).parts
        if len(parts) > 1 and parts[0] in self.order and parts[0]:
            return parts[0]
        return ""

    def strip_version(self, file: Path) -> str:
        rel = file.relative_to(self.dir).as_posix()
        seg = self.version_segment(file)
        return rel[len(seg) + 1:] if seg else rel


def workspace_mods(order: list[str]) -> list[Mod]:
    if not MODS.is_dir():
        return []
    return [Mod(p, order) for p in sorted(MODS.iterdir())
            if p.is_dir() and not p.name.startswith(".")]


def find_mod(name: str, order: list[str]) -> Mod:
    folder = MODS / name
    if folder.is_dir():
        return Mod(folder, order)
    for mod in workspace_mods(order):
        if mod.id == name:
            return mod
    raise UserError(f'No mod "{name}" in mods/. Existing: '
                    + (", ".join(m.dir.name for m in workspace_mods(order)) or "none"))
