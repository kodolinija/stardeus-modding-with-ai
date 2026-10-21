import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stardeuslib import catalog, jsonc, vdf  # noqa: E402
from stardeuslib.jpeg import image_info  # noqa: E402
from stardeuslib.util import TEMPLATES  # noqa: E402


class VdfTests(unittest.TestCase):
    def test_library_folders_current_format(self):
        data = vdf.parse(r'''
"libraryfolders"
{
    "0" { "path" "C:\\Program Files (x86)\\Steam" "apps" { "1380910" "123" } }
    "1" { "path" "D:\\SteamLibrary" }
}''')
        folders = vdf.get(data, "LibraryFolders")
        self.assertEqual(vdf.get(folders["1"], "PATH"), "D:\\SteamLibrary")
        self.assertEqual(folders["0"]["apps"]["1380910"], "123")

    def test_old_format_and_comments(self):
        data = vdf.parse('"LibraryFolders"\n{\n // note\n "TimeNextStatsReport" "1"\n "1" "E:\\\\Games"\n}')
        self.assertEqual(vdf.get(data, "libraryfolders")["1"], "E:\\Games")

    def test_appmanifest(self):
        data = vdf.parse('"AppState" { "appid" "1380910" "installdir" "Stardeus" "buildid" "42" }')
        app = vdf.get(data, "AppState")
        self.assertEqual(vdf.get(app, "InstallDir"), "Stardeus")
        self.assertEqual(app["buildid"], "42")

    def test_unterminated(self):
        with self.assertRaises(vdf.VdfError):
            vdf.parse('"a" "b')


class JsoncTests(unittest.TestCase):
    def test_comments_and_strings(self):
        value, notes = jsonc.loads('{\n // c\n "a": "x // not a comment", /* b */ "b": "/* nor this */"\n}')
        self.assertEqual(value, {"a": "x // not a comment", "b": "/* nor this */"})
        self.assertEqual(notes, [])

    def test_trailing_commas_are_noted(self):
        value, notes = jsonc.loads('{"a": [1, 2,],\n "b": 1,}')
        self.assertEqual(value, {"a": [1, 2], "b": 1})
        self.assertEqual(len(notes), 2)

    def test_duplicate_keys_fail(self):
        with self.assertRaises(jsonc.JsoncError):
            jsonc.loads('{"a": 1, "a": 2}')

    def test_error_has_line(self):
        with self.assertRaises(jsonc.JsoncError) as ctx:
            jsonc.loads('{\n "a": 1\n "b": 2\n}')
        self.assertEqual(ctx.exception.line, 3)

    def test_bom_and_escaped_quote(self):
        value, _ = jsonc.loads('\ufeff{"a": "say \\"hi\\" // ok"}')
        self.assertEqual(value["a"], 'say "hi" // ok')


class CatalogTests(unittest.TestCase):
    def test_patterns(self):
        self.assertEqual(catalog.schema_for("Mods/X/ModInfo.json"), "ModInfo.schema.json")
        self.assertEqual(catalog.schema_for("Mods/X/Definitions/Objects/A.json"), "Def.schema.json")
        self.assertEqual(catalog.schema_for("Mods/X/0.15/Definitions/A.json"), "Def.schema.json")
        self.assertIsNone(catalog.schema_for("Mods/X/Patches/A.json"))
        self.assertIsNone(catalog.schema_for("Mods/X/Sub/ModInfo.json"))


class ImageTests(unittest.TestCase):
    def test_placeholder_cover_is_800x450(self):
        self.assertEqual(image_info(TEMPLATES / "ModCover.jpg"), ("jpeg", 800, 450))


class VersionTests(unittest.TestCase):
    """The game decides which ModVersion a DisabledMods.json entry covers with these rules."""

    def test_versions_compare_like_the_game(self):
        from stardeuslib.validate import version_newer
        self.assertTrue(version_newer("1.2.6", "1.2.5"))
        self.assertFalse(version_newer("1.2.5", "1.2.5"))
        self.assertFalse(version_newer("1.2.4", "1.2.5"))
        self.assertTrue(version_newer("1.10.0", "1.9.9"))
        self.assertTrue(version_newer("1.0.1", "1.0.1-rc2"))
        self.assertFalse(version_newer("1.0.1-rc1", "1.0.1-rc2"))
        self.assertFalse(version_newer("not a version", "1.0.0"))


if __name__ == "__main__":
    unittest.main()
