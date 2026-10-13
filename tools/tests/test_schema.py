import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stardeuslib.schema import Validator  # noqa: E402

SCHEMA = {
    "$ref": "#/$defs/Def",
    "$defs": {
        "Def": {
            "type": ["object", "null"],
            "properties": {
                "Layer": {"type": ["string", "null"]},
                "Tier": {"type": "integer"},
                "Value": {"type": "number"},
                "Flag": {"type": "boolean"},
                "Kind": {"enum": ["Small", "Large"]},
                "Components": {"type": ["array", "null"], "items": {"$ref": "#/$defs/Comp"}},
                "Either": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            },
            "additionalProperties": False,
        },
        "Comp": {
            "type": "object",
            "properties": {"Component": {"type": "string"}},
            "additionalProperties": False,
        },
    },
}


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.v = Validator(SCHEMA)

    def test_valid(self):
        self.assertEqual(self.v.validate({"Layer": "Objects", "Tier": 2.0, "Value": 1, "Flag": True,
                                          "Kind": "Small", "Components": [{"Component": "A"}],
                                          "Either": 3}), [])

    def test_unknown_key_suggests(self):
        errors = self.v.validate({"Layr": "Objects"})
        self.assertEqual(errors[0][0], "/Layr")
        self.assertIn('did you mean "Layer"', errors[0][1])

    def test_types(self):
        self.assertTrue(self.v.validate({"Tier": 1.5}))
        self.assertTrue(self.v.validate({"Tier": True}))
        self.assertTrue(self.v.validate({"Flag": 1}))
        self.assertTrue(self.v.validate({"Value": "1"}))

    def test_nested_ref_and_items(self):
        errors = self.v.validate({"Components": [{"Component": "A"}, {"Componnet": "B"}]})
        self.assertEqual(errors[0][0], "/Components/1/Componnet")

    def test_enum_and_any_of(self):
        self.assertIn('did you mean "Large"', self.v.validate({"Kind": "Larg"})[0][1])
        self.assertTrue(self.v.validate({"Either": [1]}))

    def test_null_allowed(self):
        self.assertEqual(self.v.validate(None), [])


if __name__ == "__main__":
    unittest.main()
