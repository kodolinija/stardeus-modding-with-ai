"""Which schema applies to which JSON file, using the file patterns the game's generator emits."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from . import jsonc
from .util import TOOLS, UserError, read_json, write_json

CATALOG = TOOLS / "schema_catalog.json"


def _glob_regex(pattern: str) -> re.Pattern:
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def read_entries() -> list[dict]:
    return read_json(CATALOG)["entries"]


@lru_cache(maxsize=1)
def entries() -> list[tuple[list[re.Pattern], str]]:
    return [([_glob_regex(p) for p in e["fileMatch"]], e["schema"]) for e in read_entries()]


def schema_for(mods_relative: str) -> str | None:
    """mods_relative looks like "Mods/<Mod>/Definitions/Objects/X.json"."""
    for patterns, schema in entries():
        if any(p.match(mods_relative) for p in patterns):
            return schema
    return None


def sync_from_vscode(settings_path: Path) -> int:
    """Maintainers: copy the json.schemas block that Game/Generate JSON Schemas writes."""
    data, _ = jsonc.load(settings_path)
    blocks = data.get("json.schemas") if isinstance(data, dict) else None
    if not blocks:
        raise UserError(f"No json.schemas block in {settings_path}")
    result = []
    for block in blocks:
        url = block.get("url", "")
        result.append({"fileMatch": block["fileMatch"], "schema": url.rsplit("/", 1)[-1]})
    write_json(CATALOG, {
        "about": "File patterns and the schema the game ships for them in Core/Config/Schemas. "
                 "Refresh with: tools/stardeus sync-catalog --from <settings.json>",
        "entries": result,
    })
    entries.cache_clear()
    return len(result)
