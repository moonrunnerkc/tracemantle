"""Differential check of inline precedence: every helper.py link markdown-it-py
(CommonMark) renders must be reported by the tokenizer, or coverage must be incomplete."""
import json
import random
import sys

import cmarkgfm
import commonmark
from cmarkgfm.cmark import Options
from markdown_it import MarkdownIt

from tracemantle.markdown import tokenize

TOKENS = ['`', '`', '``', '[', ']', '(', ')', '"', "'", ' ', ' ', 'a', 'x.py', '\\', '\n', '\n', '[L](helper.py)', '[L](helper.py)',
          '[x](a "', '")', '[d]:', '[d]', ']: ', '](', 'helper.py', '<', '>', '- ', '\n\n', '    ', '# ', '!']
seed, count, label = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
rng = random.Random(seed)
md = MarkdownIt('commonmark')
ORACLES = {
    'markdown-it-py': lambda body: md.render(body),
    'cmark-gfm': lambda body: cmarkgfm.github_flavored_markdown_to_html(body, options=Options.CMARK_OPT_UNSAFE),
    'commonmark.py': commonmark.commonmark,
}
stats = {'documents': 0, 'complete_documents': 0}
for name in ORACLES:
    stats[name] = {'links': 0, 'reported': 0, 'incomplete': 0, 'missed': 0}
missed = {}
for _ in range(count):
    body = ''.join(rng.choice(TOKENS) for _ in range(rng.randint(3, 14)))
    stats['documents'] += 1
    result = tokenize(body)
    stats['complete_documents'] += not result.uncertain
    reported = 'helper.py' in {r.target for r in result.resources}
    for name, render in ORACLES.items():
        if 'href="helper.py"' not in render(body):
            continue
        stats[name]['links'] += 1
        outcome = 'reported' if reported else 'incomplete' if result.uncertain else 'missed'
        stats[name][outcome] += 1
        if outcome == 'missed':
            missed.setdefault(body, []).append(name)
print(json.dumps({'source': sys.argv[3], 'seed': seed, **stats}))
for body, names in list(missed.items())[:int(sys.argv[4]) if len(sys.argv) > 4 else 10]:
    print(names, repr(body))
