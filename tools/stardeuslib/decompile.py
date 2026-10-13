"""Decompiles game DLLs with dnSpy (Windows) or ilspycmd (any system) into local/decompiled/."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .util import LOCAL, TOOLS, UserError, rel

HOST_SRC = TOOLS / "dnspy-host"
HOST_OUT = LOCAL / "tools" / "dnspy-host"


def dnspy_dir(paths: dict) -> Path | None:
    candidates = [os.environ.get("DNSPY_DIR"), (paths.get("tools") or {}).get("dnspy_dir")]
    for exe in ("dnSpy.Console.exe", "dnSpy.exe"):
        found = shutil.which(exe)
        if found:
            candidates.append(str(Path(found).parent))
    for c in candidates:
        if not c:
            continue
        for d in (Path(c), Path(c) / "bin"):
            if (d / "dnSpy.Console.dll").is_file():
                return d
    return None


def ilspy_command() -> list[str] | None:
    found = shutil.which("ilspycmd")
    return [found] if found else None


def _host_exe() -> Path | None:
    for p in HOST_OUT.rglob("DnSpyHost.exe") if HOST_OUT.is_dir() else []:
        return p
    return None


def _build_host() -> Path:
    exe = _host_exe()
    newest_src = max(p.stat().st_mtime for p in HOST_SRC.iterdir())
    if exe and exe.stat().st_mtime >= newest_src:
        return exe
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise UserError("dnSpy's console needs a small helper built with the .NET SDK "
                        "(https://dotnet.microsoft.com/download). Or use --tool ilspy.")
    result = subprocess.run([dotnet, "build", str(HOST_SRC / "DnSpyHost.csproj"), "-c", "Release",
                             "-nologo", "-v", "q", "--artifacts-path", str(HOST_OUT)],
                            capture_output=True, text=True)
    exe = _host_exe()
    if result.returncode != 0 or exe is None:
        raise UserError(f"Building the dnSpy helper failed:\n{result.stdout}\n{result.stderr}")
    return exe


def resolve_dll(target: str, paths: dict) -> Path:
    p = Path(target)
    if p.is_file():
        return p
    managed = Path(paths["managed_dir"])
    for name in (target, f"{target}.dll"):
        if (managed / name).is_file():
            return managed / name
    raise UserError(f'"{target}" is not a file or a DLL in {managed}')


def run(target: str, paths: dict, tool: str | None, out: str | None, type_name: str | None) -> int:
    dll = resolve_dll(target, paths)
    out_dir = Path(out) if out else LOCAL / "decompiled" / paths["snapshot_id"] / dll.stem
    windows = sys.platform.startswith("win")
    dn = dnspy_dir(paths) if windows else None
    if tool is None:
        tool = "dnspy" if dn else "ilspy"
    out_dir.mkdir(parents=True, exist_ok=True)
    if tool == "dnspy":
        if not windows:
            raise UserError("dnSpy runs on Windows only; use --tool ilspy")
        if dn is None:
            raise UserError("dnSpy was not found. Get dnSpyEx from https://github.com/dnSpyEx/dnSpy/releases, "
                            "unzip it, and run: tools/stardeus setup --dnspy \"<its folder>\" "
                            "(or set DNSPY_DIR). Or use --tool ilspy.")
        cmd = [str(_build_host()), str(dn), "--no-sln", "-o", str(out_dir), str(dll)]
    else:
        ilspy = ilspy_command()
        if ilspy is None:
            raise UserError("ilspycmd was not found. Install it with: dotnet tool install -g ilspycmd "
                            "(needs the .NET SDK), then open a new terminal.")
        cmd = ilspy + ["-p", "-o", str(out_dir), str(dll)]
    print(f"Decompiling {dll.name} with {tool} into {rel(out_dir)} (can take a minute)...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    files = list(out_dir.rglob("*.cs"))
    if result.returncode != 0 or not files:
        detail = (result.stderr or result.stdout or "").strip()[-2000:]
        raise UserError(f"{tool} failed (exit {result.returncode}). {detail}")
    print(f"{len(files)} .cs files in {rel(out_dir)}")
    if type_name:
        short = type_name.split(".")[-1]
        hits = [f for f in files if f.stem == short]
        for f in hits:
            print(f"  {rel(f)}")
        if not hits:
            print(f"  no file named {short}.cs; search inside with grep")
    print("Read these files to learn; never publish or redistribute decompiled game code.")
    return 0
