---
paths:
  - "mods/**/*.cs"
  - "mods/**/*.csproj"
---

# Mod C#

- Check every game type and method you use in the snapshot's ReferenceSourceCode or in
  decompiled code, and find a place where the game itself uses it. Do not guess APIs.
- Entry points are private static methods with `[SelfInit]` (`using Game.Utils;`) or
  `[RuntimeInitializeOnLoadMethod]`.
- Component, system and tab names are global: include the mod's name in them. Keep the
  `AssemblyName` unique, never `Stardeus_Mod_Template`, and not starting with System, Unity,
  Microsoft., Mono. or Newtonsoft.
- Code that runs per tick, per frame or per entity must not allocate: no LINQ, no new
  collections, no string building; cache hashes (`Hashes.S`) in static fields.
- Harmony: patch once (`Harmony.HasAnyPatches`), prefer postfixes, return early.
- Build with `tools/stardeus build <ModId>`, then restart the game to load the new DLL.
