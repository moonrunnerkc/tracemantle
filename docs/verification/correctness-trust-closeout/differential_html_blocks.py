"""Differential check: every helper.py link markdown-it-py (CommonMark) renders
must be reported by the tokenizer, or coverage must be incomplete."""
import random, sys, json
from markdown_it import MarkdownIt
import tracemantle
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
         '[helper](helper.py)', '[helper](helper.py)', '  [helper](helper.py)', '- [helper](helper.py)', '<b>[helper](helper.py)</b>']
seed, count = int(sys.argv[1]), int(sys.argv[2])
rng = random.Random(seed)
md = MarkdownIt('commonmark')
stats = {'documents': 0, 'oracle_links': 0, 'reported': 0, 'incomplete': 0, 'missed': 0, 'complete_documents': 0}
missed = []
for _ in range(count):
    body = '\n'.join(rng.choice(LINES) for _ in range(rng.randint(2, 9)))
    stats['documents'] += 1
    result = tokenize(body)
    stats['complete_documents'] += not result.uncertain
    if 'href="helper.py"' not in md.render(body):
        continue
    stats['oracle_links'] += 1
    if 'helper.py' in {r.target for r in result.resources}:
        stats['reported'] += 1
    elif result.uncertain:
        stats['incomplete'] += 1
    else:
        stats['missed'] += 1
        if len(missed) < 8:
            missed.append(body)
print(json.dumps({'source': sys.argv[3], 'seed': seed, **stats}))
for body in missed:
    print(repr(body))
