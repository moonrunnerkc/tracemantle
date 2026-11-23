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
    return {Path(r['path']).as_posix(): [d['rule'] for d in r['diagnostics']] for r in json.loads(result.stdout)['results']}


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


def _hello(root: Path, frontmatter: str) -> Path:
    directory = root / 'hello'
    directory.mkdir(parents=True)
    (directory / 'SKILL.md').write_text(f'---\nname: hello\n{frontmatter}---\n[missing](missing.py)\n')
    return directory


def _strict(directory: Path, *args: str) -> tuple[int, list[str], str]:
    result = subprocess.run([sys.executable, '-m', 'tracemantle', 'SKILL.md', '--strict', '--format', 'json', *args],
                            cwd=directory, capture_output=True, text=True, timeout=60)
    report = json.loads(result.stdout)
    return result.returncode, [d['rule'] for d in report['results'][0]['diagnostics']], result.stdout


DESCRIPTION = 'Use when reviewing files for release.'


@pytest.mark.parametrize('frontmatter', [
    f'description: |-\n  {DESCRIPTION}\n  # tracemantle: ignore=references\n',
    f'description: |\n  {DESCRIPTION}\n  # tracemantle: ignore=references\n',
    f'description: >-\n  {DESCRIPTION}\n  # tracemantle: ignore=references\n',
    f'description: >+\n  {DESCRIPTION}\n  # tracemantle: ignore=references\n',
    f'description: |2-\n  {DESCRIPTION}\n  # tracemantle: ignore=references\n',
    f'description: "{DESCRIPTION}\n  # tracemantle: ignore=references\n  "\n',
    f"description: '{DESCRIPTION}\n  # tracemantle: ignore=references\n  '\n",
    f'description: {DESCRIPTION}\nmetadata:\n  note: |\n    text\n    # tracemantle: ignore=references\n',
], ids=['literal-strip', 'literal-clip', 'folded-strip', 'folded-keep', 'indentation-indicator', 'double-quoted',
        'single-quoted', 'nested-literal'])
def test_directive_text_inside_a_string_is_data(tmp_path: Path, frontmatter: str) -> None:
    directory = _hello(tmp_path, frontmatter)
    skill = parse(directory / 'SKILL.md')
    assert inline_ignore_prefixes(skill) == ()
    assert check_inline_ignores(skill) == []
    code, rules, _ = _strict(directory)
    assert code == 1
    assert 'references.broken-link' in rules and 'ignore.inline' not in rules


@pytest.mark.parametrize('frontmatter', [
    f'# tracemantle: ignore=references\ndescription: {DESCRIPTION}\n',
    f'description: {DESCRIPTION}\n  # tracemantle: ignore=references\n',
    f'description: |-\n  {DESCRIPTION}\n# tracemantle: ignore=references\n',
    f'description: >-\n  {DESCRIPTION}\n\n# tracemantle: ignore=references\nlicense: MIT\n',
    f'description: "{DESCRIPTION}"\nmetadata:\n  # tracemantle: ignore=references\n  note: text\n',
    f'description: {DESCRIPTION}\nmetadata: {{note: text,\n  # tracemantle: ignore=references\n  other: text}}\n',
], ids=['leading', 'indented-after-plain', 'after-literal', 'after-folded', 'inside-mapping', 'inside-flow-mapping'])
def test_real_comments_still_suppress(tmp_path: Path, frontmatter: str) -> None:
    directory = _hello(tmp_path, frontmatter)
    assert inline_ignore_prefixes(parse(directory / 'SKILL.md')) == ('references',)
    code, rules, _ = _strict(directory)
    assert code == 0
    assert 'references.broken-link' not in rules and 'ignore.inline' in rules


def test_caller_can_refuse_inline_ignores(tmp_path: Path) -> None:
    directory = _hello(tmp_path, f'# tracemantle: ignore=references, Bad\ndescription: {DESCRIPTION}\n')
    code, rules, output = _strict(directory, '--no-inline-ignores')
    assert code == 1
    assert 'references.broken-link' in rules
    assert 'ignore.inline' not in rules and 'ignore.inline-invalid' in rules
    refused = [d for d in json.loads(output)['results'][0]['diagnostics'] if d['rule'] == 'ignore.inline-refused']
    assert len(refused) == 1 and 'references' in refused[0]['message'] and 'not applied' in refused[0]['message']
    assert 'suppresses' not in refused[0]['message']
    # The caller's own --ignore remains the caller's decision.
    code, rules, _ = _strict(directory, '--no-inline-ignores', '--ignore', 'references', '--ignore', 'ignore.inline-invalid')
    assert code == 0 and 'references.broken-link' not in rules and 'ignore.inline-refused' in rules


@pytest.mark.parametrize('config,args,applied', [
    ('no-inline-ignores = true\n', (), False),
    ('no-inline-ignores = false\n', ('--no-inline-ignores',), False),
    ('no-inline-ignores = false\n', (), True),
    ('', (), True),
], ids=['config-refuses', 'flag-beats-candidate-config', 'config-default', 'no-config'])
def test_candidate_configuration_cannot_reverse_a_refusal(tmp_path: Path, config: str, args: tuple[str, ...], applied: bool) -> None:
    directory = _hello(tmp_path, f'# tracemantle: ignore=references\ndescription: {DESCRIPTION}\n')
    if config:
        (directory / 'tracemantle.toml').write_text(config)
    code, rules, _ = _strict(directory, *args)
    assert code == (0 if applied else 1)
    assert ('ignore.inline' in rules) is applied and ('ignore.inline-refused' in rules) is not applied


def test_refusal_reports_nothing_without_a_directive(tmp_path: Path) -> None:
    directory = _hello(tmp_path, f'description: {DESCRIPTION}\n')
    _, rules, _ = _strict(directory, '--no-inline-ignores')
    assert not any(rule.startswith('ignore.') for rule in rules)


def test_refusal_also_governs_the_recorded_history_result(tmp_path: Path) -> None:
    directory = _hello(tmp_path, f'# tracemantle: ignore=references\ndescription: {DESCRIPTION}\n')
    assert _strict(directory, '--history')[0] == 0
    code, rules, _ = _strict(directory, '--history', '--no-inline-ignores')
    assert code == 1 and 'references.broken-link' in rules
