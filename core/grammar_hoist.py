"""Hoist EBNF optionals into helper rules so Lark stops duplicating their parent.

Why this exists
---------------
Lark's EBNF handling (`EBNF_to_BNF.maybe` + `SimplifyRule_Visitor.expansion`)
turns ``(a b)?`` inside a rule into *two full copies of the parent rule*, one
with the group and one without.  With several optionals in one alternative the
copies multiply: `grammar.lark` has ~470 optionals, and `search_action` alone
(a 10-alternative rule) compiles to 2,706 grammar rules.  The whole grammar
becomes 9,644 rules.

That is not just a build-time cost.  Lark's Earley parser precomputes, per
nonterminal, every rule reachable from it (`GrammarAnalyzer.expand_rule`) and
predicts all of them at each chart position.  Since nearly everything is
reachable from `start`, every position's item set is the entire grammar, so
even a one-token sentence costs ~1.8 s in `predict_and_complete`.

Hoisting each optional into its own rule makes the growth linear instead of
exponential: the parent keeps one alternative, and the helper carries the two
(`<body>` and empty).  Helpers are named with a leading underscore, so Lark
splices their children into the parent and the parse tree keeps its shape.

Measured effect (classic.json sample, same trees): 9,644 -> ~2,800 rules,
build 4.9 s -> 0.5 s, single-sentence parse 1.8 s -> 0.09 s.

Known caveat
------------
Moving an optional into its own rule changes rule indices, and the grammar is
genuinely ambiguous in places, so `ambiguity='resolve'` can pick a different
winning alternative for a small share of sentences (see docs/HOIST-SHIFTS.md).  The
transform itself never changes the *language*: every hoisted group keeps its
two possibilities.

This module is version-sensitive: it depends on how lark 1.3.1 expands optionals
(see requirements.txt). Re-measure the rule count after upgrading lark; if a
future version stops duplicating parents, the pass simply becomes a no-op.
"""

import re
import sys

STR = r'"(?:[^"\\]|\\.)*"'
REX = r'/(?:[^/\\\n]|\\.)+/[imslux]*'
NAME = r'[A-Za-z_][A-Za-z0-9_]*'
COMMENT = r'//[^\n]*'
_TOK = re.compile(f'{STR}|{REX}|{COMMENT}|{NAME}|\\s+|.', re.S)

HOISTED_PREFIX = '_opt_'


def tokenize(line):
    """Split a grammar line into [(text, kind)] tokens.

    kinds: 'str' (string literal), 'rex' (regex terminal), 'cmt' (comment),
    'name' (rule/terminal name), 'ws', 'char'.  Nothing inside 'str'/'rex'/'cmt'
    is ever inspected, so parentheses and `?` in a regex or a comment are inert.
    """
    toks = []
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c == '"':
            m = re.match(STR, line[i:])
            if m:
                toks.append((m.group(0), 'str')); i += m.end(); continue
        if c == '/' and line.startswith('//', i):
            m = re.match(COMMENT, line[i:])
            toks.append((m.group(0), 'cmt')); i += m.end(); continue
        if c == '/':
            # a regex terminal starts a value: after ':', '|', '(' or line start
            prev = ''.join(t for t, _ in toks).rstrip()
            if not prev or prev[-1] in ':|(':
                m = re.match(REX, line[i:])
                if m:
                    toks.append((m.group(0), 'rex')); i += m.end(); continue
        if c.isalpha() or c == '_':
            m = re.match(NAME, line[i:])
            toks.append((m.group(0), 'name')); i += m.end(); continue
        if c.isspace():
            m = re.match(r'\s+', line[i:])
            toks.append((m.group(0), 'ws')); i += m.end(); continue
        toks.append((line[i], 'char')); i += 1
    return toks


def _text(toks):
    return ''.join(t for t, _ in toks)


def _hoist_line(line, rules):
    """Hoist the first optional found on `line`; return (new_line, True) or (line, False)."""
    toks = tokenize(line)

    # 1) innermost ( ... )? groups -- innermost first so nested groups are
    #    already replaced by a reference when the outer group is handled.
    stack, groups = [], []
    for i, (t, k) in enumerate(toks):
        if k == 'char' and t == '(':
            stack.append(i)
        elif k == 'char' and t == ')' and stack:
            groups.append((stack.pop(), i))

    def is_optional(g):
        j = g[1] + 1
        while j < len(toks) and toks[j][1] == 'ws':
            j += 1
        return j < len(toks) and toks[j] == ('?', 'char')

    opts = [g for g in groups if is_optional(g)]
    inner = [g for g in opts
             if not any(g[0] < s2 < g[1] for (s2, _) in opts)]
    if inner:
        s, e = sorted(inner)[0]
        body = _text(toks[s + 1:e])
        name = f'{HOISTED_PREFIX}{len(rules)}'
        rules.append((name, body))
        j = e + 1
        while j < len(toks) and toks[j][1] == 'ws':
            j += 1
        return _text(toks[:s]) + name + _text(toks[j + 1:]), True

    # 2) single-atom optionals: ATOM? where ATOM is a literal, a regex or one name
    out = []
    i = 0
    while i < len(toks):
        t, k = toks[i]
        if k in ('str', 'rex', 'name') and i + 1 < len(toks) and toks[i + 1] == ('?', 'char'):
            name = f'{HOISTED_PREFIX}{len(rules)}'
            rules.append((name, t))
            out.append(name)
            i += 2
            return _text(toks[:i - 2]) + name + _text(toks[i:]), True
        out.append(t)
        i += 1
    return line, False


def hoist(text):
    """Rewrite `text` so optionals live in helper rules.  Returns (new_text, rules)."""
    rules = []
    lines = text.split('\n')
    while True:
        for li, line in enumerate(lines):
            new, changed = _hoist_line(line, rules)
            if changed:
                lines[li] = new
                break
        else:
            break
    # a rule may span lines (a trailing '|' continues on the next line); the
    # helpers are emitted at the end, where nothing follows but the file end.
    extra = []
    for name, body in rules:
        extra.append(f'{name}: {body}')
        extra.append('      |')
    return '\n'.join(lines) + '\n' + '\n'.join(extra) + '\n', rules


def hoisted_grammar(path):
    """Read `path` and return (hoisted_text, n_hoisted, n_added_rules)."""
    with open(path) as fh:
        src = fh.read()
    out, rules = hoist(src)
    return out, len(rules)


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    out, n = hoisted_grammar(src)
    if dst:
        with open(dst, 'w') as fh:
            fh.write(out)
    print(f'hoisted {n} optionals from {src}', file=sys.stderr)
