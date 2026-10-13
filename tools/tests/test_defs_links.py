import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stardeuslib import links  # noqa: E402
from stardeuslib.defs import DefIndex, merge, name_key  # noqa: E402
from stardeuslib.util import UserError  # noqa: E402

PARENT = {
    "Layer": "Objects", "IsAbstract": True, "TranslationVars": ["1"], "InternalValue": 5,
    "Researchable": {"Prerequisites": ["Research/A"], "IsAutoDiscovered": True, "Storage": 2},
    "Components": [{"Component": "TileTransform", "Properties": [
        {"Key": "Width", "Int": 2}, {"Key": "Height", "Int": 1}]}],
}


class MergeTests(unittest.TestCase):
    def test_child_rules(self):
        child = {"ParentId": "P", "Layer": "Objects", "InternalValue": 9,
                 "Components": [
                     {"Component": "TileTransform", "Properties": [{"Key": "Width", "Float": 1.5},
                                                                   {"Key": "IsRotatable", "Bool": True}]},
                     {"Component": "Battery", "Properties": [{"Key": "Capacity", "Int": 10}]}]}
        result = merge(PARENT, child, "Objects/Devices/X")
        self.assertEqual(result["Id"], "Objects/Devices/X")
        self.assertFalse(result.get("IsAbstract"))
        self.assertNotIn("TranslationVars", result)  # the child's (unset) value replaces the parent's
        self.assertEqual(result["InternalValue"], 5)  # the parent's value wins
        self.assertEqual(result["Researchable"], {"Storage": 2, "Prerequisites": ["Research/A"]})
        props = result["Components"][0]["Properties"]
        self.assertEqual(props[0], {"Key": "IsRotatable", "Bool": True})
        self.assertEqual(props[1], {"Key": "Width", "Int": 0, "Float": 1.5})  # Int is reset
        self.assertEqual(props[2], {"Key": "Height", "Int": 1})
        self.assertEqual(result["Components"][1]["Component"], "Battery")

    def test_index_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Base").mkdir()
            (root / "Base/P.json").write_text(json.dumps(PARENT), encoding="utf-8")
            (root / "Base/C.json").write_text(json.dumps({"ParentId": "Base/P", "Layer": "Objects"}),
                                              encoding="utf-8")
            (root / "Base/Orphan.json").write_text(json.dumps({"ParentId": "Base/Nope"}), encoding="utf-8")
            index = DefIndex()
            index.load_dir(root, "Test")
            self.assertEqual(index.chain("Base/C"), ["Base/C", "Base/P"])
            self.assertEqual(index.effective("Base/C")["Components"][0]["Properties"][0]["Int"], 2)
            self.assertEqual(index.missing_parent("Base/Orphan"), "Base/Nope")

    def test_name_key(self):
        self.assertEqual(name_key("Objects/Devices/Battery", {}), "objects.devices.battery")
        self.assertEqual(name_key("Obj/X", {"NameKey": "obj.y"}), "obj.y")


class LinkTests(unittest.TestCase):
    def test_link_lifecycle_keeps_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "workspace" / "MyMod"
            target.mkdir(parents=True)
            (target / "ModInfo.json").write_text("{}", encoding="utf-8")
            link = root / "game" / "Mods" / "MyMod"
            links.create_dir_link(link, target)
            self.assertTrue(links.is_link(link))
            self.assertTrue(links.same_path(links.link_target(link), target))
            self.assertTrue((link / "ModInfo.json").is_file())
            links.remove_dir_link(link)
            self.assertFalse(link.exists())
            self.assertTrue((target / "ModInfo.json").is_file())

    def test_refuses_real_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "Real"
            real.mkdir()
            with self.assertRaises(UserError):
                links.remove_dir_link(real)
            self.assertTrue(real.is_dir())


if __name__ == "__main__":
    unittest.main()
