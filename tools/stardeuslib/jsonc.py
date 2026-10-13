"""JSON with // and /* */ comments, the way Stardeus reads its files.

The game parses JSON with Newtonsoft, which accepts comments. Trailing commas are removed here
too, but reported, because other tools (and stricter parsers) reject them.
"""
from __future__ import annotations

import json
from pathlib import Path


class JsoncError(Exception):
    def __init__(self, message: str, line: int = 0, col: int = 0):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def __str__(self) -> str:
        if self.line:
            return f"line {self.line}, column {self.col}: {self.message}"
        return self.message


def _strip_comments(text: str) -> str:
    out = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise JsoncError("unterminated /* comment", *_pos(text, i))
            for ch in text[i:end + 2]:
                out.append("\n" if ch == "\n" else " ")
            i = end + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _strip_trailing_commas(text: str) -> tuple[str, list[tuple[int, int]]]:
    chars = list(text)
    found = []
    in_str = False
    i, n = 0, len(chars)
    while i < n:
        c = chars[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == ",":
            j = i + 1
            while j < n and chars[j] in " \t\r\n":
                j += 1
            if j < n and chars[j] in "}]":
                found.append(_pos(text, i))
                chars[i] = " "
        i += 1
    return "".join(chars), found


def _pos(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    col = index - (text.rfind("\n", 0, index) + 1) + 1
    return line, col


def _no_duplicates(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise JsoncError(f'duplicate key "{k}" (the game refuses files with duplicate keys)')
        obj[k] = v
    return obj


def loads(text: str):
    """Returns (value, notes). Notes are human-readable warnings such as trailing commas."""
    if text.startswith("﻿"):
        text = text[1:]
    stripped, commas = _strip_trailing_commas(_strip_comments(text))
    notes = [f"line {line}: trailing comma" for line, _ in commas]
    try:
        value = json.loads(stripped, object_pairs_hook=_no_duplicates)
    except json.JSONDecodeError as e:
        raise JsoncError(e.msg, e.lineno, e.colno) from None
    return value, notes


def load(path: Path):
    """Like loads, for a file. Raises JsoncError (with the line) or OSError."""
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    return loads(text)
