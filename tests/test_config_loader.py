"""Tests for skillcheck.toml discovery and parsing (config_loader)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.conftest import CLI_AVAILABLE, TRACEMANTLE_CMD
from tracemantle.config_loader import (
    ConfigError,
    load_config,
    load_project_config,
    project_configs,
)


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_int_type_error_includes_offending_value(tmp_path: Path) -> None:
    cfg = _write(tmp_path / "skillcheck.toml", 'max-lines = "nope"\n')
    with pytest.raises(ConfigError, match=r"must be an integer \(got 'nope'\)"):
        load_config(cfg)


def test_bool_type_error_includes_offending_value(tmp_path: Path) -> None:
    cfg = _write(tmp_path / "skillcheck.toml", 'strict-vscode = "yes"\n')
    with pytest.raises(ConfigError, match=r"must be true or false \(got 'yes'\)"):
        load_config(cfg)


def test_str_type_error_includes_offending_value(tmp_path: Path) -> None:
    cfg = _write(tmp_path / "skillcheck.toml", "format = 5\n")
    with pytest.raises(ConfigError, match=r"must be a string \(got 5\)"):
        load_config(cfg)


def test_toml_parser_respects_literal_strings_and_comments(tmp_path: Path) -> None:
    assert load_config(_write(tmp_path / "skillcheck.toml", "format = 'a#b' # comment\n# whole line\n")).format == 'a#b'
    with pytest.raises(ConfigError, match="Fix the TOML syntax"):
        load_config(_write(tmp_path / "skillcheck.toml", 'bare = value'))


def test_hash_inside_quotes_is_part_of_the_value(tmp_path: Path) -> None:
    assert load_config(_write(tmp_path / "skillcheck.toml", 'format = "a#b"  # comment\n')).format == "a#b"


def test_discovery_stops_at_git_root(tmp_path: Path) -> None:
    # A config above the repo root must not be discovered from inside the repo.
    _write(tmp_path / "skillcheck.toml", "max-lines = 10\n")
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    assert project_configs(nested / "SKILL.md") == ()


def test_discovery_finds_config_at_git_root(tmp_path: Path) -> None:
    # A config at the repo root (alongside .git) is still found.
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    cfg = _write(repo / "skillcheck.toml", "max-lines = 10\n")
    nested = repo / "a"
    nested.mkdir()
    assert project_configs(nested / "SKILL.md") == (cfg.resolve(),)


def test_discovery_cache_matches_uncached_walks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    pyproject = _write(repo / "pyproject.toml", "[tool.tracemantle]\nmax_lines = 10\n")
    inner = repo / "skills" / "inner"
    inner.mkdir(parents=True)
    own = _write(inner / "tracemantle.toml", "max_lines = 20\n")
    plain = repo / "skills" / "plain"
    plain.mkdir()
    cache: dict[Path, tuple[Path, ...]] = {}
    for start in (plain, inner, repo / "skills", plain):
        assert project_configs(start, cache=cache) == project_configs(start)
    assert cache[plain.resolve()] == (pyproject.resolve(),)
    assert cache[inner.resolve()] == (own.resolve(),)


def test_pyproject_without_a_tool_namespace_is_not_a_project_config(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    _write(tmp_path / "pyproject.toml", "[project]\nname = 'other'\n")
    assert project_configs(tmp_path) == ()


def test_legacy_namespace_in_pyproject_is_reported(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    _write(tmp_path / "pyproject.toml", "[tool.skillcheck]\nmax_lines = 30\n")
    config, paths, legacy = load_project_config(tmp_path)
    assert config.max_lines == 30
    assert paths == ((tmp_path / "pyproject.toml").resolve(),)
    assert legacy is True


@pytest.mark.skipif(not CLI_AVAILABLE, reason="tracemantle not installed")
def test_cli_reports_loaded_config_path(tmp_path: Path) -> None:
    skill_dir = tmp_path / "cfg-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: cfg-skill\ndescription: Validates that the loaded config path is reported to stderr.\n---\nBody.\n",
        encoding="utf-8",
    )
    cfg = _write(skill_dir / "skillcheck.toml", "max-lines = 900\n")
    result = subprocess.run(
        [*TRACEMANTLE_CMD, "--skip-dirname-check", str(skill_dir / "SKILL.md")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert f"Loaded config from {cfg}" in result.stderr
