"""The suite's tiktoken vocabulary loads with the network closed.

CI's tokenizer job and offline containers would otherwise fetch cl100k_base
from openaipublic.blob.core.windows.net, and every tiktoken test would fail
for the network rather than for the code. conftest.py points
TIKTOKEN_CACHE_DIR at tests/fixtures/tiktoken, which holds the vocabulary
under the cache key tiktoken derives from its URL.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_HAS_TIKTOKEN = importlib.util.find_spec("tiktoken") is not None


@pytest.mark.skipif(not _HAS_TIKTOKEN, reason="tiktoken extra is not installed")
def test_cl100k_base_loads_with_the_network_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import tempfile

    import tiktoken
    import tiktoken.load
    import tiktoken.registry

    def closed(blobpath: str) -> bytes:
        if "://" in blobpath:
            raise OSError(f"network closed in this test; refused {blobpath}")
        with open(blobpath, "rb") as handle:
            return handle.read()

    # A warm cache in the machine's temp directory must not satisfy the load:
    # only the cache the suite configures may.
    empty = tmp_path / "temp"
    empty.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(empty))
    monkeypatch.delenv("DATA_GYM_CACHE_DIR", raising=False)
    monkeypatch.setattr(tiktoken.load, "read_file", closed)
    monkeypatch.setattr(tiktoken.registry, "ENCODINGS", {})

    encoding = tiktoken.get_encoding("cl100k_base")

    assert encoding.encode("hello world") == [15339, 1917]
