"""Evidence adapters turn an evaluator export into canonical check-evidence records.

The built-in Promptfoo adapter and any file passed to ``import-evidence --adapter``
implement one function::

    def adapt(export_bytes: bytes, bindings: dict[str, Any]) -> list[CheckEvidence]

``export_bytes`` is the original export, already bounded to the import size limit.
``bindings`` is the decoded ``--bindings`` JSON object, or ``{'schema_version': 1, 'rows': {}}``
when none was supplied. The return value is a list of records built with
``evidence_from_dict``. Anything unsupported or malformed raises ``EvidenceError``;
an adapter never returns a partial or guessed result.

An external adapter is Python source that runs with the invoking user's privileges.
It is tooling, not evidence: TraceMantle refuses one stored inside the evaluated
bundle, and loads one only when ``--adapter`` is supplied.
"""
from __future__ import annotations

import hashlib
import types
from pathlib import Path
from typing import Any

from tracemantle.evidence import Evidence, evidence_from_dict
from tracemantle.io_limits import read_bounded_bytes
from tracemantle.storage import EvidenceError

__all__ = ['CheckEvidence', 'EvidenceError', 'MAX_ADAPTER_BYTES', 'adapt_external', 'evidence_from_dict']

CheckEvidence = Evidence
MAX_ADAPTER_BYTES = 1024 * 1024
_MAX_RECORDS = 10000


def adapt_external(path: Path, export_bytes: bytes, bindings: dict[str, Any]) -> tuple[Evidence, ...]:
    """Run the ``adapt`` function defined in the Python file at ``path``.

    The file is read once, so the bytes that are hashed are the bytes that run.
    Every returned record is revalidated and stamped with two identities the
    adapter cannot choose: ``adapter`` becomes ``external/sha256:<file digest>``
    and ``artifact_sha256`` becomes the digest of ``export_bytes``. A trusted
    policy can therefore pin an exact adapter file through ``context.adapter``,
    and an external adapter cannot present itself as the built-in one.

    Raises:
        EvidenceError: the file is unreadable or over 1 MiB, defines no ``adapt``
            function, fails while running, or returns anything other than a list
            of at most 10000 valid records.
    """
    source = read_bounded_bytes(path, max_bytes=MAX_ADAPTER_BYTES, what='Adapter', error_cls=EvidenceError)
    identity = f'external/sha256:{hashlib.sha256(source).hexdigest()}'
    artifact = hashlib.sha256(export_bytes).hexdigest()
    module = types.ModuleType('tracemantle_external_adapter')
    module.__file__ = str(path)
    try:
        exec(compile(source, str(path), 'exec'), module.__dict__)
        adapt = getattr(module, 'adapt', None)
        if not callable(adapt):
            raise EvidenceError(f'Adapter {path} must define adapt(export_bytes, bindings).')
        produced = adapt(export_bytes, bindings)
        if not isinstance(produced, list) or len(produced) > _MAX_RECORDS or not all(isinstance(r, Evidence) for r in produced):
            raise EvidenceError(f'Adapter {path} must return a list of at most {_MAX_RECORDS} records built with evidence_from_dict.')
        return tuple(evidence_from_dict({**r.to_dict(), 'adapter': identity, 'artifact_sha256': artifact}) for r in produced)
    except EvidenceError:
        raise
    except Exception as exc:
        # The adapter is foreign code; its failure is an import error to report, not a TraceMantle defect.
        raise EvidenceError(f'Adapter {path} failed: {type(exc).__name__}: {exc}') from exc
