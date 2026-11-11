"""Per-file inline ignores declared as a frontmatter comment."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tracemantle.inline_ignores import check_inline_ignores, inline_ignore_prefixes
from tracemantle.parser import parse

# Breaks two rules: the unknown field and the description's first-person voice.
BODY = 'author_note: hi\ndescription: I help when reviewing release notes for teams.\n---\nBody.\n'


def _skill(root: Path, name: str, directive: str = '') -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / 'SKILL.md').write_text(f'---\nname: {name}\n{directive}{BODY}')
    return directory / 'SKILL.md'


def _report(root: Path, *args: str) -> dict[str, list[str]]:
    result = subprocess.run([sys.executable, '-m', 'tracemantle', '.', '--format', 'json', *args], cwd=root,
                            capture_output=True, text=True, timeout=60)
    return {r['path']: [d['rule'] for d in r['diagnostics']] for r in json.loads(result.stdout)['results']}


def test_directive_suppresses_only_its_own_file_and_is_reported(tmp_path: Path) -> None:
    _skill(tmp_path, 'quiet-skill', '# tracemantle: ignore=frontmatter.field, frontmatter.description.person-voice\n')
    _skill(tmp_path, 'plain-skill')
    report = _report(tmp_path)
    quiet, plain = report['quiet-skill/SKILL.md'], report['plain-skill/SKILL.md']
    assert 'frontmatter.field.unknown' in plain and 'frontmatter.description.person-voice' in plain
    assert not any(rule.startswith('frontmatter.field') or rule == 'frontmatter.description.person-voice' for rule in quiet)
    assert 'ignore.inline' in quiet and 'ignore.inline' not in plain


def test_global_ignore_still_applies_and_can_hide_the_note(tmp_path: Path) -> None:
    _skill(tmp_path, 'quiet-skill', '# tracemantle: ignore=frontmatter.field\n')
    rules = _report(tmp_path, '--ignore', 'ignore.', '--ignore', 'frontmatter.description')['quiet-skill/SKILL.md']
    assert not any(rule.startswith(('ignore.', 'frontmatter.field', 'frontmatter.description')) for rule in rules)


@pytest.mark.parametrize('directive,prefixes,invalid', [
    ('# tracemantle: ignore=sizing,sizing , compat.unverified\n', ('sizing', 'compat.unverified'), []),
    ('  #tracemantle:ignore=Sizing\n', (), ['Sizing']),
    ('# tracemantle: ignore=ignore.inline, ign\n', (), ['ignore.inline', 'ign']),
    ('# tracemantle: ignore=\n', (), []),
], ids=['dedup-and-spaces', 'uppercase', 'own-namespace', 'empty'])
def test_tokens_are_validated(tmp_path: Path, directive: str, prefixes: tuple[str, ...], invalid: list[str]) -> None:
    skill = parse(_skill(tmp_path, 'demo-skill', directive))
    assert inline_ignore_prefixes(skill) == prefixes
    diagnostics = check_inline_ignores(skill)
    assert [d.message.split("'")[1] for d in diagnostics if d.rule == 'ignore.inline-invalid'] == invalid
    assert any(d.rule == 'ignore.inline' for d in diagnostics) is bool(prefixes)


def test_directive_in_the_body_is_not_honored(tmp_path: Path) -> None:
    source = tmp_path / 'SKILL.md'
    source.write_text('---\nname: demo\ndescription: d\n---\n# tracemantle: ignore=sizing\n')
    assert inline_ignore_prefixes(parse(source)) == ()


def test_own_suppression_note_survives_a_directive_naming_its_namespace(tmp_path: Path) -> None:
    _skill(tmp_path, 'quiet-skill', '# tracemantle: ignore=frontmatter, ignore\n')
    rules = _report(tmp_path)['quiet-skill/SKILL.md']
    assert 'ignore.inline' in rules and 'ignore.inline-invalid' in rules
    assert not any(rule.startswith('frontmatter') for rule in rules)
