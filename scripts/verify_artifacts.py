"""Verify exactly the artifacts handed to publishing, in clean isolated installs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS = ROOT / 'constraints-dev.txt'


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f'Artifact check failed: {command!r}\n{result.stdout}\n{result.stderr}')
    return result.stdout.strip()


def verify(artifact: Path, legacy: Path | None = None) -> dict[str, object]:
    artifact = artifact.resolve()
    if not artifact.name.startswith('tracemantle-'):
        raise ValueError(f'Refusing non-TraceMantle artifact {artifact.name}')
    if artifact.suffix == '.whl':
        with zipfile.ZipFile(artifact) as wheel:
            metadata_paths = [n for n in wheel.namelist() if n.endswith('.dist-info/METADATA')]
            if len(metadata_paths) != 1 or '\nName: tracemantle\n' not in '\n' + wheel.read(metadata_paths[0]).decode():
                raise ValueError('Wheel distribution metadata must name tracemantle.')
    with tempfile.TemporaryDirectory(prefix='tracemantle-artifact-') as directory:
        work = Path(directory)
        environment = work / 'venv'
        venv.EnvBuilder(with_pip=True).create(environment)
        binary = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        pip = [str(binary), '-m', 'pip']
        run([*pip, 'install', '-c', str(CONSTRAINTS), 'hatchling'], work)
        if legacy:
            run([*pip, 'install', str(legacy.resolve())], work)
            run([*pip, 'uninstall', '-y', 'skillcheck'], work)
        run([*pip, 'install', '--no-build-isolation', '-c', str(CONSTRAINTS), str(artifact)], work)
        executable = environment / ('Scripts/tracemantle.exe' if os.name == 'nt' else 'bin/tracemantle')
        old_executable = environment / ('Scripts/skillcheck.exe' if os.name == 'nt' else 'bin/skillcheck')
        if old_executable.exists() or not executable.exists():
            raise ValueError('Clean install must expose tracemantle and no skillcheck executable.')
        check = '''import importlib.metadata as m, importlib.resources as r, warnings
import tracemantle
assert m.metadata('tracemantle')['Name'] == 'tracemantle'
assert r.files('tracemantle').joinpath('py.typed').is_file()
for name in ('critique-v1.json', 'graph-v1.json', 'evidence-v1.json'):
    assert r.files('tracemantle').joinpath('schemas', name).is_file(), name
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    import skillcheck
    assert skillcheck.validate is tracemantle.validate
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
from skillcheck.core import extract_graph_heuristic
assert callable(extract_graph_heuristic)
print(tracemantle.__version__)
'''
        version = run([str(binary), '-I', '-c', check], work)
        assert run([str(executable), '--version'], work) == f'tracemantle {version}'
        assert run([str(binary), '-I', '-m', 'tracemantle', '--version'], work) == f'tracemantle {version}'
        bundle = work / 'control'
        bundle.mkdir()
        (bundle / 'SKILL.md').write_text('---\nname: control\ndescription: Validates Python source when users ask for code checks.\nlicense: MIT\n---\n# Validate source\nRead source and report errors.\n')
        output = run([str(executable), str(bundle), '--analyze-graph', '--format', 'json'], work)
        report = json.loads(output)
        assert report['tool'] == 'TraceMantle' and report['gate']['passed']
        manifest = json.loads(run([str(executable), 'manifest', str(bundle), '--format', 'json'], work))
        assert manifest['result']['complete']
        run([*pip, 'check'], work)
        return {'artifact': artifact.name, 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
                'version': version, 'clean_install': 'passed', 'legacy_migration': 'passed' if legacy else 'not requested'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--legacy-wheel', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    artifacts = sorted([*args.directory.glob('*.whl'), *args.directory.glob('*.tar.gz')])
    if len(artifacts) != 2 or not any(p.suffix == '.whl' for p in artifacts):
        raise ValueError('Select a clean directory containing exactly one wheel and one source archive.')
    records = [verify(path, args.legacy_wheel) for path in artifacts]
    output = json.dumps({'python': sys.version, 'checks': records}, indent=2) + '\n'
    if args.output:
        args.output.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
