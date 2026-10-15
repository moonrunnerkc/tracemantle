"""Bounded live observation; hosted model identity never authorizes reuse."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from sarif_workflow import ROOT, SKILL, sha

PROMPT = '''Use the SARIF skill at sarif-parsing/SKILL.md to read scan.sarif and return
its total finding count and by_level counts. The skill's {baseDir} denotes the
sarif-parsing directory. You may inspect its supporting files or execute its
standard-library helper read-only. Do not run a new scanner, change files, use
network services, or delegate. Return only the requested JSON. Empty severity
categories should be omitted. This is a real maintainer lint report; do not
invent findings or infer skill routing success from this explicit invocation.'''
SCHEMA = {'type': 'object', 'properties': {'total': {'type': 'integer'}, 'by_level': {
    'type': 'object', 'properties': {level: {'type': 'integer'} for level in ('error', 'warning', 'note', 'none')},
    'additionalProperties': False}}, 'required': ['total', 'by_level'], 'additionalProperties': False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'docs/verification/workflow-study/consumer/seed/run/scan.stdout'
    rows: list[dict[str, Any]] = []
    (output / 'prompt.txt').write_text(PROMPT)
    (output / 'schema.json').write_text(json.dumps(SCHEMA))
    for repetition in range(3):
        with tempfile.TemporaryDirectory(prefix='sarif-agent-') as directory:
            work = Path(directory)
            shutil.copytree(SKILL, work / 'sarif-parsing', ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
            shutil.copyfile(source, work / 'scan.sarif')
            command = ['codex', 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                       '--sandbox', 'read-only', '--model', 'gpt-6-astra', '--json', '-C', str(work),
                       '--output-last-message', str(output / f'{repetition}-answer.json'), PROMPT]
            start = time.perf_counter()
            timeout = False
            with (output / f'{repetition}-events.jsonl').open('wb') as stdout, (output / f'{repetition}-stderr.txt').open('wb') as stderr:
                with subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True) as process:
                    try:
                        code = process.wait(timeout=120)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        code = process.wait()
                        timeout = True
            answer = output / f'{repetition}-answer.json'
            parsed = None
            if answer.exists():
                try:
                    parsed = json.loads(answer.read_bytes())
                except json.JSONDecodeError:
                    pass  # A non-JSON final answer is an observed acceptance failure.
            rows.append({'repetition': repetition, 'argv': command, 'exit_code': code, 'timed_out': timeout,
                         'seconds': time.perf_counter() - start, 'answer': parsed,
                         'accepted': parsed == {'total': 0, 'by_level': {}},
                         'model': 'gpt-6-astra', 'model_immutable': False, 'input_sha256': sha(source)})
            (output / 'observations.json').write_text(json.dumps(rows, indent=2) + '\n')
            print(f'Live repetition {repetition}: exit={code}, accepted={rows[-1]["accepted"]}', flush=True)
            if code != 0 or timeout:
                break
    (output / 'hashes.json').write_text(json.dumps({p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}, indent=2) + '\n')


if __name__ == '__main__':
    main()
