"""Untrusted skill text must parse in time proportional to its length.

Each body below once triggered quadratic regex backtracking: a single 90 KB line
took tens of seconds, and a file near the 4 MiB cap would run for hours. The
bound is loose enough for slow CI runners and still far below the old cost.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from tracemantle.markdown import tokenize
from tracemantle.parser import parse
from tracemantle.rules.disclosure import check_body_bloat

REPEATS = 100_000


@pytest.mark.parametrize('body', [
    '<a ' * REPEATS,
    '[a](' + "'" * REPEATS,
    '[a](x ' + '"' * REPEATS,
    'file:' * REPEATS,
    '`' + 'a/' * REPEATS + ' x`',
    '[' * REPEATS,
    '```x\n' * REPEATS,
], ids=['html', 'link-quotes', 'link-title', 'directive', 'code-span-path', 'reference', 'unclosed-fences'])
def test_crafted_bodies_parse_in_linear_time(tmp_path: Path, body: str) -> None:
    source = tmp_path / 'SKILL.md'
    source.write_text('---\nname: crafted\ndescription: Use when testing parser time bounds.\n---\n' + body + '\n')
    started = time.perf_counter()
    check_body_bloat(parse(source))
    assert time.perf_counter() - started < 5


@pytest.mark.parametrize('line,targets', [
    ('[a](helper.py "title (with parens)")', ['helper.py']),
    ("[a](helper.py 'title')", ['helper.py']),
    ('[outer [inner](helper.py)', ['helper.py']),
    ('<a class="x" href="helper.py">', ['helper.py']),
    ('(source: helper.py)', ['helper.py']),
    ('**include:** helper.py', []),
    ('myfile: helper.py', []),
])
def test_link_forms_keep_their_targets(line: str, targets: list[str]) -> None:
    assert [r.target for r in tokenize(line).resources] == targets


def _bloat_messages(tmp_path: Path, body: str) -> list[str]:
    source = tmp_path / 'SKILL.md'
    source.write_text('---\nname: bloat\ndescription: Use when testing bloat detection.\n---\n' + body)
    return [d.message for d in check_body_bloat(parse(source))]


def test_base64_after_a_hex_digest_is_still_reported(tmp_path: Path) -> None:
    body = 'sha ' + 'a1' * 40 + '\n' + 'QUJjZGVm' * 12 + '\n'
    assert any('Base64' in message for message in _bloat_messages(tmp_path, body))


def test_code_block_size_is_reported_only_for_closed_blocks(tmp_path: Path) -> None:
    block = '```python\n' + 'x = 1\n' * 60 + '```\n'
    assert any('Code block with 60 lines' in m for m in _bloat_messages(tmp_path, block))
    assert not any('Code block' in m for m in _bloat_messages(tmp_path, '```python\n' + 'x = 1\n' * 60))
