#!/usr/bin/env python3
"""Invariant checker: free structural audit of the interpreted output (no LLM).

Walks every already-interpreted sentence (from the content_check output cache)
and flags structural anomalies that indicate a silent parse bug:

  raw_action    the effect is {'verb':'raw',...} -> parsed but NOT decomposed.
                This is the headline "silent structure loss" metric; recurring
                raw texts reveal the grammar patterns still missing.
  pt_format     a power/toughness value that is not well-formed (e.g. "2/2", "+1/+1");
                disjunctions ("+X/+X or -X/-X") and an "an additional" prefix are valid
  unknown_zone  a zone value outside the MTG zone vocabulary (anaphoric "from among
                them" is accepted; one flag per zone site)
  bad_quantifier a quantifier outside the expected set (int and {'up_to': n} forms ok)
  bad_amount    an amount that is not a number/word-number, a mana value, a mana
                phrase, or a computed/relative expression
  empty_target  a card/card_type target with no kind/type/value (empty placeholders on
                object-less verbs are ignored; ability words like "activated" still fire)
  bare_fragment a `fragment` payload on a node that is not marked unparsed (free text
                must only live on unparsed=true or type=unparsed)
  fallback_text a `text` key anywhere in the output (the purge removed text payloads)

Usage:
  python invariant_check.py [data.json]
  python invariant_check.py classic.json --min 2     # only show >=2 occurrences
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import paths as _paths
_paths.bootstrap()
import sys, os, re, json, argparse, glob
from collections import Counter, defaultdict
BASE = _paths.ROOT
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, 'core'))
from clause_metric import classify_clause, CLAUSE, EXPRESSION

ZONE      = {'battlefield', 'hand', 'library', 'graveyard', 'exile', 'stack', 'yard',
             'hands', 'libraries', 'graveyards', 'stacks', 'battlefields'}
# "from among them" refers to a set revealed/exiled earlier, it is not a zone.  Accept
# these anaphors only as the source of a "from" phrase (artifacts S16/S18/S28/S29/S33).
ANAPHORIC_ZONE = {'them', 'it', 'those', 'these'}
ZONE_PREPS     = {'from'}
QUANT     = {'a', 'an', 'each', 'all', 'other', 'target', 'up', 'no', 'x', 'that', 'their',
             'the', 'any', 'every', 'any number of', 'up to', 'some',
             'half', 'half the', 'one', 'one or more', 'another', 'that many', 'one or two'}      # S24, S36, S42
# structured quantifier encodings: "up to N" / "one or more" (S13, S42)
QUANT_KEYS = {'up_to', 'one_or_more', 'at_least', 'at_most'}
WORD_AMT  = {'a', 'an', 'x', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
             'nine', 'ten', 'each', 'equal'}
PT_ITEM   = r'[+-]?(?:x|\d+)/[+-]?(?:x|\d+)'
PT_RE     = re.compile(rf'^{PT_ITEM}$', re.I)                        # 2/2, +1/+1, -x/-x
PT_DISJ_RE = re.compile(rf'^{PT_ITEM}(?:\s+or\s+{PT_ITEM})+$', re.I)  # "+X/+X or -X/-X" (S11)
PT_PREFIX_RE = re.compile(r'^(?:an?\s+)?additional\s+', re.I)         # "an additional +2/+2" (S34)
MANA_RE   = re.compile(r'^\{[^{}]+\}(\s*\{[^{}]+\})*$')        # {1}, {R}, {1}{B}, {2} {U}
MANA_DISJ_RE = re.compile(r'^\{[^{}]+\}(\s*(?:or|and)\s*\{[^{}]+\})+$')  # "{B} or {R}" (S04-S08, S19-S23)
# counts that may precede a mana symbol or "mana" phrase ("6 {R}", "three mana of ...")
NUM_CNT   = r'(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|x)'
MANA_COUNT_RE = re.compile(rf'^{NUM_CNT}\s+\{{[^{{}}]+\}}$', re.I)   # "6 {R}" (S39)
MANA_PHRASE_RE = re.compile(
    rf'^{NUM_CNT}\s+mana\s+'
    r'(?:of\s+any(?:\s+one)?\s+colou?rs?'
    r'|in\s+any\s+combination\s+of\s+colou?rs)\s*$', re.I)     # S01/S12/S14/S15/S25/S27/S35/S41/S43
NUNIT_RE  = re.compile(r'^[0-9x]+\s+\w+$')                     # "1 life", "X damage"
REL_AMT   = re.compile(r'\b(that|these|this|such|equal to)\b')  # relative: "double that", "...plus 1"
# computed amounts: the expression itself is the value (S09, S24, S37, S38, S43)
COMPUTED_AMT_RE = re.compile(
    r'^(?:half|the\s+(?:greatest|number|total)|equal\s+to|that\s+much|that\s+many|'
    r'twice|double|x)\b', re.I)
# amounts the interpreter built by str()-joining a dict: the structured value is still
# present inside the string, so nothing was lost (S02, S09, S17, S37, S44).
STRINGIFIED_STRUCT_RE = re.compile(r"\{'[A-Za-z_]+':")
# intransitive actions: card/card_target is a placeholder for the sentence-level subject,
# so an empty dict is not a lost target (S03, S30, S32, S40).
OBJECTLESS_VERBS = {'no_untap', 'assign_combat', 'can_attack_as_though',
                    'attacks_each_combat'}
# card_kind's literal ability alternatives lose the noun ("activated abilities" ->
# kind=type value='activated'), leaving no real card type (S10).
ABILITY_WORDS = {'activated', 'triggered'}


def _amount_ok(a):
    """Recognised amount shapes: number/word, mana, mana phrase, computed, relative."""
    if a.lower() in WORD_AMT or a.isdigit():
        return True
    if MANA_RE.match(a) or MANA_DISJ_RE.match(a) or MANA_COUNT_RE.match(a):
        return True
    if MANA_PHRASE_RE.match(a):
        return True
    if COMPUTED_AMT_RE.match(a):
        return True
    if STRINGIFIED_STRUCT_RE.search(a):
        return True
    return bool(NUNIT_RE.match(a) or REL_AMT.search(a))


def _pt_ok(v):
    """Well-formed power/toughness value, allowing modifiers and disjunctions."""
    s = PT_PREFIX_RE.sub('', v.strip())
    return bool(PT_RE.match(s) or PT_DISJ_RE.match(s))


def _zone_ok(z, node):
    """Zone vocabulary; an anaphor is allowed only after a 'from' preposition."""
    if z.lower() in ZONE:
        return True
    prep = node.get('prep') if isinstance(node, dict) else None
    return (isinstance(prep, str) and prep.lower() in ZONE_PREPS
            and z.lower() in ANAPHORIC_ZONE)


def _quant_ok(q):
    """Quantifier vocabulary, including the structured encodings the interpreter emits."""
    if isinstance(q, bool):
        return False
    if isinstance(q, int):
        return True
    if isinstance(q, str):
        return q.lower() in QUANT
    if isinstance(q, dict):
        return bool(QUANT_KEYS & set(q))
    return False


def load_my_outputs():
    cands = [os.path.join(_paths.CACHE, f) for f in os.listdir(_paths.CACHE)
             if f.startswith('out_')]
    if not cands:
        return {}
    blob = json.load(open(sorted(cands, key=os.path.getmtime)[-1]))
    out = {}
    for s, b in blob.items():
        if b and not b.startswith('\x00'):
            try:
                out[s] = json.loads(b)
            except Exception:
                pass
    return out


HARD = {'fallback_text', 'illegal_quote', 'label_without_structure',
        'bare_condition', 'bare_modifier', 'bare_xdef'}


def check(out, sent, flags):
    def walk(o, parent=None):
        if isinstance(o, dict):
            verb = o.get('verb') if isinstance(o.get('verb'), str) else None
            if 'text' in o:
                flags.append(('fallback_text', sent, str(o['text'])[:80]))
            if 'fragment' in o and not (o.get('unparsed') is True
                                        or o.get('type') == 'unparsed'):
                flags.append(('bare_fragment', sent, str(o['fragment'])[:80]))
            if 'label' in o and not (
                    'items' in o and any(k in o for k in ('connector', 'logic', 'kind'))):
                flags.append(('label_without_structure', sent, str(o['label'])[:80]))
            if 'quote' in o:
                scoped = (verb in ('gain_quote', 'emblem')
                          or 'token' in o or 'types' in o
                          or 'power_toughness' in o
                          or (verb == 'become' and ('target' in o or 'type' in o)))
                if not scoped:
                    flags.append(('illegal_quote', sent, str(o['quote'])[:80]))
            for k, v in o.items():
                if k in ('condition', 'if', 'unless', 'trailing_if',
                         'modifier', 'with_modifier', 'xdef'):
                    verdict = classify_clause(k, v)
                    if verdict in (CLAUSE, EXPRESSION):
                        flag = ('bare_condition' if k in
                                ('condition', 'if', 'unless', 'trailing_if')
                                else 'bare_modifier' if k in
                                ('modifier', 'with_modifier') else 'bare_xdef')
                        flags.append((flag, sent, f"{k}={str(v)[:80]}"))
                if k == 'verb' and v == 'raw':
                    flags.append(('raw_action', sent, (o.get('fragment') or '').strip()))
                elif k in ('pt', 'change', 'power', 'toughness') and isinstance(v, str):
                    if '/' in v and not _pt_ok(v):
                        flags.append(('pt_format', sent, f"{k}={v!r}"))
                elif k == 'zone':
                    z = v.get('zone') if isinstance(v, dict) else v
                    if isinstance(z, str) and not _zone_ok(z, v):
                        flags.append(('unknown_zone', sent, f"zone={z!r}"))
                    # a zone node is a leaf ({prep, zone}); descending into it would
                    # report the same site a second time (one flag per zone site).
                    continue
                elif k == 'quantifier':
                    if not _quant_ok(v):
                        flags.append(('bad_quantifier', sent, f"q={v!r}"))
                    continue
                elif k == 'amount' and isinstance(v, str):
                    if not _amount_ok(v.strip()):
                        flags.append(('bad_amount', sent, f"amount={v!r}"))
                    continue
                elif k in ('card_type', 'card') and isinstance(v, dict):
                    if k == 'card_type':
                        val = v.get('value')
                        if isinstance(val, str) and val.lower() in ABILITY_WORDS:
                            # "its activated abilities" loses the noun, leaving
                            # kind=type value='activated': no card type was captured.
                            flags.append(('empty_target', sent, f"card_type={val!r}"))
                    if not any(x in v for x in ('kind', 'value', 'type', 'card_type', 'this_that', 'ref', 'quantifier')):
                        # empty card placeholder on an intransitive action: the real
                        # target is the sentence-level subject, nothing was lost.
                        if not (k == 'card' and verb in OBJECTLESS_VERBS):
                            flags.append(('empty_target', sent, f"{k}={{}}"))
                walk(v, o)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(out)


def flagged(my_out):
    """{sentence: sorted list of flag-type strings} for structurally-suspect (parsed-wrong) sentences."""
    res = {}
    for s, o in my_out.items():
        fl = []
        check(o, s, fl)
        if fl:
            res[s] = sorted({f[0] for f in fl})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data', nargs='?', default='classic.json')
    ap.add_argument('--min', type=int, default=1)
    args = ap.parse_args()

    my_out = load_my_outputs()
    if not my_out:
        print("No output cache. Run content_check.py once first."); sys.exit(1)

    flags = []
    for s, o in my_out.items():
        check(o, s, flags)

    print(f"audited {len(my_out)} interpreted sentences -> {len(flags)} flags")
    by_type = Counter(f[0] for f in flags)
    print("\n== flags by type ==")
    for t, c in by_type.most_common():
        print(f"  {c:5d}  {t}")

    # headline: recurring raw (undeconposed) actions -> the grammar gaps to fix
    raw = Counter(f[2] for f in flags if f[0] == 'raw_action' and f[2])
    if raw:
        print(f"\n== {sum(raw.values())} raw (undeconposed) actions; "
              f"{len(raw)} distinct shapes (top 20 by frequency) ==")
        for text, c in raw.most_common(20):
            print(f"  {c:4d}x  {text[:90]}")

    # other anomalies, deduped by (type, detail)
    others = [(f[0], f[2], f[1]) for f in flags if f[0] != 'raw_action']
    oc = Counter((a, b) for a, b, _ in others)
    if oc:
        print("\n== other anomalies (type, detail) -> count, example sentence ==")
        ex = {}
        for a, b, s in others:
            ex.setdefault((a, b), s)
        for (a, b), c in oc.most_common(20):
            print(f"  {c:4d}  [{a}] {b}   e.g. {ex[(a,b)][:70]}")

    with open('invariant_flags.tsv', 'w') as fh:
        for t, s, d in flags:
            if t == 'raw_action':
                fh.write(f"raw_action\t{d}\t{s}\n")
            else:
                fh.write(f"{t}\t{d}\t{s}\n")
    print(f"\n[dumped {len(flags)} flags to invariant_flags.tsv]")
    hard = [f for f in flags if f[0] in HARD]
    if hard:
        print(f"\nHARD FAIL: {len(hard)} invariant violations "
              f"({sorted({f[0] for f in hard})})")
        sys.exit(1)


if __name__ == '__main__':
    main()
