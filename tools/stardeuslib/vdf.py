"""Reads Valve KeyValues text files (libraryfolders.vdf, appmanifest_*.acf)."""
from __future__ import annotations

from pathlib import Path


class VdfError(Exception):
    pass


def _tokens(text: str):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end + 1
        elif c in "{}":
            yield c, False
            i += 1
        elif c == '"':
            i += 1
            out = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    nxt = text[i + 1]
                    out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(nxt, "\\" + nxt))
                    i += 2
                else:
                    out.append(text[i])
                    i += 1
            if i >= n:
                raise VdfError("unterminated string")
            i += 1
            yield "".join(out), True
        else:
            start = i
            while i < n and not text[i].isspace() and text[i] not in '{}"':
                i += 1
            word = text[start:i]
            # Conditionals such as [$WIN32] follow a value and are not keys
            if not (word.startswith("[") and word.endswith("]")):
                yield word, True


def parse(text: str) -> dict:
    root: dict = {}
    stack = [root]
    key = None
    for tok, is_str in _tokens(text):
        if tok == "{" and not is_str:
            if key is None:
                raise VdfError("block without a key")
            child: dict = {}
            stack[-1][key] = child
            stack.append(child)
            key = None
        elif tok == "}" and not is_str:
            if len(stack) == 1:
                raise VdfError("unbalanced }")
            stack.pop()
            key = None
        elif key is None:
            key = tok
        else:
            stack[-1][key] = tok
            key = None
    return root


def load(path: Path) -> dict:
    with open(path, encoding="utf-8", errors="replace") as f:
        return parse(f.read())


def get(d, key: str):
    """Case-insensitive lookup: Steam does not keep key casing stable across versions."""
    if not isinstance(d, dict):
        return None
    if key in d:
        return d[key]
    low = key.lower()
    for k, v in d.items():
        if k.lower() == low:
            return v
    return None
