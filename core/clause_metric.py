"""Closed predicate for string-valued clause fields.

Spec: swarm/reports/clause_metric_spec.md. Pure, dependency-free.
Returns one of VALUE / CLAUSE / STRUCTURED / EXPRESSION / EMPTY.
"""
import re

VALUE, CLAUSE, STRUCTURED, EXPRESSION, EMPTY = (
    'VALUE', 'CLAUSE', 'STRUCTURED', 'EXPRESSION', 'EMPTY')

CONDITION_FIELDS = {'condition', 'if', 'unless', 'trailing_if'}
MODIFIER_FIELDS = {'modifier', 'with_modifier'}

VALUE_COND_EXACT = {
    'you control', "you don't control", 'an opponent controls',
    'its controller', 'their controller',
}
VALUE_COND_RE = re.compile(
    r'^(?:during\b.*\b(?:turn|combat|phase|step)\b'
    r'|only as a sorcery'
    r'|only (?:once|during .*)'
    r'|mana value\b.*)$')
CLAUSE_START_RE = re.compile(
    r'^(?:if|unless|as long as|while|for each|when|whenever|until|where|instead|only if)\b')
IMPERATIVE_RE = re.compile(
    r'^(?:pay|discard|sacrifice|exile|choose|put|create|draw|mill|reveal|return|'
    r'counter|tap|untap|destroy|remove|attach|unattach|behold|waterbend|blight|'
    r'amass|scry|surveil|investigate|proliferate|venture)\b')
MANA_THEN_IMPERATIVE_RE = re.compile(
    r'^(?:\{[^}]+\}\s*)+(?:pay|discard|sacrifice|exile|choose|put|create|draw|'
    r'mill|reveal|return|counter|tap|untap|destroy|remove|attach|unattach|behold|'
    r'waterbend)\b')
VALUE_MOD_PREFIX_RE = re.compile(
    r'^(?:with\b|of\b|named\b|exiled\b|discarded\b|revealed\b|chosen\b|'
    r'other than\b|during\b|only\b|from\b|at the beginning\b|on\b|in\b|by\b|'
    r'equal to\b|half\b|the (?:number|greatest|total)\b|mana value\b|power\b|'
    r'toughness\b|\{)')
CLAUSE_MARK_RE = re.compile(
    r"\b(?:you've|you'd|it's|it isn't|they're|there are|there is|that player|"
    r"its controller|their controller|you do|you don't|they do|they don't|that was)\b")
FINITE_VERB_RE = re.compile(
    r'\b(?:is|are|was|were|has|have|had|do|does|did|can|could|would|should|may|'
    r'might|will|enters?|entered|leaves?|left|dies?|died|attacks?|attacked|blocks?|'
    r'controls?|controlled|pays?|paid|sacrifices?|sacrificed|discards?|discarded|'
    r'casts?|cast|draws?|drew|gains?|gained|loses?|lost|puts?|put|creates?|created|'
    r'exiles?|exiled|returns?|returned|becomes?|became|triggers?|triggered|'
    r'reveals?|revealed|chooses?|chose|beholds?|beheld|counts?|counted|'
    r'targets?|targeted|descended|searched|scried|surveilled)\b')
PURE_VALUE = re.compile(r'^(?:\{[^}]+\}|[0-9x]+)(?:\s*(?:\{[^}]+\}|[0-9x]+))*$')


def _norm(value):
    s = value.strip().lower()
    s = re.sub(r'\s+', ' ', s)
    return s.rstrip('.')


def classify_xdef(v):
    if isinstance(v, dict):
        return STRUCTURED
    if isinstance(v, list):
        if any(isinstance(x, dict) for x in v):
            return STRUCTURED
        s = ' '.join(str(x) for x in v)
        return VALUE if PURE_VALUE.fullmatch(s.strip()) else EXPRESSION
    if isinstance(v, str):
        return VALUE if PURE_VALUE.fullmatch(v.strip()) else EXPRESSION
    return VALUE


def classify_clause(field, value):
    if isinstance(value, dict):
        if field == 'xdef' and 'xdef' in value:
            return classify_xdef(value['xdef'])
        return STRUCTURED
    if isinstance(value, list):
        if field == 'xdef':
            if any(isinstance(x, dict) for x in value):
                return STRUCTURED
            s = ' '.join(str(x) for x in value)
            return VALUE if PURE_VALUE.fullmatch(s.strip()) else EXPRESSION
        if any(isinstance(x, dict) for x in value):
            return STRUCTURED
        value = ' '.join(str(x) for x in value)
    if not isinstance(value, str):
        return VALUE
    s = _norm(value)
    if not s:
        return EMPTY
    if field in CONDITION_FIELDS:
        if s.startswith('only if '):
            return CLAUSE
        if VALUE_COND_RE.fullmatch(s) or s in VALUE_COND_EXACT:
            return VALUE
        return CLAUSE
    if field in MODIFIER_FIELDS:
        if CLAUSE_START_RE.match(s) or IMPERATIVE_RE.match(s):
            return CLAUSE
        if MANA_THEN_IMPERATIVE_RE.match(s):
            return CLAUSE
        if s in VALUE_COND_EXACT:
            return VALUE
        if VALUE_MOD_PREFIX_RE.match(s):
            return VALUE
        if CLAUSE_MARK_RE.search(s) or FINITE_VERB_RE.search(s):
            return CLAUSE
        return VALUE
    if field == 'xdef':
        return classify_xdef(value)
    return VALUE
