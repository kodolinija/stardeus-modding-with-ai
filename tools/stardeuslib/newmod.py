"""Creates a mod folder in mods/ from the templates, and moves existing mods into the workspace."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from . import links
from .util import MODS, TEMPLATES, UserError, rel, write_text

KINDS = ("patch", "content", "csharp")


def _game_version(paths: dict) -> str:
    m = re.match(r"v?(\d+\.\d+\.\d+)", paths.get("game_version") or "")
    return m.group(1) if m else "0.15.0"


def _fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace(f"__{k}__", v)
    return text


def create(mod_id: str, name: str | None, description: str | None, kinds: list[str],
           paths: dict) -> Path:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,63}", mod_id):
        raise UserError("Use letters, digits and _ for the mod Id, starting with a letter (for "
                        "example BetterBatteries). The Id is also the folder and C# namespace name.")
    if mod_id.endswith("Template"):
        raise UserError('Pick an Id that does not end in "Template" (the game deletes mod folders '
                        "with such names when their ModInfo.json is missing).")
    for k in kinds:
        if k not in KINDS:
            raise UserError(f'Unknown kind "{k}". Use any of: {", ".join(KINDS)}')
    folder = MODS / mod_id
    if folder.exists():
        raise UserError(f"{rel(folder)} already exists")
    game_link = Path(paths["mods_dir"]) / mod_id
    if game_link.exists() and not links.is_link(game_link):
        raise UserError(f"The game already has a mod folder {game_link}. Bring it into the "
                        f"workspace with: tools/stardeus adopt {mod_id}")
    name = name or re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", mod_id).replace("_", " ")
    description = description or f"{name}: describe what this mod changes."
    values = {
        "ID": mod_id,
        "NAME": json.dumps(name)[1:-1],
        "DESCRIPTION": json.dumps(description)[1:-1],
        "GAME_VERSION": _game_version(paths),
        "NAMESPACE": mod_id,
        "ASSEMBLY": mod_id,
        "COMPONENT": mod_id,
    }
    folder.mkdir(parents=True)
    write_text(folder / "ModInfo.json", _fill((TEMPLATES / "ModInfo.json").read_text(encoding="utf-8"), values))
    shutil.copyfile(TEMPLATES / "ModCover.jpg", folder / "ModCover.jpg")
    if "patch" in kinds:
        (folder / "Patches").mkdir()
    if "content" in kinds or "csharp" in kinds:
        (folder / "Definitions").mkdir()
        (folder / "Translations").mkdir()
        shutil.copyfile(TEMPLATES / "English.csv", folder / "Translations" / "English.csv")
    if "csharp" in kinds:
        csharp = TEMPLATES / "csharp"
        write_text(folder / ".vscode" / "mod.csproj",
                   _fill((csharp / "mod.csproj").read_text(encoding="utf-8"), values))
        write_text(folder / "Code" / f"{mod_id}Comp.cs",
                   _fill((csharp / "ExampleComp.cs").read_text(encoding="utf-8"), values))
        (folder / "Libraries").mkdir()
    return folder


def link(folder: Path, paths: dict) -> Path:
    if not (folder / "ModInfo.json").is_file():
        raise UserError(f"{rel(folder)} has no ModInfo.json; the game would skip it (and deletes such "
                        'folders when their name ends in "Template"), so it is not linked')
    game_mods = Path(paths["mods_dir"])
    target = game_mods / folder.name
    if links.is_link(target):
        current = links.link_target(target)
        if current and links.same_path(current, folder):
            return target
        raise UserError(f"{target} already links to {current}. Remove that link first: "
                        f"tools/stardeus unlink {folder.name}")
    if target.exists():
        raise UserError(f"{target} is a real folder. To work on it here, move it into the workspace "
                        f"with: tools/stardeus adopt {folder.name}")
    links.create_dir_link(target, folder)
    return target


def unlink(folder_name: str, paths: dict) -> Path:
    target = Path(paths["mods_dir"]) / folder_name
    if not links.is_link(target):
        if target.exists():
            raise UserError(f"{target} is a real folder, not a link; nothing was removed")
        raise UserError(f"{target} does not exist")
    links.remove_dir_link(target)
    return target


def adopt(folder_name: str, paths: dict) -> Path:
    """Moves a real mod folder from the game's Mods folder into mods/ and links it back."""
    source = Path(paths["mods_dir"]) / folder_name
    if links.is_link(source):
        raise UserError(f"{source} is already a link")
    if not source.is_dir():
        raise UserError(f"{source} does not exist")
    if not (source / "ModInfo.json").is_file():
        raise UserError(f"{source} has no ModInfo.json")
    for p in source.rglob("*"):
        if links.is_link(p):
            raise UserError(f"{source} contains a link ({p}); move it by hand")
    dest = MODS / folder_name
    if dest.exists():
        raise UserError(f"{rel(dest)} already exists")
    shutil.copytree(source, dest)
    copied = sum(1 for p in dest.rglob("*") if p.is_file())
    original = sum(1 for p in source.rglob("*") if p.is_file())
    if copied != original:
        shutil.rmtree(dest)
        raise UserError("Copying did not complete; nothing was changed")
    shutil.rmtree(source)
    links.create_dir_link(source, dest)
    return dest
