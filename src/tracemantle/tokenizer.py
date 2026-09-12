"""Explicit token counting. Installing an extra never changes the default."""
from __future__ import annotations

import re
from functools import lru_cache
from importlib.metadata import version
from typing import Any

_WORD_RE = re.compile(r'\w+')
_PUNCT_RE = re.compile(r'[^\w\s]+')


class TokenizerError(Exception):
    """The selected tokenizer is unavailable; choose heuristic for offline use."""


@lru_cache(maxsize=1)
def _get_tiktoken_enc() -> Any:
    try:
        import tiktoken
        return tiktoken.get_encoding('cl100k_base')
    except (ImportError, OSError, ValueError) as exc:
        raise TokenizerError('Cannot load tiktoken cl100k_base. Install tracemantle[tiktoken] and warm its cache, or select --tokenizer heuristic for offline use.') from exc


def tokenizer_provenance(backend: str = 'heuristic') -> dict[str, str]:
    if backend == 'heuristic':
        return {'backend': 'word-punctuation', 'version': '1', 'network': 'none'}
    if backend != 'tiktoken':
        raise TokenizerError(f'Unknown tokenizer {backend!r}; select heuristic or tiktoken.')
    _get_tiktoken_enc()
    return {'backend': 'tiktoken', 'version': version('tiktoken'), 'encoding': 'cl100k_base', 'network': 'cold cache may download vocabulary'}


def estimate_tokens(text: str, backend: str = 'heuristic') -> int:
    if backend == 'tiktoken':
        return max(1, len(_get_tiktoken_enc().encode(text, disallowed_special=())))
    if backend != 'heuristic':
        raise TokenizerError(f'Unknown tokenizer {backend!r}; select heuristic or tiktoken.')
    return max(1, int(len(_WORD_RE.findall(text)) * 1.3) + int(len(_PUNCT_RE.findall(text)) * 1.5))
