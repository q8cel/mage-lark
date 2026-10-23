#!/usr/bin/env python3
"""Static cross-check: interpreter handler  vs.  grammar rules.

Finds the core silent-bug class: i_<rule> handlers that look up a rule name
(_find_one/_find('name'), node.data == 'name', .data in ('a','b')) that does
NOT exist in the grammar, OR action handlers that never extract a sub-rule the
grammar rule actually produces.

  Part A: dangling lookups  -> interpreter references a rule name the grammar
          doesn't have (guaranteed no-op -> silently dropped field).
  Part B: coverage          -> for each action-like rule, which of its
          sub-rules are never referenced by the handler (potential drops).

Usage:  python check_interp_grammar.py
"""
import re, os, sys
BASE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR = os.path.join(BASE, 'grammar.lark')
INTERP = os.path.join(BASE, 'interpret.py')

def grammar_rules():
    rules = set()
    for line in open(GRAMMAR):
        m = re.match(r'^([a-z_][a-z0-9_]*):\s', line)
        if m:
            rules.add(m.group(1))
    return rules

def _method_bodies(src):
    """{method_name: body} for every indented method in the Interpreter class."""
    out = {}
    for m in re.finditer(
            r'\n    def ([A-Za-z_]\w*)\(self(?:, [^)]*)?\):\n(.*?)(?=\n    def |\nclass |\Z)',
            src, re.S):
        out[m.group(1)] = m.group(2)
    return out


def _direct_refs(body):
    refs = set()
    for r in re.finditer(r"_find(?:_one|_all)?\(children,\s*'([^']+)'\)", body):
        refs.add(r.group(1))
    for r in re.finditer(r"\.data\s*(?:==|in)\s*\(?'([a-z_][a-z0-9_]*)'?", body):
        refs.add(r.group(1))
    for r in re.finditer(r"\.data\s+in\s+\(([^)]*)\)", body):
        for s in re.finditer(r"'([^']+)'", r.group(1)):
            refs.add(s.group(1))
    return refs


def interp_lookups():
    """Return {handler_name: set(referenced rule names)} from interpret.py.

    A handler can delegate to a helper (e.g. `i_exile_action` -> `_card_action`),
    so references are expanded through `self._helper(...)` calls.  Without this,
    the checker reports dozens of false "missing" sub-rules for actions that use
    `_card_action`.
    """
    src = open(INTERP).read()
    bodies = _method_bodies(src)
    direct = {name: _direct_refs(body) for name, body in bodies.items()}
    calls = {name: set(re.findall(r'self\.([A-Za-z_]\w*)\(', body))
             for name, body in bodies.items()}

    def expand(name, seen=None):
        seen = set() if seen is None else seen
        if name in seen:
            return set()
        seen.add(name)
        refs = set(direct.get(name, ()))
        for helper in calls.get(name, ()):
            if helper in bodies:
                refs |= expand(helper, seen)
        return refs

    return {name: expand(name) for name in bodies if name.startswith('i_')}

def rule_subrules(grammar_text):
    """rule name -> set of lower-case rule names it directly references."""
    subs = {}
    for m in re.finditer(r'^([a-z_][a-z0-9_]*):\s*(.*?)(?=\n[a-z_][a-z0-9_]*:|\Z)',
                         grammar_text, re.S | re.M):
        name, body = m.group(1), m.group(2)
        referenced = set(re.findall(r'\b([a-z_][a-z0-9_]*)\b', body))
        subs[name] = referenced
    return subs

def main():
    gtext = open(GRAMMAR).read()
    rules = grammar_rules()
    handlers = interp_lookups()

    print('== PART A: dangling lookups (handler references a non-grammar name) ==')
    dangling = 0
    for h, refs in sorted(handlers.items()):
        bad = sorted(r for r in refs if r not in rules)
        if bad:
            dangling += 1
            print(f'  {h}: {bad}')
    if not dangling:
        print('  (none)')

    print('\n== PART B: action handlers that never extract a produced sub-rule ==')
    subs = rule_subrules(gtext)
    # only rules that HAVE an interpreter handler and produce card_target/amount/etc.
    interesting = {'card_target', 'amount', 'zone', 'kw_list', 'colors',
                   'damage_who', 'draw_amount', 'counter_amount', 'who',
                   'xdef', 'stat_change', 'with_modifier'}
    for r, s in sorted(subs.items()):
        if not r.endswith('_action') and r not in ('token', 'enters_action'):
            continue
        h = 'i_' + r
        if h not in handlers:
            print(f'  {r}: NO handler (i_{r} missing)')
            continue
        produced = s & interesting
        used = handlers[h]
        # also account for recursive extraction: a used sub-rule pulls in its own subs
        missing = produced - used
        if missing:
            print(f'  {r}: handler never looks up {sorted(missing)}')

if __name__ == '__main__':
    main()
