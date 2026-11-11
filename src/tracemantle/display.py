"""Escape at presentation boundaries; preserve original values in machine data."""
from __future__ import annotations

import re

# C0/C1 controls; lone surrogates, which cannot be encoded for output and would
# otherwise raise UnicodeEncodeError at print time; bidirectional formatting
# controls (U+061C, U+200E-U+200F, U+202A-U+202E, U+2066-U+2069), which can
# visually reorder a line so it reads differently from its bytes; and the
# Unicode line/paragraph separators, which some terminals treat as newlines.
# Joiners (U+200C, U+200D) are left alone: scripts and emoji sequences need them.
_CONTROLS = re.compile(r'[\x00-\x1f\x7f-\x9f\u061c\u200e\u200f\u2028-\u202e\u2066-\u2069\ud800-\udfff]')


def terminal(text: object) -> str:
    return _CONTROLS.sub(lambda m: f'\\x{ord(m[0]):02x}' if ord(m[0]) <= 0xff else f'\\u{ord(m[0]):04x}', str(text))


def markdown(text: object) -> str:
    return re.sub(r'([\\`*_{}\[\]()<>#!|])', r'\\\1', terminal(text))
