---
name: stardeus-mod-workshop
description: Publish a Stardeus mod on the Steam Workshop and update it later - the pre-upload checklist, the in-game Upload to Steam Workshop button and its conditions, what the upload check rejects, SteamWorkshopItemId, descriptions with Steam formatting, tags and visibility, the modding terms, updating, dependencies on other Workshop mods, and sharing outside Steam. Use when the user asks how to upload, update, hide or share a mod, or the upload fails.
---

# Steam Workshop

Uploading is done by the user in the game. Never upload for them; walk them through it.

## Before the first upload

1. `tools/stardeus validate <ModId>`: no errors, and the upload notes at the end are clean.
2. `ModInfo.json`: a real `Name` and `Description` (`DescriptionSteam` for a description with
   Steam formatting such as `[b]`, `[i]`, `[url=...]...[/url]`, `[list][*]...[/list]`), a
   `ModVersion`, and `"SteamWorkshop": true` (it shows the upload button).
3. `ModCover.jpg`: the user's own 800x450 JPEG, under 1 MB (Steam refuses bigger previews).
4. The mod folder holds only what players need. No `SteamWorkshopItemId` copied from another
   mod (the official template ships one: delete it), no `Stardeus_Mod_Template.dll`.
5. The user has read the Stardeus modding terms: https://stardeusgame.com/eula/#modding-agreement

## Upload

1. Start the game through Steam. The mod must be in the user Mods folder (the workspace's link
   counts), enabled, and loaded without errors in this run. Any mod error popup this session
   blocks the upload; fix it and restart.
2. Main Menu > Mods > Installed Mods, select the mod, open the cog menu, Upload to Steam
   Workshop. The first time, the game shows the modding terms; Steam may also ask the user to
   accept the Steam Workshop agreement once (the game opens the link).
3. A popup confirms the upload and offers to open the item in the browser.

What the game does: it copies the mod to `ModsUploadTemp` in the user folder, leaves out
first-level folders whose name starts with a dot (`.git`, `.vscode`...) and `obj`, and files
ending in `.exe`, `.blend` or `.blend1`-`.blend3`. Then it refuses the upload when `Id`, `Name`
or `Description` is empty, `ModCover.jpg` is missing, any other file or folder name starts with
a dot (`.gitignore`, `.DS_Store`), a `Stardeus_Mod_Template.dll` is inside, the mod had errors
this run, or the game has turned this mod version off. In the console, `mod debug_prepare <Id>`
builds and opens that folder without uploading.

Each upload sets the title (`Name`), the description, the preview (`ModCover.jpg`), the
files, the tags (`Mod`, the game version like `v0.15`, and `Cheat` for cheat mods), and makes
the item **public**, even if it was hidden on Steam before.

## After the first upload

- The game writes `SteamWorkshopItemId` into the mod folder (through the link, into
  `mods/<ModId>/`). Keep it: it is how the next upload finds the item. Back it up with the mod.
  If the item was deleted on Steam, delete the file and upload again to create a new item.
- On the Workshop page the user can add screenshots, change visibility and edit the
  description. The next upload overwrites the description unless `ModInfo.json` has
  `"DoNotUpdateSteamDescription": true`.
- Only the Steam account that created the item can update it.

## Updating

Raise `ModVersion`, validate, test, then upload again the same way. Subscribers get the update
from Steam. Changes that break saves (removed defs or components) deserve a warning in the
description and the change notes on the Workshop page.

## Good to know

- Subscribing to one's own mod while the local copy exists: the game loads the local copy and
  skips the Workshop one, with a warning. Their Ids match, so turning off one turns off both.
- In the game, Workshop mods get `_<item id>` appended to their Id; `Dependencies` may still
  use the plain Id. Players need every dependency installed; say so in the description.
- Steam's experimental branch of the game can be a few versions ahead of the default branch,
  so subscribers may run either. The stardeus-mod-update skill covers supporting both.
- Outside Steam (GOG, sharing a test build): zip the mod folder; players unzip it into their
  user Mods folder (Main Menu > Mods > Create Mods > Open User Mods Directory).
- Workshop browse page: https://steamcommunity.com/workshop/browse/?appid=1380910&requiredtags[]=Mod
