---
paths:
  - "mods/**/Translations/*.csv"
---

# Mod translations

- The first line is a header the game skips. Rows have 4 columns: key, text, version (empty),
  comment. Quote texts with commas, quotes (`""`) or line breaks.
- Def names use the def id in lower case with dots; descriptions add `.desc`.
- Keep `{0}` placeholders exactly as the def's `TranslationVars` (or the game's text, when
  overriding one of its keys) expect.
- Add new keys at the end of the file. Override a game text only when the user wants that
  text changed.
