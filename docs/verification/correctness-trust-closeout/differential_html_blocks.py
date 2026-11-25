"""Differential check: every helper.py link markdown-it-py (CommonMark) renders
must be reported by the tokenizer, or coverage must be incomplete."""
import json
import random
import sys

import cmarkgfm
import commonmark
from cmarkgfm.cmark import Options
from markdown_it import MarkdownIt

from tracemantle.markdown import tokenize

LINES = ['', '', '', '~~~', '```', '~~~~', '   ```', '    ```', '<!--', '-->', '<!-- c -->', '<div>', '</div>', '<div', '<DIV class="a">',
         '<pre>', '</pre>', '<pre', '<script>', '</script>', '<style>', '</style>', '<?', '?>', '<!X', '>', '<![CDATA[', ']]>',
         '<span>', '</span>', '<span class="a">', '<a href="other.py">', '<b>bold</b> text', 'Text', 'More text', '- item', '  continued',
         '1. first', '# Heading', '<table>', '<hr/>', '<p>', '<x-y a=b c=\'d\' e="f" />', '<http://example.com>', '<img src="i.png">',
         'text <!-- inline', '`code`', ' <div>', '   <!--', '  </pre>', '<details>', '<summary>s</summary>', '- <div>', '- <!--', '  -->',
         '<textarea>', '</textarea>', '<source src="s.png">', '<search>', '\t<div>', '<div>\t', '> quote', '[h]: helper.py', '[use][h]',
         '  - nested', '    <div>', '    ~~~', '<pre>~~~</pre>', '<!-- ` -->', '``` <div>', '~~~ html', '<div> ```', '</pre> ~~~', '<a\thref="x.py">',
         '<br>', '<br/>', '</br >', '<x y>', '<x y=>', '<1bad>', '<!>', '<?x ?>', '<!DOCTYPE html>', '===', '---', '***',
         '<?>', '<!-->', '<!--->', '<!x>', '<!X>', '[d]: x', '===', '=', '-', '- <style', '- <pre>', '  </style>', '  text',
         '`[x](a "` [helper](helper.py) ")', '    [helper](helper.py)', '- a', '<span>',
         '[d]: x', '[d]: x', '[e]:', 'y.py', '"title"', '""', '    text', '1. one', '2. two', '<span>', '</span>', '---', '=', '[d]',
         '[helper](helper.py)', '[helper](helper.py)', '  [helper](helper.py)', '- [helper](helper.py)', '<b>[helper](helper.py)</b>']
seed, count = int(sys.argv[1]), int(sys.argv[2])
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
    body = '\n'.join(rng.choice(LINES) for _ in range(rng.randint(2, 9)))
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
