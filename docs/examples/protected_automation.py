#!/usr/bin/env python3
"""Runnable Linux automation mechanics demo, using bubblewrap and a deterministic helper.

No agent/model evaluation occurs. Run this file only from owner-approved tooling.
The setup command creates a local example policy/key, not a production deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tracemantle.adapters.neutral import ADAPTER, adapt
from tracemantle.approvals import approval_envelope, verify_approval
from tracemantle.bundle import create_manifest
from tracemantle.comparison import compare
from tracemantle.evidence import evidence_from_dict, timestamp
from tracemantle.io_limits import MAX_INGEST_BYTES, read_bounded_bytes
from tracemantle.policy import git_blob, load_trusted_policy
from tracemantle.signatures import NAMESPACE
from tracemantle.storage import EvidenceError, canonical, put_bytes, put_record

CHECKER = b'''import json, pathlib, sys
observed = json.loads(pathlib.Path(sys.argv[1]).read_bytes())
expected = pathlib.Path(sys.argv[2]).read_text()
sys.exit(0 if observed["exit_code"] == 0 and observed["stdout"] == expected else 1)
'''
SKILL = b'''---
name: demo
description: Prints a fixed greeting. Use when testing the evidence approval workflow.
---

Run [helper](helper.py) to print the demonstration greeting.
'''


def setup(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    trust = root / 'trusted'
    trust.mkdir()
    (trust / 'producer.py').write_bytes(Path(__file__).read_bytes())
    (trust / 'checker.py').write_bytes(CHECKER)
    (trust / 'fixture.txt').write_bytes(b'hello\n')
    (trust / 'configuration.json').write_bytes(b'{"timeout_seconds":10}')
    (trust / 'profile.json').write_bytes(b'{"purpose":"deterministic mechanics, not an agent"}')
    bundle = root / 'candidate' / 'demo'
    bundle.mkdir(parents=True)
    (bundle / 'SKILL.md').write_bytes(SKILL)
    (bundle / 'helper.py').write_bytes(b'print("hello")\n')
    shutil.copytree(bundle, root / 'baseline' / 'demo')
    keys = root / 'keys'
    keys.mkdir(mode=0o700)
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(keys / 'approval')], check=True)
    public = (keys / 'approval.pub').read_text().strip()
    identity = {name: hashlib.sha256((trust / filename).read_bytes()).hexdigest() for name, filename in (
        ('checker', 'checker.py'), ('configuration', 'configuration.json'), ('fixture', 'fixture.txt'), ('profile', 'profile.json'))}
    runner = 'protected-demo/sha256:' + hashlib.sha256((trust / 'producer.py').read_bytes()).hexdigest()
    (trust / 'pyproject.toml').write_text(f'''[tool.tracemantle.release]
schema_version=2
trusted_evidence=[]
[tool.tracemantle.release.automation]
signers=[{json.dumps(public)}]
checks=["greeting"]
max_age_seconds=3600
[[tool.tracemantle.release.checks]]
id="greeting"
kind="behavioral"
inputs=["SKILL.md", "helper.py"]
coverage_complete=true
checker_path="checker.py"
checker_sha256="{identity['checker']}"
configuration_sha256="{identity['configuration']}"
fixture_sha256="{identity['fixture']}"
profile_sha256="{identity['profile']}"
max_age_seconds=3600
required=true
routing_neighbors=[]
context={{runner="{runner}", adapter="{ADAPTER}", permissions="execute-helper,read-bundle,write-output", sandbox="bubblewrap", network="disabled"}}
''', encoding='utf-8')
    for command in (['init', '-q'], ['add', '.'], ['-c', 'user.name=TraceMantle demo', '-c', 'user.email=demo@example.invalid',
                                                  'commit', '-qm', 'One-time synthetic automation authority']):
        subprocess.run(['git', '-C', str(trust), *command], check=True)
    print(subprocess.check_output(['git', '-C', str(trust), 'rev-parse', 'HEAD'], text=True).strip())


def run(root: Path, revision: str, run_id: str, started: str) -> None:
    trust = root / 'trusted'
    policy = load_trusted_policy(trust, revision)
    producer = git_blob(trust, revision, 'producer.py')
    if Path(__file__).read_bytes() != producer:
        raise EvidenceError('Run the owner-approved producer bytes from the selected trusted base.')
    if not policy.automation:
        raise EvidenceError('This example requires explicitly configured automation authority.')
    before = create_manifest(root / 'candidate' / 'demo')
    if not before.complete:
        raise EvidenceError('Candidate dependencies must be complete.')
    now = datetime.now(timezone.utc)
    if not timestamp(started) <= now < timestamp(started) + timedelta(seconds=policy.automation.max_age_seconds):
        raise EvidenceError('Supply a fresh start time from the protected scheduler.')
    # Snapshot bytes, then validate the copy: candidate changes cannot race identity and execution.
    with tempfile.TemporaryDirectory(prefix='tracemantle-observer-') as temporary:
        scratch = Path(temporary)
        bundle = scratch / 'bundle'
        shutil.copytree(root / 'candidate' / 'demo', bundle, symlinks=True)
        manifest = create_manifest(bundle)
        if not manifest.complete or manifest.sha256 != before.sha256:
            raise EvidenceError('Candidate changed during the snapshot or contains unsupported resources.')
        for name in ('checker.py', 'fixture.txt', 'configuration.json', 'profile.json'):
            (scratch / name).write_bytes(git_blob(trust, revision, name))
        configuration = json.loads((scratch / 'configuration.json').read_bytes())
        observed_at = datetime.now(timezone.utc).isoformat()
        output = scratch / 'stdout'
        error = scratch / 'stderr'
        # Only system runtime and the read-only bundle enter the sandbox. No host home,
        # repository, key directory, environment, network or observer output is mounted.
        command = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session', '--clearenv',
                   '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib', '--ro-bind', '/lib64', '/lib64',
                   '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--ro-bind', str(bundle), '/bundle',
                   '--chdir', '/bundle', '/usr/bin/prlimit', '--fsize=5242880', '--cpu=10', '--nproc=64',
                   '/usr/bin/python3', '-I', '/bundle/helper.py']
        with output.open('wb') as stdout, error.open('wb') as stderr:
            completed = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       timeout=configuration['timeout_seconds'], check=False)
        transcript = {'exit_code': completed.returncode,
                      'stdout': read_bounded_bytes(output, max_bytes=MAX_INGEST_BYTES, what='stdout', error_cls=EvidenceError).decode('utf-8'),
                      'stderr': read_bounded_bytes(error, max_bytes=MAX_INGEST_BYTES, what='stderr', error_cls=EvidenceError).decode('utf-8')}
        transcript_path = scratch / 'transcript.json'
        transcript_path.write_bytes(canonical(transcript))
        verdict = subprocess.run([sys.executable, '-I', str(scratch / 'checker.py'), str(transcript_path), str(scratch / 'fixture.txt')],
                                 timeout=10, check=False)
        check = next(c for c in policy.checks if c.id == 'greeting')
        record = evidence_from_dict({
            'schema_version': 1, 'kind': 'check-evidence', 'check_id': check.id,
            'state': {0: 'pass', 1: 'fail'}.get(verdict.returncode, 'infrastructure-error'),
            'bundle_sha256': manifest.sha256, 'inputs': {f.path: f.sha256 for f in manifest.files},
            **{f'{name}_sha256': hashlib.sha256((scratch / filename).read_bytes()).hexdigest() for name, filename in (
                ('checker', 'checker.py'), ('configuration', 'configuration.json'), ('fixture', 'fixture.txt'), ('profile', 'profile.json'))},
            'artifact_sha256': hashlib.sha256(transcript_path.read_bytes()).hexdigest(),
            'observed_at': observed_at, 'observation_method': 'observed-execution',
            'runner': 'protected-demo/sha256:' + hashlib.sha256(producer).hexdigest(), 'adapter': ADAPTER,
            'model': 'deterministic-helper', 'model_revision': 'sha256:' + dict((f.path, f.sha256) for f in manifest.files)['helper.py'],
            'model_immutable': True, 'permissions': ['read-bundle', 'write-output', 'execute-helper'],
            'environment': {'sandbox': 'bubblewrap', 'network': 'disabled'}, 'tokenizer': {'id': 'none-deterministic'},
            'reason': 'Trusted checker compared isolated helper output with the fixed fixture; not a live agent evaluation.'})
        raw = canonical({'schema_version': 1, 'records': [record.to_dict()]})
        imported = adapt(raw, {'schema_version': 1, 'rows': {}})[0]
        # This temporary allowlist checks all existing compatibility rules before signing.
        # It never writes or weakens the trusted policy and cannot bless an uploaded record.
        report = compare(manifest, manifest, (imported,), replace(policy, trusted_evidence=frozenset({imported.sha256})))
        if report.state != 'pass':
            raise EvidenceError(f'Observer refuses approval: {report.to_dict()}')
        store = root / 'store'
        put_bytes(store / 'transcripts', transcript_path.read_bytes())
        put_bytes(store / 'sources', raw)
        record_path = put_record(store / 'records', imported.to_dict())
        issued = datetime.now(timezone.utc)
        approval = approval_envelope(imported, policy, run_id=run_id, run_started_at=started, issued_at=issued.isoformat(),
                                     expires_at=(timestamp(started) + timedelta(seconds=policy.automation.max_age_seconds)).isoformat())
        approval_path = record_path.with_name(record_path.name + '.approval.json')
        with approval_path.open('xb') as stream:
            stream.write(canonical(approval))
        subprocess.run(['ssh-keygen', '-Y', 'sign', '-f', str(root / 'keys' / 'approval'), '-n', NAMESPACE, str(approval_path)],
                       check=True, capture_output=True, timeout=30)
        if not verify_approval(imported, record_path, policy, candidate_sha256=manifest.sha256, run_id=run_id,
                               run_started_at=started, now=datetime.now(timezone.utc)):
            raise EvidenceError('Approval verification failed.')
        print(record_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'run'])
    parser.add_argument('root', type=Path)
    parser.add_argument('--base-revision')
    parser.add_argument('--run-id')
    parser.add_argument('--run-started-at')
    args = parser.parse_args()
    if args.command == 'setup':
        setup(args.root.resolve())
    else:
        if not all((args.base_revision, args.run_id, args.run_started_at)):
            parser.error('run requires --base-revision, --run-id and --run-started-at from the protected caller')
        run(args.root.resolve(), args.base_revision, args.run_id, args.run_started_at)


if __name__ == '__main__':
    main()
