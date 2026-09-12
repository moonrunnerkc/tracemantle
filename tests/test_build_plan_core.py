"""Independent reproductions for R01 and the shared analysis repairs."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tracemantle import validate
from tracemantle.config_loader import ConfigError, load_project_config
from tracemantle.display import markdown, terminal
from tracemantle.formatters import _format_json, _format_text
from tracemantle.io_limits import UntrustedInputError, read_bounded_bytes
from tracemantle.parser import DocumentSettings, ParseError, parse
from tracemantle.result import Diagnostic, Severity, ValidationResult
from tracemantle.rules.references import check_dependencies
from tracemantle.storage import EvidenceError, decode_json
from tracemantle.tokenizer import estimate_tokens, tokenizer_provenance

CASES = Path(__file__).parent / 'fixtures/tracemantle/cases'


@pytest.mark.parametrize('name', ['duplicate-name', 'duplicate-nested', 'inline-close', 'nonstring-key', 'boolean-key', 'mapping-key', 'recursive-alias'])
def test_malformed_yaml_is_rejected(name: str) -> None:
    with pytest.raises(ParseError):
        parse(CASES / f'{name}.md')


@pytest.mark.parametrize('name', ['valid-standard', 'valid-multiline', 'valid-empty-block', 'valid-bom', 'valid-crlf', 'valid-alias'])
def test_valid_yaml_boundaries(name: str) -> None:
    skill = parse(CASES / f'{name}.md')
    assert not skill.body.startswith('---')
    if name != 'valid-empty-block':
        assert skill.field_lines['name'] == 2
        assert skill.raw_text.splitlines()[skill.body_start_line - 1] == '# Validate modules'


def test_parsed_document_is_deeply_immutable() -> None:
    skill = parse(CASES / 'valid-standard.md')
    with pytest.raises(TypeError):
        skill.frontmatter['name'] = 'mutated'
    with pytest.raises(TypeError):
        skill.frontmatter['metadata']['author'] = 'mutated'


@pytest.mark.parametrize('name,rule', [('bad-metadata', 'frontmatter.metadata.type'), ('bad-metadata-values', 'frontmatter.metadata.type'), ('bad-compatibility', 'frontmatter.compatibility.type')])
def test_standard_field_validation(name: str, rule: str) -> None:
    result = validate(CASES / f'{name}.md', skip_dirname_check=True)
    assert any(d.rule == rule and d.source == 'spec' for d in result.diagnostics)


def test_standard_fields_are_not_vendor_or_unknown() -> None:
    result = validate(CASES / 'valid-standard.md', skip_dirname_check=True)
    assert not any(d.rule in {'frontmatter.field.unknown', 'frontmatter.field.ecosystem', 'compat.claude-only'} for d in result.diagnostics)


@pytest.mark.parametrize('name', ['fenced-links', 'external-links'])
def test_examples_and_external_schemes_are_not_local_dependencies(name: str) -> None:
    assert check_dependencies(parse(CASES / f'{name}.md')) == []


def test_actual_dependency_chains_and_cycles(tmp_path: Path) -> None:
    (tmp_path / 'docs').mkdir()
    source = tmp_path / 'SKILL.md'
    source.write_bytes((CASES / 'reference-links.md').read_bytes())
    (tmp_path / 'docs/guide.md').write_text('[next](second.md)\n')
    (tmp_path / 'docs/second.md').write_text('[cycle](guide.md)\n')
    diagnostics = check_dependencies(parse(source))
    assert {'references.cycle', 'references.depth-exceeded'} <= {d.rule for d in diagnostics}
    assert all(d.line == 7 for d in diagnostics)


def test_read_cap_is_enforced_on_actual_bytes(tmp_path: Path) -> None:
    path = tmp_path / 'growing.bin'
    path.write_bytes(b'x' * 100)
    with pytest.raises(UntrustedInputError, match='64-byte'):
        read_bounded_bytes(path, max_bytes=64, what='Test')
    assert read_bounded_bytes(path, max_bytes=100, what='Test') == b'x' * 100
    with pytest.raises(UntrustedInputError):
        read_bounded_bytes(tmp_path, max_bytes=64, what='Test')


def test_deep_yaml_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / 'SKILL.md'
    path.write_text('---\nmetadata: ' + '[' * 1000 + '0' + ']' * 1000 + '\n---\n')
    with pytest.raises(ParseError, match='limit'):
        parse(path)


@pytest.mark.parametrize('raw', ['{"x": 1, "x": 2}', '{"x": NaN}', '[' * 1000 + '0' + ']' * 1000])
def test_evidence_json_rejects_ambiguous_and_deep_inputs(raw: str) -> None:
    with pytest.raises(EvidenceError):
        decode_json(raw)


def test_controls_are_escaped_only_for_display() -> None:
    original = '\x1b[2Jé\x85\r\n'
    result = ValidationResult(Path('a\x1b.md'), [Diagnostic('test.rule', Severity.ERROR, original)])
    assert '\x1b' not in _format_text([result])
    assert '\x85' not in terminal(original)
    assert 'é' in terminal(original)
    assert json.loads(_format_json([result], '1.6.0'))['results'][0]['diagnostics'][0]['message'] == original
    assert markdown('[link](url)') == r'\[link\]\(url\)'


def test_config_precedence_and_no_global_state(tmp_path: Path) -> None:
    (tmp_path / 'skillcheck.toml').write_text('max-lines=20\nmax-tokens=100\n[frontmatter]\nreserved_words=["legacy"]\n')
    (tmp_path / 'pyproject.toml').write_text('[tool.tracemantle]\nmax-lines=30\n[tool.tracemantle.frontmatter]\nreserved_words=["canonical"]\n')
    (tmp_path / 'tracemantle.toml').write_text('max-lines=40\n')
    config, _, legacy = load_project_config(tmp_path)
    assert (config.max_lines, config.max_tokens, config.reserved_words, legacy) == (40, 100, ('canonical',), True)
    skill = parse(CASES / 'valid-standard.md')
    modified = replace(skill, settings=DocumentSettings(reserved_words=('control',)))
    assert any(d.rule == 'frontmatter.name.reserved-word' for d in validate(modified).diagnostics)
    assert not any(d.rule == 'frontmatter.name.reserved-word' for d in validate(skill).diagnostics)


def test_explicit_default_cli_values_win(tmp_path: Path) -> None:
    (tmp_path / 'skillcheck.toml').write_text('format="json"\ntarget-agent="vscode"\n')
    source = tmp_path / 'SKILL.md'
    source.write_bytes((CASES / 'valid-standard.md').read_bytes())
    proc = subprocess.run([sys.executable, '-m', 'tracemantle', str(source), '--format', 'text', '--target-agent=all', '--skip-dirname-check'], capture_output=True, text=True)
    assert proc.returncode == 0
    assert 'Checked 1 file' in proc.stdout
    assert 'Deprecated SkillCheck' in proc.stderr


def test_duplicate_toml_is_rejected(tmp_path: Path) -> None:
    (tmp_path / 'skillcheck.toml').write_text('format="text"\nformat="json"\n')
    with pytest.raises(ConfigError):
        load_project_config(tmp_path)


@pytest.mark.parametrize('mode', ['--emit-graph', '--emit-critique-prompt', '--emit-graph-prompt', '--activation-hypotheses', '--agent-reason', '--analyze-graph'])
def test_batch_json_is_one_document(mode: str) -> None:
    paths = [str(CASES / 'valid-standard.md'), str(CASES / 'valid-multiline.md')]
    proc = subprocess.run([sys.executable, '-m', 'tracemantle', *paths, mode, '--format', 'json', '--skip-dirname-check'], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert isinstance(json.loads(proc.stdout), dict)


def test_duplicate_paths_are_resolved_once_and_graph_ignore_controls_gate() -> None:
    path = str(CASES / 'valid-standard.md')
    proc = subprocess.run([sys.executable, '-m', 'tracemantle', path, path, '--analyze-graph', '--ignore', 'graph', '--strict', '--skip-dirname-check', '--format', 'json'], capture_output=True, text=True)
    data = json.loads(proc.stdout)
    assert data['files_checked'] == 1
    assert not any(d['rule'].startswith('graph') for d in data['results'][0]['diagnostics'])
    assert data['gate']['exit_code'] == proc.returncode


def test_explicit_tokenizer_provenance_and_special_markers() -> None:
    assert estimate_tokens('<|endoftext|>') > 0
    assert tokenizer_provenance()['backend'] == 'word-punctuation'
    try:
        import tiktoken
    except ImportError:
        from tracemantle.tokenizer import TokenizerError
        with pytest.raises(TokenizerError):
            estimate_tokens('<|endoftext|>', 'tiktoken')
    else:
        assert estimate_tokens('<|endoftext|>', 'tiktoken') == len(tiktoken.get_encoding('cl100k_base').encode('<|endoftext|>', disallowed_special=()))
