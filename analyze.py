#!/usr/bin/env python3
"""Survey tool: extract unique oracle-text sentences from FDN.json to find patterns."""
import json, re, sys
from collections import Counter

def strip_reminders(text):
    """Remove parenthetical reminders, handling nested parens, across whole text."""
    out = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '(':
            depth += 1
            i += 1
            continue
        if ch == ')':
            depth = max(0, depth - 1)
            i += 1
            continue
        if depth == 0:
            out.append(ch)
        i += 1
    return re.sub(r'[ \t]*\n[ \t]*', '\n', ''.join(out)).strip()

def split_sentences(text):
    parts = re.split(r'(?<=[.)"”])\s+(?=[A-Z(])', text)
    return [p.strip() for p in parts if p.strip()]

def normalize_cardnames(text, name):
    if name:
        text = text.replace(name, '~')
    return text

def get_sentences(text, name):
    text = normalize_cardnames(text, name)
    text = strip_reminders(text)
    sents = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        for s in split_sentences(line):
            sents.append(s)
    return sents

def main():
    d = json.load(open('FDN.json'))
    cards = d['data']['cards']
    sents = []
    for c in cards:
        text = c.get('text') or ''
        name = c.get('name') or ''
        sents.extend(get_sentences(text, name))

    counter = Counter(sents)
    print(f"Total sentences: {len(sents)}")
    print(f"Unique sentences: {len(counter)}")
    print()
    for s, n in counter.most_common():
        print(f"[{n}] {s}")

if __name__ == '__main__':
    main()
