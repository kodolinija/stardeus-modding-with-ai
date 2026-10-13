"""Applies Stardeus JSON patches the way the game does, and explains what would go wrong.

The game's patcher supports a subset of RFC 6902: "add", "replace" and "remove", plus array
queries such as /Components[Component=Battery]/Properties[Key=Capacity]/Int. It has quirks
that this module reproduces on purpose, because a patch is only correct if it works in the game:

- A failing operation is logged to Player.log and skipped; the later operations still run.
- "remove" of a key that does not exist removes the object that should have held it.
- "add" or "replace" whose last segment is a [Key=Value] query does not replace the matched
  element: it adds a junk key named after the query to that element.
- "replace" of a key that does not exist adds it (RFC 6902 would fail).
"""
from __future__ import annotations

import copy
import re

SUPPORTED_OPS = ("add", "replace", "remove")
_INT = re.compile(r"^\s*[+-]?\d+\s*$")


class PatchProblem:
    def __init__(self, index: int, severity: str, message: str):
        self.index = index
        self.severity = severity  # "error" or "warning"
        self.message = message

    def __str__(self) -> str:
        if self.index < 0:
            return self.message
        return f"operation {self.index + 1}: {self.message}"


class _Fail(Exception):
    pass


def _as_int(s: str):
    """int.TryParse: the game treats any integer-looking segment as an array index."""
    return int(s) if _INT.match(s) else None


def _json_text(v) -> str:
    """How the game's JSON library prints a value when matching [Key=Value] queries."""
    if isinstance(v, bool):
        return "True" if v else "False"
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _parse_query(segment: str):
    start = segment.index("[")
    end = segment.find("]")
    if end < start:
        raise _Fail(f'"{segment}": a [Key=Value] query needs a closing ]')
    name = segment[:start]
    parts = segment[start + 1:end].split("=")
    if len(parts) < 2:
        raise _Fail(f'"{segment}": a query must look like Array[Key=Value]')
    return name, parts[0], parts[1].strip('"')


def _index(arr, idx: int, allow_end: bool = False) -> int:
    limit = len(arr) + (1 if allow_end else 0)
    if not 0 <= idx < limit:
        raise _Fail(f"index {idx} is out of range (the array has {len(arr)} items)")
    return idx


def _resolve(doc, path: str):
    """Walks to the container the operation acts on.

    Returns (target, final_key, parent, parent_key) where parent/parent_key locate target.
    """
    segments = path.strip("/").split("/")
    final_key = segments[-1]
    count = len(segments) - 1
    if "[" in final_key:
        count += 1
    current, parent, parent_key = doc, None, None
    for segment in segments[:count]:
        idx = _as_int(segment)
        if idx is not None:
            if not isinstance(current, list):
                raise _Fail(f'"{segment}" is an index, but the value there is not an array')
            idx = _index(current, idx)
            parent, parent_key, current = current, idx, current[idx]
        elif "[" in segment:
            name, key, value = _parse_query(segment)
            if not isinstance(current, dict) or current.get(name) is None:
                raise _Fail(f'"{name}" not found')
            arr = current[name]
            if not isinstance(arr, list):
                raise _Fail(f'"{name}" is not an array, so [{key}={value}] cannot search it')
            match = None
            for i, item in enumerate(arr):
                if isinstance(item, dict) and key in item and _json_text(item[key]) == value:
                    match = i
                    break
            if match is None:
                raise _Fail(f'no element of "{name}" has {key}={value}')
            parent, parent_key, current = arr, match, arr[match]
        else:
            if not isinstance(current, dict):
                raise _Fail(f'"{segment}" is a key, but the value there is not an object')
            if current.get(segment) is None:
                raise _Fail(f'"{segment}" not found')
            parent, parent_key, current = current, segment, current[segment]
    return current, final_key, parent, parent_key


def apply_operation(doc, op: dict, index: int):
    """Returns (new_doc, problems). The document is changed in place where the game would."""
    problems: list[PatchProblem] = []
    if not isinstance(op, dict):
        return doc, [PatchProblem(index, "error", "is not an object; the game skips it")]
    name = str(op.get("op") or "")
    path = str(op.get("path") or "")
    has_value = "value" in op
    value = op.get("value")
    if not name or not path:
        return doc, [PatchProblem(index, "error", '"op" and "path" are required; the game skips it')]
    if not path.startswith("/"):
        return doc, [PatchProblem(index, "error", f'path "{path}" must start with /; the game skips it')]
    if "/[" in path:
        return doc, [PatchProblem(index, "error",
                                  f'path "{path}" is invalid, write {path.replace("/[", "[")}')]
    kind = name.lower()
    if kind not in SUPPORTED_OPS:
        return doc, [PatchProblem(index, "error",
                                  f'"{name}" is not supported (only add, replace and remove)')]
    try:
        target, key, parent, parent_key = _resolve(doc, path)
    except _Fail as e:
        return doc, [PatchProblem(index, "error", f"{e}; the game skips this operation")]
    key_index = _as_int(key)
    try:
        if kind in ("add", "replace") and not has_value:
            raise _Fail(f'"{kind}" needs a "value"')
        if kind in ("add", "replace") and "[" in key:
            problems.append(PatchProblem(
                index, "warning",
                f'the last segment "{key}" is a query, so the game adds a junk key named '
                f'"{key}" to the matched element instead of replacing it. Remove the element '
                f'and add a new one with "-" instead'))
        if kind == "add":
            if key == "-":
                if not isinstance(target, list):
                    raise _Fail('"-" appends to an array, but the target is not an array')
                target.append(copy.deepcopy(value))
            elif key_index is not None:
                if not isinstance(target, list):
                    raise _Fail("an index needs an array target")
                target.insert(_index(target, key_index, allow_end=True), copy.deepcopy(value))
            elif path == "/":
                raise _Fail('"add" with path / is not supported')
            else:
                if not isinstance(target, dict):
                    raise _Fail(f'cannot set "{key}" on an array')
                target[key] = copy.deepcopy(value)
        elif kind == "replace":
            if key_index is not None:
                if not isinstance(target, list):
                    raise _Fail("an index needs an array target")
                target[_index(target, key_index)] = copy.deepcopy(value)
            elif path == "/":
                doc = copy.deepcopy(value)
            else:
                if not isinstance(target, dict):
                    raise _Fail(f'cannot set "{key}" on an array')
                if key not in target and "[" not in key:
                    problems.append(PatchProblem(
                        index, "warning",
                        f'"{key}" does not exist yet; the game adds it (use "add" to say so)'))
                target[key] = copy.deepcopy(value)
        else:  # remove
            if has_value and key == "-":
                if not isinstance(target, list):
                    raise _Fail('remove with "value" and "-" only works on arrays')
                before = len(target)
                target[:] = [item for item in target if item != value]
                if len(target) == before:
                    problems.append(PatchProblem(index, "warning", "no array element equals the value"))
            elif key_index is not None:
                if not isinstance(target, list):
                    raise _Fail("an index needs an array target")
                del target[_index(target, key_index)]
            elif path == "/":
                raise _Fail('"remove" with path / is not supported')
            elif not isinstance(target, dict):
                raise _Fail(f'cannot remove "{key}" from an array')
            elif key in target:
                del target[key]
            elif parent is None:
                raise _Fail(f'"{key}" not found')
            elif "[" in key:
                # Removing a queried element: the game removes the element itself
                del parent[parent_key]
            else:
                problems.append(PatchProblem(
                    index, "error",
                    f'"{key}" does not exist, so the game removes the whole object that should '
                    f'hold it ({_describe(parent_key)}). Check the path'))
                del parent[parent_key]
    except _Fail as e:
        problems.append(PatchProblem(index, "error", f"{e}; the game skips this operation"))
    return doc, problems


def _describe(key) -> str:
    return f"element {key}" if isinstance(key, int) else f'"{key}"'


def apply_patch(doc, patch: dict):
    """Applies every operation of one patch file to a copy of doc. Returns (doc, problems)."""
    result = copy.deepcopy(doc)
    problems: list[PatchProblem] = []
    ops = patch.get("operations") if isinstance(patch, dict) else None
    if not isinstance(ops, list) or not ops:
        return result, [PatchProblem(-1, "error", '"operations" is missing or empty')]
    for i, op in enumerate(ops):
        result, found = apply_operation(result, op, i)
        problems.extend(found)
    return result, problems
