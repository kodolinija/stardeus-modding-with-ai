---
name: stardeus-mod-test
description: Test a Stardeus mod in the game and find out why it does not work - enable it, restart, read Player.log with tools/stardeus log, compare the game's Patched output, use the in-game console (help, story, quest, research, dev_menu, sandbox) and launch options, and know which mistakes the game reports and how (MOD PROBLEMS popups, mods disabled as broken or outdated). Use after every change worth trying, and whenever the user says the mod does nothing, crashes or shows errors.
---

# Testing a mod

## The loop

1. `tools/stardeus validate <ModId>`: fix errors first, the game would hit them too.
2. The mod must be linked (`tools/stardeus status`) and enabled: Main Menu > Mods > Installed
   Mods, tick it. The game reads mods only at startup: restart after every change, including
   after enabling.
3. Try it in the game: build the thing, open the research, wait for the event. Tell the user
   exactly what to check and where.
4. `tools/stardeus log --mod <ModId>` (the run before: add `--prev`). It lists the mods that
   loaded, mods that are disabled, and the errors the game logged about the mod, with
   stack traces of exceptions from mod code.
5. For patches, `tools/stardeus patched` lists the files the game patched in this run and
   `tools/stardeus patched <end of path>` prints one: that is what the game really used.

To start faster while iterating, launch the game with `--uncompressed-textures` (Steam: right
click Stardeus > Properties > Launch Options). It skips texture compression when the game
rebuilds its graphics cache, which happens after sprites change.

## How the game reports mod problems

| What the player sees | Meaning |
|---|---|
| "MOD PROBLEMS" popup at startup, the mod listed as broken | The mod is disabled for this run: a DLL failed to load or its initializer threw, a def or patch error, a missing dependency. The log says which |
| A popup naming the mod and a def | A def error (missing parent, unknown component, missing research prerequisite, duplicate component). Other mods keep loading |
| "Mod Content Corrupted" with JSON errors | A JSON file failed to load. The popup names each file, highlights the line and position the parser stopped at, and the file's path opens its folder. Restart Now relaunches the game after the fix |
| "SKIPPING MOD" naming `ModInfo.json` | The mod's `ModInfo.json` has a syntax error or (outside the Workshop) an unknown key, so the mod is not loaded at all. The popup shows where |
| A mod listed as disabled by the developer | The game knows this mod version is broken: its Id and version are in `DisabledMods.json` in the game's StreamingAssets folder, with the reason when there is one. A fixed upload needs a higher `ModVersion`; `tools/stardeus validate` reports it before you upload |
| Raw keys like `objects.devices.mylamp` in the UI | Missing translation (stardeus-mod-assets skill) |
| Missing sprites | The sprite id does not match a file in the mod's or the game's Graphics |
| Nothing happens | The mod is disabled, not linked, the patch target or path is wrong, or a property key is one no code reads (`validate` warns) |

Any error popup about the mod also blocks its Workshop upload until a restart without errors.

## The console

The key left of 1 (backquote) opens it; rebind it in Settings > Input. `help` lists the
commands; a command with a wrong subcommand lists its subcommands. The code is in the
snapshot's `ReferenceSourceCode/Console/`.

**Most commands turn achievements off for the save they run in.** Test in a throwaway game.

- `story` (`list`, `check <eventId>`, `trigger <eventId>`, `trigger random`...): story events.
- `quest`, `research`, `tunable`, `need`, `economy`, `clock`, `find`, `ship`, `space`: what
  their names say; read their subcommands with a wrong subcommand or in the source.
- `dev_menu`: the developer tool menu. `sandbox`: turns sandbox mode on and off.
- `mod create <Id> <Name>`: makes an empty mod in the game's Mods folder (in this workspace use
  `tools/stardeus new` instead). `mod debug_prepare <Id>`: prepares and opens the folder the
  Workshop upload would send.

## Mods, saves and players

- Saves keep the things a mod added. Removing a mod from a game in progress can leave things
  missing or break the save: test with a new game or a copy.
- Mod code runs every tick on every player's machine: watch the frame rate with big colonies
  when the mod does work per tick or per entity.
