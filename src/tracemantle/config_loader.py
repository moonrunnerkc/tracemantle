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


def find_config(start: Path) -> Path | None:
    """Find skillcheck.toml from a path or one of its parents.

    The upward walk stops at a repository root (a directory containing ``.git``)
    or the user's home directory, whichever is reached first. This keeps the
    search from escaping the project into a parent or a system directory and
    picking up an unrelated config.

    Args:
        start: File or directory path used as the search anchor.

    Returns:
        Path to skillcheck.toml, or None when not found.
    """
    try:
        home = Path.home()
    except RuntimeError:
        home = None
    current = start if start.is_dir() else start.parent
    for directory in (current, *current.parents):
        candidate = directory / "skillcheck.toml"
        if candidate.exists():
            return candidate
        # Do not ascend past a repo root or the user's home directory.
        if (directory / ".git").exists() or directory == home:
            break
    return None


def _parse_without_tomllib(raw: str) -> dict[str, Any]:
    """Compatibility helper; all supported interpreters use a real TOML parser."""
    try:
        return cast(dict[str, Any], tomllib.loads(raw))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML: {exc}") from exc


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
    try:
        raw = read_guarded_text(path, max_bytes=MAX_CONFIG_BYTES, what="Config", error_cls=ConfigError)
    except OSError as exc:
        raise ConfigError(f"Cannot read {path}: {exc}. Check file permissions and retry.") from exc

    try:
        data = tomllib.loads(raw)
    except ConfigError:
        raise
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Cannot parse {path}: {exc}. Fix the TOML syntax and retry.") from exc

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


def project_configs(start: Path) -> tuple[Path, ...]:
    """Choose one project root; combine namespaces only within that root."""
    current = start.resolve()
    if not current.is_dir():
        current = current.parent
    for directory in (current, *current.parents):
        paths = [directory / name for name in ("skillcheck.toml", "pyproject.toml", "tracemantle.toml")]
        found_list = []
        for path in paths:
            if not path.is_file():
                continue
            if path.name == "pyproject.toml":
                raw = read_guarded_text(path, max_bytes=MAX_CONFIG_BYTES, what="Config", error_cls=ConfigError)
                try:
                    namespaces = tomllib.loads(raw).get("tool", {})
                except tomllib.TOMLDecodeError as exc:
                    raise ConfigError(f"Invalid project TOML at {path}: {exc}") from exc
                if not any(name in namespaces for name in ("tracemantle", "skillcheck")):
                    continue
            found_list.append(path)
        found = tuple(found_list)
        if found:
            return found
        if (directory / ".git").exists() or directory == Path.home():
            break
    return ()


def load_project_config(start: Path, explicit: Path | None = None) -> tuple[TraceMantleConfig, tuple[Path, ...], bool]:
    paths = (explicit,) if explicit else project_configs(start)
    values: dict[str, Any] = {}
    legacy_used = False
    for path in paths:
        loaded = load_config(path)
        for name in loaded.supplied:
            values[name] = getattr(loaded, name)
        legacy_used |= path.name == "skillcheck.toml"
        if path.name == "pyproject.toml":
            raw = read_guarded_text(path, max_bytes=MAX_CONFIG_BYTES, what="Config", error_cls=ConfigError)
            legacy_used |= "skillcheck" in tomllib.loads(raw).get("tool", {})
    return TraceMantleConfig(**values, supplied=frozenset(values)), paths, legacy_used
