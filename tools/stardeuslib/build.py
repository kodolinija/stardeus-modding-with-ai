"""Builds a mod's C# project into its Libraries folder."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .mods import Mod
from .util import UserError, rel


def projects(mod: Mod) -> list[Path]:
    found = sorted((mod.dir / ".vscode").glob("*.csproj"))
    if not found:
        found = sorted(p for p in mod.dir.rglob("*.csproj")
                       if "obj" not in p.relative_to(mod.dir).parts)
    return found


def run(mod: Mod, paths: dict, configuration: str) -> int:
    found = projects(mod)
    if not found:
        raise UserError(f"{rel(mod.dir)} has no .csproj. Create one with the C# template "
                        "(see the stardeus-mod-csharp skill).")
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise UserError("The .NET SDK is not installed: https://dotnet.microsoft.com/download")
    code = 0
    for proj in found:
        cmd = [dotnet, "build", str(proj), "-c", configuration, "-nologo",
               f"-p:StardeusManaged={paths['managed_dir']}"]
        print(f"Building {rel(proj)}")
        code = subprocess.run(cmd).returncode or code
    libs = mod.content("Libraries")
    if libs:
        for dll in sorted(libs.glob("*.dll")):
            print(f"  {rel(dll)}")
    if code == 0:
        print("Restart the game to load the new DLL (the game loads mod code only at startup).")
    return code
