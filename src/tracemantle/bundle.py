"""Canonical bundle identity. Content identity does not establish correctness."""
from __future__ import annotations

import hashlib
import os
import re
import stat
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tracemantle.dependencies import analyze_dependencies
from tracemantle.io_limits import MAX_SCAN_BYTES, MAX_SCAN_FILES, read_bounded_bytes
from tracemantle.parser import ParsedSkill, ParseError, parse
from tracemantle.storage import EvidenceError, digest

EXCLUDED = frozenset({'.git', '__pycache__', '.DS_Store', '.skillcheck-history.json'})


@dataclass(frozen=True, slots=True)
class BundleFile:
    path: str
    sha256: str
    executable: bool
    size: int


def normalized_path(value: str) -> str:
    if not value or value.startswith('/') or '\\' in value or ':' in value or any(part in {'', '.', '..'} for part in value.split('/')):
        raise EvidenceError(f'Ambiguous bundle path {value!r}. Use normalized relative paths.')
    if any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value):
        raise EvidenceError(f'Control character in bundle path {value!r}. Rename the resource.')
    normalized = unicodedata.normalize('NFC', value)
    if normalized != value:
        raise EvidenceError(f'Non-NFC bundle path {value!r}. Normalize the filename before comparing.')
    return normalized


@dataclass(frozen=True, slots=True)
class BundleManifest:
    files: tuple[BundleFile, ...]
    description_sha256: str
    dependencies: tuple[tuple[str, str], ...]
    complete: bool
    issues: tuple[str, ...]

    @property
    def sha256(self) -> str:
        return digest({'schema_version': 1, 'files': [asdict(f) for f in self.files]})

    def to_dict(self) -> dict[str, Any]:
        return {'schema_version': 1, 'bundle_sha256': self.sha256, 'files': [asdict(f) for f in self.files],
                'description_sha256': self.description_sha256, 'dependencies': [list(e) for e in self.dependencies],
                'complete': self.complete, 'issues': list(self.issues)}


def create_manifest(root: Path, *, document: ParsedSkill | None = None) -> BundleManifest:
    root = root.resolve()
    if not root.is_dir():
        raise EvidenceError(f'Bundle {root} must be a directory containing SKILL.md.')
    try:
        document = document or parse(root / 'SKILL.md')
    except ParseError as exc:
        raise EvidenceError(f'Cannot manifest invalid skill: {exc}') from exc
    if document.path.resolve() != root / 'SKILL.md':
        raise EvidenceError('Parsed document does not belong to this bundle SKILL.md.')
    description = document.frontmatter.get('description')
    # Null remains hashable for history of skills with an empty/missing field;
    # ordinary validation still reports the required description diagnostic.
    if description is not None and not isinstance(description, str):
        raise EvidenceError(
            f'Cannot manifest description of type {type(description).__name__}; '
            'description must be a string. Quote date-like text in YAML.'
        )
    files: list[BundleFile] = []
    issues: list[str] = []
    seen: set[str] = set()
    total = 0
    def walk_error(exc: OSError) -> None:
        raise EvidenceError(f'Cannot scan bundle: {exc}') from exc
    for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
        for name in sorted([*dirs, *names]):
            if name in EXCLUDED:
                continue
            path = Path(directory) / name
            relative = normalized_path(path.relative_to(root).as_posix())
            key = relative.casefold()
            if key in seen:
                raise EvidenceError(f'Ambiguous case-colliding path {relative!r}. Rename one resource.')
            seen.add(key)
            if len(seen) > MAX_SCAN_FILES:
                raise EvidenceError(f'Bundle exceeds the {MAX_SCAN_FILES}-entry limit.')
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                issues.append(f'Unsupported symlink: {relative}')
                continue
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode):
                issues.append(f'Unsupported non-regular resource: {relative}')
                continue
            raw = document.raw_bytes if document is not None and relative == 'SKILL.md' else read_bounded_bytes(path, max_bytes=min(16 * 1024 * 1024, MAX_SCAN_BYTES - total), what='Bundle resource', error_cls=EvidenceError)
            total += len(raw)
            files.append(BundleFile(relative, hashlib.sha256(raw).hexdigest(), bool(info.st_mode & 0o111), len(raw)))
    if not any(f.path == 'SKILL.md' for f in files):
        raise EvidenceError(f'Bundle {root} has no regular SKILL.md.')
    try:
        skill = document or parse(root / 'SKILL.md')
        dependencies = analyze_dependencies(skill.path, skill.markdown)
        issues.extend(d.message for d in dependencies.diagnostics if d.severity.value == 'error')
        if not dependencies.complete:
            issues.append('Resource dependency coverage is incomplete; rerun the full relevant suite.')
        return BundleManifest(tuple(sorted(files, key=lambda f: f.path)), digest(description), dependencies.edges,
                              not issues, tuple(sorted(set(issues))))
    except ParseError as exc:
        raise EvidenceError(f'Cannot manifest invalid skill: {exc}') from exc


def manifest_from_dict(value: Any) -> BundleManifest:
    if not isinstance(value, dict) or set(value) != {'schema_version', 'bundle_sha256', 'files', 'description_sha256', 'dependencies', 'complete', 'issues'}:
        raise EvidenceError('Manifest must contain exactly the version-one manifest fields.')
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or type(value['complete']) is not bool:
        raise EvidenceError('Unsupported manifest schema or invalid complete flag.')
    if not isinstance(value['files'], list) or len(value['files']) > MAX_SCAN_FILES:
        raise EvidenceError('Manifest files must be a bounded array.')
    files = []
    for row in value['files']:
        if not isinstance(row, dict) or set(row) != {'path', 'sha256', 'executable', 'size'}:
            raise EvidenceError('Invalid manifest file fields.')
        if not isinstance(row['path'], str) or not isinstance(row['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise EvidenceError('Manifest file requires a path and full SHA-256 digest.')
        normalized_path(row['path'])
        if type(row['executable']) is not bool or type(row['size']) is not int or row['size'] < 0:
            raise EvidenceError('Manifest executable must be boolean and size a nonnegative integer.')
        files.append(BundleFile(**row))
    if len({f.path.casefold() for f in files}) != len(files) or files != sorted(files, key=lambda f: f.path):
        raise EvidenceError('Manifest paths must be unique and canonically sorted.')
    if not isinstance(value['dependencies'], list) or not all(isinstance(e, list) and len(e) == 2 and all(isinstance(p, str) for p in e) for e in value['dependencies']):
        raise EvidenceError('Manifest dependencies must be path pairs.')
    for edge in value['dependencies']:
        for item in edge:
            normalized_path(item)
    if not isinstance(value['issues'], list) or not all(isinstance(i, str) for i in value['issues']):
        raise EvidenceError('Manifest issues must be strings.')
    if not isinstance(value['description_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', value['description_sha256']):
        raise EvidenceError('Manifest description requires a full SHA-256 digest.')
    manifest = BundleManifest(tuple(files), value['description_sha256'], tuple(tuple(e) for e in value['dependencies']), value['complete'], tuple(value['issues']))
    if manifest.sha256 != value['bundle_sha256']:
        raise EvidenceError('Manifest bundle_sha256 does not match its canonical contents.')
    return manifest
