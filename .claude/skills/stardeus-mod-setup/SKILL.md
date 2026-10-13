---
name: stardeus-mod-setup
description: First-run setup of this Stardeus modding workspace and answers about where things are. Use when tools/stardeus status says the workspace is not set up or the game changed, when Python or another tool is missing, when the game is not found (GOG, unusual Steam library, Proton), or when the user asks where Stardeus is installed, where mods, saves or Player.log go, or which game version they have.
---

# Setting up the workspace

The workspace needs to know where the game is. `tools/stardeus setup` finds it and writes:

- `local/paths.json`: the install, the user folder, the game version, the snapshot id
- `local/game/<version>_<build>/`: a read-only copy of the game's text files (defs, configs,
  translations, schemas, ReferenceSourceCode) and a list of sprite ids. Agents read the game
  from here, and after a game update two snapshots show what changed
- `local/stardeus.props`: the path to the game's DLLs, for C# mods

## Steps

1. `tools/stardeus status`. Typical outcomes:
   - "Python 3.10 or newer is needed": see Python below.
   - "Not set up yet": go on with step 2.
   - "The installed game changed": run step 2 again, then see the stardeus-mod-update skill.
2. `tools/stardeus setup`. Add `--vscode` when the user edits in VS Code: it maps mod JSON files
   to the game's schemas for autocomplete and checks.
3. If the game is not found, ask the user where it is. In Steam: right click Stardeus >
   Manage > Browse local files. Then `tools/stardeus setup --game-dir "<that folder>"`. The
   choice is remembered.
4. Read the tool list at the end of the output. Only C# mods need the .NET SDK, only
   decompiling needs dnSpy or ilspycmd. Install nothing before the user agrees.

The game version comes from the installed build itself. `LastPlayedVersion.txt` in the user
folder only changes after the game runs, so it can lag behind a Steam update.

## Where Stardeus keeps things

| | Windows | Linux | macOS |
|---|---|---|---|
| Install (Steam) | `<library>\steamapps\common\Stardeus` | `<library>/steamapps/common/Stardeus` | `<library>/steamapps/common/Stardeus/Stardeus.app` |
| Game data | `Stardeus_Data\StreamingAssets\Mods\Core` | same | `Stardeus.app/Contents/Resources/Data/StreamingAssets/Mods/Core` |
| Game DLLs | `Stardeus_Data\Managed` | same | `Stardeus.app/Contents/Resources/Data/Managed` |
| User folder | `%USERPROFILE%\AppData\LocalLow\Kodo Linija\Stardeus` | `~/.config/unity3d/Kodo Linija/Stardeus` | `~/Library/Application Support/Kodo Linija/Stardeus` |

The default Steam library is `C:\Program Files (x86)\Steam` on Windows, `~/.local/share/Steam`
(or `~/.steam/steam`, or under `~/.var/app/com.valvesoftware.Steam` for Flatpak) on Linux,
and `~/Library/Application Support/Steam` on macOS. Other libraries are listed in
`<Steam>/steamapps/libraryfolders.vdf`; the library that has Stardeus holds
`steamapps/appmanifest_1380910.acf` (1380910 is the game's Steam app id).

In the user folder: `Mods/` (the user's mods; the game opens it from Main Menu > Mods > Create
Mods > Open User Mods Directory), `Saves/`, `Player.log` (this run) and `Player-prev.log`
(the run before), and `Patched/` (what the game's JSON patcher produced, written at startup).
Linux players who run the Windows build through Proton have the user folder inside
`steamapps/compatdata/1380910/pfx/drive_c/users/steamuser/AppData/LocalLow/Kodo Linija/Stardeus`;
setup finds it there too.

Never put a mod into the install's `StreamingAssets/Mods`. That folder is for the game's own
mods: Steam overwrites it, and mods there get no Workshop upload button.

## Python

The workspace tools need Python 3.10 or newer. `tools/stardeus` tries `python3`, `python` and
`py -3`. On Windows, `python3` can be the Microsoft Store placeholder that only opens the Store;
the wrapper detects that and moves on. To install, with the user's agreement:

- Windows: `winget install Python.Python.3.12`, or the installer from
  https://www.python.org/downloads/ with "Add python.exe to PATH" ticked. Open a new terminal.
- macOS: the python.org installer, or `brew install python`.
- Linux: the distribution's `python3` package.

Without Python, do the work by hand: find the install as described above, read the game's JSON
and ReferenceSourceCode directly from the install (read only), and check mods carefully
against the rules in the other skills. Say that `validate` could not run.

## Optional tools

- .NET SDK (C# mods, and dnSpy's console helper): https://dotnet.microsoft.com/download
- dnSpy (Windows): unzip a release from https://github.com/dnSpyEx/dnSpy/releases, then
  `tools/stardeus setup --dnspy "<folder>"`
- ilspycmd (any system, needs the .NET SDK): `dotnet tool install -g ilspycmd`
- git, to keep versions of a mod (stardeus-mod-new skill)
- VS Code: https://code.visualstudio.com, for editing JSON with schema checks

## Other platforms

- GOG: the same files, the user folder is the same. Pass the install folder with `--game-dir`.
  The Steam Workshop is not available there; share the mod folder another way.
- A demo build ships no ReferenceSourceCode.
