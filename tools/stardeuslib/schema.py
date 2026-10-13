"""Validates JSON against the schemas the game ships in Core/Config/Schemas.

The game generates those schemas from its C# types and uses a small subset of JSON Schema:
type, properties, additionalProperties, items, $ref into $defs, enum, anyOf, pattern and
required. This validator implements exactly that subset.
"""
from __future__ import annotations

import difflib
import re

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "integer": lambda v: (isinstance(v, int) and not isinstance(v, bool))
    or (isinstance(v, float) and v.is_integer()),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


def _type_name(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    return "object"


class Validator:
    def __init__(self, schema: dict):
        self.root = schema

    def validate(self, value) -> list[tuple[str, str]]:
        """Returns (json pointer, message) pairs; empty when the value matches."""
        errors: list[tuple[str, str]] = []
        self._check(value, self.root, "", errors)
        return errors

    def _resolve(self, schema: dict) -> dict:
        seen = 0
        while "$ref" in schema:
            ref = schema["$ref"]
            if not ref.startswith("#/"):
                return {}
            node = self.root
            for part in ref[2:].split("/"):
                node = node.get(part, {}) if isinstance(node, dict) else {}
            extra = {k: v for k, v in schema.items() if k != "$ref"}
            schema = {**node, **extra} if extra else node
            seen += 1
            if seen > 50:
                return {}
        return schema

    def _check(self, value, schema: dict, path: str, errors: list) -> None:
        schema = self._resolve(schema)
        if not schema:
            return
        if "anyOf" in schema:
            best = None
            for option in schema["anyOf"]:
                attempt: list = []
                self._check(value, option, path, attempt)
                if not attempt:
                    best = None
                    break
                if best is None or len(attempt) < len(best):
                    best = attempt
            if best:
                errors.extend(best)
                return
        types = schema.get("type")
        if types is not None:
            names = types if isinstance(types, list) else [types]
            if not any(_TYPES.get(t, lambda v: True)(value) for t in names):
                errors.append((path or "/", f"expected {' or '.join(names)}, got {_type_name(value)}"))
                return
        if "enum" in schema and value not in schema["enum"]:
            allowed = [str(x) for x in schema["enum"]]
            hint = difflib.get_close_matches(str(value), allowed, n=1)
            msg = f'"{value}" is not one of the allowed values'
            if hint:
                msg += f' (did you mean "{hint[0]}"?)'
            elif len(allowed) <= 12:
                msg += f": {', '.join(allowed)}"
            errors.append((path or "/", msg))
        if isinstance(value, str) and "pattern" in schema:
            if not re.search(schema["pattern"], value):
                errors.append((path or "/", f'"{value}" does not match the pattern {schema["pattern"]}'))
        if isinstance(value, dict):
            props = schema.get("properties", {})
            extra = schema.get("additionalProperties", True)
            for key in schema.get("required", []):
                if key not in value:
                    errors.append((path or "/", f'missing required key "{key}"'))
            for key, sub in value.items():
                sub_path = f"{path}/{key}"
                if key in props:
                    self._check(sub, props[key], sub_path, errors)
                elif extra is False:
                    hint = difflib.get_close_matches(key, list(props), n=1)
                    msg = f'unknown key "{key}"'
                    msg += f' (did you mean "{hint[0]}"?)' if hint else " (the game ignores it)"
                    errors.append((sub_path, msg))
                elif isinstance(extra, dict):
                    self._check(sub, extra, sub_path, errors)
        if isinstance(value, list) and isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                self._check(item, schema["items"], f"{path}/{i}", errors)


def top_level_keys(schema: dict) -> list[str]:
    """The keys the root object of a schema accepts."""
    node = Validator(schema)._resolve(schema)
    return list(node.get("properties", {}))
