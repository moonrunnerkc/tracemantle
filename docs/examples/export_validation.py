#!/usr/bin/env python3
"""Export real local static validation through the evaluator-neutral data contract."""
from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from tracemantle import __version__, validate
from tracemantle.bundle import create_manifest
from tracemantle.evidence import evidence_from_dict
from tracemantle.parser import DocumentSettings
from tracemantle.storage import EvidenceError, canonical, digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    manifest = create_manifest(args.bundle)
    if not manifest.complete:
        raise EvidenceError('Resolve missing or ambiguous bundle resources before exporting evidence.')
    result = validate(args.bundle / 'SKILL.md')
    record = evidence_from_dict({
        'schema_version': 1, 'kind': 'check-evidence', 'check_id': 'static-validation',
        'state': 'pass' if result.valid else 'fail', 'bundle_sha256': manifest.sha256,
        'inputs': {entry.path: entry.sha256 for entry in manifest.files},
        'configuration_sha256': digest(asdict(DocumentSettings())),
        'profile_sha256': digest({'profile': 'default-static', 'version': __version__}),
        'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'fixture_sha256': digest({'case': 'validate-the-supplied-bundle'}),
        'artifact_sha256': digest({'diagnostics': [d.rule for d in result.diagnostics]}),
        'observed_at': datetime.now(timezone.utc).isoformat(), 'observation_method': 'static-analysis',
        'runner': f'tracemantle/{__version__}', 'adapter': 'neutral-export-example',
        'model': 'unknown', 'model_revision': 'unknown', 'model_immutable': False,
        'permissions': ['read-bundle'], 'environment': {'network': 'disabled'},
        'tokenizer': {'backend': 'word-punctuation', 'version': '1'},
        'reason': 'Local static validation with default API settings; no agent evaluation.'})
    sys.stdout.buffer.write(canonical({'schema_version': 1, 'records': [record.to_dict()]}))


if __name__ == '__main__':
    main()
