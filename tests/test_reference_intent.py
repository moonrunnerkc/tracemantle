"""Authentic upstream prose is data, not a missing-resource assertion."""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from tracemantle.bundle import create_manifest
from tracemantle.dependencies import analyze_dependencies
from tracemantle.markdown import tokenize
from tracemantle.parser import DocumentSettings, parse
from tracemantle.result import Severity

UPSTREAM = Path(__file__).resolve().parents[1] / 'integrations/sarif/vendor/sarif-parsing'


@pytest.mark.parametrize('target', ['/path/to/project/', '/github/workspace/', 'auth/login.py', 'admin/login.py'])
def test_authentic_examples_are_not_asserted_resources(target: str) -> None:
    skill = parse(UPSTREAM / 'SKILL.md')
    result = analyze_dependencies(skill.path, skill.markdown)
    assert not any(d.severity == Severity.ERROR and target in d.message for d in result.diagnostics)
    assert any(d.rule == 'references.uncertain' and target in d.message for d in result.diagnostics)
    assert not result.complete


@pytest.mark.parametrize('exists', [False, True])
def test_inline_intent_does_not_depend_on_file_existence(tmp_path: Path, exists: bool) -> None:
    (tmp_path / 'resources').mkdir()
    if exists:
        (tmp_path / 'resources/helper.py').write_text('pass\n')
    result = analyze_dependencies(tmp_path / 'SKILL.md', tokenize('Consider `resources/helper.py`.'))
    assert not result.complete
    assert [d.rule for d in result.diagnostics] == ['references.uncertain']


def test_base_dir_is_an_explicit_skill_root_interpretation(tmp_path: Path) -> None:
    shutil.copytree(UPSTREAM, tmp_path / 'sarif-parsing')
    path = tmp_path / 'sarif-parsing/SKILL.md'
    default = create_manifest(path.parent)
    assert not default.complete
    settings = DocumentSettings(reference_format='skill-base-dir')
    manifest = create_manifest(path.parent, document=parse(path, settings=settings))
    assert ('SKILL.md', 'resources/sarif_helpers.py') in manifest.dependencies
    assert ('SKILL.md', 'resources/jq-queries.md') in manifest.dependencies
    assert not manifest.complete  # Examples and runtime mentions remain ambiguous.
    (path.parent / 'resources/sarif_helpers.py').unlink()
    missing = create_manifest(path.parent, document=parse(path, settings=settings))
    assert any('does not exist' in issue and 'sarif_helpers.py' in issue for issue in missing.issues)


@pytest.mark.parametrize('target,rule', [
    ('missing.py', 'references.broken-link'),
    ('../outside.py', 'references.escape'),
    ('{baseDir}/../outside.py', 'references.escape'),
    ('{baseDir}/%2e%2e/outside.py', 'references.escape'),
    ('{baseDir}/%2Foutside.py', 'references.escape'),
    ('{baseDir}/..\\outside.py', 'references.escape'),
])
def test_explicit_links_keep_boundary_failures(tmp_path: Path, target: str, rule: str) -> None:
    result = analyze_dependencies(tmp_path / 'SKILL.md', tokenize(f'[required]({target})'), reference_format='skill-base-dir')
    assert not result.complete
    assert any(d.rule == rule for d in result.diagnostics)


@pytest.mark.parametrize('target', ['{other}/helper.py', '${HOME}/helper.py', '{baseDir}/$VAR/helper.py'])
def test_unresolved_variables_are_incomplete(tmp_path: Path, target: str) -> None:
    result = analyze_dependencies(tmp_path / 'SKILL.md', tokenize(f'[required]({target})'), reference_format='skill-base-dir')
    assert not result.complete


def test_base_dir_in_transitive_document_uses_skill_root(tmp_path: Path) -> None:
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'helper.py').write_text('pass\n')
    (tmp_path / 'docs/read.md').write_text('[helper]({baseDir}/helper.py)')
    body = tokenize('[guide]({baseDir}/docs/read.md)')
    initial = analyze_dependencies(tmp_path / 'SKILL.md', body, reference_format='skill-base-dir')
    assert initial.complete
    assert ('docs/read.md', 'helper.py') in initial.edges
    (tmp_path / 'helper.py').unlink()
    missing = analyze_dependencies(tmp_path / 'SKILL.md', body, reference_format='skill-base-dir')
    assert not missing.complete
    assert any(d.rule == 'references.broken-link' for d in missing.diagnostics)


@pytest.mark.skipif(__import__('sys').platform == 'win32', reason='Symlinks require Windows developer mode')
def test_template_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / 'skill'
    root.mkdir()
    (tmp_path / 'outside.py').write_text('pass\n')
    (root / 'helper.py').symlink_to(tmp_path / 'outside.py')
    result = analyze_dependencies(root / 'SKILL.md', tokenize('[helper]({baseDir}/helper.py)'), reference_format='skill-base-dir')
    assert not result.complete
    assert any(d.rule == 'references.escape' for d in result.diagnostics)


def test_upstream_bytes_match_provenance() -> None:
    provenance = json.loads((UPSTREAM.parent / 'PROVENANCE.json').read_text())
    assert provenance['revision'] == '1f68e03536f7980d4c0e6869596f708043a19443'
    for name, expected in provenance['files'].items():
        assert hashlib.sha256((UPSTREAM.parent / name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize('changed', ['helper.py', 'docs/read.md'])
def test_template_dependency_change_requires_rerun(tmp_path: Path, changed: str) -> None:
    from tests.test_build_plan_product import NOW, _bundle, _policy, _record
    from tracemantle.comparison import compare

    base = _bundle(tmp_path / 'base')
    (base / 'docs').mkdir()
    (base / 'docs/read.md').write_text('[helper]({baseDir}/helper.py)')
    skill = base / 'SKILL.md'
    skill.write_text(skill.read_text().replace('[helper](helper.py)', '[guide]({baseDir}/docs/read.md)'))
    settings = DocumentSettings(reference_format='skill-base-dir')
    before = create_manifest(base, document=parse(skill, settings=settings))
    record = replace(_record(base), inputs=tuple((f.path, f.sha256) for f in before.files if f.path == 'SKILL.md'),
                     observation_method='static-analysis')
    policy = _policy(record, 'static')
    policy = replace(policy, checks=(replace(policy.checks[0], inputs=('SKILL.md',)),))
    assert compare(before, before, (record,), policy, now=NOW).state == 'pass'
    (base / changed).write_text('changed\n')
    after = create_manifest(base, document=parse(skill, settings=settings))
    report = compare(before, after, (record,), policy, now=NOW)
    assert report.state == 'unknown'
    assert report.checks[0].rerun
    assert 'Declared helper' in ' '.join(report.checks[0].reasons)


def test_ambiguous_self_mention_does_not_assert_a_cycle(tmp_path: Path) -> None:
    result = analyze_dependencies(tmp_path / 'SKILL.md', tokenize('Consider `./SKILL.md`.'))
    assert not result.complete
    assert result.edges == (('SKILL.md', 'SKILL.md'),)
    assert [d.rule for d in result.diagnostics] == ['references.uncertain']
