#!/usr/bin/env python3
"""Preprocess oracle text:
- replace card names (full + short) with ~
- split into ability lines
- strip parenthetical reminders (kept aside)
- segment each line into sentence items with light typing (modal/bullet detection)
"""
import re
from mtd import name_set

def strip_reminders(text):
    """Remove all parenthetical (reminder) groups, handling nested parens."""
    out = []
    depth = 0
    for ch in text:
        if ch == '(':
            depth += 1
            continue
        if ch == ')':
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out.append(ch)
    return re.sub(r'[ \t]*\n[ \t]*', '\n', ''.join(out)).strip()

def normalize_names(text, names=None):
    names = names or name_set()
    # replace longest names first to avoid partial clobbering
    for n in sorted(names, key=len, reverse=True):
        if n:
            text = re.sub(re.escape(n), '~', text)
    return text

def split_sentences(line):
    """Split a line into sentences on sentence-ending punctuation (`.`, `)`,
    straight/closing quote) followed by whitespace and an uppercase letter or
    `(`. A `.` inside a double-quoted region (a granted ability) is NOT a
    boundary, so `gains "...library. You may play..."` stays one sentence."""
    parts = []
    start = 0
    quote_count = 0  # number of straight double-quotes seen so far
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == '"':
            quote_count += 1
            i += 1
            continue
        if ch in '.)"\u201d' and i + 1 < n:
            j = i + 1
            while j < n and line[j].isspace():
                j += 1
            if j < n and (line[j].isupper() or line[j] == '(' or line[j] == '~'):
                in_quote = (quote_count % 2 == 1)
                if ch == '"' or ch == '\u201d':
                    in_quote = False  # this is the closing quote
                if not in_quote:
                    parts.append(line[start:i + 1].strip())
                    start = j
                    i = j
                    continue
        i += 1
    parts.append(line[start:].strip())
    return [p for p in parts if p]

def segment(text, names=None):
    """Return a list of sentence dicts: {text, modal, bullet}.
    Modal markers ('Choose one —') are kept as their own items (modal=True)."""
    text = normalize_names(text, names)
    text = strip_reminders(text)
    items = []
    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if not line:
            continue
        for s in split_sentences(line):
            s = s.strip()
            if not s:
                continue
            bullet = s.startswith('•')
            s_body = s[1:].strip() if bullet else s
            # strip trailing sentence punctuation (period / em-dash) — not structure
            s_body = s_body.rstrip('.—').strip()
            if not s_body:
                continue
            modal = bool(re.match(r'^(Choose one|Choose [a-z]+)$', s_body))
            items.append({'text': s_body, 'modal': modal, 'bullet': bullet})
    return items
