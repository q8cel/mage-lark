#!/usr/bin/env python3
"""Show the ACTUAL structured output the parser+interpreter produces for
successful parses, using a real set's name/type vocabulary (so card names
become `~`).

Usage:
    python demo_output.py                        # built-in examples (classic.json)
    python demo_output.py "Draw a card" "Flying, first strike"
    python demo_output.py FDN.json "Draw a card"   # .json arg = data file
    python demo_output.py --data FDN.json "Draw a card"
    python demo_output.py --cards 5               # first 5 fully-parsing cards
"""
import sys, os, json
from lark import Lark, LarkError
BASE = os.path.dirname(os.path.abspath(__file__))
GRAMMAR = os.path.join(BASE, 'grammar.lark')
from setdata import load
from preprocess import segment
from interpret import Interpreter

BUILTIN = [
    "Flying, first strike, and deathtouch",
    "Target creature you control gets +1/+1 until end of turn",
    "Creatures your opponents control get -1/-1",
    "Whenever this creature attacks, draw a card",
    "{2}, {T}: Draw two cards",
    "[+1]: Draw a card",
    "Create a 1/1 blue Bird creature token with flying",
    "At the beginning of each opponent's upkeep, this creature deals 1 damage to that opponent",
    "Whenever a creature an opponent controls enters the battlefield, put a -1/-1 counter on it",
    "When this creature dies, return it to the battlefield tapped under its owner's control at the beginning of their next upkeep",
]

def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(x) for x in o]
    if hasattr(o, 'value') and hasattr(o, 'type'): return str(o)
    return o

def _resolve(raw, names):
    """Deterministic anaphora pass -> (resolutions, rewritten text)."""
    import refs, rulecoref
    from anaphora import find_anaphors
    from preprocess import normalize_names, strip_reminders
    from setdata import normalize_text
    text = normalize_text(raw, names)
    res = rulecoref.resolve(text, refs.build(text), find_anaphors(text))
    return res, text


def show(parser, interp, names, raw, resolve=False, label=None):
    rewritten = None
    if resolve:
        try:
            res, text = _resolve(raw, names)
            print(f"\n===== RAW:{' ' + label if label else ''} {raw}")
            print("  resolutions:")
            for a in res["anaphors"]:
                ant = a["canonical"] or "?"
                extra = " [set]" if a.get("set_valued") else ""
                print(f"    {a['surface']!r:<18} -> {ant!r:<38} [{a['status']}]{extra}")
            rewritten = res["rewritten_text"]
            if rewritten != text:
                print(f"  rewritten: {rewritten}")
            raw = rewritten
        except Exception as e:
            print(f"  [resolve failed: {type(e).__name__}: {e}]")
    else:
        print(f"\n===== RAW:{' ' + label if label else ''} {raw}")
    for it in segment(raw, names):
        s = it['text']
        try:
            tree = parser.parse(s)
            out = interp.interp(tree)
            print(f"  segment: {s}")
            print(json.dumps(clean(out), indent=2, ensure_ascii=False))
        except LarkError as e:
            print(f"  segment: {s}\n  [UNPARSED] {str(e).splitlines()[0][:80]}")

def main():
    args = sys.argv[1:]
    data = 'classic.json'
    examples = []
    flags = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--data':
            data = args[i+1]; i += 1
        elif a == '--resolve':
            flags['resolve'] = True
        elif a == '--cards':
            flags['cards'] = True
            if i+1 < len(args) and args[i+1].isdigit():
                flags['ncards'] = args[i+1]; i += 1
        elif a.endswith('.json'):
            data = a                      # positional data file
        else:
            examples.append(a)
        i += 1

    items, types, names, sets = load(data)
    parser = Lark.open(GRAMMAR, parser='earley', start='start',
                       ambiguity='resolve', keep_all_tokens=True)
    interp = Interpreter(types=types, names=names)

    if flags.get('resolve'):
        print("(--resolve: anaphora resolved deterministically before interpreting)")

    if flags.get('cards'):
        n = int(flags.get('ncards', 5))
        shown = 0
        for name, text, code in items:
            if not text: continue
            segs = [d for d in segment(text, names) if d['text'] and not d['modal']]
            if not segs: continue
            ok = 0
            for d in segs:
                try: parser.parse(d['text']); ok += 1
                except LarkError: pass
            if ok != len(segs): continue      # only fully-parsing cards
            show(parser, interp, names, text, resolve=flags.get("resolve", False),
                 label=f"[{name}]")
            shown += 1
            if shown >= n: break
    else:
        for e in (examples if examples else BUILTIN):
            show(parser, interp, names, e, resolve=flags.get("resolve", False))

if __name__ == '__main__':
    main()
