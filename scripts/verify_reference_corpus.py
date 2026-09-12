"""Compare the pinned skills-ref validator with TraceMantle standard diagnostics."""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from tracemantle import validate

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'tests/fixtures/upstream/skills-ref-69ef37e'


def verify() -> dict[str, Any]:
    sys.path.insert(0, str(REFERENCE))
    try:
        reference = importlib.import_module('skills_ref.validator')
    finally:
        sys.path.pop(0)
    cases: list[tuple[str, dict[str, Any], str | None]] = [
        ('valid', {'name': 'control', 'description': 'Validates source when reviewing code.'}, None),
        ('optional', {'name': 'control', 'description': 'Validates source.', 'license': 'MIT', 'metadata': {'author': 'test'}, 'compatibility': 'Python'}, None),
        ('uppercase', {'name': 'CONTROL', 'description': 'Validates source.'}, None),
        ('consecutive-hyphen', {'name': 'con--trol', 'description': 'Validates source.'}, None),
        ('missing-name', {'description': 'Validates source.'}, None),
        ('missing-description', {'name': 'control'}, None),
        ('long-name', {'name': 'a' * 65, 'description': 'Validates source.'}, None),
        ('long-description', {'name': 'control', 'description': 'a' * 1025}, None),
        ('long-compatibility', {'name': 'control', 'description': 'Validates source.', 'compatibility': 'a' * 501}, None),
        ('nonstring-compatibility', {'name': 'control', 'description': 'Validates source.', 'compatibility': 1}, None),
        ('unicode-name', {'name': 'café', 'description': 'Validates source.'}, 'TraceMantle portable naming profile intentionally accepts ASCII only; reference normalizes NFKC and accepts Unicode alphanumerics.'),
        ('metadata-value', {'name': 'control', 'description': 'Validates source.', 'metadata': {'count': 3}}, 'TraceMantle enforces specification string metadata values; this reference revision does not validate metadata contents.'),
        ('empty-compatibility', {'name': 'control', 'description': 'Validates source.', 'compatibility': ''}, 'TraceMantle enforces the specification minimum length of one; reference revision checks maximum length only.'),
    ]
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        for name, fields, divergence in cases:
            skill_dir = Path(directory) / str(fields.get('name', 'control'))
            skill_dir.mkdir(exist_ok=True)
            path = skill_dir / 'SKILL.md'
            path.write_text('---\n' + yaml.safe_dump(fields) + '---\nBody.\n')
            reference_errors = reference.validate_metadata(fields, skill_dir)
            result = validate(path)
            errors = [d.rule for d in result.diagnostics if d.source == 'spec' and d.severity.value == 'error']
            if bool(reference_errors) != bool(errors) and not divergence:
                raise ValueError(f'Unexpected conformance divergence in {name}: {reference_errors}, {errors}')
            rows.append({'case': name, 'reference_errors': reference_errors, 'tracemantle_errors': errors, 'intentional_divergence': divergence})
    return {'python': sys.version, 'reference_revision': '69ef37e9424c0a7ea9dd2293b559e43ec8176379', 'reference_version': '0.1.0',
            'source': 'https://github.com/agentskills/agentskills/tree/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref', 'cases': rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(verify(), indent=2, ensure_ascii=True) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
