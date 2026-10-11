"""Opt-in detached signatures over canonical evidence records.

A signature is a sidecar file next to the record: ``RECORD.json.sig`` for
``ssh-keygen -Y sign`` output, ``RECORD.json.minisig`` for minisign. The signed
message is the record's canonical JSON bytes, which is exactly what
``import-evidence`` writes under ``STORE/records/``. Verification shells out to
the system tools, so there is no cryptography dependency.

Signatures never replace the ``trusted_evidence`` digest allowlist. They are
checked only when the trusted policy declares ``required_signers``.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tracemantle.io_limits import read_bounded_bytes
from tracemantle.storage import EvidenceError

NAMESPACE = 'tracemantle-evidence'
MAX_SIGNATURE_BYTES = 64 * 1024
_PRINCIPAL = 'tracemantle'
_TIMEOUT_SECONDS = 30
_SSH_KEY = re.compile(
    r'(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(?:256|384|521)|sk-ssh-ed25519@openssh\.com|sk-ecdsa-sha2-nistp256@openssh\.com)'
    r' ([A-Za-z0-9+/]{32,}={0,2})(?: [^\r\n]*)?')
# 2-byte algorithm, 8-byte key ID and a 32-byte Ed25519 key, base64 encoded.
_MINISIGN_KEY = re.compile(r'[A-Za-z0-9+/]{56}')


def signer_key(value: Any) -> str:
    """Validate one ``required_signers`` entry and drop any SSH key comment."""
    if isinstance(value, str):
        ssh = _SSH_KEY.fullmatch(value)
        if ssh:
            return f'{ssh.group(1)} {ssh.group(2)}'
        if _MINISIGN_KEY.fullmatch(value):
            return value
    raise EvidenceError('required_signers entries must be an OpenSSH public key ("ssh-ed25519 AAAA...") '
                        'or a 56-character minisign public key.')


def _run(command: list[str], tool: str, message: bytes | None = None) -> bool:
    try:
        return subprocess.run(command, input=message, capture_output=True, timeout=_TIMEOUT_SECONDS, check=False).returncode == 0
    except FileNotFoundError as exc:
        raise EvidenceError(f'The trusted policy requires signed evidence, but {tool} is not installed. '
                            f'Install it on the machine running the comparison.') from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvidenceError(f'Cannot verify an evidence signature with {tool}: {exc}') from exc


def has_required_signature(record_bytes: bytes, evidence_path: Path, signers: tuple[str, ...]) -> bool:
    """Report whether a sidecar of ``evidence_path`` is a valid signature of
    ``record_bytes`` by one of ``signers`` (already normalized by ``signer_key``).

    A missing sidecar, a signature by another key, a different namespace and a
    signature over other bytes all return False.

    Raises:
        EvidenceError: a sidecar exists but the tool needed to check it is not
            installed or cannot run, or the sidecar exceeds 64 KiB.
    """
    ssh_keys = [key for key in signers if ' ' in key]
    minisign_keys = [key for key in signers if ' ' not in key]
    for suffix, keys in (('.sig', ssh_keys), ('.minisig', minisign_keys)):
        sidecar = evidence_path.with_name(evidence_path.name + suffix)
        if not keys or not sidecar.is_file():
            continue
        signature = read_bounded_bytes(sidecar, max_bytes=MAX_SIGNATURE_BYTES, what='Evidence signature', error_cls=EvidenceError)
        with tempfile.TemporaryDirectory(prefix='tracemantle-verify-') as scratch:
            signature_copy = Path(scratch, 'signature')
            signature_copy.write_bytes(signature)
            if suffix == '.sig':
                allowed = Path(scratch, 'allowed_signers')
                allowed.write_text(''.join(f'{_PRINCIPAL} namespaces="{NAMESPACE}" {key}\n' for key in keys), encoding='utf-8')
                if _run(['ssh-keygen', '-Y', 'verify', '-f', str(allowed), '-I', _PRINCIPAL, '-n', NAMESPACE,
                         '-s', str(signature_copy)], 'ssh-keygen', record_bytes):
                    return True
            else:
                message = Path(scratch, 'record')
                message.write_bytes(record_bytes)
                if any(_run(['minisign', '-V', '-P', key, '-m', str(message), '-x', str(signature_copy)], 'minisign') for key in keys):
                    return True
    return False
