---
name: stardeus-mod-assets
description: Add translations, sprites, sounds and the mod cover to a Stardeus mod - Translations/<Language>.csv format and key rules, overriding the game's texts, Graphics/ sprite ids, sizes per tile and rotation suffixes, replacing the game's sprites, Sounds/, and ModCover.jpg. Use whenever a mod adds or changes text, images or sound.
---

# Texts, sprites, sounds

## Translations

`Translations/English.csv`, one file per language, named like the game's own files in
`local/game/<build>/Core/Translations/` (`English.csv`, `Spanish.csv`...):

```
Key,Translation,Version,Comment (context for translators)
objects.devices.mylamp,My Lamp,,
objects.devices.mylamp.desc,"A lamp that glows, flickers and hums.",,
```

- The game always skips the first line. Every row has 4 columns: key, text, version (leave it
  empty), comment. Quote a text that contains commas, quotes (doubled: `""`) or line breaks.
- A def's name key is its id in lower case with dots, the description key adds `.desc`.
  `{0}`, `{1}` in a text are filled from the def's `TranslationVars`.
- Formatting: the game's texts use rich text tags such as `<b>`; search the game's
  `English.csv` for an example before using a tag.
- English is the fallback. A key the current language lacks shows the English text; a key no
  file has shows the raw key in the game.
- A mod can replace the game's own texts: put the game's key in the mod's file for that
  language. The replacement applies only to players using that language, and only when its
  `{0}` placeholders match the game's text; otherwise the game keeps its own.

## Sprites

- `Graphics/<path>.png` (or `.jpg`) becomes the sprite id `<path>`:
  `Graphics/Objects/Devices/MyLamp.png` is `Objects/Devices/MyLamp`, which defs name in
  properties like `Graphic` or `PreviewIcon`.
- A file at the same path as a game sprite replaces it (see `local/game/<build>/graphics.txt`).
- Size: 256 pixels per tile. Look at the game's sprite of a similar thing and match it:
  a 2x1 device is 512x256; `"HasHeight": true` in `TileGraphics` adds one tile row on top
  (512x512); items are 256x256; icons 128x128.
- Rotatable objects need four sprites: `<id>_D` (facing down), `<id>_U`, `<id>_L`, `<id>_R`. Left
  and right turn the footprint: a 2x1 device with height is 512x512 down and up, 256x768 left
  and right. `AliasLR` / `AliasUD` (TileGraphics properties) reuse the right sprite for left
  and the down one for up.
- Floors with see-through parts use `"Shader": "TransparentFloorTile"` (the game's frames and
  angled floors do). The game treats a floor as an angled corner when it is not walkable and
  not full integrity: its transparent half is where the ship ends, so it gets an ink line
  along its sprite's edge and a diagonal foundation. Say it outright with `"IsAngled"` in
  `TileGraphics`: `false` for a frame piece that is not walkable but not a corner, `true` for
  a corner that is walkable.
- Keep sprites in the same folders as the game's sprites of their kind: the game packs sprites
  into atlases by folder, and some kinds (floors, walls) are drawn with atlas-specific settings.
- PNG with transparency, no padding beyond what the game's sprites have.
- The official template's `Artwork/` folder has Blender files and scripts that render sprites
  in the game's style: https://github.com/kodolinija/stardeus-mod-template

## Sounds

`Sounds/<path>.ogg` (or `.wav`, `.mp3`) becomes the sound id `<path>`, which defs and code use
like the game's own ids: a def's `"AmbienceClip": "Devices/AssemblerSFX"`, or
`"FX/Explosion_01"` in code. The game's sounds are not files in the Core mod, so there is
nothing to copy; to replace one, give the mod's sound the same id and check in the game that
it plays.

## ModCover.jpg

In the mod's root folder: 800x450 JPEG, under 1 MB (Steam refuses larger preview images).
Shown in the game's mod list and as the Workshop preview. `tools/stardeus new` puts a
placeholder there; `validate` warns until it is replaced.
