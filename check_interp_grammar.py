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

def interp_lookups():
    """Return {handler_name: set(referenced rule names)} from interpret.py."""
    src = open(INTERP).read()
    # split into methods i_*
    handlers = {}
    # find each def i_name(self, children): and capture until next 'def '
    for m in re.finditer(r'\n    def (i_\w+)\(self, children\):\n(.*?)(?=\n    def |\nclass |\Z)',
                         src, re.S):
        name, body = m.group(1), m.group(2)
        refs = set()
        for r in re.finditer(r"_find(?:_one|_all)?\(children,\s*'([^']+)'\)", body):
            refs.add(r.group(1))
        for r in re.finditer(r"\.data\s*(?:==|in)\s*\(?'([a-z_][a-z0-9_]*)'?", body):
            refs.add(r.group(1))
        for r in re.finditer(r"\.data\s+in\s+\(([^)]*)\)", body):
            for s in re.finditer(r"'([^']+)'", r.group(1)):
                refs.add(s.group(1))
        handlers[name] = refs
    return handlers

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
