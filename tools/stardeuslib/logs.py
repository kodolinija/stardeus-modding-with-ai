"""Pulls what matters for modding out of Player.log."""
from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path

from .util import UserError

_PREFIX = re.compile(r"^\[[\d.]+m\|[\d.]+d\|-?\d+\]\s*")
_VERSION = re.compile(r"Stardeus [Vv]ersion: (\S+)")
_LOADED = re.compile(r"^Loading Mod: (.+? \[[^\]]*\])")
_DISABLED = re.compile(r"^Skipping disabled (?:pending )?mod: (.+)")
_DEV_DISABLED = re.compile(r"^Skipping dev disabled (?:pending )?mod: (.+)|Mod (\S+) with version .* is obsolete")
_DLL = re.compile(r"^Loading mod DLL file: (.+)")
_PATCHED = re.compile(r"^Creating patched: (\S+)")
# What ModLoader, JSONPatcher, ModRegistry, Translations and the def loader log when mod
# content is wrong. Plain informational loading lines are left out on purpose.
_PROBLEM = re.compile(
    r"JSON Error|Json errors after|Failed deserializing|ModInfo parsing failed|"
    r"Marking mod .* broken|runtime broken|Skipping runtime broken|Mod Issue|Mod: <b>|"
    r"missing dependencies|Failed resolving some dependencies|Dependency for mod|dependency not found|"
    r"Mod dependency is disabled|Patch target not defined|Patch target mod not found|"
    r"Failed parsing patch|Error while executing patch|Invalid patch operation|Operation '.*' is not supported|"
    r"path should start with slash|value is missing|Definitions could not be loaded|"
    r"Layer is not defined|Duplicate component|Duplicate property|component that does not exist|"
    r"Misconfigured|Researchable has null|missing prerequisite|Failed invoking RuntimeInitialize|Failed executing self init|"
    r"Failed loading assembly|runtime exception when loading code|Stardeus_Mod_Template|"
    r"SKIPPING|Skipping mod folder|already loaded from|placeholder|Mods override \d+ core|"
    r"Atlas not defined|Failed preloading texture|Could not find sprite|Sprite not found")
_EXCEPTION = re.compile(r"\b\w+Exception\b(:|$)")
_FRAME = re.compile(r"^\s+at |^\s*\(Filename|^\s*[\w.`<>+]+:[\w.`<>|]+ ?\(")
_GAME_FRAME = re.compile(r"^\s*(at )?(Game|KL|UnityEngine|System|Mono|Newtonsoft|Steamworks)\.")


def _add(store: "OrderedDict[str, int]", text: str) -> None:
    store[text] = store.get(text, 0) + 1


def triage(log: Path, mod: str | None, limit: int = 40) -> str:
    if not log.is_file():
        raise UserError(f"{log} does not exist. Start the game once (it writes the log while it runs).")
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    version = None
    loaded, disabled, dev_disabled, dlls, patched = [], [], [], [], []
    problems: "OrderedDict[str, int]" = OrderedDict()
    stacks: dict[str, list[str]] = {}
    wanted = (lambda t: mod.lower() in t.lower()) if mod else (lambda t: True)
    for i, raw in enumerate(lines):
        if _FRAME.match(raw):
            continue
        text = _PREFIX.sub("", raw).strip()
        if not text:
            continue
        m = _VERSION.search(text)
        if m:
            version = version or m.group(1)
            continue
        for pattern, bucket in ((_LOADED, loaded), (_DISABLED, disabled), (_DLL, dlls),
                                (_PATCHED, patched)):
            m = pattern.search(text)
            if m:
                bucket.append(m.group(1))
                break
        else:
            m = _DEV_DISABLED.search(text)
            if m:
                dev_disabled.append(m.group(1) or m.group(2))
            elif _PROBLEM.search(text) and wanted(text):
                _add(problems, text)
            elif _EXCEPTION.search(text):
                frames = []
                j = i + 1
                while j < len(lines) and len(frames) < 12 and _FRAME.match(lines[j]):
                    frames.append(lines[j].strip())
                    j += 1
                foreign = [f for f in frames if not _GAME_FRAME.match(f)]
                # Exceptions with code outside the game's namespaces in the stack likely come from mods
                if (mod and any(mod.lower() in f.lower() for f in frames + [text])) or \
                        (not mod and foreign):
                    _add(problems, text)
                    stacks.setdefault(text, frames[:8])
    out = [f"Log: {log}", f"Game version: {version or 'not in this log'}",
           "Mods loaded: " + (", ".join(dict.fromkeys(loaded)) or "none logged")]
    if disabled:
        out.append("Disabled (enable in Main Menu > Mods, then restart): "
                   + ", ".join(dict.fromkeys(disabled)))
    if dev_disabled:
        out.append("Disabled by the game as outdated (raise ModVersion when fixed): "
                   + ", ".join(dict.fromkeys(dev_disabled)))
    if dlls:
        out.append("Mod DLLs loaded: " + ", ".join(dict.fromkeys(d.split(": ")[-1] for d in dlls)))
    if patched:
        out.append(f"Files patched by mods: {len(set(patched))} (see tools/stardeus patched)")
    out.append(f"Problems{' about ' + mod if mod else ''}:")
    if not problems:
        out.append("  none found")
    for n, (text, count) in enumerate(problems.items()):
        if n >= limit:
            out.append(f"  ... {len(problems) - limit} more")
            break
        out.append(f"  - {text}" + (f"  (x{count})" if count > 1 else ""))
        for frame in stacks.get(text, []):
            out.append(f"      {frame}")
    return "\n".join(out)
