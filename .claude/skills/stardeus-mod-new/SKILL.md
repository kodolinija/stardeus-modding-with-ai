---
name: stardeus-mod-new
description: Start a Stardeus mod - choose between a JSON patch, new JSON content and C# code, create the mod folder with tools/stardeus new, fill in ModInfo.json, link it into the game, and enable it. Also covers bringing an existing mod into the workspace (adopt), starting from the official template, empty mod or examples, mod Ids, dependencies, and keeping a mod under version control.
---

# Starting a mod

## Choose the approach

| The user wants to... | Approach | Kinds for `new` |
|---|---|---|
| Change numbers or settings of things the game has (power, cost, speed, range, chances) | JSON patch | `patch` |
| Change a trait, quest, story event, recipe or tunable | JSON patch | `patch` |
| Add a device, furniture, item, material, research node, trait, story event, recipe | New JSON files (and sprites, translations) | `content` |
| Add a new kind of behavior, UI, key binding, or change game code | C# (often with some JSON) | `csharp` or `csharp,content` |
| Recolor the UI | A UI theme: start from https://github.com/kodolinija/stardeus-ui-theme-template | `content` |

Prefer patches: they keep working when a game update changes other parts of the same file, and
several mods can patch one file. Check the idea is possible before promising it: find the
relevant defs, components and code first (stardeus-mod-source skill).

## Create it

```
tools/stardeus new BetterBatteries --name "Better Batteries" --description "Batteries hold twice the charge." --kind patch
```

- The Id uses letters, digits and `_`, starts with a letter, and becomes the folder name and the
  C# namespace. Other mods refer to it in their `Dependencies`. Keep it once the mod is
  published. Ids ending in "Template" are refused: the game deletes such a mod folder when its
  ModInfo.json is missing, which through the link would delete the workspace copy.
- It creates `mods/<Id>/` with `ModInfo.json`, a placeholder `ModCover.jpg` and the folders for
  the chosen kinds (`csharp` adds `.vscode/mod.csproj` and a component in `Code/`), then links
  the folder into the game's Mods folder (a junction on Windows, a symlink elsewhere). `--no-link`
  skips the link. `tools/stardeus link <Id>` and `unlink <Id>` manage it later; unlink never
  deletes the mod.
- Then the user enables it: Main Menu > Mods > Installed Mods, tick the mod, and restart the
  game (the game offers to). New mods start disabled, and enabled mods load only at startup.

## ModInfo.json

The game reads it with `//` comments allowed. Fields (checked by `ModInfo.schema.json`):

| Field | Meaning |
|---|---|
| `Id` | Unique id. Workshop copies get `_<WorkshopItemId>` appended in the game, but `Dependencies` may use the plain Id |
| `Name`, `Description` | Shown in the mod list and on the Workshop page. Both are required for the upload |
| `DescriptionSteam` | Workshop description with Steam formatting (`[b]`, `[url=...]`); `Description` is used when empty |
| `DoNotUpdateSteamDescription` | `true` keeps the Workshop description untouched on later uploads |
| `SteamWorkshop` | `true` shows "Upload to Steam Workshop" in the mod's menu |
| `ModVersion` | Like `1.2.0`, no `*`. Raise it with every upload: the game turns off mod versions it knows to be broken until the version changes |
| `GameVersion` | The game version the mod was made for, like `0.15.0` |
| `Dependencies` | Mod Ids that must load first; `Core` is implied |
| `Cheat` | `true` marks a cheat mod: achievements stay off while it is enabled and in games played with it, and the Workshop item gets a Cheat tag |
| `DLLFiles` | Only these DLLs from `Libraries/` load (by default all of them do) |
| `Atlases` | Sprite atlas settings, rarely needed (see the Core mod's `ModInfo.json`) |
| `IsCoreTranslation` | For community translation mods only |

## Mods that already exist

- A mod in the game's Mods folder: `tools/stardeus adopt "<folder name>"` copies it into
  `mods/`, removes the original and links the copy back in its place. Ask the user first.
- The official starting points: clone into `mods/` and rename the folder to the new Id.
  - https://github.com/kodolinija/stardeus-mod-template: examples of nearly everything,
    C# included. Before publishing your own mod from it: delete `SteamWorkshopItemId` (it
    belongs to the template's Workshop item), `Libraries/Stardeus_Mod_Template.dll`, `.gitignore`
    and what you do not use; change `Id`, `Name`, `Description` and the `AssemblyName` in
    `.vscode/mod.csproj`; replace `ModCover.jpg`.
  - https://github.com/kodolinija/stardeus-mod-empty: just the folders.
  - https://github.com/kodolinija/stardeus-mod-examples: one small mod per folder.
- Run `tools/stardeus validate <Id>` afterwards: it reports leftovers like these.

## Versions of a mod

`mods/` is not part of this workspace's repository, so updating the workspace (`git pull`)
never touches mods. To keep versions of a mod, make it its own repository:
`git init` inside `mods/<Id>`. The game leaves the `.git` folder out of Workshop uploads, but
rejects a `.gitignore` file, so put ignore rules in `mods/<Id>/.git/info/exclude` instead.
