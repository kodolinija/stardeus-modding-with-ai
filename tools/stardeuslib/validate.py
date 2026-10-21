"""Checks a mod the way the game will load it, before the game gets the chance to complain."""
from __future__ import annotations

import bisect
import csv
import difflib
import hashlib
import io
import json
import re
import shutil
from functools import cached_property
from pathlib import Path

from . import catalog, jsonc, links, mods, patch, snapshot
from .defs import CHILD_IGNORED, RESEARCH_DROPPED, DefIndex, merge_property, name_key
from .jpeg import image_info
from .schema import Validator
from .util import LOCAL, TEMPLATES, UserError, rel, write_text

# SelfInit skips assemblies whose name starts with one of these (Game.Utils SelfInit.cs)
ASSEMBLY_BLACKLIST = ("Unity", "mscorlib", "netstandard", "KLUnityUtils", "ProjectDawn.",
                      "MessagePack", "ThirdParty", "Uween", "Microsoft.", "Bee.", "0Harmony",
                      "AutomaticGraphLayout", "ExCSS", "System", "websocket", "Newtonsoft",
                      "Mono.", "com.rlabrecque.")
# Workshop ids that ship with the official template and examples: never upload under them
KNOWN_TEMPLATE_WORKSHOP_IDS = {"2681464044"}
SOUND_SUFFIXES = {".ogg", ".wav", ".mp3"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
GRAPHIC_KEYS = {"Graphic", "Icon", "IconId", "Sprite", "SpriteId", "PreviewIcon"}
_PLACEHOLDER = re.compile(r"\{(\d+)(?:[:,][^}]*)?\}")


class Report:
    def __init__(self, title: str):
        self.title = title
        self.items: list[tuple[str, str, str]] = []

    def add(self, severity: str, where: str, message: str) -> None:
        self.items.append((severity, where, message))

    def error(self, where, message):
        self.add("error", where, message)

    def warn(self, where, message):
        self.add("warning", where, message)

    def info(self, where, message):
        self.add("info", where, message)

    def count(self, severity: str) -> int:
        return sum(1 for s, _, _ in self.items if s == severity)

    def render(self, verbose: bool) -> str:
        lines = [self.title]
        order = {"error": 0, "warning": 1, "info": 2}
        shown = [i for i in self.items if verbose or i[0] != "info"]
        for severity, where, message in sorted(shown, key=lambda i: (order[i[0]], i[1])):
            prefix = {"error": "ERROR  ", "warning": "WARNING", "info": "info   "}[severity]
            lines.append(f"  {prefix} {where}: {message}" if where else f"  {prefix} {message}")
        hidden = len(self.items) - len(shown)
        summary = f"  {self.count('error')} errors, {self.count('warning')} warnings"
        if hidden:
            summary += f", {hidden} notes (show them with --verbose)"
        lines.append(summary)
        return "\n".join(lines)


class Context:
    """What the game itself provides, read from the workspace's snapshot of the install."""

    def __init__(self, paths: dict):
        self.paths = paths
        self.snap = snapshot.current(paths)
        self.core = self.snap / "Core"
        self.order = mods.load_order(self.snap)
        self._schemas: dict[str, Validator | None] = {}
        self.missing_schemas: set[str] = set()

    def schema(self, name: str) -> Validator | None:
        if name not in self._schemas:
            path = self.core / "Config/Schemas" / name
            if path.is_file():
                data, _ = jsonc.load(path)
                self._schemas[name] = Validator(data)
            else:
                self._schemas[name] = None
                self.missing_schemas.add(name)
        return self._schemas[name]

    @cached_property
    def core_defs(self) -> DefIndex:
        index = DefIndex()
        index.load_dir(self.core / "Definitions", "Core")
        return index

    @cached_property
    def disabled_mods(self) -> dict[str, dict]:
        """Mod Id -> entry of the game's DisabledMods.json: versions it refuses to load."""
        path = self.snap / "DisabledMods.json"
        if not path.is_file():
            return {}
        try:
            data, _ = jsonc.load(path)
        except jsonc.JsoncError:
            return {}
        return {str(e.get("Id")): e for e in (data or {}).get("Mods") or [] if e.get("Id")}

    @cached_property
    def sprites(self) -> list[str]:
        path = self.snap / "graphics.txt"
        return sorted(path.read_text(encoding="utf-8").split()) if path.is_file() else []

    @cached_property
    def ref_src(self) -> Path:
        return self.core / "ReferenceSourceCode"

    @cached_property
    def core_components(self) -> set[str]:
        names = set()
        for e in self.core_defs.entries.values():
            for c in e["data"].get("Components") or []:
                if isinstance(c, dict) and c.get("Component"):
                    names.add(c["Component"])
        if self.ref_src.is_dir():
            pattern = re.compile(r"class\s+(\w+?)Comp\s*:\s*BaseComponent<")
            for f in self.ref_src.rglob("*Comp.cs"):
                for m in pattern.finditer(f.read_text(encoding="utf-8-sig", errors="replace")):
                    names.add(m.group(1))
        return names

    @cached_property
    def component_files(self) -> dict[str, Path]:
        out = {}
        if self.ref_src.is_dir():
            for f in self.ref_src.rglob("*Comp.cs"):
                out.setdefault(f.stem[:-4], f)
        return out

    def component_keys(self, component: str) -> set[str] | None:
        f = self.component_files.get(component)
        if f is None:
            return None
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        keys = set(re.findall(r"PropertyIdH\.(\w+)", text))
        keys |= set(re.findall(r'Hashes\.S\("(\w+)"\)', text))
        return keys

    @cached_property
    def core_layers(self) -> set[str]:
        return {e["data"]["Layer"] for e in self.core_defs.entries.values()
                if isinstance(e["data"].get("Layer"), str)}

    @cached_property
    def core_english(self) -> dict[str, str]:
        return read_translations(self.core / "Translations/English.csv")[0]

    def sprite_exists(self, sprite_id: str, extra: list[str]) -> bool:
        for ids in (self.sprites, extra):
            i = bisect.bisect_left(ids, sprite_id)
            if i < len(ids) and (ids[i] == sprite_id or ids[i].startswith(sprite_id + "_")):
                return True
        return False


def _version_key(v: str):
    v = v.replace("v", "")
    rc = None
    if "-rc" in v:
        v, _, rc_s = v.partition("-rc")
        rc = int(rc_s) if rc_s.isdigit() else 0
    parts = v.split(".")
    if not all(p.isdigit() for p in parts):
        return None
    return [int(p) for p in parts], (1, 0) if rc is None else (0, rc)


def version_newer(v1: str, v2: str) -> bool:
    """The game's VersionInfo.IsVersionNewerWithRC: is v1 above v2 (a release sorts after its rcs)."""
    a, b = _version_key(v1), _version_key(v2)
    if a is None or b is None:
        return False
    n = max(len(a[0]), len(b[0]))
    pa, pb = a[0] + [0] * (n - len(a[0])), b[0] + [0] * (n - len(b[0]))
    return pa > pb if pa != pb else a[1] > b[1]


def read_translations(path: Path) -> tuple[dict[str, str], list[str]]:
    """Returns (key -> text, problems). The game skips the first line as a header."""
    problems = []
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    out: dict[str, str] = {}
    for n, row in enumerate(rows[1:], start=2):
        if not row or not any(cell.strip() for cell in row):
            continue
        key = row[0].strip()
        if len(row) < 2:
            problems.append(f"line {n}: no translation column")
            continue
        if len(row) != 4:
            problems.append(f"line {n}: {len(row)} columns, the game expects 4 (key,translation,version,comment)")
        if key in out:
            problems.append(f'line {n}: key "{key}" appears twice')
        out[key] = row[1]
    return out, problems


def placeholders(s: str) -> set[str]:
    return set(_PLACEHOLDER.findall(s or ""))


def _walk_json(mod_dir: Path):
    for p in sorted(mod_dir.rglob("*.json")):
        parts = p.relative_to(mod_dir).parts
        if parts[0].startswith(".") or parts[0] in ("obj", "bin"):
            continue
        yield p


def validate_mod(mod: mods.Mod, ctx: Context, all_mods: list[mods.Mod]) -> Report:
    r = Report(f"{mod.id} ({rel(mod.dir)})")
    where = lambda p: p.relative_to(mod.dir).as_posix()  # noqa: E731

    # ModInfo
    if mod.info_error:
        r.error("ModInfo.json", mod.info_error)
    else:
        v = ctx.schema("ModInfo.schema.json")
        if v:
            for ptr, msg in v.validate(mod.info):
                r.error("ModInfo.json", f"{ptr}: {msg}")
        for key in ("Id", "Name", "Description"):
            if not str(mod.info.get(key) or "").strip():
                sev = r.error if key == "Id" else r.warn
                sev("ModInfo.json", f'"{key}" is empty (the Workshop upload requires it)')
        if "*" in str(mod.info.get("ModVersion", "")):
            r.warn("ModInfo.json", '"ModVersion" must not contain *; the game replaces it with 0')
        listed = ctx.disabled_mods.get(mod.id)
        if listed is not None:
            version = str(mod.info.get("ModVersion") or "1.0.0").replace("*", "0")
            if not listed.get("Version") or not version_newer(version, listed["Version"]):
                why = f" ({listed['Reason']})" if listed.get("Reason") else ""
                r.error("ModInfo.json", f'this game version refuses to load "{mod.id}" '
                                        f'{listed.get("Version") or "in any version"} and older'
                                        f"{why}: fix the mod and raise ModVersion above "
                                        f'{listed.get("Version") or "it"} before uploading')
        if not mod.info.get("GameVersion"):
            r.warn("ModInfo.json", f'"GameVersion" is not set (this game is {ctx.paths.get("game_version")})')
        ids = [m.id for m in all_mods]
        if ids.count(mod.id) > 1:
            r.error("ModInfo.json", f'another mod in mods/ also has the Id "{mod.id}"; the game loads only one')
        for dep in mod.info.get("Dependencies") or []:
            if dep != "Core" and dep not in ids:
                r.warn("ModInfo.json", f'dependency "{dep}" is not in mods/; players need it installed')
        if re.search(r"\s", mod.id):
            r.warn("ModInfo.json", "the Id contains spaces; other mods refer to it in Dependencies")
        if mod.id.endswith("Template"):
            r.warn("ModInfo.json", 'avoid Ids ending in "Template": the game treats such folders specially')

    # Version folders
    for top in mods.TOP_FOLDERS:
        found = mod.candidates(top)
        if len(found) > 1:
            r.warn(where(found[1]), f"ignored on this game version: the game reads {where(found[0])} "
                                    "instead (a mod uses one version folder per kind of content)")

    patches_dir = mod.content("Patches")
    patch_files: list[Path] = []
    all_json = list(_walk_json(mod.dir))
    mod_sprites = _mod_sprites(mod)

    for f in all_json:
        rel_path = where(f)
        if rel_path == "ModInfo.json":
            continue
        if patches_dir and _is_under(f, patches_dir):
            patch_files.append(f)
            continue
        if any(_is_under(f, c) for c in mod.candidates("Patches")):
            continue  # a shadowed Patches folder, reported above
        try:
            data, notes = jsonc.load(f)
        except jsonc.JsoncError as e:
            r.error(rel_path, f"not valid JSON: {e}")
            continue
        for note in notes:
            r.warn(rel_path, f"{note}; remove it to be safe")
        stripped = mod.strip_version(f)
        schema_name = catalog.schema_for(f"Mods/{mod.dir.name}/{stripped}")
        if schema_name is None:
            if stripped.startswith(("Definitions/", "Config/")):
                r.warn(rel_path, "no game loader reads JSON from this folder; check the folder name "
                                 "against the Core mod")
            continue
        v = ctx.schema(schema_name)
        if v:
            for ptr, msg in v.validate(data):
                r.error(rel_path, f"{ptr}: {msg}")
        if stripped.startswith("Config/") and (ctx.core / stripped).is_file():
            if stripped.startswith("Config/Tunable/"):
                r.info(rel_path, "tunable values override the game's by key")
            else:
                r.warn(rel_path, "same path as a Core file: it replaces the whole Core file, and game "
                                 "updates to it no longer reach your players. A patch changes only "
                                 "what you need")

    _check_defs(mod, ctx, all_mods, r, mod_sprites)
    _check_patches(mod, ctx, all_mods, patch_files, r)
    _check_translations(mod, ctx, r)
    _check_assets(mod, ctx, r)
    _check_code(mod, r)
    _check_upload(mod, r)
    _check_link(mod, ctx, r)
    return r


def _is_under(f: Path, folder: Path) -> bool:
    try:
        f.relative_to(folder)
        return True
    except ValueError:
        return False


def _mod_sprites(mod: mods.Mod) -> list[str]:
    g = mod.content("Graphics")
    if not g:
        return []
    return sorted((p.relative_to(g).with_suffix("")).as_posix()
                  for p in g.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)


def _all_defs(ctx: Context, all_mods: list[mods.Mod]) -> DefIndex:
    """Core plus every workspace mod, the way the game would see them together."""
    index = DefIndex()
    index.entries = dict(ctx.core_defs.entries)
    for m in all_mods:
        d = m.content("Definitions")
        if d:
            other = DefIndex()
            other.load_dir(d, m.id)
            for k, e in other.entries.items():
                index.entries.setdefault(k, e)
    return index


def _check_defs(mod, ctx: Context, all_mods, r: Report, mod_sprites: list[str]) -> None:
    defs_dir = mod.content("Definitions")
    if not defs_dir:
        return
    own = DefIndex()
    own.load_dir(defs_dir, mod.id)
    combined = _all_defs(ctx, all_mods)
    for def_id, e in own.entries.items():
        combined.entries[def_id] = e
    translations = _mod_translations(mod)
    mod_code_components = _mod_components(mod)
    where_def = lambda e: e["file"].relative_to(mod.dir).as_posix()  # noqa: E731

    for def_id, e in own.entries.items():
        data, at = e["data"], where_def(e)
        if def_id in ctx.core_defs.entries:
            r.error(at, f'"{def_id}" already exists in Core; the game refuses a mod def with the '
                        "same id. Change the Core def with a patch instead")
            continue
        for other in all_mods:
            od = other.content("Definitions")
            if other is not mod and od and (od / f"{def_id}.json").is_file():
                r.error(at, f'mod "{other.id}" defines the same def id; only one of them loads')
        if not data.get("IsAbstract") and not data.get("Layer"):
            r.error(at, '"Layer" is required in every def that is not abstract, even when it has '
                        "a ParentId (the child's Layer replaces the parent's)")
        elif data.get("Layer") and ctx.core_layers and data["Layer"] not in ctx.core_layers:
            hint = difflib.get_close_matches(data["Layer"], sorted(ctx.core_layers), n=1)
            r.warn(at, f'Layer "{data["Layer"]}" is not used by any Core def'
                       + (f' (did you mean "{hint[0]}"?)' if hint else ""))
        parent_id = data.get("ParentId")
        parent = combined.get(parent_id) if parent_id else None
        if parent_id and parent is None:
            hint = difflib.get_close_matches(parent_id, list(combined.entries), n=1)
            r.error(at, f'ParentId "{parent_id}" does not exist'
                        + (f' (did you mean "{hint[0]}"?)' if hint else "")
                        + "; the game marks the mod as broken")
        if parent_id:
            for key in CHILD_IGNORED:
                if key in data:
                    r.warn(at, f'"{key}" is ignored in a def with a ParentId (the parent\'s value is used)')
            for key in RESEARCH_DROPPED:
                if key in (data.get("Researchable") or {}):
                    r.warn(at, f'"Researchable.{key}" is dropped when a def has a ParentId')
        effective_parent = combined.effective(parent_id) if parent else None
        seen = set()
        for i, comp in enumerate(data.get("Components") or []):
            if not isinstance(comp, dict) or not comp.get("Component"):
                r.error(at, f"Components/{i} has no \"Component\" name")
                continue
            name = comp["Component"]
            if name in seen:
                r.error(at, f'component "{name}" appears twice; the game rejects the def')
            seen.add(name)
            if name not in ctx.core_components and name not in mod_code_components:
                hint = difflib.get_close_matches(name, sorted(ctx.core_components), n=1)
                r.warn(at, f'component "{name}" is not in the game'
                           + (f' (did you mean "{hint[0]}"?)' if hint else "")
                           + "; fine only if your C# code adds it")
            _check_properties(at, name, comp, ctx, r, effective_parent, mod_sprites)
        for prereq in (data.get("Researchable") or {}).get("Prerequisites") or []:
            if prereq not in combined.entries:
                r.error(at, f'research prerequisite "{prereq}" does not exist; the game marks the mod as broken')
        icon = data.get("PreviewIcon")
        if icon and not ctx.sprite_exists(icon, mod_sprites):
            r.warn(at, f'PreviewIcon "{icon}" is not a sprite in Core or this mod')
        if not data.get("IsAbstract") and not data.get("UseParentTexts"):
            key = name_key(def_id, data)
            if key not in translations and key not in ctx.core_english:
                r.warn(at, f'no translation for the name key "{key}"; the game shows the raw key. '
                           "Add it to Translations/English.csv")
            texts = translations.get(key) or ctx.core_english.get(key) or ""
            if placeholders(texts) and not data.get("TranslationVars"):
                r.warn(at, f'the name "{texts}" has placeholders but the def sets no TranslationVars')


def _check_properties(at, comp_name, comp, ctx: Context, r: Report, effective_parent, mod_sprites):
    known = ctx.component_keys(comp_name)
    parent_props = {}
    if effective_parent:
        for c in effective_parent.get("Components") or []:
            if c.get("Component") == comp_name:
                parent_props = {p.get("Key"): p for p in c.get("Properties") or [] if isinstance(p, dict)}
    keys = set()
    for j, prop in enumerate(comp.get("Properties") or []):
        if not isinstance(prop, dict) or not prop.get("Key"):
            r.error(at, f'{comp_name}: property {j} has no "Key"')
            continue
        key = prop["Key"]
        if key in keys:
            r.error(at, f'{comp_name}: property "{key}" appears twice')
        keys.add(key)
        values = [k for k in prop if k not in ("Key", "IsUsed")]
        if not values:
            r.warn(at, f'{comp_name}.{key} has no value (add "Int", "Float", "Bool", "String"...)')
        if known is not None and key not in known:
            hint = difflib.get_close_matches(key, sorted(known), n=1)
            r.warn(at, f'{comp_name}.{key}: the component\'s code does not read this key'
                       + (f' (did you mean "{hint[0]}"?)' if hint else "")
                       + "; check its *Comp.cs in the reference source")
        if key in parent_props:
            before = parent_props[key]
            after = merge_property(before, prop)
            for field in ("Int", "Float", "Bool"):
                if before.get(field) not in (None, 0, False) and field not in prop \
                        and after.get(field) in (0, False):
                    r.warn(at, f'{comp_name}.{key}: the parent sets "{field}": {before[field]}, and a child '
                               f'property without "{field}" resets it to {after[field]}')
        s = prop.get("String")
        if isinstance(s, str) and (key in GRAPHIC_KEYS or key.endswith(("Graphic", "Sprite"))):
            if s and not ctx.sprite_exists(s, mod_sprites):
                r.warn(at, f'{comp_name}.{key}: sprite "{s}" is not in Core or this mod\'s Graphics')


def _mod_components(mod: mods.Mod) -> set[str]:
    names = set()
    for f in mod.dir.rglob("*.cs"):
        if f.relative_to(mod.dir).parts[0] in ("obj", "bin"):
            continue
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        names |= set(re.findall(r"class\s+(\w+?)Comp\s*:\s*BaseComponent<", text))
    return names


def _mod_translations(mod: mods.Mod) -> dict[str, str]:
    t = mod.content("Translations")
    if t and (t / "English.csv").is_file():
        return read_translations(t / "English.csv")[0]
    return {}


def _patch_target(mod: mods.Mod, raw: str) -> str:
    target = raw.replace("\\", "/").lstrip("/")
    first, _, rest = target.partition("/")
    if first in mod.order and first and rest:
        target = rest
    return target


def _check_patches(mod, ctx: Context, all_mods, files: list[Path], r: Report) -> None:
    results: dict[tuple[str, str], tuple] = {}
    for f in sorted(files):
        at = f.relative_to(mod.dir).as_posix()
        try:
            data, notes = jsonc.load(f)
        except jsonc.JsoncError as e:
            r.error(at, f"not valid JSON: {e}; the game marks the mod as broken")
            continue
        for note in notes:
            r.warn(at, f"{note}; remove it to be safe")
        if not isinstance(data, dict) or not data.get("target"):
            r.error(at, '"target" is missing; the game marks the mod as broken')
            continue
        unknown = sorted(set(data) - {"target", "targetMod", "operations"})
        for k in unknown:
            hint = difflib.get_close_matches(k, ["target", "targetMod", "operations"], n=1)
            r.warn(at, f'unknown key "{k}"' + (f' (did you mean "{hint[0]}"?)' if hint else ""))
        target_mod = data.get("targetMod") or "Core"
        target = _patch_target(mod, str(data["target"]))
        if target.endswith("ModInfo.json"):
            r.error(at, "ModInfo.json cannot be patched")
            continue
        if target_mod == "Core":
            base = ctx.core / target
        else:
            other = next((m for m in all_mods if m.id == target_mod), None)
            if other is None:
                r.warn(at, f'targetMod "{target_mod}" is not in mods/, so the patch cannot be checked; '
                           "it does nothing for players who do not have that mod")
                continue
            base = other.dir / target
        if not base.is_file():
            hint = _closest_file(ctx.core, target) if target_mod == "Core" else None
            r.error(at, f'target "{target}" does not exist in {target_mod}, so the patch does nothing'
                        + (f' (did you mean "{hint}"?)' if hint else ""))
            continue
        key = (target_mod, target)
        if key not in results:
            try:
                doc, _ = jsonc.load(base)
            except jsonc.JsoncError as e:
                r.error(at, f"cannot read the target {target}: {e}")
                continue
            results[key] = (doc, [])
        doc, sources = results[key]
        doc, problems = patch.apply_patch(doc, data)
        results[key] = (doc, sources + [at])
        for p in problems:
            (r.error if p.severity == "error" else r.warn)(at, str(p))

    out_root = LOCAL / "patched" / mod.dir.name
    if out_root.is_dir() and not links.is_link(out_root):
        shutil.rmtree(out_root)
    for (target_mod, target), (doc, sources) in results.items():
        schema_name = catalog.schema_for(f"Mods/{target_mod}/{target}")
        v = ctx.schema(schema_name) if schema_name else None
        if v:
            for ptr, msg in v.validate(doc):
                r.error(", ".join(sources), f"after patching {target}: {ptr}: {msg}")
        header = "".join(f"// - {s}\n" for s in sources)
        write_text(out_root / target_mod / target,
                   f"// What {target} looks like after this mod's patches (simulated)\n"
                   f"// Patches:\n{header}{json.dumps(doc, indent=4, ensure_ascii=False)}\n")
    if results:
        r.info("", f"simulated patch results: {rel(out_root)}/")


def _closest_file(root: Path, target: str) -> str | None:
    parent = (root / target).parent
    if not parent.is_dir():
        return None
    names = [p.name for p in parent.iterdir()]
    hint = difflib.get_close_matches(Path(target).name, names, n=1)
    return (Path(target).parent / hint[0]).as_posix() if hint else None


def _check_translations(mod, ctx: Context, r: Report) -> None:
    t = mod.content("Translations")
    if not t:
        return
    core_locales = {p.stem for p in (ctx.core / "Translations").glob("*.csv")}
    for f in sorted(t.glob("*.csv")):
        at = f.relative_to(mod.dir).as_posix()
        if f.stem not in core_locales:
            r.info(at, f'"{f.stem}" is not one of the game\'s languages ({", ".join(sorted(core_locales))})')
        first = f.read_text(encoding="utf-8-sig", errors="replace").splitlines()[:1]
        if first and "." in first[0].split(",")[0] and not first[0].lower().startswith("key"):
            r.warn(at, "the game always skips the first line as a header, and this one looks like "
                       "a translation")
        entries, problems = read_translations(f)
        for p in problems:
            r.warn(at, p)
        for key, value in entries.items():
            if not value.strip():
                r.warn(at, f'"{key}" has an empty translation')
            core_value = ctx.core_english.get(key)
            if core_value is not None:
                if placeholders(core_value) != placeholders(value):
                    r.error(at, f'"{key}" overrides a game text but its placeholders differ from the '
                                f'game\'s "{core_value}"; the game skips this override')
                else:
                    r.info(at, f'"{key}" replaces a game text (only for players using {f.stem})')


def _check_assets(mod, ctx: Context, r: Report) -> None:
    g = mod.content("Graphics")
    if g:
        for p in g.rglob("*"):
            if p.is_file() and p.suffix.lower() not in IMAGE_SUFFIXES and p.suffix.lower() != ".json":
                r.info(p.relative_to(mod.dir).as_posix(), "the game loads only .png and .jpg from Graphics")
        for sprite in _mod_sprites(mod):
            i = bisect.bisect_left(ctx.sprites, sprite)
            if i < len(ctx.sprites) and ctx.sprites[i] == sprite:
                r.info(f"Graphics/{sprite}", "replaces the game's sprite with the same path")
    s = mod.content("Sounds")
    if s:
        for p in s.rglob("*"):
            if p.is_file() and p.suffix.lower() not in SOUND_SUFFIXES:
                r.warn(p.relative_to(mod.dir).as_posix(), "the game loads only .ogg, .wav and .mp3 sounds")


def _assembly_name(csproj: Path) -> str | None:
    m = re.search(r"<AssemblyName>\s*([^<]+?)\s*</AssemblyName>",
                  csproj.read_text(encoding="utf-8-sig", errors="replace"))
    return m.group(1) if m else csproj.stem


def _check_code(mod, r: Report) -> None:
    sources = [p for p in mod.dir.rglob("*.cs") if p.relative_to(mod.dir).parts[0] not in ("obj", "bin")
               and "obj" not in p.relative_to(mod.dir).parts]
    projects = [p for p in mod.dir.rglob("*.csproj") if "obj" not in p.relative_to(mod.dir).parts]
    libs = mod.content("Libraries")
    dlls = sorted(libs.glob("*.dll")) if libs else []
    for proj in projects:
        name = _assembly_name(proj) or ""
        at = proj.relative_to(mod.dir).as_posix()
        if name == "Stardeus_Mod_Template":
            r.error(at, "AssemblyName is still Stardeus_Mod_Template; the game refuses that DLL")
        elif name.startswith(ASSEMBLY_BLACKLIST):
            r.error(at, f'AssemblyName "{name}" starts with a reserved prefix; the game does not run '
                        "[SelfInit] methods in it. Pick another name")
    for dll in dlls:
        at = dll.relative_to(mod.dir).as_posix()
        if dll.name == "Stardeus_Mod_Template.dll":
            r.error(at, "the template's DLL: the game refuses to load it and the upload is rejected")
        elif dll.stem.startswith(ASSEMBLY_BLACKLIST):
            r.warn(at, "this DLL name starts with a reserved prefix, so [SelfInit] in it does not run")
    if sources and not dlls:
        r.warn("Code", "there is C# code but no DLL in Libraries/: build it with tools/stardeus build "
                       f"{mod.dir.name}")
    elif sources and dlls:
        newest_src = max(p.stat().st_mtime for p in sources)
        # A few seconds of slack: a fresh git checkout writes files in no particular order
        if all(d.stat().st_mtime < newest_src - 5 for d in dlls):
            r.warn("Libraries", "the DLL is older than the C# code: rebuild it")
    for name in mod.info.get("DLLFiles") or []:
        if not libs or not (libs / name).is_file():
            r.error("ModInfo.json", f'DLLFiles lists "{name}", which is not in Libraries/')


def _check_upload(mod, r: Report) -> None:
    cover = mod.dir / "ModCover.jpg"
    if not cover.is_file():
        r.warn("ModCover.jpg", "missing; the Workshop upload requires an 800x450 cover image")
    else:
        fmt, w, h = image_info(cover)
        if fmt is None:
            r.warn("ModCover.jpg", "not a JPEG or PNG image")
        elif fmt == "png":
            r.warn("ModCover.jpg", "is a PNG file with a .jpg name; save it as a real JPEG")
        if fmt and (w, h) != (800, 450):
            r.warn("ModCover.jpg", f"is {w}x{h}; the game asks for 800x450")
        if cover.stat().st_size > 1024 * 1024:
            r.warn("ModCover.jpg", "is over 1 MB; Steam refuses preview images that large")
        placeholder = TEMPLATES / "ModCover.jpg"
        if placeholder.is_file() and _sha1(placeholder) == _sha1(cover):
            r.warn("ModCover.jpg", "is still the workspace's placeholder; make your own before uploading")
    item = mod.dir / "SteamWorkshopItemId"
    if item.is_file():
        value = item.read_text(encoding="utf-8", errors="replace").strip()
        if value in KNOWN_TEMPLATE_WORKSHOP_IDS:
            r.error("SteamWorkshopItemId", "belongs to the official template's Workshop item; delete "
                                           "this file before your first upload")
        elif not value.isdigit():
            r.error("SteamWorkshopItemId", "should hold only the Workshop item number")
        else:
            r.info("SteamWorkshopItemId", f"uploads update Workshop item {value}; never delete this file")
    if mod.info and not mod.info.get("SteamWorkshop"):
        r.info("ModInfo.json", '"SteamWorkshop" is false: the upload button stays hidden until it is true')
    for p in mod.dir.rglob("*"):
        parts = p.relative_to(mod.dir).parts
        if parts[0].startswith(".") and (p.is_dir() or len(parts) > 1):
            continue  # first-level dot folders are left out of the upload
        if parts[-1].startswith(".") and not any(part.startswith(".") for part in parts[:-1]):
            r.error(p.relative_to(mod.dir).as_posix(),
                    "names starting with a dot fail the Workshop upload check; delete it")
        elif p.is_file() and p.suffix.lower() in (".exe", ".blend", ".blend1", ".blend2", ".blend3"):
            r.info(p.relative_to(mod.dir).as_posix(), "the game leaves this file out of the upload")


def _sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def _check_link(mod, ctx: Context, r: Report) -> None:
    game_mods = Path(ctx.paths["mods_dir"])
    link = game_mods / mod.dir.name
    if links.is_link(link):
        target = links.link_target(link)
        if target and links.same_path(target, mod.dir):
            return
        r.warn("", f"{link} points to {target}, not to this folder")
    elif link.exists():
        r.warn("", f"{link} is a separate copy, not a link: the game loads that copy, not this one")
    else:
        r.info("", f"not linked into the game yet (tools/stardeus link {mod.dir.name})")


def validate_core(ctx: Context) -> Report:
    """Validates the game's own JSON with its own schemas: proves the validator and catalog agree."""
    r = Report(f"Core ({ctx.paths.get('game_version')})")
    checked = 0
    for f in sorted(ctx.core.rglob("*.json")):
        relp = f.relative_to(ctx.core).as_posix()
        if relp.startswith(("Config/Schemas/", "ReferenceSourceCode/")) or relp == "ModInfo.json"                 or relp.endswith(".schema.json"):
            continue
        name = catalog.schema_for(f"Mods/Core/{relp}")
        if name is None:
            r.warn(relp, "no schema pattern matches this file")
            continue
        v = ctx.schema(name)
        if v is None:
            continue
        try:
            data, _ = jsonc.load(f)
        except jsonc.JsoncError as e:
            r.error(relp, str(e))
            continue
        checked += 1
        for ptr, msg in v.validate(data):
            r.error(relp, f"{ptr}: {msg}")
    r.info("", f"{checked} files checked")
    if ctx.missing_schemas:
        r.info("", f"{len(ctx.missing_schemas)} schemas are not shipped with this game version: "
                   + ", ".join(sorted(ctx.missing_schemas)))
    return r


def run(names: list[str], paths: dict, verbose: bool) -> int:
    ctx = Context(paths)
    all_mods = mods.workspace_mods(ctx.order)
    if names == ["--core"]:
        reports = [validate_core(ctx)]
    else:
        targets = all_mods if not names else [mods.find_mod(n, ctx.order) for n in names]
        if not targets:
            raise UserError("There are no mods in mods/ yet. Create one with: tools/stardeus new <Id>")
        reports = [validate_mod(m, ctx, all_mods) for m in targets]
    for rep in reports:
        print(rep.render(verbose))
    if ctx.missing_schemas and names != ["--core"]:
        print(f"Note: this game version ships no schema for {', '.join(sorted(ctx.missing_schemas))}; "
              "those files were only checked for valid JSON.")
    return 1 if any(rep.count("error") for rep in reports) else 0
