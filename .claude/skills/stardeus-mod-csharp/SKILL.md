---
name: stardeus-mod-csharp
description: Write C# code for a Stardeus mod - set up and build the mod's DLL (tools/stardeus build, .vscode/mod.csproj against the game's DLLs), register components, game systems and entity tabs with [SelfInit] or RuntimeInitializeOnLoadMethod, read def properties, save state, log, patch game methods with Harmony, and avoid the traps (reserved assembly names, Stardeus_Mod_Template, per-tick cost). Use when JSON alone cannot do what the mod needs.
---

# C# mods

The game loads every DLL in a mod's `Libraries/` folder at startup (or only those listed in
`DLLFiles`), before its own initialization runs. Mod code compiles against the game's DLLs in
`Managed/`; read the game's code in the snapshot's ReferenceSourceCode (stardeus-mod-source
skill) and decompile what is missing (stardeus-mod-decompile skill). Do not guess APIs: find
the method you call, and a place where the game itself calls it.

## Project and build

- `tools/stardeus new <Id> --kind csharp,content` creates `.vscode/mod.csproj` (builds
  `Code/**/*.cs` into `Libraries/<Id>.dll`) and an example component in `Code/`. The template
  matches the official mod template's layout; the game leaves `.vscode/` out of uploads.
- `tools/stardeus build <Id>` builds it against this computer's game DLLs (the path comes from
  `local/stardeus.props`, written by setup). It needs the .NET SDK; the first build may download
  the .NET Framework reference assemblies from NuGet. In VS Code, "Run Build Task" works too.
- Target: .NET Framework 4.8.1 profile, C# 9. All game DLLs are referenced, including
  `0Harmony.dll`; none are copied into the mod.
- The game only loads code at startup: build, then restart the game.
- Naming: never `Stardeus_Mod_Template` (the game refuses that DLL). An assembly name that
  starts with `System`, `Unity`, `Microsoft.`, `Mono.`, `Newtonsoft`, `MessagePack`, `0Harmony`,
  `KLUnityUtils` (and a few more, see `validate`) loads, but the game skips its `[SelfInit]`
  methods. Component, system and tab names are global: keep the mod's name in them.

## Entry points

- `[SelfInit]` (`using Game.Utils;`) on a private static method: runs during the game's
  initialization stages, `CoreDefs` by default. Stages: `BeforeCoreDefs`, `CoreDefs`,
  `AfterCoreDefs`, `AfterMods`, `Finalize`. Use `[SelfInit(SelfInit.Stage.AfterMods)]` when the
  code needs all defs and mods loaded.
- `[RuntimeInitializeOnLoadMethod]` (UnityEngine) on a private static method: runs right after
  the mod's DLL loads, before the stages. The place for Harmony and key bindings.
- An exception in a `RuntimeInitializeOnLoadMethod` marks the mod as broken and tells the
  player. One in a `[SelfInit]` method is only logged ("Failed executing self init method"),
  and the game carries on without whatever it should have registered.

## A component

The class name minus `Comp` is the component name defs use. The game's components are
`sealed`: extend behavior with a new component that works next to an existing one, not by
inheritance.

```csharp
public sealed class MyModHeaterComp : BaseComponent<MyModHeaterComp> {
    private static readonly int PowerH = Hashes.S("Power");   // your own property key

    [SelfInit]
    private static void Register() {
        AddComponentPrototype(new MyModHeaterComp());
    }

    private int power;

    protected override void OnConfig() {                  // the def's Properties
        power = Config.GetInt(PowerH, 10);
    }

    public override void OnSave() {                       // saved per entity
        GetOrCreateData().SetInt("Power", power);
    }

    protected override void OnLoad(ComponentData data) {
        power = data.GetInt("Power", 10);
    }

    public override void OnLateReady(bool wasLoaded) { }  // all components ready; wasLoaded after a save load
}
```

Keys the game already uses have constants in `PropertyIdH` (`using Game.CodeGen;`); your own
keys are hashed with `Hashes.S("Key")` (`using KL.Utils;`), once, in a static field. Lifecycle:
placed `OnConfig` then `OnReady(false)` then `OnLateReady(false)`; loaded `OnConfig`,
`OnLoad`, `OnReady(true)`, `OnLateReady(true)`; `OnRemove` when the entity goes away. Messages
from other components arrive in `Receive(IComponent sender, int message)` (`MsgIdH`
constants). The template's `Code/ExampleModComp.cs` (official mod template) shows
electricity and AI goals.

## A system, a tab

- Systems: `GameSystem` subclasses registered with `GameSystems.Register(id, () => new MySys())`
  in a `[SelfInit]` method; implement `ISaveable` to save. See the official template's
  `Code/ExampleModSys.cs`, and `Systems/` in the reference source.
- Entity panel tabs: `BaseEntityTab` registered with `RegisterTab(new MyTab())`, widgets via
  `UISpawn`; see the template's `Code/ExampleTab.cs` and
  `Systems/UIUX/Helpers/UISpawnExamples.cs` in the reference source.
- The game state is `S` inside components and systems (`A.S` elsewhere): `S.Sys.<System>`,
  `S.Sig.<Signal>.AddListener(...)`, `S.Query.<Query>.Ask()`, `S.Clock`.

## Harmony

For code the game offers no hook for, patch the method with Harmony (it ships with the game):

```csharp
[RuntimeInitializeOnLoadMethod]
private static void Init() {
    if (Harmony.HasAnyPatches("MyModId")) { return; }          // never patch twice
    new Harmony("MyModId").PatchAll(typeof(MyInit).Assembly);
}

[HarmonyPatch(typeof(SomeGameClass), nameof(SomeGameClass.SomeMethod))]
private static class SomeMethodPatch {
    private static void Postfix() { /* runs after the original */ }
}
```

Prefer a postfix to replacing a method. A patch on a method that runs every frame or tick must
return at once in the common case. Patches break when a game update renames or changes the
method: check them after updates (stardeus-mod-update skill). Worked example with key binding,
reflection and postfixes: `OpenCapsuleHotkey` in https://github.com/kodolinija/stardeus-mod-examples

## Logging and errors

`D.Warn("...{0}", x)` and `D.Err(...)` (`using KL.Utils;`) write to Player.log and the in-game
console (the key left of 1). `tools/stardeus log --mod <Id>` collects them and the exceptions
from the mod's code.

## Performance

Code in ticks, frames and per-entity updates runs thousands of times a minute: no allocations
(no LINQ, no new lists, no string concatenation; build strings with `$"..."` only when they are
shown), cache lookups and hashes in fields, and return early.

Attaching a debugger needs a development build of the game; logging is the practical way.
