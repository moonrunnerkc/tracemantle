"""Which descriptions take part in quality scoring."""
from __future__ import annotations

from pathlib import Path

import pytest

from tracemantle.parser import parse
from tracemantle.rules.description import scorable_description


@pytest.mark.parametrize('frontmatter,expected', [
    ('description: Use when reviewing release notes.', 'Use when reviewing release notes.'),
    ('description: "   "', None),
    ('description: 42', None),
    ('other: value', None),
    ('description: Replace with your description.', None),
], ids=['ordinary', 'blank', 'non-string', 'missing', 'template'])
def test_only_real_descriptions_are_scored(tmp_path: Path, frontmatter: str, expected: str | None) -> None:
    source = tmp_path / 'SKILL.md'
    source.write_text(f'---\nname: demo\n{frontmatter}\n---\nBody.\n')
    assert scorable_description(parse(source)) == expected
