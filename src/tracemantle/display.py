"""Escape at presentation boundaries; preserve original values in machine data."""
from __future__ import annotations

import re

# C0/C1 controls, plus lone surrogates, which cannot be encoded for output and
# would otherwise raise UnicodeEncodeError at print time.
_CONTROLS = re.compile(r'[\x00-\x1f\x7f-\x9f\ud800-\udfff]')


def terminal(text: object) -> str:
    return _CONTROLS.sub(lambda m: f'\\x{ord(m[0]):02x}' if ord(m[0]) <= 0xff else f'\\u{ord(m[0]):04x}', str(text))


def markdown(text: object) -> str:
    return re.sub(r'([\\`*_{}\[\]()<>#!|])', r'\\\1', terminal(text))
