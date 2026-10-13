---
paths:
  - "mods/**/*.json"
---

# Mod JSON

- Before writing JSON, open the closest Core file in `local/game/<build>/Core/` and follow its
  shape. Components, property keys and config fields come from the game's files and code;
  never make one up (`tools/stardeus find`, `tools/stardeus def`, the component's `*Comp.cs`).
- Do not copy a Core file into the mod to change it: write a patch (`Patches/`). New content
  gets new ids; put the mod's name in new file names to avoid clashes with other mods.
- Every def that is not `"IsAbstract": true` sets `"Layer"`, even when its parent has one.
- `//` comments are fine. No duplicate keys, no trailing commas.
- After every change: `tools/stardeus validate <ModId>`, and fix what it reports.
