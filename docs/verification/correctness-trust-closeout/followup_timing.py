import json
import time

from tracemantle.markdown import tokenize

CASES = {
    'definition-lines': lambda n: '[a]: x\n' * n,
    'definition-open-title': lambda n: '[a]: x "\n' + 't\n' * n,
    'definition-then-indented': lambda n: '[a]: x\n' + '    y\n' * n,
    'definition-then-prose-indented': lambda n: '[a]: x\ntext\n' + '    y\n' * n,
    'definitions-with-breaks': lambda n: '[a]: x\n<span>\n\n' * n,
    'three-alternatives': lambda n: '<textarea>\n<search>\n<source>\n' + '[a](b) `c`\n' * n,
    'backtick-runs': lambda n: '`' * n,
    'mixed-backtick-runs': lambda n: ''.join('`' * (i % 50 + 1) + ' ' for i in range(n // 26)),
    'unclosed-spans': lambda n: '`a ``b ```c ' * (n // 12),
    'bracket-backtick': lambda n: '[`' * (n // 2),
    'escaped-space-destinations': lambda n: '[a](b\\ c ' * (n // 9),
    'list-blank-comments': lambda n: '- <!--\n\n  -->\n' * (n // 14),
}
out = {}
for name, make in CASES.items():
    row = []
    for size in (200_000, 400_000):
        body = make(size)
        started = time.perf_counter()
        tokenize(body)
        row.append(round(time.perf_counter() - started, 3))
    out[name] = row
print(json.dumps(out, indent=1))
