---
name: stardeus-mod-update
description: Keep a Stardeus mod working when the game updates - refresh the workspace snapshot, see what changed in the game files the mod touches (tools/stardeus diff), revalidate patches and defs, rebuild C# against the new DLLs and check Harmony targets, and support several game versions at once with version folders (CommonPre, 0.15, 0.14, CommonPost). Use when the game updated, a mod broke after an update, or players on different game versions need the mod.
---

# After a game update

## Find what changed

1. `tools/stardeus status` says "The installed game changed". Run `tools/stardeus setup`: it
   keeps the old snapshot and adds one for the new build (the last three are kept).
2. `tools/stardeus diff` compares the previous snapshot with the new one: added, removed and
   changed files under Core. Narrow it with `--path "Definitions/Objects/Devices/*"` or
   `--path "ReferenceSourceCode/Components/*"`, and show one file's changes with
   `--file Definitions/Objects/Devices/Battery.json`. Older snapshots: name them,
   `tools/stardeus diff <old> <new>` (prefixes of the folder names in `local/game/` work).
3. Look first at what the mod depends on: its patch targets, the parents of its defs, the
   components and property keys it uses, the configs it replaces, and for C# the classes and
   methods it calls or patches.

## Check the mod

- `tools/stardeus validate` (all mods): broken patch paths and targets, keys that moved,
  parents that disappeared, new schema rules.
- C#: `tools/stardeus build <ModId>`; compile errors show changed APIs. A Harmony patch on a
  renamed or removed method throws when the mod loads: diff the patched classes in
  `ReferenceSourceCode`, or decompile when they are not in it.
- Test in the game and read `tools/stardeus log --mod <ModId>` (stardeus-mod-test skill).
- Then raise `ModVersion`, set `GameVersion` to the new version, and upload.

## Supporting several game versions

A mod can hold content per game version. For each kind of content (Definitions, Patches,
Graphics, Translations, Libraries, each Config folder), the game uses the first of these
folders that exists in the mod and ignores the others:

1. `CommonPre/`
2. its own version and the older ones, newest first: `0.15/`, `0.14/`, ...
3. `CommonPost/`
4. the mod's root

Folders for versions newer than the game are ignored. The list for the installed game is
`ModDirLoadOrder` in the snapshot's `ReferenceSourceCode/Constants/Consts.cs`; `validate` reads
it and warns about folders the installed game ignores.

So when version 0.16 needs a different `Patches/`, put the new one in `0.16/Patches/`: 0.16
games use it, older games keep using the old one at the root. Version folders do not merge
with each other, so each must be complete for its kind of content. Within one version (for
example the default and the experimental branch of 0.15) they cannot tell builds apart; make
the mod work on both, or tell players which branch it needs.
