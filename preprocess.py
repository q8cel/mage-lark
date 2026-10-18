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

_NAME_RE_CACHE = {}

def _name_re(names):
    """Compile a single alternation regex for the name set (cached by set id).
    Longest names first so they win in leftmost-alternation, avoiding partial
    clobbering. One combined sub is far faster than one sub per name.

    Each alternative is fenced with letter/digit lookarounds: card names that are
    also word prefixes must not fire inside ordinary words. Without this, a card
    named `Sear` turns `Search your library` into `~ch your library`, `Opt` turns
    `Options` into `~ions`, and so on (45 such names exist in the Standard set,
    affecting 91 dev card texts)."""
    key = frozenset(names)
    pat = _NAME_RE_CACHE.get(key)
    if pat is None:
        alts = sorted((n for n in names if n), key=len, reverse=True)
        pat = (re.compile(r'(?<![A-Za-z0-9])(?:' +
                          '|'.join(re.escape(n) for n in alts) +
                          r')(?![A-Za-z0-9])')
               if alts else None)
        _NAME_RE_CACHE[key] = pat
    return pat

def normalize_names(text, names=None):
    names = names or name_set()
    pat = _name_re(names)
    if pat is not None:
        text = pat.sub('~', text)
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
            # strip saga-chapter prefix ("III — ") and leveler prefix ("12+ | ")
            # — the body is an ordinary ability; the marker is dropped for now
            s_body = re.sub(r'^(?:I{1,3}|IV|V|VI{0,3}|IX|X)\s*\u2014\s+', '', s_body)
            s_body = re.sub(r'^\d+\s*\+\s*\|\s*', '', s_body)
            s_body = s_body.strip()
            if not s_body:
                continue
            modal = bool(re.match(r'^(Choose one|Choose [a-z]+)$', s_body))
            items.append({'text': s_body, 'modal': modal, 'bullet': bullet})
    return items
