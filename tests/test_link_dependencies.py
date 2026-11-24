"""Link forms that must keep a helper governed by approved evidence.

Expectations follow CommonMark 0.31.2 sections 4.7 (link reference
definitions) and 6.3 (links), not the tokenizer's implementation. The records
are synthetic policy controls; no skill or evaluator is executed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.test_build_plan_acceptance import _cli
from tests.test_build_plan_product import _bundle, _record, _trusted_repository
from tracemantle.markdown import tokenize


def _targets(body: str, start_line: int = 1) -> list[tuple[str, int]]:
    return [(r.target, r.line) for r in tokenize(body, start_line).resources]


@pytest.mark.parametrize('body,complete,dependency', [
    ('Run [helper](helper.py).', True, True),
    ('[helper](\nhelper.py\n)', True, True),
    ('[run [helper]](helper.py)', True, True),
    ('[run][helper]\n\n[helper]: helper.py\n[helper]: unused.py', True, True),
    ('[run][ HELPER\n  script ]\n\n[helper script]:\n  <helper.py>\n  "Helper"', True, True),
    ('![diagram of\nthe helper](helper.py "Helper")', True, True),
    ('[run \\] it](helper.py)', True, True),
    ('[run][helper]\n\n[helper]: unused.py\n[helper]: helper.py', True, True),
    ('Text.\n[helper]: helper.py\n\n[run][helper]', True, True),
    ('Text.\n[helper]: unused.py\n\n[helper]: helper.py\n\n[run][helper]', True, True),
    ('[helper](helper.py unquoted title)', False, False),
    ('    [example](helper.py)', True, False),
    ('```md\n[run][helper]\n\n[helper]: helper.py\n```', True, False),
], ids=['single-line-control', 'multiline-destination', 'nested-label', 'first-definition-wins',
        'normalized-multiline-definition', 'multiline-image', 'escaped-bracket', 'later-definition-also-governed',
        'definition-inside-paragraph', 'paragraph-decoy-before-definition', 'malformed-inline-tail', 'indented-code-example', 'fenced-example'])
def test_link_forms_control_real_trusted_comparison(tmp_path: Path, body: str, complete: bool, dependency: bool) -> None:
    base = _bundle(tmp_path / 'base')
    source = base / 'SKILL.md'
    source.write_text(source.read_text().replace('Run [helper](helper.py).', body))
    # Both files exist so a missing-file error cannot stand in for discovery.
    (base / 'unused.py').write_text('print("unused")\n')
    # Policy and evidence bind ONLY SKILL.md; binding helper.py would govern
    # its digest directly and hide a dependency-discovery defect.
    record = _record(base)
    record = replace(record, inputs=tuple(item for item in record.inputs if item[0] == 'SKILL.md'),
                     observed_at=datetime.now(timezone.utc).isoformat())
    trusted = tmp_path / 'trusted'
    _trusted_repository(trusted, record)
    policy_file = trusted / 'pyproject.toml'
    policy_file.write_text(policy_file.read_text().replace('inputs=["SKILL.md", "helper.py"]', 'inputs=["SKILL.md"]'))
    subprocess.run(['git', '-C', str(trusted), 'add', '.'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(trusted), '-c', 'user.name=TraceMantle tests', '-c', 'user.email=tests@example.invalid',
                    'commit', '-qm', 'Declare only the skill input'], check=True, capture_output=True)
    revision = subprocess.check_output(['git', '-C', str(trusted), 'rev-parse', 'HEAD'], text=True).strip()
    assert set(json.loads((trusted / 'approved.json').read_bytes())['inputs']) == {'SKILL.md'}
    identity = json.loads(_cli('manifest', str(base), '--format', 'json').stdout)['result']
    assert identity['complete'] is complete
    assert (['SKILL.md', 'helper.py'] in identity['dependencies']) is dependency
    candidate = tmp_path / 'candidate'
    shutil.copytree(base, candidate)
    args = ('compare', str(base), str(candidate), '--trusted-root', str(trusted), '--base-revision', revision,
            '--evidence', str(trusted / 'approved.json'), '--format', 'json')
    assert _cli(*args).returncode == (0 if complete else 4)
    (candidate / 'notes.txt').write_text('Unrelated change')
    assert _cli(*args).returncode == (0 if complete else 4)
    (candidate / 'notes.txt').unlink()
    (candidate / 'helper.py').write_text('print("changed helper")\n')
    result = _cli(*args)
    report = json.loads(result.stdout)
    invalidated = dependency or not complete
    assert result.returncode == report['exit_code'] == (4 if invalidated else 0)
    assert report['result']['state'] == ('unknown' if invalidated else 'pass')
    assert report['result']['changed_inputs'] == ['helper.py']
    assert report['result']['required_reruns'] == (['validate'] if invalidated else [])
    assert 'Traceback' not in result.stderr


@pytest.mark.parametrize('body,expected', [
    ('[a](helper.py)', [('helper.py', 3)]),
    ('[a](\nhelper.py\n)', [('helper.py', 4)]),
    ('[a\nb](helper.py)', [('helper.py', 4)]),
    ('[a]( <helper.py> )', [('helper.py', 3)]),
    ('[a](helper.py\n"multi\nline title")', [('helper.py', 3)]),
    ("[a](helper.py 'title')", [('helper.py', 3)]),
    ('[a](helper.py (title))', [('helper.py', 3)]),
    ('[a](dir/help(er).py)', [('dir/help(er).py', 3)]),
    ('[a](help\\)er.py)', [('help)er.py', 3)]),
    ('[a](<my helper.py>)', [('my helper.py', 3)]),
    ('[a](help&#101;r.py)', [('helper.py', 3)]),
    ('[a](help%65r.py)', [('helper.py', 3)]),
    ('![a ![b](inner.png)](helper.png)', [('inner.png', 3), ('helper.png', 3)]),
    ('[a [b] c](helper.py)', [('helper.py', 3)]),
    ('[a \\[b c](helper.py)', [('helper.py', 3)]),
    ('\\[a](helper.py)', []),
    ('[a]\\(helper.py)', []),
    ('[a] (helper.py)', []),
    ('[a]()', []),
])
def test_inline_link_forms_and_source_lines(body: str, expected: list[tuple[str, int]]) -> None:
    result = tokenize(body, 3)
    assert [(r.target, r.line) for r in result.resources] == expected
    assert not result.uncertain


@pytest.mark.parametrize('body,expected', [
    ('[use][ref]\n\n[ref]: helper.py', [('helper.py', 1)]),
    ('[ref][]\n\n[ref]: helper.py', [('helper.py', 1)]),
    ('[ref]\n\n[ref]: helper.py', [('helper.py', 1)]),
    ('![use][ref]\n\n[ref]: helper.png', [('helper.png', 1)]),
    ('[use][REF]\n\n[ref]: helper.py', [('helper.py', 1)]),
    ('[use][ref  two]\n\n[Ref\tTwo]: helper.py', [('helper.py', 1)]),
    ('[use][ẞ]\n\n[SS]: helper.py', [('helper.py', 1)]),
    ('[ref]: first.py\n[ref]: second.py\n\n[ref]', [('first.py', 1), ('second.py', 1)]),
    ('[REF]: first.py\n\n[ ref ]: second.py\n\n[use][ref]', [('first.py', 1), ('second.py', 1)]),
    ('[ref]:\nhelper.py\n\n[ref]', [('helper.py', 1)]),
    ('[ref]: helper.py\n"title"\n\n[ref]', [('helper.py', 1)]),
    ('[ref]: helper.py "title" junk\n\n[ref]', []),
    ('[ref]: helper.py\n"title" junk\n\n[ref]', [('helper.py', 1)]),
    ('- [ref]: helper.py\n\n[ref]', [('helper.py', 1)]),
    ('[use][ref]\n\n[ref\\]]: other.py\n\n[ref]: helper.py', [('helper.py', 1), ('other.py', 3)]),
    ('[ref]\n\n[ref]: <>', []),
])
def test_reference_definitions_follow_commonmark(body: str, expected: list[tuple[str, int]]) -> None:
    result = tokenize(body)
    # A definition is also recorded as a use of its own label, at its own line.
    # CommonMark's first definition is listed first; later definitions of the
    # same label stay governed because the tokenizer cannot always rank them.
    assert [(r.target, r.line) for r in result.resources] == expected
    assert not result.uncertain or 'junk' in body


def test_a_definition_shaped_paragraph_line_cannot_shadow_the_real_definition() -> None:
    # CommonMark 4.7: a definition cannot interrupt a paragraph, so line 2 is
    # text and the link on line 6 resolves to helper.py. Renderers that accept
    # line 2 would use decoy.py, so both stay governed.
    result = tokenize('Text\n[helper]: decoy.py\n\n[helper]: helper.py\n\n[run][helper]')
    assert {(r.target, r.line) for r in result.resources} == {('decoy.py', 2), ('helper.py', 2)}
    assert not result.uncertain


@pytest.mark.parametrize('body', [
    '[a](helper.py extra words)',
    '[a](<helper.py)',
    '[a](helper.py "unterminated)',
    'Paragraph text\n[ref]: helper.py trailing words',
    '[a](' + '(' * 40 + 'helper.py' + ')' * 40 + ')',
])
def test_unresolved_link_syntax_keeps_coverage_incomplete(body: str) -> None:
    assert tokenize(body).uncertain


@pytest.mark.parametrize('body', [
    'Call array[i](x, y) here.\n\n`[a](helper.py extra words)`',
    '```\n[a](helper.py extra words)\n```',
    'A [plain] bracket and (parentheses) apart.',
    '[ref]: helper.py',
])
def test_ordinary_text_and_code_do_not_reduce_coverage(body: str) -> None:
    result = tokenize(body)
    assert not result.uncertain or 'array[i]' in body


@pytest.mark.parametrize('line_ending', ['\n', '\r\n', '\r'])
def test_multiline_links_survive_every_line_ending(tmp_path: Path, line_ending: str) -> None:
    from tracemantle.parser import parse

    source = tmp_path / 'SKILL.md'
    text = '---\nname: endings\ndescription: Use when checking line endings.\n---\n[helper](\nhelper.py\n)\n\n[run][h]\n\n[h]:\n  other.py\n'
    source.write_bytes(text.replace('\n', line_ending).encode())
    assert [(r.target, r.line) for r in parse(source).markdown.resources] == [('helper.py', 6), ('other.py', 9)]


def test_transitive_multiline_link_reaches_the_helper(tmp_path: Path) -> None:
    from tracemantle.bundle import create_manifest

    root = tmp_path / 'skill'
    root.mkdir()
    (root / 'SKILL.md').write_text('---\nname: skill\ndescription: Use when checking transitive links.\n---\n[guide](\nguide.md\n)\n')
    (root / 'guide.md').write_text('[run [it]][h]\n\n[h]: helper.py\n[h]: unused.py\n')
    (root / 'helper.py').write_text('pass\n')
    (root / 'unused.py').write_text('pass\n')
    manifest = create_manifest(root)
    assert manifest.dependencies == (('SKILL.md', 'guide.md'), ('guide.md', 'helper.py'), ('guide.md', 'unused.py'))
    assert manifest.complete


REPEATS = 100_000


@pytest.mark.parametrize('body', [
    '[a](x "' * REPEATS,
    "[a](x '" * REPEATS,
    '[a](x (' * REPEATS,
    '[a](<x ' * REPEATS,
    '[a](' * REPEATS,
    '[a](x' * REPEATS,
    '[' * REPEATS + ']' * REPEATS,
    '[a]: x "' * REPEATS,
    '[a]:\n' * REPEATS,
    '[a][' * REPEATS,
    '\\' * REPEATS + '[a](b)',
    '[a](b\n' * REPEATS,
], ids=['double-title', 'single-title', 'paren-title', 'angle', 'open-paren', 'bare-destination', 'nesting',
        'definition-title', 'definition-lines', 'reference-labels', 'backslashes', 'multiline-tails'])
def test_crafted_link_syntax_parses_in_linear_time(body: str) -> None:
    started = time.perf_counter()
    tokenize(body)
    assert time.perf_counter() - started < 5


def test_exhausted_destination_scans_stay_incomplete_and_local_to_their_block() -> None:
    # Overlapping failed scans stop being retried within the crafted block. A
    # link hidden after them may then go unreported, which is why the document
    # is incomplete; links in other blocks are unaffected.
    crafted = '[a](' * 5000
    result = tokenize(crafted + '[late](late.py)\n\n[helper](helper.py)')
    assert result.uncertain
    assert 'helper.py' in {r.target for r in result.resources}
    assert tokenize('[helper](helper.py)\n\n' + crafted).resources[0].target == 'helper.py'


@pytest.mark.parametrize('body', [
    '<!--\n\n[a]: other.py\n\n-->\n\n[a]: helper.py\n\n[a]\n',
    '[a\xa0]: other.py\n\n[a]: helper.py\n\n[a]\n',
    '[x `a`]: other.py\n\n[x]: helper.py\n\n[x]\n',
    '[a]: oth\\ er.py\n\n[a]: helper.py\n\n[a]\n',
    'foo\n2. [a]: other.py\n\n[a]: helper.py\n\n[a]\n',
], ids=['html-comment', 'nbsp-label', 'code-span-label', 'escaped-space', 'ordered-item-in-paragraph'])
def test_text_shaped_like_an_earlier_definition_cannot_hide_the_real_one(body: str) -> None:
    # CommonMark resolves each link to helper.py: the earlier line is inside an
    # HTML block, has a different label, or is not a definition at all. This
    # tokenizer cannot always tell, so every candidate destination is governed.
    assert 'helper.py' in {r.target for r in tokenize(body).resources}


@pytest.mark.parametrize('body', [
    '[a\\b\nc]: helper.py\n\n[a\\b c]\n',
    '[fo\\]o\nbar]: helper.py\n\n[fo\\]o bar]\n',
    "[`]: x.py\n[b]: helper.py '`'\n\n[b]\n",
    "[x]: y '`'\n[foo]: helper.py '`'\n\n[foo]\n",
    '<span title="`">[x](helper.py)</span> text `\n',
    '<http://a/`> [x](helper.py) `\n',
    '<!-- ` -->\n[x](helper.py) `\n',
    '<!--\n`\n-->\n\n[x](helper.py) `\n',
    'x\x0b```\n[a](helper.py)\n',
    'x\x0c```\n[a](helper.py)\n',
    'x\x85```\n[a](helper.py)\n',
    'x ```\n[a](helper.py)\n',
    '[foo\n\xa0\nbar](helper.py)\n',
    '[foo\n2. bar](helper.py)\n',
    '[foo\n*\nbar](helper.py)\n',
])
def test_a_link_is_reported_or_coverage_is_incomplete(body: str) -> None:
    result = tokenize(body)
    assert 'helper.py' in {r.target for r in result.resources} or result.uncertain


@pytest.mark.parametrize('body,targets', [
    ('1. first\n2. [second](helper.py)', ['helper.py']),
    ('- first\n-\n  [second](helper.py)', ['helper.py']),
    ('Steps\n1. [first](helper.py)', ['helper.py']),
    ('Text with <b>bold</b> and `code`.\n\n[a](helper.py)', ['helper.py']),
    ('a < b and `c` or d > e\n\n[a](helper.py)', ['helper.py']),
])
def test_ordinary_lists_and_inline_html_stay_complete(body: str, targets: list[str]) -> None:
    result = tokenize(body)
    assert [r.target for r in result.resources] == targets and not result.uncertain


def test_many_conflicting_definitions_are_bounded_and_incomplete() -> None:
    body = ''.join(f'[a]: file{index}.py\n' for index in range(50)) + '\n[a]\n'
    result = tokenize(body)
    assert result.uncertain and 0 < len(result.resources) < 50


@pytest.mark.parametrize('body', [
    '[' * 1_000_000 + ']' * 1_000_000,
    '[x' * 500_000 + ']' * 500_000,
    '<a' + ' ' * 400_000,
    'file:a,' * 200_000,
    '[a]: x\n' * 200_000 + '\n' + '[a] ' * 200_000,
], ids=['deep-nesting', 'deep-nesting-text', 'html-spaces', 'directive-run', 'definition-uses'])
def test_review_found_inputs_parse_in_linear_time(body: str) -> None:
    started = time.perf_counter()
    tokenize(body)
    assert time.perf_counter() - started < 5
