"""Block boundaries with synthetic approved evidence, never live execution."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_dependency_numeric_regressions import test_dependency_closure_controls_real_trusted_comparison as _check_reuse
from tracemantle.markdown import tokenize


@pytest.mark.parametrize('underline', ['=', '==', '======', '-', '--', '---', '------', '   == \t', '  --\t '])
def test_setext_helper_change_blocks_trusted_reuse(tmp_path: Path, underline: str) -> None:
    _check_reuse(tmp_path, f'`Title\n{underline}\n[helper](helper.py) `', True, True)


@pytest.mark.parametrize('body', [
    '- `Title\n  ==\n  [helper](helper.py) `',
    '1. `Title\n   --\n   [helper](helper.py) `',
    '- Steps:\n    - `Title\n      ==\n      [helper](helper.py) `',
    '-\t`Title\n\t==\n\t[helper](helper.py) `',
    '   # `Title\n[helper](helper.py) `',
    '`Before\n   # Heading\n[helper](helper.py) `',
    '`Before\n_ _ _\n[helper](helper.py) `',
    '`Before\n  * * * \t\n[helper](helper.py) `',
    '`Before\n- - -\n[helper](helper.py) `',
    '`Title\nsecond line\n==\n[helper](helper.py) `',
    '`Before\n\nTitle\n==\n[helper](helper.py) `',
    '`First\n==\nSecond\n--\n[helper](helper.py) `',
])
def test_adjacent_blocks_keep_governed_helper(tmp_path: Path, body: str) -> None:
    _check_reuse(tmp_path, body, True, True)


@pytest.mark.parametrize('underline', ['=', '-', '--', '---', '   ===\t'])
@pytest.mark.parametrize('prefix', ['', '- ', '1. '])
def test_multiline_heading_code_span_stays_intact(underline: str, prefix: str) -> None:
    indent = ' ' * len(prefix)
    body = f'{prefix}`Example\n{indent}[example](missing.py) `\n{indent}{underline}\n{indent}[helper](helper.py)'
    parsed = tokenize(body, 11)
    assert [(r.target, r.line) for r in parsed.resources] == [('helper.py', 14)]
    assert not parsed.uncertain


@pytest.mark.parametrize('middle', ['    ==', '\t==', '= =', '== text', r'\==', '-_', '#not-heading'])
def test_non_boundaries_preserve_paragraph_code_spans(middle: str) -> None:
    parsed = tokenize(f'`Example\n{middle}\n[example](missing.py) `')
    assert not parsed.resources
    assert not parsed.uncertain


@pytest.mark.parametrize('body', [
    '```md\n`Title\n==\n[example](missing.py) `\n```',
    '~~~md\n`Title\n--\n[example](missing.py) `\n~~~',
    '    `Title\n    ==\n    [example](missing.py) `',
    '- Examples:\n\n      `Title\n      --\n      [example](missing.py) `',
    '- ```md\n  `Title\n  ==\n  [example](missing.py) `\n  ```',
    '`Example\n[example](missing.py) `\n==',
    'Title\n==\n    [example](missing.py)',
])
def test_heading_code_examples_do_not_govern_helper(tmp_path: Path, body: str) -> None:
    _check_reuse(tmp_path, body.replace('missing.py', 'helper.py'), True, False)


@pytest.mark.parametrize('body', [
    '`Title\n==\n[helper](helper.py) ``',
    '``Title\n--\n[helper](helper.py) `',
    '`Title\n==\n[helper](helper.py)',
    '`Title\n[helper](helper.py)\n==',
    '==\n[helper](helper.py)',
])
def test_unmatched_heading_delimiters_keep_source_locations(body: str) -> None:
    parsed = tokenize(body, 21)
    assert [(r.target, r.line) for r in parsed.resources] == [('helper.py', 21 + body[:body.index('[helper]')].count('\n'))]
    assert not parsed.uncertain


@pytest.mark.parametrize('body,dependency', [
    ('> `Title\n> ==\n> [helper](helper.py) `', False),
    ('- `Title\n==\n[helper](helper.py) `', True),
])
def test_unsupported_heading_containers_cannot_authorize_reuse(tmp_path: Path, body: str, dependency: bool) -> None:
    # Exact dependencies are deliberately not claimed for unsupported containers.
    _check_reuse(tmp_path, body, False, dependency)
