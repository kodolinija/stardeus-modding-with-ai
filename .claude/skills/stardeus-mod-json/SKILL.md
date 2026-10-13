---
name: stardeus-mod-json
description: Write Stardeus mod JSON - defs in Definitions/ (devices, furniture, items, materials, beings, walls, floors, research) and configs in Config/ (traits, quests, story events, recipes, materials, tunables, curves) - with the right ids, ParentId inheritance, components and typed properties, and check them against the game's JSON schemas with tools/stardeus validate. Use for adding new content or deciding where a JSON file goes; for changing existing content use the patches skill.
---

# Defs and configs

Look at how the game does the same thing first: find the closest Core def or config
(stardeus-mod-source skill) and follow its shape. The game is the reference, these notes explain
what is not obvious.

## Defs (`Definitions/`)

A def describes something that exists in the world. Its id is its path under `Definitions/`
without `.json` (`Definitions/Objects/Devices/MyLamp.json` is `Objects/Devices/MyLamp`), unless
the file sets `"Id"`.

```jsonc
{
    "Layer" : "Objects",
    "ParentId" : "Objects/Devices/BaseDevice",
    "Researchable" : { "Prerequisites" : [ "Research/Energy/Solar" ] },
    "TranslationVars" : [ "50" ],
    "Components" : [
        {
            "Component" : "TileTransform",
            "Properties" : [
                { "Key" : "Width", "Int" : 2 },
                { "Key" : "IsRotatable", "Bool" : true }
            ]
        }
    ]
}
```

- `Layer`: `Objects` (devices, furniture, cosmetics), `FreeEntities` (items, materials,
  beings), `Floor`, `Walls` (walls and doors). Every def that is not `"IsAbstract": true` must
  set it, even when its parent does.
- A component is a C# class (`<Name>Comp.cs`). A property has a `Key` and exactly one typed
  value: `Int`, `Float`, `Bool`, `String`, `Vector2` (`{ "x": 0, "y": -1 }`), `IntSet`,
  `FloatSet`, `StringSet`, `BoolSet`, `Vector2Set`, `PosIdx`, or `RawMaterials`
  (`[ { "TypeId": "SteelPlate", "StackSize": 4 } ]`). Use the type the component's code reads.
- Name and description: the translation keys are the id in lower case with dots
  (`objects.devices.mylamp`, `objects.devices.mylamp.desc`), or `NameKey` / `DescKey`.
  `TranslationVars` fill `{0}`, `{1}` in the name and description. `UseParentTexts` reuses the
  parent's texts. Add the keys to `Translations/English.csv` (stardeus-mod-assets skill).
- `ToolPath` (build menu category, like `Energy` or `Devices/Facilities`), `BuildGroup`,
  `Researchable` (tech tree gate), `Spawnable` (appears in generated places), `PreviewIcon`.
- Ids are global. A mod def whose id already exists is refused (the game says to use JSON
  patching), so new defs need new ids. Putting the mod's name in the file name avoids clashes
  with other mods.

### What a child def inherits

`ParentId` copies the parent (already merged with its own parents), then applies the child:

| Field | Result |
|---|---|
| `Components` | Merged by component name: a child component adds properties to the parent's one or replaces properties with the same `Key`; new components are added |
| A property with the same `Key` | `String` and the `...Set` / `RawMaterials` values replace the parent's when set. `Int`, `Float`, `Bool`, `PosIdx` and `Vector2` always take the child's value, 0 or false when the child leaves them out |
| `Layer`, `TranslationVars`, `NameKey`, `DescKey`, `UseParentTexts`, `BuildGroup`, `ParentId` | Always the child's own value, even when the child does not set them |
| `ToolPath`, `PreviewIcon`, `Seasonal` | The child's when set, else the parent's |
| `Researchable` | `Prerequisites`, `UnlockEffects` and `DatoidCosts` from the child when set; `UnlockValue` and `Storage` the larger; `IsTreeNode` either. Other Researchable fields are dropped |
| `Spawnable` | The child's whole block when it sets `Chance`, `ChanceLocked`, `TierDiff`, `Category` or `SkipOwned`, else the parent's |
| `Tier` | The larger. `ResearchValue`: the child's when above 0. `WealthValueMul`: the child's unless 1 |
| `IsAbstract` | Only when both are abstract |
| `IsImportant`, `IsUnfinished`, `IgnoreMarket`, `SkipToolListing` | True when either is |
| `InternalValue`, `IsBeing` | Always the parent's |

So a variant of an existing device can inherit straight from it
(`"ParentId": "Objects/Devices/Battery"`) and override only what differs, setting `Layer`
and `TranslationVars` again. `tools/stardeus def <id>` shows the result, including for mod defs.

## Configs (`Config/`)

Each folder holds one type of data, one object per file, loaded from Core and then from every
mod in load order. When a config type has an `Id` and the file does not set it, the id is the
file's path inside the folder. A mod file at the same path as a Core file replaces it
entirely, so to change a Core config, patch it instead. `tools/schema_catalog.json` lists the
folders the game reads.

- Tunables (`Config/Tunable/`): global numbers in `Ints`, `Floats` and similar lists of
  `{ "Key": ..., "Int": ... }`. A mod's tunable file may have any name and only the keys it
  changes; its values replace the game's by key.
- Materials: a material needs a config in `Config/Materials/<folder>/<Id>.json`, an item def
  in `Definitions/Obj/Materials/<Id>.json` whose `UnstoredMat` component has `Type` = the
  material Id, and usually recipes in `Config/Craftable/<Type>/` (`ProductDefId` names what
  is made). Copy the pattern of a similar Core material.
- Story events, quests and traits have their own folders and schemas. Mirror a Core file of
  the same kind, then test it in the game (stardeus-mod-test skill has the console commands).

## Checking

`tools/stardeus validate <ModId>` reads every JSON file like the game does (`//` and `/* */`
comments are fine; duplicate keys are refused; avoid trailing commas), checks each against the
schema the game ships for it, and checks ids, parents, components, property keys, sprites and
translation keys. Fix every error. Warnings are likely mistakes; leave one only when you know
why it is fine (a key read by your own C# code, for example).

The schemas live in `local/game/<build>/Core/Config/Schemas/`. Older game versions ship only
some of them; files without a schema are checked for valid JSON and the def rules only.
`tools/stardeus setup --vscode` maps the schemas in VS Code for autocomplete.
