# Stardeus Modding with AI

A ready-made workspace for making [Stardeus](https://store.steampowered.com/app/1380910/Stardeus/)
mods with an AI coding assistant such as Claude Code, Codex, Cursor or GitHub Copilot. Clone it,
start your assistant in the folder, and describe the mod you want. The assistant finds your game,
looks up how the game does things in its own files, writes the mod, checks it, and walks you
through testing and publishing it on the Steam Workshop.

## What you need

- Stardeus, installed through Steam (a GOG copy works too, without the Workshop).
- An AI coding assistant that works inside a folder. With [Claude Code](https://claude.com/claude-code)
  the skills and rules here load on their own; other assistants read `AGENTS.md`.
- [Python](https://www.python.org/downloads/) 3.10 or newer, for the workspace tools. On
  Windows, tick "Add python.exe to PATH" in the installer.
- [Git](https://git-scm.com/downloads), to download this workspace and keep it updated.
- Only for C# mods: the [.NET SDK](https://dotnet.microsoft.com/download). Only for reading game
  code that is not shipped as source: [dnSpy](https://github.com/dnSpyEx/dnSpy/releases)
  (Windows) or ILSpy.

## Quick start

```
git clone https://github.com/kodolinija/stardeus-modding-with-ai.git
cd stardeus-modding-with-ai
claude
```

Then ask: "Set up this workspace". The assistant finds the game and prepares everything. After
that, ask for a mod:

- "Make a mod that lets batteries store twice as much energy."
- "Add a bigger solar panel that needs a new research."
- "Add a trait that makes colonists work faster but eat more."
- "My mod doesn't show up in the game. Why?"
- "How do I upload my mod to the Steam Workshop?"
- "The game updated. Is my mod still fine?"
- "Where are my saves and Player.log?"

New mods start disabled: enable them in the game under Main Menu > Mods > Installed Mods, and
restart the game after every change.

## What is in here

| | |
|---|---|
| `AGENTS.md`, `CLAUDE.md` | Instructions for the assistant |
| `.claude/skills/` | Know-how per task: setup, starting a mod, finding things in the game's code and data, JSON, patches, C#, decompiling, texts and sprites, testing, the Workshop, game updates |
| `.claude/rules/` | Short rules for mod files |
| `tools/stardeus` | Commands the assistant runs, and you can too (`tools\stardeus.cmd` in cmd or PowerShell): `setup`, `status`, `new`, `link`, `validate`, `def`, `find`, `log`, `patched`, `diff`, `decompile`, `build`. See `tools/stardeus --help` |
| `mods/` | Your mods. Each one is linked into the game's Mods folder, so the game loads them straight from here. They are not part of this repository: updating the workspace never touches them |
| `local/` | Created by the tools on your computer: where the game is, a searchable copy of the game's text files, decompiled code. Never shared |

The tools run on your computer only. Your assistant sends what it reads to its provider as part
of your conversation, like any other project you use it on.

## Updating

Run `git pull` from time to time: the skills and tools follow the game's updates. They were
last checked against Stardeus v0.15.0-rc329. When your game is newer and something differs,
the assistant trusts the game's own files.

## More about modding Stardeus

- [Mod template](https://github.com/kodolinija/stardeus-mod-template): examples of almost everything, including C#, UI and the Blender art pipeline
- [Mod examples](https://github.com/kodolinija/stardeus-mod-examples): small focused mods (patches, traits, story events, research, a C# hotkey with Harmony)
- [Empty mod](https://github.com/kodolinija/stardeus-mod-empty) and [UI theme template](https://github.com/kodolinija/stardeus-ui-theme-template)
- [Modding videos](https://www.youtube.com/playlist?list=PLvm1mLYInibc8n0Q5_caRql5nEUiBwvTC)
- [Stardeus Discord](https://discord.com/invite/89amEwP), channel #stardeus-modding
- [Mods on the Steam Workshop](https://steamcommunity.com/workshop/browse/?appid=1380910&requiredtags[]=Mod)

## Terms

Read https://stardeusgame.com/eula/ for more info. Every mod you publish must follow its
[modding agreement](https://stardeusgame.com/eula/#modding-agreement).
