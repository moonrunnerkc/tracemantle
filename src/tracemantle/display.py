"""Escape at presentation boundaries; preserve original values in machine data."""
from __future__ import annotations

import re

_CONTROLS = re.compile(r'[\x00-\x1f\x7f-\x9f]')


def terminal(text: object) -> str:
    return _CONTROLS.sub(lambda m: f'\\x{ord(m[0]):02x}', str(text))


def markdown(text: object) -> str:
    return re.sub(r'([\\`*_{}\[\]()<>#!|])', r'\\\1', terminal(text))
