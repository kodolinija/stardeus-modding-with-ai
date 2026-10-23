---
name: stardeus-mod-patches
description: Change existing Stardeus content with JSON patches (Patches/*.json - target, targetMod, add/replace/remove operations, [Key=Value] array queries) - power, costs, ranges, research prerequisites, traits, story events, tunables, recipes, starting jobs, or another mod's files. Covers the path syntax, the game patcher's quirks, simulating patches with tools/stardeus validate (local/patched) and checking the real result in the game's Patched folder.
---

# JSON patches

A patch changes one JSON file of the game (or of another mod) at load time, without copying
it. Patches keep working when a game update changes other parts of the file, and several mods
can patch the same file. Any JSON file can be patched except `ModInfo.json`: defs, configs,
tunables.

## Format

`Patches/<any name>.json` (subfolders are fine):

```jsonc
{
    // Double the charge of the basic battery
    "target" : "Definitions/Objects/Devices/Battery.json",
    "operations" : [
        {
            "op" : "replace",
            "path" : "/Components[Component=ElectricNode]/Properties[Key=BatteryMaxCharge]/Int",
            "value" : 20000
        }
    ]
}
```

- `target`: the file's path inside the target mod (as in `local/game/<build>/Core/`).
  A leading version folder (`0.15/...`) is ignored.
- `targetMod`: the Id of the mod that owns the file; `Core` when left out. A patch whose
  target mod is not installed does nothing.
- `operations`: applied in order to the file as written, before `ParentId` inheritance. A
  property the file only inherits is not in it: add it to the file's own component, or patch
  the parent (which changes every child).

## Paths

- `/Key/Sub/2/...`: object keys and array indexes, starting with `/`.
- `/Components[Component=Battery]`: the first element of the `Components` array whose
  `Component` is `Battery`. Works on any array of objects: `/Ints[Key=AutoSaveCount]/Int`,
  `/StartingJobs[Job=Hauling]`. Write `Name[Key=Value]`, never `Name/[Key=Value]`. Booleans
  match as `True` / `False`.
- There is no escaping: keys that contain `/` cannot be addressed.

## Operations

| op | path ends with | effect |
|---|---|---|
| `replace` | a key | sets the key; a key that does not exist is added |
| `replace` | an index | replaces that array element |
| `replace` | `/` | replaces the whole file |
| `add` | `/-` | appends `value` to the array |
| `add` | an index | inserts before that position |
| `add` | a key | sets the key (same as replace) |
| `remove` | a key or an index | removes it |
| `remove` | `[Key=Value]` | removes the matched element |
| `remove` + `value` | `/-` | removes every array element equal to `value` |

Nothing else is supported (no `move`, `copy`, `test`).

Quirks of the game's patcher (the validator reports each):

- A failing operation is logged to Player.log and skipped; the next operations still run.
- `remove` of a key that does not exist removes the object that should have held it.
- `add` or `replace` whose last segment is a `[Key=Value]` query does not replace the matched
  element; it adds a junk key named after the query. Remove the element, then add the new one
  with `/-`.

## Recipes

- Change a property: `replace` `/Components[Component=X]/Properties[Key=Y]/Int` (or `/Float`,
  `/String`... the type the file uses).
- Add a property: `add` `/Components[Component=X]/Properties/-` with
  `{ "Key": "Y", "Int": 3 }`.
- Add a component: `add` `/Components/-` with `{ "Component": "X", "Properties": [...] }`.
- Remove a component: `remove` `/Components[Component=X]`.
- Gate a def behind research: `add` `/Researchable` with `{ "Prerequisites": [ "Research/..." ] }`.
- Change a tunable: `replace` `/Ints[Key=AutoSaveCount]/Int` in `Config/Tunable/System.json`.
- The name's numbers: `replace` `/TranslationVars` with strings, like `[ "16", "40" ]`.

## Check it

1. `tools/stardeus validate <ModId>` applies the mod's patches to the snapshot like the game
   does, reports operations that would fail, checks the patched files against their schemas,
   and writes the results to `local/patched/<ModId>/`. Read the result there.
2. In the game (restart it with the mod enabled): the game writes each patched file to the
   user folder's `Patched/` folder with a header listing the patches applied.
   `tools/stardeus patched` lists them, `tools/stardeus patched Devices/Battery.json` prints one.
   `tools/stardeus log --mod <ModId>` shows patch errors.

When several mods patch the same file, mods without `Dependencies` patch first, and a mod
patches after every mod it lists in `Dependencies`. To patch on top of another mod's change,
list that mod in `Dependencies`. A mod whose dependency is missing or disabled is not loaded,
so none of its patches apply. A patch that fails is skipped and its mod is marked broken; the
other mods' patches to the same file still apply. A broken mod (a patch file without a `target`
or with bad JSON, a DLL that fails to load, a patch that fails) applies no further patches, and
neither do the mods that depend on it.
