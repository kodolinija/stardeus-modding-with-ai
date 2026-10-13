---
name: stardeus-mod-decompile
description: Decompile Stardeus DLLs (Game.dll, Game.Utils, Game.CodeGen, Game.I18n, KLUnityUtils) with dnSpy or ILSpy into local/decompiled to read code the shipped ReferenceSourceCode leaves out - logging, hashing, SelfInit, the console, rendering, audio, Steam code - or to confirm exactly what the installed build does. Covers tools/stardeus decompile, the dnSpy console helper, ilspycmd, the dnSpy GUI, and what not to do with decompiled code.
---

# Decompiling the game

Start with the reference source in the snapshot: it is the real code with its comments, and it
covers most of what mods touch (stardeus-mod-source skill). Decompile when the code is not
there, or to check the exact behavior of the installed build.

## Command

```
tools/stardeus decompile Game.Utils --type Hashes
tools/stardeus decompile KLUnityUtils
tools/stardeus decompile Game --tool ilspy
```

- The argument is a DLL name from the game's `Managed/` folder (listed in
  `local/game/<build>/managed.txt`) or a path to any .NET DLL.
- Output: `local/decompiled/<build>/<DLL>/`, one `.cs` file per type, folders by namespace.
  `--type` prints the file of that type afterwards. Search the output with an explicit path.
- `--tool dnspy` is the default on Windows when dnSpy is set up, `--tool ilspy` otherwise.
- Decompile again after a game update; the output folder is per build.

| DLL | What to look for there |
|---|---|
| `Game` | All game code. Mostly in the reference source already; parts left out (rendering, audio, Steam, AI planner, projectiles) are here |
| `Game.Utils` | `SelfInit`, `SelfInitAttribute`, `Hashes` |
| `Game.CodeGen` | The generated `*H` hash constants |
| `Game.I18n` | `Translations`, `T` |
| `KLUnityUtils` | `KL.Utils.D` (logging), `Files`, `Json`, the console (`KL.Console`), JSON patching (`KL.JSON.EnhancedJsonPatch`), signals, collections |
| `0Harmony`, `Newtonsoft.Json`, `UnityEngine.*` | Third-party libraries; read their own documentation first |

## dnSpy (Windows)

- Get dnSpyEx from https://github.com/dnSpyEx/dnSpy/releases (the 64-bit zip), unzip it,
  and run `tools/stardeus setup --dnspy "<folder>"` once (or set `DNSPY_DIR`).
- dnSpy's console program sets the console encoding first thing and crashes with "The handle
  is invalid" when started from an agent's shell, where output is a pipe and there is no console.
  The workspace runs it through a small helper (`tools/dnspy-host`) that opens a hidden console
  first. The helper is built on first use with the .NET SDK into `local/tools/`.
- For browsing by hand, the dnSpy window is easier: File > Open the DLLs from the game's
  `Managed/` folder, then search (Ctrl+Shift+K) and Analyze (who calls what).

## ILSpy (any system)

- `dotnet tool install -g ilspycmd` (needs the .NET SDK), then open a new terminal. Ask the
  user before installing.
- The ILSpy window app and JetBrains dotPeek are good GUIs too.

## Rules

- Decompiled code is for understanding how to mod the game. Never put it in a mod, a repository,
  a post or a message, and never upload it. The game's EULA applies.
- Copying small call patterns into your own code is fine; copying whole classes is not, and
  breaks with game updates anyway. Call the game's code, or patch it with Harmony.
