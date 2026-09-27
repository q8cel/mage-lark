#!/usr/bin/env python3
"""Extract vocabularies (verbs, keywords, zones, statuses, card types) from oracle items."""
import re
from collections import Counter
from preprocess import segment
from mtd import all_oracle_text

def items():
    for name, text in all_oracle_text():
        for it in segment(text):
            yield it['text']

def main():
    all_items = list(items())
    # verbs: leading lowercase word after cost/trigger or at sentence start
    verbs = Counter()
    for s in all_items:
        m = re.match(r'^([a-z]+)', s)
        if m: verbs[m.group(1)] += 1
    print("=== leading lowercase words (candidate verbs) ===")
    for w,n in verbs.most_common(60):
        print(f"  {n:4d}  {w}")

    # capitalized words (keywords / types / names)
    caps = Counter()
    for s in all_items:
        for w in re.findall(r'\b[A-Z][a-z]+s?\b', s):
            caps[w] += 1
    print("\n=== capitalized words (keywords/types/names) top 80 ===")
    for w,n in caps.most_common(80):
        print(f"  {n:4d}  {w}")

    # zones
    zones = Counter()
    zwords = ['battlefield','graveyard','hand','library','exile','zone']
    for s in all_items:
        for z in zwords:
            zones[z] += s.lower().count(z)
    print("\n=== zone words ===")
    for w,n in zones.most_common(): print(f"  {n:4d}  {w}")

if __name__ == '__main__':
    main()
