# Stardeus modding workspace

You are helping someone make a mod for Stardeus, a colony management game on Steam by Kodo
Linija. They own the game. They may not be a programmer: explain what you change in game terms,
name the files you touch, and pick the simplest approach that does the job (JSON before C#).

## Start of every session

1. Run `tools/stardeus status` (in cmd or PowerShell: `tools\stardeus.cmd status`). If it says the
   workspace is not set up, that the game changed, or that Python is missing, follow
   `.claude/skills/stardeus-mod-setup/SKILL.md` before anything else.
2. `local/paths.json` then holds every path you need. Never guess where the game is.

## Where things are

| What | Where |
|---|---|
| The user's mods | `mods/<ModId>/`, each linked into the game's own Mods folder, so the game loads them from here |
| The game's files, read only | `local/game/<build>/Core/` (`snapshot_id` in `local/paths.json`): Definitions, Config, Translations, ReferenceSourceCode (the game's C# for reading) |
| The game's schemas | `local/game/<build>/Core/Config/Schemas/` (older game versions ship fewer) |
| Sprite ids of the game | `local/game/<build>/graphics.txt` |
| Simulated patch results | `local/patched/<mod>/`, written by `tools/stardeus validate` |
| The game install | `game_dir` in `local/paths.json`. Never change anything in it |
| Player data | `user_dir`: `Mods/`, `Saves/`, `Player.log`, `Patched/` (what the game's patcher produced) |

`local/` is ignored by git, so search tools skip it unless you pass the path explicitly, for
example `local/game/<build>/Core/ReferenceSourceCode`. All commands: `tools/stardeus --help`.

## How Stardeus mods work

- A mod is a folder with a `ModInfo.json`. The game loads the Core mod (the game itself) first,
  then the enabled mods in dependency order, and only at startup: restart the game after every
  change. New mods start disabled (Main Menu > Mods > Installed Mods).
- `Definitions/` holds defs: everything that exists in the world (devices, furniture, items,
  beings, walls, floors, research nodes). A def's id is its path, and `ParentId` inherits from
  another def. `Config/` holds game data loaded by type (traits, quests, story events,
  materials, recipes, tunables, curves...). `Patches/` changes existing JSON. `Graphics/`,
  `Sounds/` and `Translations/` hold assets, `Libraries/` compiled C# DLLs.
- Change what the game already has with a **patch**. The game refuses a mod def whose id
  already exists, and a Config file with the same path as a Core file replaces the whole file,
  so game updates to it never reach the player.
- Add new things as new files that follow the Core folder layout. Use C# only for behavior that
  JSON cannot express.
- Mods can keep content per game version in `0.15/`, `0.14/`... subfolders; see the
  stardeus-mod-update skill.

## Rules

- Never write to the game install or its `StreamingAssets/Mods` folder: Steam overwrites it,
  and mods there cannot be uploaded to the Workshop.
- Never invent a component, property key, config field or API. Find it in the game's files
  first (stardeus-mod-source skill). When these instructions and the game's files disagree, the
  game's files are right for the installed version.
- After every change run `tools/stardeus validate <ModId>` and fix its errors before you say the
  work is done. Then tell the user to restart the game and what to look for in it.
- `mods/<ModId>` belongs to the user: ask before deleting or rewriting their files, before
  `tools/stardeus adopt` moves a mod, and before installing any program.
- Never upload, publish or push for the user. Walk them through it (stardeus-mod-workshop).
- Once a mod is on the Workshop, keep its `Id` and never delete its `SteamWorkshopItemId` file.
- Decompiled game code stays in `local/`. Read it to learn; never copy large parts into a mod.

## Skills

Read the matching file before you start that kind of work. Claude Code loads them on its own;
other tools: open the file.

| Task | Read |
|---|---|
| First run, finding the game, missing tools, "where is my game / where do mods go" | `.claude/skills/stardeus-mod-setup/SKILL.md` |
| Starting a mod, choosing JSON, patch or C#, ModInfo.json, an existing mod | `.claude/skills/stardeus-mod-new/SKILL.md` |
| Finding how something works in the game, component keys, defs, the reference source | `.claude/skills/stardeus-mod-source/SKILL.md` |
| Writing defs and configs, inheritance, schemas | `.claude/skills/stardeus-mod-json/SKILL.md` |
| Changing existing game content with patches | `.claude/skills/stardeus-mod-patches/SKILL.md` |
| C# code, Harmony, building the DLL | `.claude/skills/stardeus-mod-csharp/SKILL.md` |
| Code that is not in the reference source, decompiling with dnSpy or ILSpy | `.claude/skills/stardeus-mod-decompile/SKILL.md` |
| Translations, sprites, sounds, the cover image | `.claude/skills/stardeus-mod-assets/SKILL.md` |
| Testing in the game, Player.log, "my mod does not work" | `.claude/skills/stardeus-mod-test/SKILL.md` |
| Uploading or updating on the Steam Workshop | `.claude/skills/stardeus-mod-workshop/SKILL.md` |
| A game update broke a mod, supporting several game versions | `.claude/skills/stardeus-mod-update/SKILL.md` |

Rules for specific files (Claude Code applies them on its own): `.claude/rules/mod-json.md`
(any mod JSON), `.claude/rules/mod-patches.md` (Patches), `.claude/rules/mod-csharp.md` (C#),
`.claude/rules/mod-translations.md` (Translations CSV).

## More help

- Official mod template, with C#, UI tab, patches and Blender art examples: https://github.com/kodolinija/stardeus-mod-template
- Small focused mod examples (JSON patches, traits, story events, research, a C# hotkey with Harmony): https://github.com/kodolinija/stardeus-mod-examples
- Empty mod: https://github.com/kodolinija/stardeus-mod-empty
- UI color theme template: https://github.com/kodolinija/stardeus-ui-theme-template
- Stardeus Discord, #stardeus-modding: https://discord.com/invite/89amEwP
- Modding videos: https://www.youtube.com/playlist?list=PLvm1mLYInibc8n0Q5_caRql5nEUiBwvTC
- Modding terms in the EULA (every published mod must follow them): https://stardeusgame.com/eula/#modding-agreement
