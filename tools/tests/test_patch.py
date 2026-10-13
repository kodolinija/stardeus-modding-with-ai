import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stardeuslib.patch import apply_patch  # noqa: E402


def doc():
    return {
        "TranslationVars": ["8", "20"],
        "Components": [
            {"Component": "TileTransform", "Properties": [{"Key": "Width", "Int": 1}]},
            {"Component": "ElectricNode", "Properties": [
                {"Key": "MaxConnections", "Int": 8},
                {"Key": "ConnectorRange", "Int": 20},
                {"Key": "IsConsumer", "Bool": True},
            ]},
        ],
        "StartingJobs": [{"Job": "Hauling"}],
    }


def run(*ops):
    return apply_patch(doc(), {"target": "x", "operations": list(ops)})


class PatchTests(unittest.TestCase):
    def test_template_style_replace(self):
        result, problems = run(
            {"op": "replace", "path": "/TranslationVars", "value": [16, 40]},
            {"op": "replace", "path": "/Components[Component=ElectricNode]/Properties[Key=MaxConnections]/Int",
             "value": 16})
        self.assertEqual(problems, [])
        self.assertEqual(result["TranslationVars"], [16, 40])
        self.assertEqual(result["Components"][1]["Properties"][0]["Int"], 16)

    def test_append_and_insert(self):
        result, problems = run({"op": "add", "path": "/StartingJobs/-", "value": {"Job": "Shooting"}},
                               {"op": "add", "path": "/StartingJobs/0", "value": {"Job": "First"}})
        self.assertEqual(problems, [])
        self.assertEqual([j["Job"] for j in result["StartingJobs"]], ["First", "Hauling", "Shooting"])

    def test_remove_queried_element(self):
        result, problems = run({"op": "remove", "path": "/Components[Component=TileTransform]"})
        self.assertEqual(problems, [])
        self.assertEqual([c["Component"] for c in result["Components"]], ["ElectricNode"])

    def test_query_on_bool_uses_game_text(self):
        result, problems = run({"op": "replace",
                                "path": "/Components[Component=ElectricNode]/Properties[Bool=True]/Bool",
                                "value": False})
        self.assertEqual(problems, [])
        self.assertFalse(result["Components"][1]["Properties"][2]["Bool"])

    def test_remove_missing_key_removes_parent(self):
        result, problems = run({"op": "remove",
                                "path": "/Components[Component=ElectricNode]/Properties[Key=MaxConnections]/Float"})
        self.assertEqual(problems[0].severity, "error")
        self.assertEqual(len(result["Components"][1]["Properties"]), 2)

    def test_missing_element_is_skipped(self):
        result, problems = run({"op": "replace", "path": "/Components[Component=Nope]/Properties", "value": []},
                               {"op": "replace", "path": "/TranslationVars", "value": []})
        self.assertEqual(len(problems), 1)
        self.assertIn("no element", problems[0].message)
        self.assertEqual(result["TranslationVars"], [])

    def test_query_as_last_segment_warns(self):
        _, problems = run({"op": "replace", "path": "/Components[Component=TileTransform]", "value": {}})
        self.assertEqual(problems[0].severity, "warning")

    def test_replace_missing_key_adds_it(self):
        result, problems = run({"op": "replace", "path": "/NewKey", "value": 1})
        self.assertEqual(result["NewKey"], 1)
        self.assertEqual(problems[0].severity, "warning")

    def test_invalid_paths_and_ops(self):
        _, problems = run({"op": "replace", "path": "/Components/[Component=X]", "value": 1},
                          {"op": "move", "path": "/A", "from": "/B"},
                          {"op": "add", "path": "StartingJobs/-", "value": 1},
                          {"op": "add", "path": "/StartingJobs/-1", "value": 1},
                          {"op": "add", "path": "/StartingJobs/-"})
        self.assertEqual([p.severity for p in problems], ["error"] * 5)

    def test_remove_by_value(self):
        result, problems = run({"op": "remove", "path": "/StartingJobs/-", "value": {"Job": "Hauling"}})
        self.assertEqual(problems, [])
        self.assertEqual(result["StartingJobs"], [])

    def test_no_operations(self):
        _, problems = apply_patch(doc(), {"target": "x"})
        self.assertEqual(problems[0].severity, "error")


if __name__ == "__main__":
    unittest.main()
