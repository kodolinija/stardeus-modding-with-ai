"""Finds the Stardeus install, the player's user folder and the installed game version."""
from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

from . import vdf
from .util import APP_ID, UserError, read_saved

COMPANY = "Kodo Linija"
PRODUCT = "Stardeus"
# The build's changelog starts with "<b>v0.15.0-rc324</b> (2026.10.09)", the build's own version
_VERSION_RE = re.compile(rb"<b>(v\d+\.\d+\.\d+(?:-rc\d+)?)</b> \(\d{4}\.\d\d\.\d\d\)")


def os_name() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _registry_steam_paths() -> list[Path]:
    try:
        import winreg
    except ImportError:
        return []
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]
    found = []
    for hive, key, value in keys:
        try:
            with winreg.OpenKey(hive, key) as k:
                v, _ = winreg.QueryValueEx(k, value)
            if v:
                found.append(Path(v))
        except OSError:
            pass
    return found


def steam_roots() -> list[Path]:
    home = Path.home()
    system = os_name()
    if system == "windows":
        candidates = _registry_steam_paths() + [
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Steam",
        ]
    elif system == "macos":
        candidates = [home / "Library/Application Support/Steam"]
    else:
        candidates = [
            home / ".steam/steam",
            home / ".steam/root",
            home / ".local/share/Steam",
            home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
            home / ".var/app/com.valvesoftware.Steam/data/Steam",
            home / "snap/steam/common/.local/share/Steam",
        ]
    roots, seen = [], set()
    for c in candidates:
        try:
            r = c.resolve()
        except OSError:
            continue
        key = os.path.normcase(str(r))
        if key in seen or not (r / "steamapps").is_dir():
            continue
        seen.add(key)
        roots.append(r)
    return roots


def library_folders(root: Path) -> list[Path]:
    libs = [root]
    for path in (root / "steamapps/libraryfolders.vdf", root / "config/libraryfolders.vdf"):
        if not path.is_file():
            continue
        try:
            data = vdf.load(path)
        except (OSError, vdf.VdfError):
            continue
        folders = vdf.get(data, "libraryfolders") or {}
        for key, val in folders.items():
            if not key.isdigit():
                continue
            lib = vdf.get(val, "path") if isinstance(val, dict) else val
            if lib:
                libs.append(Path(lib))
    unique, seen = [], set()
    for lib in libs:
        k = os.path.normcase(os.path.abspath(lib))
        if k not in seen:
            seen.add(k)
            unique.append(lib)
    return unique


def find_steam_install() -> dict | None:
    for root in steam_roots():
        for lib in library_folders(root):
            manifest = lib / "steamapps" / f"appmanifest_{APP_ID}.acf"
            if not manifest.is_file():
                continue
            try:
                app = vdf.get(vdf.load(manifest), "AppState") or {}
            except (OSError, vdf.VdfError):
                app = {}
            game = lib / "steamapps" / "common" / (vdf.get(app, "installdir") or "Stardeus")
            if game.is_dir():
                return {
                    "steam_root": str(root),
                    "library": str(lib),
                    "game_dir": game,
                    "build_id": vdf.get(app, "buildid"),
                    "target_build_id": vdf.get(app, "TargetBuildID"),
                }
    return None


def _non_steam_candidates() -> list[Path]:
    home = Path.home()
    system = os_name()
    if system == "windows":
        pf86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        return [pf86 / "GOG Galaxy/Games/Stardeus", Path(r"C:\GOG Games\Stardeus")]
    if system == "macos":
        return [Path("/Applications/Stardeus"), Path("/Applications")]
    return [home / "GOG Games/Stardeus", home / "Games/Stardeus"]


def find_data_dir(game_dir: Path) -> Path | None:
    """Stardeus_Data on Windows and Linux, Stardeus.app/Contents/Resources/Data on macOS."""
    candidates = [game_dir / "Stardeus_Data", game_dir / "Stardeus.app/Contents/Resources/Data"]
    candidates += sorted(game_dir.glob("*_Data")) + sorted(game_dir.glob("*.app/Contents/Resources/Data"))
    for c in candidates:
        if (c / "StreamingAssets/Mods/Core/ModInfo.json").is_file():
            return c
    return None


def default_user_dir(steam: dict | None) -> Path:
    """Unity's persistentDataPath for the game: saves, Mods, Player.log, Patched."""
    home = Path.home()
    system = os_name()
    if system == "windows":
        base = Path(os.environ.get("USERPROFILE") or home)
        return base / "AppData" / "LocalLow" / COMPANY / PRODUCT
    if system == "macos":
        return home / "Library/Application Support" / COMPANY / PRODUCT
    xdg = os.environ.get("XDG_CONFIG_HOME")
    native = (Path(xdg) if xdg else home / ".config") / "unity3d" / COMPANY / PRODUCT
    if native.is_dir() or not steam:
        return native
    # The Windows build running through Proton keeps its data inside the Proton prefix
    proton = (Path(steam["library"]) / "steamapps/compatdata" / APP_ID
              / "pfx/drive_c/users/steamuser/AppData/LocalLow" / COMPANY / PRODUCT)
    return proton if proton.is_dir() else native


def read_game_version(data_dir: Path) -> str | None:
    assets = data_dir / "resources.assets"
    if not assets.is_file():
        return None
    try:
        m = _VERSION_RE.search(assets.read_bytes())
    except OSError:
        return None
    return m.group(1).decode() if m else None


def _fingerprint(data_dir: Path, core_dir: Path) -> str:
    h = hashlib.sha1()
    for p in (data_dir / "resources.assets", core_dir / "ModInfo.json", core_dir / "Definitions"):
        if p.exists():
            st = p.stat()
            h.update(f"{p.name}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:10]


def detect(game_dir: str | None = None, user_dir: str | None = None) -> dict:
    """Everything the workspace needs to know about this machine's Stardeus.

    Priority: arguments, then STARDEUS_GAME_DIR / STARDEUS_USER_DIR, then the overrides saved
    by an earlier `setup`, then auto-detection.
    """
    saved = read_saved().get("overrides") or {}
    game_override = game_dir or os.environ.get("STARDEUS_GAME_DIR") or saved.get("game_dir")
    user_override = user_dir or os.environ.get("STARDEUS_USER_DIR") or saved.get("user_dir")

    steam = find_steam_install()
    if game_override:
        game = Path(game_override).expanduser()
        source = "override"
        if steam and not os.path.normcase(os.path.abspath(steam["game_dir"])) == \
                os.path.normcase(os.path.abspath(game)):
            steam = None
    elif steam:
        game = steam["game_dir"]
        source = "steam"
    else:
        game = next((c for c in _non_steam_candidates() if find_data_dir(c)), None)
        source = "guess"
        if game is None:
            raise UserError(
                "Could not find Stardeus. Install it through Steam, or tell the workspace where "
                "it is: tools/stardeus setup --game-dir \"<folder that contains Stardeus.exe>\"")
    data = find_data_dir(game)
    if data is None:
        raise UserError(f"{game} does not look like a Stardeus install "
                        "(no Stardeus_Data/StreamingAssets/Mods/Core inside)")
    core = data / "StreamingAssets/Mods/Core"
    user = Path(user_override).expanduser() if user_override else default_user_dir(steam)
    version = read_game_version(data)
    build = steam.get("build_id") if steam else None
    tag = f"b{build}" if build else f"f{_fingerprint(data, core)}"
    last_played = None
    lp = user / "LastPlayedVersion.txt"
    if lp.is_file():
        last_played = lp.read_text(encoding="utf-8", errors="replace").strip() or None
    ref = core / "ReferenceSourceCode"
    schemas = core / "Config/Schemas"
    return {
        "os": os_name(),
        "source": source,
        "game_dir": str(game),
        "data_dir": str(data),
        "managed_dir": str(data / "Managed"),
        "core_dir": str(core),
        "reference_source_dir": str(ref) if ref.is_dir() else None,
        "schemas_dir": str(schemas) if schemas.is_dir() else None,
        "user_dir": str(user),
        "mods_dir": str(user / "Mods"),
        "player_log": str(user / "Player.log"),
        "player_prev_log": str(user / "Player-prev.log"),
        "patched_dir": str(user / "Patched"),
        "game_version": version,
        "last_played_version": last_played,
        "steam": {k: v for k, v in (steam or {}).items() if k != "game_dir"} or None,
        "snapshot_id": f"{version or 'unknown'}_{tag}",
        # Only explicit choices are remembered; environment variables apply per run
        "overrides": {"game_dir": game_dir or saved.get("game_dir"),
                      "user_dir": user_dir or saved.get("user_dir")},
    }
