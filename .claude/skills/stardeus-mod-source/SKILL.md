---
name: stardeus-mod-source
description: Find out how something works in Stardeus before modding it - search the game's own defs, configs, translations and the shipped C# ReferenceSourceCode in the workspace snapshot (local/game), map a JSON component to its C# class and the property keys it reads, list the defs that use a component or key, show the effective def after ParentId inheritance (tools/stardeus def / find), find a def from its in-game name, and know what the reference source leaves out.
---

# Finding things in the game

Everything below lives in the snapshot `local/game/<build>/Core/` (the `snapshot_id` in
`local/paths.json`). It is git-ignored, so give search tools the path explicitly.

## The game's files

| Folder | What is in it |
|---|---|
| `Definitions/` | Defs: devices (`Objects/Devices`), furniture, cosmetics, items and materials (`Obj/...`), walls, floors and doors (`Structure/...`), beings, research (`Research/<Category>`). Id = path without `.json` |
| `Config/` | Data loaded by type: `Traits`, `Quests`, `Story` (events, generators), `Materials`, `Craftable` (recipes), `Tunable` (global numbers), `Curves`, `Species`, `Body`, `Needs`, `Jobs`, `Economy`, `Diplomacy`, `Ships`, `UITheme`... and `Schemas` |
| `Translations/` | `English.csv` and other languages: `key,text,version,comment` |
| `ReferenceSourceCode/` | The game's C#, for reading. Nothing compiles against it; mods reference the game's DLLs |

`tools/schema_catalog.json` says which file patterns each schema (and so each C# type) covers.

## ReferenceSourceCode map

| Path | What is in it |
|---|---|
| `Components/<Name>Comp.cs` | The component a def lists as `"Component": "<Name>"` |
| `Components/Base/` | `BaseComponent`, `ComponentConfig` (how properties are read), `ComponentData` (saving) |
| `Systems/` | Game systems (`GameSystem` subclasses: electricity, AI, story, trade, research...) and `UIUX/` (entity tabs, widgets, `Helpers/UISpawnExamples.cs`) |
| `Data/` | `Def.cs`, `Defs.cs`, `ModInfo.cs`, `Tunable.cs`, the config types |
| `Mods/` | How mods load: `ModLoader.cs`, `ModDiscovery.cs`, `JSONPatcher.cs` |
| `Game.Constants/Generated/` | Indexes generated from Core: `ComponentId`, `PropertyId` (every property key, with the defs that use it), `DefIds`, `MatId`, `IconId`, `GraphicsId`, `TunableKey`, `Tunables`, `CurveId`, `QuestId`, `T` (translation keys), `UIPrefabId` |
| `Console/` | In-game console commands (`ConsoleCommand*.cs`) |
| `Constants/Consts.cs` | `ModDirLoadOrder` (version folders) and other constants |

## Recipes

- **What a component does and which keys it reads**: open `Components/<Name>Comp.cs`, read
  `OnConfig()`, and search for `PropertyIdH.` and `Config.Get`. `Config.GetInt(PropertyIdH.Width, 1)`
  reads the key `Width`, default 1. A key no code reads does nothing, whatever the JSON says.
- **The effective def** (a def merged with its `ParentId` chain, as the game builds it):
  `tools/stardeus def Objects/Devices/Battery`. `--raw` shows the file as written. Patches act on
  the file, not on the merged result, so check both before writing a patch.
- **Defs with a component, a key, a parent or a layer**:
  `tools/stardeus find --component Battery`, `--property MaxConnections`,
  `--parent Objects/Devices/BaseDevice`, `--layer Objects`, `--id "Turret"`
  (regular expression). `--mods` includes the workspace mods.
- **From an in-game name to a def**: search `Translations/English.csv` for the name. The key
  is the def id in lower case with dots: `objects.devices.battery` belongs to
  `Definitions/Objects/Devices/Battery.json` (unless the def sets its own `NameKey`).
- **Global numbers** (auto save count, raid timing, prices...): `Config/Tunable/*.json` with
  their keys, and `Game.Constants/Generated/Tunables.cs` / `TunableKey.cs` for where code reads
  them.
- **A system's API**: `Systems/<Area>/...Sys.cs`. Systems are reached through the game state
  (`S.Sys...`, `S.Sig...` signals, `S.Query...`); search for how existing components call them.
- **Console commands**: `Console/ConsoleCommand*.cs` (name and subcommands at the top).

## What the reference source leaves out

It is the code modders call, extend or write JSON for. Left out: implementation details nobody
mods (rendering, audio, platform and Steam code, the AI planner, projectiles, some internal
tools), and these assemblies entirely:

| DLL | Holds |
|---|---|
| `Game.Utils` | `[SelfInit]`, `Hashes` (`Hashes.S(string)` makes property and id hashes) |
| `Game.CodeGen` | The `*H` hash constants (`PropertyIdH`, `ComponentIdH`, `MsgIdH`...) |
| `Game.I18n` | Translations and the `T` text constants |
| `KLUnityUtils` | Logging (`KL.Utils.D`), files, JSON, the console, signals, collections |

For those, decompile (stardeus-mod-decompile skill). For signatures only, an IDE that
references the game DLLs (the C# template does) shows them too.
