"""Loads defs and computes the effective def the game builds from a ParentId chain.

The merge rules mirror ModLoader.ProcessDefsWithParents, Researchable.Merge,
GenSpawnable.Merge and ComponentConfig.MergeWith in the reference source. Read those when a
result here looks surprising: the game's behavior is the truth.
"""
from __future__ import annotations

import copy
from pathlib import Path

from . import jsonc

# Def fields the game takes from the parent even when the child sets them
CHILD_IGNORED = ("InternalValue", "IsBeing")
# Researchable fields Researchable.Merge does not copy, so a def with a ParentId loses them
RESEARCH_DROPPED = ("IsDiscoverable", "IsAutoDiscovered", "UnlockCost",
                    "SkipCostValidation", "CanBeResearchedNow")
_PROP_SCALARS = (("Int", 0), ("Float", 0), ("Bool", False), ("PosIdx", 0),
                 ("Vector2", {"x": 0, "y": 0}))
_PROP_REFS = ("String", "BoolSet", "IntSet", "StringSet", "FloatSet", "Vector2Set", "RawMaterials")


class DefIndex:
    def __init__(self):
        self.entries: dict[str, dict] = {}
        self.errors: list[tuple[Path, str]] = []

    def load_dir(self, defs_dir: Path, origin: str) -> None:
        for f in sorted(defs_dir.rglob("*.json")):
            rel = f.relative_to(defs_dir).with_suffix("").as_posix()
            try:
                data, _ = jsonc.load(f)
            except (jsonc.JsoncError, OSError) as e:
                self.errors.append((f, str(e)))
                continue
            if not isinstance(data, dict):
                self.errors.append((f, "a def must be a JSON object"))
                continue
            def_id = data.get("Id") or rel
            self.entries[def_id] = {"data": data, "file": f, "origin": origin}

    def get(self, def_id: str):
        e = self.entries.get(def_id)
        return e["data"] if e else None

    def chain(self, def_id: str) -> list[str]:
        """[def, parent, grandparent, ...]; stops at a missing parent or a cycle."""
        out, seen = [], set()
        cur = def_id
        while cur and cur in self.entries and cur not in seen:
            out.append(cur)
            seen.add(cur)
            cur = self.entries[cur]["data"].get("ParentId")
        return out

    def effective(self, def_id: str) -> dict | None:
        ids = self.chain(def_id)
        if not ids:
            return None
        root = copy.deepcopy(self.entries[ids[-1]]["data"])
        root["Id"] = ids[-1]
        result = root
        for child in reversed(ids[:-1]):
            result = merge(result, self.entries[child]["data"], child)
        return result

    def missing_parent(self, def_id: str) -> str | None:
        ids = self.chain(def_id)
        if not ids:
            return None
        last = self.entries[ids[-1]]["data"].get("ParentId")
        return last if last and last not in self.entries else None


def _truthy(d: dict, key: str) -> bool:
    return bool(d.get(key))


def merge_property(ours: dict, theirs: dict) -> dict:
    p = copy.deepcopy(ours)
    for key in _PROP_REFS:
        if theirs.get(key) is not None:
            p[key] = copy.deepcopy(theirs[key])
    for key, default in _PROP_SCALARS:
        # The game copies these from the child even when the child leaves them out
        value = theirs.get(key, default)
        if key in theirs or key in p:
            p[key] = copy.deepcopy(value)
    return p


def merge_properties(ours, theirs) -> list:
    ours = copy.deepcopy(ours or [])
    theirs = copy.deepcopy(theirs or [])
    if not theirs:
        return ours
    if not ours:
        return theirs
    new_values = []
    for t in theirs:
        for i, o in enumerate(ours):
            if o.get("Key") == t.get("Key"):
                ours[i] = merge_property(o, t)
                break
        else:
            new_values.append(t)
    return new_values + ours if new_values else ours


def merge_researchable(base, res):
    if base is None and res is None:
        return None
    base, res = base or {}, res or {}
    r = {}
    for key in ("UnlockValue", "Storage"):
        v = max(base.get(key, 0) or 0, res.get(key, 0) or 0)
        if v or key in base or key in res:
            r[key] = v
    if _truthy(base, "IsTreeNode") or _truthy(res, "IsTreeNode"):
        r["IsTreeNode"] = True
    for key in ("Prerequisites", "UnlockEffects", "DatoidCosts"):
        v = res.get(key) if res.get(key) else base.get(key)
        if v is not None:
            r[key] = copy.deepcopy(v)
    return r


def merge_spawnable(base, s):
    if base is None:
        return copy.deepcopy(s)
    if s is None:
        return copy.deepcopy(base)
    override = ((s.get("Chance") or 0) > 0 or (s.get("ChanceLocked") or 0) > 0
                or (s.get("TierDiff") or 0) != 0 or s.get("Category") is not None
                or (s.get("SkipOwned") or 0) > 0)
    return copy.deepcopy(s if override else base)


def merge(parent: dict, child: dict, child_id: str) -> dict:
    final = copy.deepcopy(parent)

    def put(key, value, keep_default=False):
        if value is None or (value in (False, 0) and not keep_default
                             and key not in parent and key not in child):
            final.pop(key, None)
        else:
            final[key] = copy.deepcopy(value)

    final["Id"] = child_id
    if (child.get("ToolPath") or "").strip():
        final["ToolPath"] = child["ToolPath"]
    put("BuildGroup", child.get("BuildGroup"))  # never inherited
    put("IsUnfinished", _truthy(parent, "IsUnfinished") or _truthy(child, "IsUnfinished"))
    put("ParentId", child.get("ParentId"))
    put("IgnoreMarket", _truthy(parent, "IgnoreMarket") or _truthy(child, "IgnoreMarket"))
    if child.get("Seasonal") is not None:
        final["Seasonal"] = copy.deepcopy(child["Seasonal"])
    put("Tier", max(parent.get("Tier", 0) or 0, child.get("Tier", 0) or 0))
    rv = child.get("ResearchValue", 0) or 0
    put("ResearchValue", rv if rv > 0 else parent.get("ResearchValue", 0))
    wv = child.get("WealthValueMul", 1)
    wv = wv if wv != 1 else parent.get("WealthValueMul", 1)
    if wv != 1:
        final["WealthValueMul"] = wv
    else:
        final.pop("WealthValueMul", None)
    put("IsImportant", _truthy(parent, "IsImportant") or _truthy(child, "IsImportant"))
    put("IsAbstract", _truthy(parent, "IsAbstract") and _truthy(child, "IsAbstract"))
    put("Researchable", merge_researchable(parent.get("Researchable"), child.get("Researchable")))
    put("Spawnable", merge_spawnable(parent.get("Spawnable"), child.get("Spawnable")))
    put("Layer", child.get("Layer"))
    put("TranslationVars", child.get("TranslationVars"))
    put("UseParentTexts", _truthy(child, "UseParentTexts"))
    put("NameKey", child.get("NameKey"))
    put("DescKey", child.get("DescKey"))
    if (child.get("PreviewIcon") or "").strip():
        final["PreviewIcon"] = child["PreviewIcon"]
    put("SkipToolListing", _truthy(parent, "SkipToolListing") or _truthy(child, "SkipToolListing"))

    comps = copy.deepcopy(parent.get("Components") or [])
    added = []
    for comp in child.get("Components") or []:
        if not isinstance(comp, dict) or comp.get("Component") is None:
            continue
        existing = next((c for c in comps if c.get("Component") == comp["Component"]), None)
        if existing is None:
            added.append(copy.deepcopy(comp))
        else:
            existing["Properties"] = merge_properties(existing.get("Properties"), comp.get("Properties"))
    comps.extend(added)
    if comps:
        final["Components"] = comps
    return final


def name_key(def_id: str, data: dict) -> str:
    """Defs.Set: the translation key of a def's name unless NameKey is set."""
    return data.get("NameKey") or def_id.replace("/", ".").lower()


def desc_key(def_id: str, data: dict) -> str:
    return data.get("DescKey") or f"{name_key(def_id, data)}.desc"
