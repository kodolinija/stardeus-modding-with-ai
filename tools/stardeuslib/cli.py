"""Command line of the Stardeus modding workspace: tools/stardeus <command>."""
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import build, catalog, decompile, links, logs, mods, newmod, paths, snapshot, validate
from .defs import DefIndex
from .util import LOCAL, PATHS_FILE, ROOT, UserError, load_paths, read_saved, rel, write_json, write_text


def _props_xml(managed: str) -> str:
    return ("<Project>\n  <!-- Written by tools/stardeus setup -->\n  <PropertyGroup>\n"
            f"    <StardeusManaged>{Path(managed).as_posix()}</StardeusManaged>\n"
            "  </PropertyGroup>\n</Project>\n")


def _tool_status(info: dict) -> list[str]:
    out = [f"Python {sys.version.split()[0]}"]
    dotnet = shutil.which("dotnet")
    if dotnet:
        sdks = subprocess.run([dotnet, "--list-sdks"], capture_output=True, text=True).stdout.split("\n")
        sdks = [s.split()[0] for s in sdks if s.strip()]
        out.append(f".NET SDK: {', '.join(sdks) if sdks else 'only the runtime (C# mods need the SDK)'}")
    else:
        out.append(".NET SDK: not installed (needed only for C# mods and dnSpy's console)")
    dn = decompile.dnspy_dir(info) if info["os"] == "windows" else None
    out.append(f"dnSpy: {dn or 'not found (optional)'}")
    out.append(f"ilspycmd: {'found' if decompile.ilspy_command() else 'not found (optional)'}")
    out.append(f"git: {'found' if shutil.which('git') else 'not found (optional)'}")
    return out


def _write_vscode(info: dict) -> str:
    schemas = info.get("schemas_dir")
    if not schemas:
        return "VS Code: this game version ships no schemas"
    blocks = []
    for e in catalog.read_entries():
        path = Path(schemas) / e["schema"]
        if path.is_file():
            blocks.append({"fileMatch": e["fileMatch"], "url": path.as_uri()})
    body = json.dumps(blocks, indent=4).replace("\n", "\n    ")
    block = f'    // BEGIN stardeus schemas (tools/stardeus setup --vscode)\n    "json.schemas": {body},\n' \
            f"    // END stardeus schemas\n"
    settings = ROOT / ".vscode" / "settings.json"
    if not settings.exists():
        write_text(settings, '{\n    "files.associations": { "*.json": "jsonc" },\n' + block.rstrip(",\n") + "\n}\n")
        return f"VS Code: wrote {rel(settings)} ({len(blocks)} schemas)"
    text = settings.read_text(encoding="utf-8")
    m = re.search(r"    // BEGIN stardeus schemas.*?// END stardeus schemas\n", text, re.S)
    if not m:
        return (f"VS Code: {rel(settings)} exists without the stardeus markers; left unchanged. "
                "Delete it and run setup --vscode again to have it written.")
    write_text(settings, text[:m.start()] + block + text[m.end():])
    return f"VS Code: updated {rel(settings)} ({len(blocks)} schemas)"


def cmd_setup(a) -> int:
    saved = read_saved()
    info = paths.detect(a.game_dir, a.user_dir)
    tools = dict(saved.get("tools") or {})
    if a.dnspy:
        tools["dnspy_dir"] = str(Path(a.dnspy).expanduser())
    info["tools"] = tools
    info["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_json(PATHS_FILE, info)
    write_text(LOCAL / "stardeus.props", _props_xml(info["managed_dir"]))
    print(f"Stardeus {info['game_version'] or '(version unknown)'} found ({info['source']}):")
    for key in ("game_dir", "core_dir", "managed_dir", "user_dir", "mods_dir", "player_log"):
        print(f"  {key:12} {info[key]}")
    if not info["reference_source_dir"]:
        print("  Note: this install has no ReferenceSourceCode (demo builds ship none)")
    if not a.no_snapshot:
        snap, created = snapshot.make(info, force=a.refresh)
        print(f"Game snapshot: {rel(snap)} ({'created' if created else 'up to date'})")
    if a.vscode:
        print(_write_vscode(info))
    print("Tools:")
    for line in _tool_status(info):
        print(f"  {line}")
    print(f"Saved to {rel(PATHS_FILE)}. Next: tools/stardeus status")
    return 0


def cmd_status(a) -> int:
    saved = read_saved()
    if not saved:
        print("Not set up yet. Run: tools/stardeus setup")
        return 1
    try:
        now = paths.detect()
    except UserError as e:
        print(f"The game is no longer where setup found it: {e}")
        return 1
    print(f"Game: Stardeus {now['game_version'] or '(version unknown)'} at {now['game_dir']}")
    if now["snapshot_id"] != saved.get("snapshot_id") or not snapshot.is_complete(
            snapshot.path_for(now["snapshot_id"])):
        print(f"  The installed game changed since setup ({saved.get('snapshot_id')} -> "
              f"{now['snapshot_id']}). Run: tools/stardeus setup, then tools/stardeus diff")
    steam = now.get("steam") or {}
    if steam.get("target_build_id") and steam.get("build_id") and \
            steam["target_build_id"] != steam["build_id"] and steam["target_build_id"] != "0":
        print("  Steam has an update for Stardeus that is not installed yet")
    print(f"User folder: {now['user_dir']}")
    order = mods.load_order(snapshot.path_for(saved["snapshot_id"]))
    ws = mods.workspace_mods(order)
    print("Workspace mods (mods/):" if ws else "Workspace mods: none yet (tools/stardeus new <Id>)")
    game_mods = Path(now["mods_dir"])
    for m in ws:
        link = game_mods / m.dir.name
        if links.is_link(link) and links.same_path(links.link_target(link) or Path(), m.dir):
            state = "linked into the game"
        elif link.exists():
            state = "NOT linked: the game has a different folder with this name"
        else:
            state = f"not linked (tools/stardeus link {m.dir.name})"
        print(f"  {m.dir.name:28} {m.info.get('ModVersion', '?'):8} {state}")
    if game_mods.is_dir():
        others = [p for p in sorted(game_mods.iterdir())
                  if p.is_dir() and not any(links.same_path(p, game_mods / m.dir.name) for m in ws)]
        if others:
            print("Other folders in the game's Mods folder:")
            for p in others:
                kind = "link" if links.is_link(p) else "folder"
                note = " (disabled by its _DISABLED suffix)" if p.name.upper().endswith("_DISABLED") else ""
                print(f"  {p.name} [{kind}]{note}")
    print("Tools:")
    for line in _tool_status(now):
        print(f"  {line}")
    return 0


def cmd_new(a) -> int:
    info = load_paths()
    kinds = [k.strip() for k in a.kind.split(",") if k.strip()]
    folder = newmod.create(a.id, a.name, a.description, kinds, info)
    print(f"Created {rel(folder)}")
    if not a.no_link:
        target = newmod.link(folder, info)
        print(f"Linked into the game: {target}")
    print("Next: enable it in the game (Main Menu > Mods; new mods start disabled), then restart the game.")
    return 0


def cmd_link(a) -> int:
    info = load_paths()
    folder = mods.find_mod(a.mod, mods.load_order(None)).dir
    target = newmod.link(folder, info)
    print(f"{target} -> {rel(folder)}")
    return 0


def cmd_unlink(a) -> int:
    target = newmod.unlink(a.mod, load_paths())
    print(f"Removed the link {target} (the mod in mods/ is untouched)")
    return 0


def cmd_adopt(a) -> int:
    dest = newmod.adopt(a.folder, load_paths())
    print(f"Moved into {rel(dest)} and linked back into the game's Mods folder")
    return 0


def cmd_validate(a) -> int:
    names = ["--core"] if a.core else a.mods
    return validate.run(names, load_paths(), a.verbose)


def _index(info: dict, with_mods: bool) -> DefIndex:
    snap = snapshot.current(info)
    index = DefIndex()
    index.load_dir(snap / "Core/Definitions", "Core")
    if with_mods:
        for m in mods.workspace_mods(mods.load_order(snap)):
            d = m.content("Definitions")
            if d:
                index.load_dir(d, m.id)
    return index


def cmd_def(a) -> int:
    index = _index(load_paths(), True)
    if a.id not in index.entries:
        hint = difflib.get_close_matches(a.id, list(index.entries), n=5, cutoff=0.5)
        raise UserError(f'No def "{a.id}".' + (f" Close: {', '.join(hint)}" if hint else ""))
    chain = index.chain(a.id)
    print("Chain: " + " <- ".join(f"{d} ({index.entries[d]['origin']})" for d in chain))
    missing = index.missing_parent(a.id)
    if missing:
        print(f'Missing parent: "{missing}"')
    data = index.get(a.id) if a.raw else index.effective(a.id)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def _props_text(comp: dict) -> str:
    parts = []
    for p in comp.get("Properties") or []:
        vals = {k: v for k, v in p.items() if k not in ("Key", "IsUsed")}
        parts.append(f"{p.get('Key')}=" + ",".join(json.dumps(v) for v in vals.values()))
    return "; ".join(parts)


def cmd_find(a) -> int:
    index = _index(load_paths(), a.mods)
    rows = []
    for def_id in sorted(index.entries):
        if a.id and not re.search(a.id, def_id, re.I):
            continue
        raw = index.get(def_id)
        if a.parent and raw.get("ParentId") != a.parent:
            continue
        eff = index.effective(def_id) if not a.raw else raw
        if a.layer and (eff.get("Layer") or "") != a.layer:
            continue
        comps = [c for c in eff.get("Components") or [] if isinstance(c, dict)]
        if a.component:
            comps = [c for c in comps if c.get("Component") == a.component]
            if not comps:
                continue
        if a.property:
            hits = []
            for c in comps:
                for p in c.get("Properties") or []:
                    if p.get("Key") == a.property:
                        vals = {k: v for k, v in p.items() if k not in ("Key", "IsUsed")}
                        hits.append(f"{c.get('Component')}.{a.property}=" + json.dumps(vals))
            if not hits:
                continue
            rows.append(f"{def_id}  {'; '.join(hits)}")
        elif a.component:
            rows.append(f"{def_id}  {_props_text(comps[0])}")
        else:
            rows.append(def_id)
    for row in rows[:a.limit]:
        print(row)
    if len(rows) > a.limit:
        print(f"... {len(rows) - a.limit} more (use --limit)")
    print(f"{len(rows)} defs" + (" (effective values, ParentId merged)" if not a.raw else ""))
    return 0


def cmd_log(a) -> int:
    info = load_paths()
    path = Path(info["player_prev_log"] if a.prev else info["player_log"])
    print(logs.triage(path, a.mod))
    return 0


def cmd_patched(a) -> int:
    root = Path(load_paths()["patched_dir"])
    if not root.is_dir():
        print(f"{root} does not exist: the game writes it when it applies patches at startup")
        return 1
    if a.file:
        hits = [p for p in root.rglob("*") if p.is_file() and p.as_posix().endswith(a.file)]
        if not hits:
            raise UserError(f"No patched file ends with {a.file}")
        print(hits[0].read_text(encoding="utf-8", errors="replace"))
        return 0
    for p in sorted(root.rglob("*")):
        if p.is_file():
            print(p.relative_to(root).as_posix())
    return 0


def cmd_snapshot(a) -> int:
    info = paths.detect()
    snap, created = snapshot.make(info, force=a.force)
    print(f"{rel(snap)} ({'created' if created else 'already up to date'})")
    return 0


def cmd_diff(a) -> int:
    snaps = snapshot.all_snapshots()
    if len(snaps) < 2 and not (a.old and a.new):
        print("Only one snapshot exists. After the game updates, run tools/stardeus setup, then diff.")
        return 1

    def pick(name: str | None, default: Path) -> Path:
        if not name:
            return default
        for p, _ in snaps:
            if p.name.startswith(name):
                return p
        raise UserError(f'No snapshot starts with "{name}". Have: ' + ", ".join(p.name for p, _ in snaps))

    old = pick(a.old, snaps[-2][0])
    new = pick(a.new, snaps[-1][0])
    if a.file:
        print(snapshot.unified(old, new, a.file) or "No difference.")
        return 0
    result = snapshot.diff(old, new, a.path)
    print(f"{old.name} -> {new.name}")
    for kind in ("added", "removed", "changed"):
        items = result[kind]
        print(f"{kind}: {len(items)}")
        for item in items[:a.limit]:
            print(f"  {item}")
        if len(items) > a.limit:
            print(f"  ... {len(items) - a.limit} more (filter with --path, or --limit)")
    return 0


def cmd_decompile(a) -> int:
    return decompile.run(a.assembly, load_paths(), a.tool, a.out, a.type)


def cmd_build(a) -> int:
    info = load_paths()
    mod = mods.find_mod(a.mod, mods.load_order(None))
    return build.run(mod, info, a.configuration)


def cmd_sync_catalog(a) -> int:
    n = catalog.sync_from_vscode(Path(a.source))
    print(f"Wrote {rel(catalog.CATALOG)} with {n} entries")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools/stardeus", description="Stardeus modding workspace tools")
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    s = sub.add_parser("setup", help="find the game, write local/paths.json and snapshot the game files")
    s.add_argument("--game-dir", help="the folder that contains Stardeus.exe (when it is not found)")
    s.add_argument("--user-dir", help="the game's user folder (with Mods/, Saves/ and Player.log)")
    s.add_argument("--dnspy", help="folder where dnSpy is unzipped")
    s.add_argument("--vscode", action="store_true", help="map mod JSON files to the game's schemas in VS Code")
    s.add_argument("--refresh", action="store_true", help="recreate the snapshot")
    s.add_argument("--no-snapshot", action="store_true")
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("status", help="game version, snapshot freshness, mods and their links, tools")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("new", help="create a mod in mods/ and link it into the game")
    s.add_argument("id", help="mod Id: letters, digits and _, for example BetterBatteries")
    s.add_argument("--name")
    s.add_argument("--description")
    s.add_argument("--kind", default="patch",
                   help="comma separated: patch (change game files), content (new defs), csharp (code)")
    s.add_argument("--no-link", action="store_true")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("link", help="link mods/<mod> into the game's Mods folder")
    s.add_argument("mod")
    s.set_defaults(func=cmd_link)
    s = sub.add_parser("unlink", help="remove the game's link to mods/<mod> (keeps the mod)")
    s.add_argument("mod")
    s.set_defaults(func=cmd_unlink)
    s = sub.add_parser("adopt", help="move a mod from the game's Mods folder into mods/ and link it back")
    s.add_argument("folder")
    s.set_defaults(func=cmd_adopt)

    s = sub.add_parser("validate", help="check mods the way the game loads them")
    s.add_argument("mods", nargs="*", help="mod folders or Ids (default: all in mods/)")
    s.add_argument("--core", action="store_true", help="check the game's own files against its schemas")
    s.add_argument("--verbose", "-v", action="store_true", help="also show notes")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("def", help="show a def as the game builds it (ParentId chain merged)")
    s.add_argument("id", help="def id, for example Objects/Devices/Battery")
    s.add_argument("--raw", action="store_true", help="the file as written, without the merge")
    s.set_defaults(func=cmd_def)

    s = sub.add_parser("find", help="search defs by id, component, property, parent or layer")
    s.add_argument("--id", help="regular expression on the def id")
    s.add_argument("--component")
    s.add_argument("--property")
    s.add_argument("--parent")
    s.add_argument("--layer")
    s.add_argument("--raw", action="store_true", help="search the files as written")
    s.add_argument("--mods", action="store_true", help="include the workspace mods")
    s.add_argument("--limit", type=int, default=200)
    s.set_defaults(func=cmd_find)

    s = sub.add_parser("log", help="mod loading and mod errors from Player.log")
    s.add_argument("--mod", help="only lines about this mod (and exceptions)")
    s.add_argument("--prev", action="store_true", help="read Player-prev.log (the run before)")
    s.set_defaults(func=cmd_log)

    s = sub.add_parser("patched", help="list or print what the game's patcher produced in Patched/")
    s.add_argument("file", nargs="?", help="end of a path, for example Objects/Devices/Battery.json")
    s.set_defaults(func=cmd_patched)

    s = sub.add_parser("snapshot", help="copy the installed game's Core text files into local/game/")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_snapshot)

    s = sub.add_parser("diff", help="what changed in Core between two snapshots (game updates)")
    s.add_argument("old", nargs="?")
    s.add_argument("new", nargs="?")
    s.add_argument("--path", help="glob on Core-relative paths, for example 'Definitions/*'")
    s.add_argument("--file", help="show the changes of one Core-relative file")
    s.add_argument("--limit", type=int, default=100)
    s.set_defaults(func=cmd_diff)

    s = sub.add_parser("decompile", help="decompile a game DLL into local/decompiled/")
    s.add_argument("assembly", help="for example Game.Utils, KLUnityUtils or a .dll path")
    s.add_argument("--tool", choices=("dnspy", "ilspy"))
    s.add_argument("--type", help="print the file of this type afterwards")
    s.add_argument("--out")
    s.set_defaults(func=cmd_decompile)

    s = sub.add_parser("build", help="build a mod's C# project into its Libraries folder")
    s.add_argument("mod")
    s.add_argument("--configuration", default="Release")
    s.set_defaults(func=cmd_build)

    s = sub.add_parser("sync-catalog", help="maintainers: refresh tools/schema_catalog.json")
    s.add_argument("--from", dest="source", required=True,
                   help="a VS Code settings.json with the json.schemas block the game's generator writes")
    s.set_defaults(func=cmd_sync_catalog)
    return p


def main(argv: list[str]) -> int:
    args = parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except UserError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
