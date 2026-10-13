# Your mods

Each folder here is one mod (`tools/stardeus new <ModId>` creates one). Every mod is linked
into the game's own Mods folder, so the game loads it straight from here: edit, restart the
game, see the change.

The contents of this folder are not part of the workspace's repository, so `git pull` never
touches them. Back your mods up, or make each one its own git repository (`git init` inside
the mod's folder).

`Directory.Build.props` points C# mod projects at the game's DLLs on this computer.
