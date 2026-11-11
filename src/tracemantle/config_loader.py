"""Project configuration with a deprecated SkillCheck transition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from tracemantle.io_limits import MAX_CONFIG_BYTES, read_guarded_text

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


@dataclass(frozen=True, slots=True)
class TraceMantleConfig:
    """Immutable configuration values loaded from TOML.

    All fields are optional so command-line flags can override them cleanly.
    """

    supplied: frozenset[str] = frozenset()
    tokenizer: str | None = None
    format: str | None = None
    max_lines: int | None = None
    max_tokens: int | None = None
    min_desc_score: int | None = None
    target_agent: str | None = None
    strict_vscode: bool | None = None
    strict_cursor: bool | None = None
    strict_all: bool | None = None
    skip_dirname_check: bool | None = None
    skip_ref_check: bool | None = None
    ignore: tuple[str, ...] = ()
    analyze_graph: bool | None = None
    semantic: bool | None = None
    history: bool | None = None
    critique_agent: str | None = None
    graph_agent: str | None = None
    extension_fields: frozenset[str] = frozenset()
    reserved_words: tuple[str, ...] | None = None


class ConfigError(Exception):
    """Raised when a selected project configuration cannot be parsed or validated."""


_KEY_MAP = {
    "tokenizer": "tokenizer",
    "format": "format",
    "max-lines": "max_lines",
    "max_lines": "max_lines",
    "max-tokens": "max_tokens",
    "max_tokens": "max_tokens",
    "min-desc-score": "min_desc_score",
    "min_desc_score": "min_desc_score",
    "target-agent": "target_agent",
    "target_agent": "target_agent",
     "strict-vscode": "strict_vscode",
     "strict_vscode": "strict_vscode",
     "strict-cursor": "strict_cursor",
     "strict_cursor": "strict_cursor",
     "strict-all": "strict_all",
     "strict_all": "strict_all",
    "skip-dirname-check": "skip_dirname_check",
    "skip_dirname_check": "skip_dirname_check",
    "skip-ref-check": "skip_ref_check",
    "skip_ref_check": "skip_ref_check",
    "ignore": "ignore",
    "analyze-graph": "analyze_graph",
    "analyze_graph": "analyze_graph",
    "semantic": "semantic",
    "history": "history",
    "critique-agent": "critique_agent",
    "critique_agent": "critique_agent",
    "graph-agent": "graph_agent",
    "graph_agent": "graph_agent",
}

_INT_FIELDS = {"max_lines", "max_tokens", "min_desc_score"}
_BOOL_FIELDS = {"strict_vscode", "strict_cursor", "strict_all", "skip_dirname_check", "skip_ref_check", "analyze_graph", "semantic", "history"}
_STR_FIELDS = {"tokenizer","format", "target_agent", "critique_agent", "graph_agent"}


def _read_toml(path: Path) -> dict[str, Any]:
    """Read and parse one bounded TOML file.

    Raises:
        ConfigError: the file is unreadable, oversized, not UTF-8 or not TOML.
    """
    try:
        raw = read_guarded_text(path, max_bytes=MAX_CONFIG_BYTES, what="Config", error_cls=ConfigError)
    except OSError as exc:
        raise ConfigError(f"Cannot read {path}: {exc}. Check file permissions and retry.") from exc
    try:
        # tomllib resolves to Any under the 3.10 type target (no stubs there).
        return cast(dict[str, Any], tomllib.loads(raw))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Cannot parse {path}: {exc}. Fix the TOML syntax and retry.") from exc


def _normalize_keys(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data.items():
        normalized = _KEY_MAP.get(key, key)
        if normalized in result:
            raise ConfigError(f'Ambiguous config aliases for {normalized!r}; provide one spelling.')
        result[normalized] = value
    frontmatter = result.get('frontmatter', {})
    if not isinstance(frontmatter, dict):
        raise ConfigError("Config section 'frontmatter' must be a table.")
    return result


def load_config(path: Path | None) -> TraceMantleConfig:
    """Load and validate a standalone or namespaced TOML configuration.

    Args:
        path: Config path, or None for an empty config.

    Returns:
        Validated TraceMantleConfig.

    Raises:
        ConfigError: If the file cannot be read, parsed, or validated.
    """
    if path is None:
        return TraceMantleConfig()
    return _config_from_data(_read_toml(path), path)


def _config_from_data(data: dict[str, Any], path: Path) -> TraceMantleConfig:
    if "tool" in data or path.name == "pyproject.toml":
        tool = data.get("tool", {})
        if not isinstance(tool, dict):
            raise ConfigError("Config section 'tool' must be a table.")
        legacy = tool.get("skillcheck", {})
        canonical = tool.get("tracemantle", {})
        if not isinstance(legacy, dict) or not isinstance(canonical, dict):
            raise ConfigError("Config tool namespaces must be tables.")
        legacy, canonical = _normalize_keys(legacy), _normalize_keys(canonical)
        data = {**legacy, **canonical, "frontmatter": {**legacy.get("frontmatter", {}), **canonical.get("frontmatter", {})}}
    data = _normalize_keys(data)
    data.pop("release", None)  # Release policy is read only from a trusted Git base.
    values: dict[str, Any] = {}
    frontmatter = data.pop("frontmatter", {})
    if not isinstance(frontmatter, dict):
        raise ConfigError("Config section 'frontmatter' must be a table.")
    for raw_key, value in frontmatter.items():
        if raw_key == "extension_fields":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ConfigError("Config key 'frontmatter.extension_fields' must be an array of strings.")
            values["extension_fields"] = frozenset(value)
        elif raw_key == "reserved_words":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ConfigError("Config key 'frontmatter.reserved_words' must be an array of strings.")
            values["reserved_words"] = tuple(value)
        else:
            raise ConfigError(f"Unknown config key 'frontmatter.{raw_key}' in {path}.")

    for raw_key, value in data.items():
        field = _KEY_MAP.get(raw_key)
        if field is None:
            raise ConfigError(f"Unknown config key '{raw_key}' in {path}; remove it or use a supported tracemantle option.")
        if field in _INT_FIELDS:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ConfigError(f"Config key '{raw_key}' must be an integer (got {value!r}).")
            values[field] = value
        elif field in _BOOL_FIELDS:
            if not isinstance(value, bool):
                raise ConfigError(f"Config key '{raw_key}' must be true or false (got {value!r}).")
            values[field] = value
        elif field in _STR_FIELDS:
            if not isinstance(value, str):
                raise ConfigError(f"Config key '{raw_key}' must be a string (got {value!r}).")
            values[field] = value
        elif field == "ignore":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ConfigError("Config key 'ignore' must be an array of strings.")
            values[field] = tuple(value)

    return TraceMantleConfig(**values, supplied=frozenset(values))


def _configs_in(directory: Path) -> tuple[Path, ...]:
    """Return the config files that select ``directory`` as a project root."""
    found = []
    for name in ("skillcheck.toml", "pyproject.toml", "tracemantle.toml"):
        path = directory / name
        if not path.is_file():
            continue
        if name == "pyproject.toml":
            namespaces = _read_toml(path).get("tool", {})
            if not isinstance(namespaces, dict):
                raise ConfigError(f"Config section 'tool' in {path} must be a table.")
            if not any(namespace in namespaces for namespace in ("tracemantle", "skillcheck")):
                continue
        found.append(path)
    return tuple(found)


def project_configs(start: Path, *, cache: dict[Path, tuple[Path, ...]] | None = None) -> tuple[Path, ...]:
    """Choose one project root; combine namespaces only within that root.

    The upward walk stops at the first directory holding a config, a
    repository root (``.git``) or the home directory. A directory's answer
    depends only on it and its ancestors, so a batch passes one ``cache`` to
    resolve shared ancestors, and their ``pyproject.toml`` files, once.

    Raises:
        ConfigError: a candidate ``pyproject.toml`` cannot be read or parsed.
    """
    current = start.resolve()
    if not current.is_dir():
        current = current.parent
    visited = []
    result: tuple[Path, ...] = ()
    for directory in (current, *current.parents):
        if cache is not None and directory in cache:
            result = cache[directory]
            break
        visited.append(directory)
        result = _configs_in(directory)
        if result or (directory / ".git").exists() or directory == Path.home():
            break
    if cache is not None:
        cache.update(dict.fromkeys(visited, result))
    return result


def load_project_config(start: Path, explicit: Path | None = None) -> tuple[TraceMantleConfig, tuple[Path, ...], bool]:
    """Load the merged project configuration for ``start``.

    Returns the merged config, the files it came from, and whether any
    deprecated SkillCheck configuration contributed.

    Raises:
        ConfigError: a selected file cannot be read, parsed or validated.
    """
    paths = (explicit,) if explicit else project_configs(start)
    values: dict[str, Any] = {}
    legacy_used = False
    for path in paths:
        data = _read_toml(path)
        loaded = _config_from_data(data, path)
        for name in loaded.supplied:
            values[name] = getattr(loaded, name)
        tool = data.get("tool", {})
        legacy_used |= path.name == "skillcheck.toml" or (isinstance(tool, dict) and "skillcheck" in tool)
    return TraceMantleConfig(**values, supplied=frozenset(values)), paths, legacy_used
