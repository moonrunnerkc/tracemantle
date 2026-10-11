#!/usr/bin/env python3
"""Reference runner: execute an agent command against a skill bundle and record what happened.

This is an example to copy and adapt. TraceMantle never imports or runs it. It
runs the command you give it with your privileges, so use a sandbox you trust.

    python observed_execution_runner.py --bundle skills/my-skill --check-id invoke \\
        --checker checks/invoke.py --configuration checks/agent-config.json \\
        --fixture checks/invoke-prompt.txt --profile checks/profile.json \\
        --model my-local-model --model-revision sha256:0123... --model-immutable \\
        --tokenizer my-tokenizer-v1 --output-dir out -- my-agent --skill skills/my-skill

The fixture file is piped to the command's stdin. Its stdout, stderr and exit
code are written to OUTPUT_DIR/CHECK_ID.transcript.json. The checker then runs as
``python CHECKER TRANSCRIPT`` and decides the outcome: exit 0 is pass, exit 1 is
fail, anything else is infrastructure-error. The record is written to
OUTPUT_DIR/CHECK_ID.observed.json in the observed-execution-v1 format.

Model identity, tokenizer, sandbox and permissions are your declarations; the
runner cannot observe them. Declare only what you actually pinned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PERMISSIONS = ('read-bundle', 'write-output', 'network', 'execute-helper')


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(bundle: Path) -> dict[str, Any]:
    result = subprocess.run([sys.executable, '-m', 'tracemantle', 'manifest', str(bundle), '--format', 'json'],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f'tracemantle manifest failed for {bundle} (exit {result.returncode}); '
                         f'fix the bundle until its identity is complete.\n{result.stdout}{result.stderr}')
    manifest: dict[str, Any] = json.loads(result.stdout)['result']
    return manifest


def _observe(command: list[str], fixture: Path, timeout: float) -> tuple[dict[str, Any], str | None]:
    """Run the agent command once. Returns the transcript and, when the command
    could not complete, the reason the run is an infrastructure error."""
    transcript: dict[str, Any] = {'command': command, 'exit_code': None, 'stdout': '', 'stderr': ''}
    try:
        completed = subprocess.run(command, input=fixture.read_bytes(), capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        return transcript, f'Agent command could not start: {exc}'
    except subprocess.TimeoutExpired:
        return transcript, f'Agent command exceeded the {timeout:g}-second timeout.'
    transcript.update(exit_code=completed.returncode, stdout=completed.stdout.decode('utf-8', 'replace'),
                      stderr=completed.stderr.decode('utf-8', 'replace'))
    return transcript, None


def _judge(checker: Path, transcript: Path, timeout: float) -> tuple[str, str]:
    try:
        verdict = subprocess.run([sys.executable, str(checker), str(transcript)], capture_output=True, text=True,
                                 timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return 'infrastructure-error', f'Checker exceeded the {timeout:g}-second timeout.'
    outcome = {0: 'pass', 1: 'fail'}.get(verdict.returncode, 'infrastructure-error')
    detail = (verdict.stdout.strip() or verdict.stderr.strip()).splitlines()
    return outcome, (detail[0] if detail else f'Checker exited {verdict.returncode}.')[:4096]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bundle', type=Path, required=True, help='Skill bundle directory')
    parser.add_argument('--check-id', required=True, help='ID of the trusted check this run answers')
    parser.add_argument('--checker', type=Path, required=True, help='Python script that judges the transcript')
    parser.add_argument('--configuration', type=Path, required=True, help='Agent configuration file used by the command')
    parser.add_argument('--fixture', type=Path, required=True, help='Test input, piped to the command on stdin')
    parser.add_argument('--profile', type=Path, required=True, help='Profile file the check is bound to')
    parser.add_argument('--model', required=True)
    parser.add_argument('--model-revision', required=True, help='Immutable revision or weights digest, not an alias')
    parser.add_argument('--model-immutable', action='store_true', help='Declare that --model-revision cannot change')
    parser.add_argument('--tokenizer', required=True, help='Identifier of the tokenizer the agent used')
    parser.add_argument('--network', default='disabled', help='Network access during the run (default: disabled)')
    parser.add_argument('--sandbox', default='none', help='Sandbox the command ran in (default: none)')
    parser.add_argument('--permission', action='append', choices=PERMISSIONS, help='Repeatable (default: read-bundle)')
    parser.add_argument('--timeout', type=float, default=600.0, help='Seconds allowed for the command and for the checker')
    parser.add_argument('--output-dir', type=Path, required=True, help='Directory outside the bundle')
    parser.add_argument('command', nargs=argparse.REMAINDER, help='Agent command, after --')
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('give the agent command after --')
    if args.output_dir.resolve().is_relative_to(args.bundle.resolve()):
        parser.error('--output-dir must be outside the bundle, or the run would change the bundle it measures')

    before = _manifest(args.bundle)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    observed_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    transcript, failure = _observe(command, args.fixture, args.timeout)
    transcript_path = args.output_dir / f'{args.check_id}.transcript.json'
    transcript_path.write_text(json.dumps(transcript, sort_keys=True, indent=2) + '\n', encoding='utf-8')

    if failure:
        outcome, reason = 'infrastructure-error', failure
    elif _manifest(args.bundle)['bundle_sha256'] != before['bundle_sha256']:
        outcome, reason = 'infrastructure-error', 'The bundle changed while the command ran; the run does not describe one bundle.'
    else:
        outcome, reason = _judge(args.checker, transcript_path, args.timeout)

    record = {
        'schema_version': 1,
        'kind': 'observed-execution',
        'check_id': args.check_id,
        'outcome': outcome,
        'observation_method': 'observed-execution',
        'observed_at': observed_at,
        'bundle_sha256': before['bundle_sha256'],
        'inputs_sha256': {entry['path']: entry['sha256'] for entry in before['files']},
        'checker_sha256': _sha256(args.checker),
        'configuration_sha256': _sha256(args.configuration),
        'fixture_sha256': _sha256(args.fixture),
        'profile_sha256': _sha256(args.profile),
        'artifact_sha256': _sha256(transcript_path),
        'context': {
            'runner': f'tracemantle-reference-runner/sha256:{_sha256(Path(__file__))}',
            'model': args.model,
            'model_revision': args.model_revision,
            'model_immutable': args.model_immutable,
            'permissions': sorted(set(args.permission or ['read-bundle'])),
            'environment': {'os': platform.system().lower(), 'python': platform.python_version(),
                            'architecture': platform.machine().lower(), 'network': args.network, 'sandbox': args.sandbox},
            'tokenizer': {'id': args.tokenizer},
        },
        'reason': reason,
    }
    record_path = args.output_dir / f'{args.check_id}.observed.json'
    record_path.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(record_path)


if __name__ == '__main__':
    main()
