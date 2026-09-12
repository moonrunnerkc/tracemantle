from __future__ import annotations

from collections.abc import Mapping

import yaml

from tracemantle import config
from tracemantle.parser import ParsedSkill
from tracemantle.result import Diagnostic, Severity


def check_unknown_fields(skill: ParsedSkill) -> list[Diagnostic]:
    diagnostics = []
    for field in skill.frontmatter:
        field_name = str(field)
        if field_name in config.SPEC_FIELDS or field_name in skill.settings.extension_fields or field_name in config.VENDOR_FIELDS:
            continue
        if field_name in config.ECOSYSTEM_FIELDS:
            diagnostics.append(Diagnostic(
                rule="frontmatter.field.ecosystem",
                severity=Severity.INFO,
                message=(
                    f"Field '{field_name}' is ecosystem-common but not in the "
                    f"agentskills.io spec. Add it to tracemantle.toml under "
                    f"[frontmatter] extension_fields if intentional."
                ),
                line=skill.field_lines.get(field_name),
                context=f"{field_name}: ...",
                source="advisory",
                confidence="medium",
            ))
            continue
        diagnostics.append(Diagnostic(
            rule="frontmatter.field.unknown",
            severity=Severity.WARNING,
            message=(
                f"Unknown frontmatter field '{field_name}'. "
                f"Known fields: {', '.join(sorted(config.SPEC_FIELDS))}."
            ),
            line=skill.field_lines.get(field_name),
            context=f"{field_name}: ...",
        ))
    return diagnostics


def _collect_anchor_names(fm_raw: str) -> list[str]:
    """Return the anchor names declared or referenced in the frontmatter.

    Uses the YAML event stream so only real anchors/aliases are seen. A ``&`` or
    ``*`` inside a quoted scalar (e.g. ``"Reviews R&D notes and *only* flags..."``)
    is part of the value, not an anchor, so it is not reported. Scalar and
    collection-start events carry ``.anchor`` for a declaration; alias events
    carry ``.anchor`` for a reference; both are collected.
    """
    try:
        events = yaml.parse(fm_raw, Loader=yaml.SafeLoader)
        anchors = [anchor for event in events if (anchor := getattr(event, "anchor", None))]
    except yaml.YAMLError:
        return []
    return sorted(set(anchors))


def check_yaml_anchors(skill: ParsedSkill) -> list[Diagnostic]:
    """Warn when YAML anchors or aliases are used in frontmatter."""
    names = skill.yaml_anchors
    if not names:
        return []

    return [Diagnostic(
        rule="frontmatter.yaml-anchors",
        severity=Severity.WARNING,
        message=(
            f"YAML anchors/aliases detected in frontmatter ({', '.join(names)}). "
            f"Anchors silently copy values between fields, which can bypass "
            f"validation. Use explicit values instead."
        ),
    )]


def check_standard_fields(skill: ParsedSkill) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for name in ("license", "compatibility", "metadata"):
        if name not in skill.frontmatter:
            continue
        value = skill.frontmatter[name]
        valid = isinstance(value, str)
        expected = "a string"
        if name == "compatibility":
            valid = valid and 1 <= len(value) <= 500
            expected = "a string of 1 to 500 characters"
        elif name == "metadata":
            valid = isinstance(value, Mapping) and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())
            expected = "a mapping of string keys to string values"
        if not valid:
            diagnostics.append(Diagnostic(f"frontmatter.{name}.type", Severity.ERROR, f"Field '{name}' must be {expected} (got {value!r}). Correct the value.", line=skill.field_lines.get(name), source="spec"))
    return diagnostics
