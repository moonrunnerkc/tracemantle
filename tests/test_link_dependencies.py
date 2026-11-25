"""Link forms that must keep a helper governed by approved evidence.

Expectations follow CommonMark 0.31.2 sections 4.6 (HTML blocks), 4.7 (link
reference definitions) and 6.3 (links), not the tokenizer's implementation. The records
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
    ('<!--\n~~~\n-->\n\n[helper](helper.py)', True, True),
    ('<div>\n```\n</div>\n\n[helper](helper.py)', True, True),
    ('<pre>\n~~~\n</pre>\n[helper](helper.py)', True, True),
], ids=['single-line-control', 'multiline-destination', 'nested-label', 'first-definition-wins',
        'normalized-multiline-definition', 'multiline-image', 'escaped-bracket', 'later-definition-also-governed',
        'definition-inside-paragraph', 'paragraph-decoy-before-definition', 'malformed-inline-tail', 'indented-code-example', 'fenced-example',
        'fence-marker-in-html-comment', 'fence-marker-in-html-div', 'fence-marker-in-html-pre'])
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
    '[x](<a`b>) [L](helper.py) `',
    '<?>\n- [h]: helper.py\n[h]\n',
    '<!--->\n- [x](a "\n- [L](helper.py) ")\n',
    '[d]: x\n===\n<span>\n`[x](a "` [L](helper.py) ")\n',
    '[d]: x\n===\n    [L](helper.py)\n',
    '<!x>\n    [L](helper.py)\n',
    '- <style\n\n  `[x](a "` [L](helper.py) ")\n',
])
def test_a_link_is_reported_or_coverage_is_incomplete(body: str) -> None:
    result = tokenize(body)
    assert 'helper.py' in {r.target for r in result.resources} or result.uncertain


@pytest.mark.parametrize('body,targets', [
    ('1. first\n2. [second](helper.py)', ['helper.py']),
    ('- first\n-\n  [second](helper.py)', ['helper.py']),
    ('- first\n-\n    [second](helper.py)', ['helper.py']),
    ('1. first\n-\n    [second](helper.py)', ['helper.py']),
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
    # Measured linear from 25,000 to 200,000 repeats (0.16 s to 1.33 s). Sized
    # so slow runners with coverage tracing stay inside the bound.
    '[a]: x\n' * 50_000 + '\n' + '[a] ' * 50_000,
    # Measured linear from 200,000 to 400,000 repeats (0.03 s to 0.05 s and 0.29 s to 0.56 s).
    '<x' + ' a' * 200_000,
    '<div>\n' * 200_000,
    # Measured linear locally: 0.19 s at 40,000 definition lines and 0.38 s at 80,000; 0.16 s at 6,000
    # lines under eight readings and 0.32 s at 12,000. Sized for slow runners with coverage tracing.
    '[a]: x\n' * 40_000,
    '<textarea>\n<search>\n<source>\n' + '[a](b) `c`\n' * 6_000,
], ids=['deep-nesting', 'deep-nesting-text', 'html-spaces', 'directive-run', 'definition-uses', 'html-tag-attributes', 'html-block-lines',
        'definition-lines', 'eight-readings'])
def test_review_found_inputs_parse_in_linear_time(body: str) -> None:
    started = time.perf_counter()
    tokenize(body)
    assert time.perf_counter() - started < 5


LINK = '[helper](helper.py)'


@pytest.mark.parametrize('body', [
    f'<!--\n~~~\n-->\n\n{LINK}',
    f'<!-- note\n\n~~~\n\n-->\n{LINK}',
    f'<?php\n~~~\n?>\n{LINK}',
    f'<!DOCTYPE html\n~~~\n>\n{LINK}',
    f'<![CDATA[\n~~~\n]]>\n{LINK}',
    f'<pre>\n~~~\n</pre>\n{LINK}',
    f'<PRE class="x">\n\n~~~\n\n</Pre>\n{LINK}',
    f'<script>\n~~~\n</script>\n{LINK}',
    f'<style\n>\n~~~\n</style>\n{LINK}',
    f'<div>\n```\n</div>\n\n{LINK}',
    f'<div>\n~~~\n</div>\n\n{LINK}',
    f'  <DIV\n~~~\n\n{LINK}',
    f'</div>\n~~~\n\n{LINK}',
    f'<hr/>\n~~~\n\n{LINK}',
    f'Text\n<table>\n~~~\n\n{LINK}',
    f'<span class="a">\n~~~\n</span>\n\n{LINK}',
    f'</span>\n~~~\n\n{LINK}',
    f'<custom-tag data-x=1 />\n~~~\n\n{LINK}',
    f'- <div>\n  ~~~\n\n{LINK}',
    f'- <!--\n  ~~~\n{LINK}',
], ids=['comment', 'comment-with-blank-lines', 'processing-instruction', 'declaration', 'cdata', 'pre', 'pre-mixed-case-blank-lines',
        'script', 'style-open-tag-continues', 'div-backticks', 'div-tildes', 'indented-incomplete-div', 'closing-div', 'self-closing-hr',
        'table-interrupts-paragraph', 'complete-open-tag', 'complete-closing-tag', 'custom-element', 'div-in-list-item',
        'comment-ends-with-list-item'])
def test_a_fence_marker_inside_an_html_block_does_not_hide_a_later_link(body: str) -> None:
    # CommonMark 4.6: a fence marker inside an HTML block is raw HTML and opens
    # no code block. markdown-it-py 4.0.0 renders the link in every body.
    result = tokenize(body)
    assert ('helper.py', body.count('\n') + 1) in {(r.target, r.line) for r in result.resources}
    assert not result.uncertain


@pytest.mark.parametrize('body', [
    f'```\n<div>\n{LINK}\n```',
    f'Text\n<span>\n```\n{LINK}\n```',
    f'<div>\n\n```\n{LINK}\n```',
    f'<span>\n\n~~~\n{LINK}\n~~~',
    f'<!-- note -->\n```\n{LINK}\n```',
    f'<pre></pre>\n~~~\n{LINK}\n~~~',
    f'<?>\n~~~\n{LINK}\n~~~',
    f'<!-->\n~~~\n{LINK}\n~~~',
    f'<http://example.com>\n```\n{LINK}\n```',
    f'<div\n\n```\n{LINK}\n```',
    f'<prefix>\n\n```\n{LINK}\n```',
    f'- <div>\n\n```\n{LINK}\n```',
], ids=['html-inside-fence','open-tag-cannot-interrupt-paragraph', 'div-ends-at-blank-line',
        'span-ends-at-blank-line', 'one-line-comment', 'one-line-pre', 'end-overlaps-instruction-start', 'end-overlaps-comment-start',
        'autolink-is-not-a-tag', 'incomplete-div-ends-at-blank-line',
        'pre-prefix-is-an-ordinary-tag', 'div-in-list-item-ends-with-the-item'])
def test_a_link_inside_a_genuine_fence_stays_excluded_around_html(body: str) -> None:
    # markdown-it-py 4.0.0 renders the link line as code in every body.
    result = tokenize(body)
    assert result.resources == () and not result.uncertain


@pytest.mark.parametrize('body,complete', [
    (f'<textarea>\n\n~~~\n</textarea>\n{LINK}', True),
    (f'<textarea>\n\n~~~\n</textarea>\n\n~~~\n{LINK}\n~~~', True),
    (f'Text\n<source src="a.png">\n~~~\n\n{LINK}', True),
    (f'Text\n<search>\n~~~\n\n{LINK}', True),
    (f'<!doctype html\n~~~\n>\n{LINK}', True),
    (f'- <!--\n\n  ~~~\n  -->\n\n{LINK}', True),
    (f'<textarea>\n<search>\n<source>\n<!x>\n\n{LINK}', False),
], ids=['textarea', 'textarea-then-fence', 'source', 'search', 'lowercase-declaration', 'comment-with-blank-line-in-list-item',
        'more-forms-than-the-reading-bound'])
def test_html_forms_that_renderers_read_differently_govern_every_reading(body: str, complete: bool) -> None:
    # CommonMark 0.31.2 starts a block at <textarea>, <search> and a lowercase
    # declaration; 0.29, which GitHub Flavored Markdown follows, starts one at
    # <source> instead, and markdown-it ends a comment in a list item at a
    # blank line. In each body at least one of those readings renders the link
    # and, except in the first, another reads it as code. The helper is
    # governed under every reading, so coverage stays complete.
    result = tokenize(body)
    assert 'helper.py' in {r.target for r in result.resources}
    assert result.uncertain is not complete


@pytest.mark.parametrize('body,targets', [
    ('<div>\n<a href="helper.py">helper</a>\n</div>', ['helper.py']),
    ('<div>\n`<img src="helper.png">`\n</div>', ['helper.png']),
    ('<details>\n<summary>More</summary>\n\n[helper](helper.py)\n\n</details>', ['helper.py']),
], ids=['href-in-block', 'backticks-are-literal-in-block', 'markdown-between-block-tags'])
def test_dependencies_named_inside_html_blocks_stay_governed(body: str, targets: list[str]) -> None:
    result = tokenize(body)
    assert [r.target for r in result.resources] == targets and not result.uncertain


@pytest.mark.parametrize('body,linked', [
    ('[d]:\n`x`\n[L](helper.py)\n', True),
    ('[x](a "`") [L](helper.py) `', True),
    ('[a `]` b](helper.py)', True),
    ('`[a](helper.py)`', False),
    ('[a `b](helper.py)` c', False),
    ('\\`[a](helper.py)`', True),
    ('``[a](helper.py)`` and `x`', False),
    ('`a` [L](helper.py) `b`', True),
    ("[x](a '`') `[L](helper.py)`", False),
    ('[x]: a "`"\n\n[L](helper.py) `', True),
    ('``` [L](helper.py) `', True),
    ('[L](helper.py "`") `x`', True),
    ('`one\n\ntwo` [L](helper.py)', True),
], ids=['definition-destination-is-a-code-like-word', 'backtick-in-title', 'code-span-in-link-text', 'link-inside-code-span',
        'code-span-opens-in-link-text', 'escaped-backtick', 'double-backtick-span', 'spans-around-a-link',
        'link-inside-later-span', 'backtick-in-definition-title', 'unclosed-backtick-run', 'backtick-in-own-title', 'span-cannot-cross-blank-line'])
def test_code_spans_and_links_bind_left_to_right(body: str, linked: bool) -> None:
    # CommonMark 6.1 and 6.3: whichever of a code span or a link starts first
    # wins, and a destination or title is read as raw text. Each expectation
    # matches markdown-it-py 4.0.0.
    result = tokenize(body)
    assert ('helper.py' in {r.target for r in result.resources}) is linked
    assert not result.uncertain


def test_a_title_cannot_absorb_a_link_across_a_code_span() -> None:
    # The first bracket pair has no closing parenthesis after its title, so it
    # is not a link, and the later link is real.
    result = tokenize('[x](a "\n`[x](a "` [L](helper.py) ")\n')
    assert 'helper.py' in {r.target for r in result.resources}


@pytest.mark.parametrize('body,linked', [
    ('[d]: x\n===\n    [L](helper.py)\n', True),
    ('[d]: x\n===\n<span>\n[L](helper.py)\n', True),
    ('[d]: x\n[e]: y\n=\n[L](helper.py)\n', True),
    ('[d]: x\ntext\n===\n    [L](helper.py)\n', False),
    ('[d]: x\n---\n    [L](helper.py)\n', True),
], ids=['underline-is-text', 'underline-is-text-before-a-tag', 'two-definitions', 'heading-with-text', 'hyphens-are-text-in-cmark'])
def test_a_setext_underline_after_definitions_is_resolved_exactly(body: str, linked: bool) -> None:
    # CommonMark example 216: when definitions consume the whole paragraph the
    # underline is paragraph text, so a following indented line continues it.
    # For a line of hyphens cmark reads text and commonmark.js a thematic
    # break, so the link under it is governed for the cmark reading.
    result = tokenize(body)
    assert ('helper.py' in {r.target for r in result.resources}) is linked
    assert not result.uncertain


@pytest.mark.parametrize('body,targets', [
    ('[d]: x\n<span>\n~~~\n\n[L](helper.py)', {'x', 'helper.py'}),
    ('[d]: x\n    [L](helper.py)', {'x', 'helper.py'}),
    ('[d]: x\n"title"\n    [L](helper.py)', {'x', 'helper.py'}),
    ('[d]:x\\ [L](helper.py)', {'helper.py', 'x [L](helper.py)'}),
    ('[a](my\\ file.py) and [L](helper.py)', {'my file.py', 'helper.py'}),
    ('[d]:[L](helper.py)\n"")', {'[L](helper.py)', 'helper.py'}),
    ('[[``][L](helper.py)``<)> `', {'helper.py'}),
    ('``[L](helper.py)`` and `x`', set()),
], ids=['tag-line-after-definition', 'indented-line-after-definition', 'indented-line-after-definition-title', 'escaped-space-definition',
        'escaped-space-destination', 'definition-with-an-empty-title', 'span-beside-an-unclosed-backtick', 'spans-with-no-unclosed-backtick'])
def test_readings_that_reference_renderers_disagree_on_are_all_governed(body: str, targets: set[str]) -> None:
    # markdown-it closes the paragraph after a complete definition and cmark
    # continues it, so the first body links only in markdown-it and the next
    # two only in cmark. A backslash before a space ends a CommonMark
    # destination; renderers that predate it keep the space. commonmark.py and
    # markdown-it reject a definition whose title is empty and read its line
    # as text. markdown-it reads the span in the seventh body as literal text
    # because of the unclosed backtick after it; with no unclosed run, as in
    # the last body, every renderer reads code.
    result = tokenize(body)
    assert {r.target for r in result.resources} == targets
    assert not result.uncertain
