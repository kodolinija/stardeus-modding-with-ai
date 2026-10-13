---
paths:
  - "mods/**/Patches/**/*.json"
---

# Mod patches

- Patches act on the target file as written, before ParentId inheritance. Check paths against
  `tools/stardeus def <id> --raw` or the file in the snapshot, not the merged def.
- Array queries are `Name[Key=Value]`, never `Name/[Key=Value]`. Replace the typed field the
  file uses (`/Int`, `/Float`, `/String`...). `TranslationVars` hold strings.
- Never end an `add` or `replace` path with a `[Key=Value]` query: remove the element, then add
  the new one with `/-`.
- After `tools/stardeus validate <ModId>`, read the simulated result in `local/patched/<ModId>/`.
