"""The one place an expected validation-CLI input failure becomes output.

Covers failures the CLI documents as exit 2: unusable paths, configuration,
ingest files, revisions and option combinations. Unexpected exceptions are not
routed here, so an implementation defect still surfaces as a traceback.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import NoReturn

from tracemantle import __version__
from tracemantle.display import terminal


def exit_input_error(args: argparse.Namespace, message: str, *, text: str | None = None) -> NoReturn:
    """Report ``message`` and exit 2.

    With ``--format json`` and without ``--quiet`` this prints the schema-2
    error envelope on stdout and nothing else. Otherwise it prints ``text``
    (default ``Error: <message>``) on stderr with terminal controls escaped.
    """
    if args.format == 'json' and not args.quiet:
        print(json.dumps({'tool': 'TraceMantle', 'version': __version__, 'schema_version': 2,
                          'gate': {'passed': False, 'exit_code': 2}, 'results': [], 'errors': [{'error': message}]}))
    else:
        print(terminal(text if text is not None else f'Error: {message}'), file=sys.stderr)
    sys.exit(2)
