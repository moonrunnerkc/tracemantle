"""Opt-in evidence signatures. Keys are generated per test; records are synthetic."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.test_build_plan_product import NOW, _bundle, _policy, _record, _trusted_repository
from tracemantle.bundle import create_manifest
from tracemantle.comparison import compare
from tracemantle.policy import load_trusted_policy
from tracemantle.signatures import NAMESPACE, has_required_signature, signer_key
from tracemantle.storage import EvidenceError

needs_ssh = pytest.mark.skipif(shutil.which('ssh-keygen') is None, reason='ssh-keygen is not installed')
needs_minisign = pytest.mark.skipif(shutil.which('minisign') is None, reason='minisign is not installed')
MINISIGN_KEY = 'RWQf6LRCGA9i53mlYecO4IzT51TGPpvWucNSCh1CBM0QTaLn73Y7GFO3'


def _ssh_key(directory: Path, name: str) -> tuple[Path, str]:
    directory.mkdir(exist_ok=True)
    private = directory / name
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', f'{name}@example.invalid', '-f', str(private)],
                   check=True, capture_output=True)
    return private, private.with_name(name + '.pub').read_text().strip()


def _ssh_sign(private: Path, target: Path, namespace: str = NAMESPACE) -> Path:
    subprocess.run(['ssh-keygen', '-Y', 'sign', '-f', str(private), '-n', namespace, str(target)], check=True, capture_output=True)
    return target.with_name(target.name + '.sig')


def _compare_cli(base: Path, candidate: Path, trust: Path, revision: str) -> tuple[int, dict[str, object]]:
    result = subprocess.run([sys.executable, '-m', 'tracemantle', 'compare', str(base), str(candidate), '--trusted-root', str(trust),
                             '--base-revision', revision, '--evidence', str(trust / 'approved.json'), '--format', 'json'],
                            capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)['result']


def _gate(tmp_path: Path, release_extra: str) -> tuple[Path, Path, Path, str]:
    base = _bundle(tmp_path / 'base')
    candidate = tmp_path / 'candidate'
    shutil.copytree(base, candidate)
    trust = tmp_path / 'trust'
    record = replace(_record(base), observed_at=datetime.now(timezone.utc).isoformat())
    return base, candidate, trust, _trusted_repository(trust, record, release_extra)


@needs_ssh
def test_required_signer_accepts_a_record_signed_by_that_key(tmp_path: Path) -> None:
    private, public = _ssh_key(tmp_path / 'keys', 'owner')
    base, candidate, trust, revision = _gate(tmp_path, f'required_signers=["{public}"]')
    assert load_trusted_policy(trust, revision).required_signers == (' '.join(public.split()[:2]),)
    _ssh_sign(private, trust / 'approved.json')
    code, result = _compare_cli(base, candidate, trust, revision)
    assert code == 0 and result['state'] == 'pass', result


@needs_ssh
def test_required_signer_rejects_unsigned_foreign_and_altered_signatures(tmp_path: Path) -> None:
    private, public = _ssh_key(tmp_path / 'keys', 'owner')
    stranger, _ = _ssh_key(tmp_path / 'keys', 'stranger')
    base, candidate, trust, revision = _gate(tmp_path, f'required_signers=["{public}"]')
    record = trust / 'approved.json'
    sidecar = record.with_name('approved.json.sig')

    def rejected() -> bool:
        code, result = _compare_cli(base, candidate, trust, revision)
        reasons = result['checks'][0]['reasons']  # type: ignore[index]
        return code == 4 and result['state'] == 'unknown' and any('requires a signature' in reason for reason in reasons)

    assert rejected(), 'a record with no sidecar must not pass'
    _ssh_sign(stranger, record)
    assert rejected(), 'a signature from a key outside required_signers must not pass'
    sidecar.unlink()
    _ssh_sign(private, record, namespace='file')
    assert rejected(), 'a signature made for another namespace must not pass'
    sidecar.unlink()
    other = tmp_path / 'other.json'
    other.write_bytes(record.read_bytes().replace(b'"pass"', b'"fail"'))
    _ssh_sign(private, other).replace(sidecar)
    assert rejected(), 'a signature over different bytes must not pass'


@needs_ssh
def test_signature_covers_canonical_bytes_not_file_formatting(tmp_path: Path) -> None:
    private, public = _ssh_key(tmp_path / 'keys', 'owner')
    base, candidate, trust, revision = _gate(tmp_path, f'required_signers=["{public}"]')
    record = trust / 'approved.json'
    signature = _ssh_sign(private, record).read_bytes()
    pretty = trust / 'pretty.json'
    pretty.write_text(json.dumps(json.loads(record.read_bytes()), indent=2))
    pretty.with_name('pretty.json.sig').write_bytes(signature)
    assert has_required_signature(record.read_bytes(), pretty, load_trusted_policy(trust, revision).required_signers)


def test_policy_without_required_signers_ignores_sidecars(tmp_path: Path) -> None:
    base, candidate, trust, revision = _gate(tmp_path, '')
    (trust / 'approved.json.sig').write_text('not a signature')
    (trust / 'approved.json.minisig').write_text('not a signature')
    assert load_trusted_policy(trust, revision).required_signers == ()
    code, result = _compare_cli(base, candidate, trust, revision)
    assert code == 0 and result['state'] == 'pass', result


def test_signature_never_replaces_digest_approval(tmp_path: Path) -> None:
    base = _bundle(tmp_path / 'base')
    record = _record(base)
    manifest = create_manifest(base)
    policy = replace(_policy(record), required_signers=(MINISIGN_KEY,))
    signed = frozenset({record.sha256})
    assert compare(manifest, manifest, (record,), policy, now=NOW, signed_evidence=signed).state == 'pass'
    assert compare(manifest, manifest, (record,), policy, now=NOW).state == 'unknown'
    unapproved = replace(policy, trusted_evidence=frozenset())
    assert compare(manifest, manifest, (record,), unapproved, now=NOW, signed_evidence=signed).state == 'unknown'


@pytest.mark.parametrize('release_extra,message', [
    ('required_signers=[]', '1 to 100 public keys'),
    ('required_signers=["owner@example.invalid"]', 'OpenSSH public key'),
    ('required_signers="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGtq0000000000000000000000000000000000000000"', '1 to 100 public keys'),
    ('signers=["x"]', 'only optional key'),
])
def test_malformed_signer_policy_is_rejected(tmp_path: Path, release_extra: str, message: str) -> None:
    trust = tmp_path / 'trust'
    revision = _trusted_repository(trust, _record(_bundle(tmp_path / 'base')), release_extra)
    with pytest.raises(EvidenceError, match=message):
        load_trusted_policy(trust, revision)


def test_signer_key_keeps_key_material_and_drops_comments() -> None:
    key = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGtq0000000000000000000000000000000000000000'
    assert signer_key(key + ' release owner') == key
    assert signer_key(MINISIGN_KEY) == MINISIGN_KEY
    for invalid in (None, 7, '', MINISIGN_KEY[:-1], key + '\nssh-ed25519 AAAA', 'namespaces="x" ' + key):
        with pytest.raises(EvidenceError):
            signer_key(invalid)


def test_missing_verification_tool_is_an_error_not_a_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = tmp_path / 'record.json'
    record.write_bytes(b'{}')
    (tmp_path / 'record.json.minisig').write_text('untrusted comment: synthetic\n')
    empty = tmp_path / 'empty-path'
    empty.mkdir()
    monkeypatch.setenv('PATH', str(empty))
    with pytest.raises(EvidenceError, match='minisign is not installed'):
        has_required_signature(b'{}', record, (MINISIGN_KEY,))


@needs_minisign
def test_minisign_signature_is_accepted_only_from_a_required_key(tmp_path: Path) -> None:
    def keypair(name: str) -> tuple[Path, str]:
        secret, public = tmp_path / f'{name}.key', tmp_path / f'{name}.pub'
        subprocess.run(['minisign', '-G', '-W', '-p', str(public), '-s', str(secret)], check=True, capture_output=True)
        return secret, public.read_text().splitlines()[1]

    secret, public = keypair('owner')
    _, stranger_public = keypair('stranger')
    record = tmp_path / 'record.json'
    record.write_bytes(b'{"kind":"check-evidence"}')
    subprocess.run(['minisign', '-S', '-s', str(secret), '-m', str(record)], check=True, capture_output=True)
    assert has_required_signature(record.read_bytes(), record, (signer_key(public),))
    assert not has_required_signature(record.read_bytes(), record, (signer_key(stranger_public),))
    assert not has_required_signature(b'{"kind":"altered"}', record, (signer_key(public),))
