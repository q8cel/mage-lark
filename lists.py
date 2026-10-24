"""Deterministic capture and classification of comma lists in oracle text.

A list keeps its surface connector separate from its semantic logic:

    Birds and Frogs        connector=and  kind=set       logic=union
    noncreature, nonland   connector=None kind=property  logic=intersection

Lists are replaced with self-contained @@L<hex-json>@@ tokens so a comma
inside a list cannot be mistaken for a condition/effect boundary.
"""
import json
import re

TYPES = {
    'artifact','artifacts','battle','battles','card','cards','creature','creatures',
    'enchantment','enchantments','instant','instants','kindred','land','lands',
    'permanent','permanents','planeswalker','planeswalkers','sorcery','sorceries',
    'spell','spells','token','tokens','aura','auras','equipment','equipments',
    'vehicle','vehicles','spacecraft','planets','planet','grave','graveyard',
    'graveyards','hand','hands','library','libraries','exile','battlefield','stack',
}
PROPERTY = {
    'noncreature','nonland','nontoken','nonartifact','nonenchantment','nonplaneswalker',
    'nonangel','nondemon','nonhuman','nonlegendary','nonbasic','nonsnow','nonpermanent',
    'white','blue','black','red','green','colorless','multicolored','monocolored',
    'legendary','basic','snow','tapped','untapped','attacking','blocking','blocked',
    'modified','kicked','escaped','suspected','renowned','monstrous','equipped','enchanted',
    'flying','first strike','double strike','deathtouch','defender','haste','hexproof',
    'indestructible','lifelink','menace','reach','trample','vigilance','ward','flash',
    'fear','intimidate','protection','shroud','prowess','exalted','convoke','delve',
}
KEYWORDS = {'flying','first strike','double strike','deathtouch','defender','haste','hexproof',
    'indestructible','lifelink','menace','reach','trample','vigilance','ward','flash',
    'fear','intimidate','protection','shroud','prowess','exalted','convoke','delve'}
QUANT = {'one','two','three','four','five','six','seven','eight','nine','ten','eleven',
         'twelve','first','second','third','fourth','fifth','sixth','seventh','eighth',
         'ninth','tenth'}
ITEMS_START = re.compile(
    r'\b(?:up to \w+|one or more|\w+ or more|a|an|another|other|target|each|'
    r'the first|the second|the third|the fourth|the fifth)\b', re.I)
CONN = re.compile(r'^\s*(and/or|and|or)\s+', re.I)
PRED = re.compile(
    r'\b(?:get|gets|gain|gains|have|has|deal|deals|would|attack|attacks|enter|enters|'
    r'die|dies|is|are|was|were|become|becomes|lose|loses|can\'t|cannot|doesn\'t|don\'t|'
    r'put|draw|create|destroy|exile|return|sacrifice|discard|mill|scry|surveil|choose|'
    r'target|add|tap|untap|prevent|copy|reveal|search|shuffle|attach|fight|counter|'
    r'regenerate|skip|win|flip|roll|vote|separate|exchange|transform|convert)\b', re.I)
COLORS = {'white','blue','black','red','green','colorless','multicolored'}
ALLOWED_PREFIX_END = re.compile(
    r'(?i)(?:^|[\s,;:])(?:if|when|whenever|unless|until|as long as|for each|is|are|was|were|it\'s|that\'s|control|controls|cast|casts|target|another|other|each|a|an|the|more|has|have|with|without|becomes?|become|enters?|attacks?|blocks?|deals?|destroy|exile|return|counter|sacrifice|discard|search|reveal|put|create|choose|enchant|equip|attach|tap|untap|remove|mill)$')

SUFFIX = re.compile(
    r'\s+(you control|an opponent controls|you don\'t control|'
    r'other than [^,;:.!?]+? you\'ve cast this turn)\s*$', re.I)

def _strip_det(s):
    s = s.strip()
    m = re.match(r'(?i)^(?:up to \w+|one or more|\w+ or more|a|an|another|other|target|each|the first|the second|the third)\s+(.*)$', s)
    if m:
        return m.group(1).strip(), s[:m.start(1)].strip()
    return s, ''

def _core(s):
    s = s.strip()
    m = re.match(r'(?i)^(?:a|an|the)\s+(.*)$', s)
    if m:
        s = m.group(1).strip()
    return s

def _is_type_word(w):
    wl = w.lower().strip('.,;:')
    if wl.endswith('s') and wl[:-1] in TYPES:
        return True
    return wl in TYPES

def _is_plural_type(s):
    s = s.strip()
    if not s:
        return False
    words = s.split()
    w = words[-1].lower()
    # capitalized plural subtype (Birds, Otters, Mice, Wolves)
    if s[0].isupper() and (w.endswith('s') or w in {'mice','wolves','elves','dwarves','people'}):
        return True
    return w in TYPES and w.endswith('s')

def _is_cap_type(s):
    s=s.strip()
    if not s: return False
    w=s.split()[-1]
    return w[:1].isupper() and w.lower() not in KEYWORDS and not w.lower().startswith('non')

def _is_prop(s):
    s = s.strip().lower()
    exact = {
        'noncreature','nonland','nontoken','nonartifact','nonenchantment','nonplaneswalker',
        'nonangel','nondemon','nonhuman','nonlegendary','nonbasic','nonsnow','nonpermanent',
        'white','blue','black','red','green','colorless','multicolored','monocolored',
        'legendary','basic','snow','tapped','untapped','attacking','blocking','blocked',
        'modified','kicked','escaped','suspected','renowned','monstrous','equipped','enchanted',
    }
    if s in exact:
        return True
    if re.fullmatch(r'(?i)non-?[a-z]+', s):
        return True
    if s in KEYWORDS:
        return True
    if re.fullmatch(r'(?:first|double) strike|ward(?: \{.*\})?', s):
        return True
    return False

def _is_quantity(s):
    s = s.strip().lower()
    return s in QUANT or bool(re.fullmatch(r'\d+', s))

def _head(s):
    s = s.strip().lower()
    last = s.split()[-1] if s.split() else ''
    last = last.strip('.,;:')
    if last in TYPES or (last.endswith('s') and last[:-1] in TYPES):
        return last
    # subtype head: Bird, Frog, Otter, Rat; use capitalization
    return None

BAD_ITEM = re.compile(r"\b(?:then|where|and then|or less|or more|or fewer|or greater|from|into|onto|with|without|of|in|on|at|by|your|you|their|its|our|my|can't|cannot|can|discard|discards|activate|activates|cast|casts|gain|gains|put|puts|create|creates|draw|draws|sacrifice|sacrifices|exile|exiles|return|returns|destroy|destroys|search|searches|shuffle|reveal|chooses|choose|attacks|attack|dies|die|owner|other than)\b", re.I)
CLAUSE_START = re.compile(r"^(?:when|whenever|if|at|as|during|until|for each|each|the next|put|create|draw|sacrifice|exile|return|destroy|discard|search|shuffle|reveal|choose|your|their|this spell|that spell|tap|untap|pay|discard|activate)\b", re.I)
def _clean_type_np(s):
    s=s.strip()
    s=re.sub(r'(?i)^(?:up to \w+|one or more|\w+ or more)\s+', '', s).strip()
    if not s or CLAUSE_START.search(s) or BAD_ITEM.search(s):
        return False
    if re.search(r'\b(?:and|or|and/or)\b', s):
        return False
    if len(s.split()) > 5:
        return False
    # allow 'target'/'this'/'that' prefix but strip before head test
    c=s
    c=re.sub(r'(?i)^(?:target|another|other|each|this|that|a|an|the)\s+', '', c).strip()
    if not c or _is_prop(c):
        return False
    words=c.split()
    if not words: return False
    last=words[-1].lower().strip('.,;:')
    if last in TYPES or (last.endswith('s') and last[:-1] in TYPES):
        return True
    if words[-1][:1].isupper() and words[-1].lower() not in KEYWORDS:
        return True
    return False

def _has_modifier_head(s):
    s = s.strip()
    base = re.split(r'(?i)\s+with\s+', s)[0].strip()
    if BAD_ITEM.search(base):
        return False
    if re.match(r'(?i)^(?:this|that|these|those|you|your|each|all|any|some|no)\b', s):
        return False
    if not s or re.match(r'(?i)^(?:a|an|the|target|another|other|each|up to|one or more|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b', s):
        return False
    words = base.split()
    if len(words) < 2:
        return False
    if not (_is_prop(words[0]) or words[0].lower() in {'first','second','third','fourth','fifth'}):
        return False
    last = words[-1].lower().strip('.,;:')
    if last in TYPES or (last.endswith('s') and last[:-1] in TYPES):
        return True
    if words[-1][:1].isupper():
        return True
    return False

def _split(s):
    # comma split with simple quote/paren depth
    out=[]; start=0; depth=0; quote=False; i=0
    while i < len(s):
        c=s[i]
        if c=='"': quote = not quote
        elif not quote and c in '([{': depth += 1
        elif not quote and c in ')]}': depth = max(0, depth-1)
        elif c==',' and not quote and depth==0:
            out.append((s[start:i], start, i)); start=i+1
        i+=1
    out.append((s[start:], start, len(s)))
    return out

def _set_category(s):
    c=_clean_type_np(s)
    if not c:
        return None
    c=re.sub(r'(?i)^(?:target|another|other|each|this|that|a|an|the|up to \w+|one or more|\w+ or more)\s+', '', s.strip()).strip()
    words=c.split()
    if not words: return None
    w=words[-1].lower().strip('.,;:')
    if w in TYPES or (w.endswith('s') and w[:-1] in TYPES):
        return 'generic'
    if w in {'graveyard','hand','library','exile'}:
        return 'zone'
    return 'subtype'


def _classify(items, conn, items_surface=None):
    cores=[_core(x) for x in items]
    c0, prefix = _strip_det(cores[0])
    cores[0]=c0
    all_set = all(_clean_type_np(x) for x in items)
    all_prop = all(_is_prop(c) for c in cores)
    all_quant = all(_is_quantity(c) for c in cores)
    mod_head = (_has_modifier_head(cores[-1]) and
                all(_is_prop(c) or _has_modifier_head(c) for c in cores[:-1]))
    logic = 'intersection' if conn in (None,'and') else 'union'
    if all_quant:
        return 'quantity','union',prefix,None
    if all_set and not mod_head:
        # implicit full-NP lists are usually apposition, not enumeration
        if conn is None:
            return None
        cats={_set_category(x) for x in items}
        if len(cats) != 1:
            return None
        return 'set','union',prefix,None
    if mod_head:
        return 'property', logic, prefix, _head(cores[-1])
    if all_prop:
        return 'property', logic, prefix, None
    return None

def _two_item(text):
    out=[]
    for chunk, cstart, cend in _split(text):
        if ',' in chunk:
            continue
        for m in re.finditer(r'(?P<first>[^,;:.!?]+?)\s+(?P<conn>and/or|and|or)\s+(?P<last>[^,;:.!?]+)', chunk):
            raw_first=m.group('first').strip()
            ms=list(ITEMS_START.finditer(raw_first)); trim=ms[0].start() if ms else 0
            if re.match(r'(?i)^enchant\s+', raw_first[trim:]):
                trim += len('Enchant ')
            first=raw_first[trim:].strip()
            conn=m.group('conn').lower(); body=m.group('last').strip()
            pm=PRED.search(body); cut=pm.start() if pm else len(body)
            last=body[:cut].strip()
            if not first or not last: continue
            if re.match(r'(?i)^(?:more|less|fewer|greater|equal|than)\b', last): continue
            if re.search(r'(?i)\b(?:less|more|fewer|greater)\s+(?:than|or)\b', first): continue
            if re.search(r'(?i)\b(?:and|or)\s*$', first): continue
            suffix=''; sm=SUFFIX.search(last)
            if sm: suffix=sm.group(1); last=last[:sm.start()].strip()
            if re.search(r'(?i)\b(?:or|and)\s+(?:more|less|fewer|greater)\b', m.group(0)): continue
            cls=_classify([first,last],conn)
            if not cls: continue
            kind,logic,prefix,head=cls
            if kind=='quantity': continue
            if kind=='property' and all((_core(x).lower() in KEYWORDS or re.fullmatch(r'ward \{.*\}', _core(x).lower())) for x in [first,last]): continue
            if kind=='property' and re.search(r'(?i)\b(?:from|to|into|onto)\b', last): continue
            start=cstart+trim
            body_start = cstart + m.start('last')
            end = body_start + len(body[:cut].rstrip())
            if start > 0 and text[start-1].isalpha(): continue
            if end < len(text) and text[end].isalpha(): continue
            # m.end('last') points after body incl cut; subtract ignored tail
            obj={'kind':kind,'logic':logic,'connector':conn,'items':[first,last],'text':text[start:end].strip()}
            if suffix: obj['shared_suffix']=suffix
            if prefix: obj['shared_prefix']=prefix
            if head: obj['head']=head
            out.append((start,end,obj))
    return out

def capture(text):
    """Return `(start, end, list_object)` for high-confidence lists in text."""
    chunks = _split(text)
    cands=_two_item(text)
    for i in range(len(chunks)-1):
        raw_first = chunks[i][0]
        # trim condition prefix in first chunk
        ms=list(ITEMS_START.finditer(raw_first))
        trim = 0
        if ms:
            # The earliest marker keeps a shared quantifier such as
            # "up to one target ..." inside the list NP.
            trim = ms[0].start()
        # "Enchant creature, land, or planeswalker": Enchant is the ability
        # verb, not part of the list NP.
        if re.match(r'(?i)^enchant\s+', raw_first[trim:]):
            trim += len('Enchant ')
        first = raw_first[trim:].strip()
        if not first:
            continue
        for j in range(i+1, min(len(chunks), i+6)):
            last_raw = chunks[j][0]
            conn_m = CONN.match(last_raw)
            conn = conn_m.group(1).lower() if conn_m else None
            body = last_raw[conn_m.end():] if conn_m else last_raw
            # cut predicate from last item
            pm = PRED.search(body)
            cut = pm.start() if pm else len(body)
            last = body[:cut].strip()
            if not last or re.match(r'(?i)^(?:more|less|fewer|greater)\b', last):
                continue
            # shared suffix
            suffix=''
            pp_cut=0
            sm = SUFFIX.search(last)
            if sm:
                suffix=sm.group(1); last=last[:sm.start()].strip()
            # A list NP can be followed by a source/location PP: "a
            # noncreature, nonland card from it".  Keep the PP outside the
            # list span.
            pp = re.search(r'(?i)\s+(?:from|in|into|on|of)\s+', last)
            if pp and _head(last[:pp.start()]):
                before_pp = last
                last = last[:pp.start()].strip()
                pp_cut = len(before_pp) - len(last)
            # items text
            items=[first] + [chunks[k][0].strip() for k in range(i+1,j)] + [last]
            if any(not x for x in items):
                continue
            cls=_classify(items,conn)
            if not cls:
                continue
            kind,logic,prefix,head=cls
            # reject all-keyword property lists with no type/head
            if kind=='quantity':
                continue
            if kind=='property' and all((_core(x).lower() in KEYWORDS or re.fullmatch(r'ward \{.*\}', _core(x).lower())) for x in items):
                continue
            if kind=='property' and re.search(r'(?i)\b(?:from|to|into|onto)\b', last):
                continue
            # reject obvious sequences
            if re.match(r'(?i)^(?:then|where|and then|but|so|which)\b', last):
                continue
            start = chunks[i][1] + trim
            body_start = chunks[j][1] + (conn_m.end() if conn_m else 0)
            end = body_start + len(body[:cut].rstrip()) - pp_cut
            if start > 0 and text[start-1].isalpha():
                continue
            if end < len(text) and text[end].isalpha():
                continue
            surface=text[start:end]
            obj={'kind':kind,'logic':logic,'connector':conn or 'implicit',
                 'items':[x.strip() for x in items], 'text':surface.strip()}
            if suffix: obj['shared_suffix']=suffix
            # extract shared prefix for first item
            _, pref = _strip_det(raw_first[trim:].strip())
            if pref: obj['shared_prefix']=pref
            if head: obj['head']=head
            cands.append((start,end,obj))
    # choose non-overlapping, prefer explicit, longer
    cands.sort(key=lambda x:(bool(CONN.match(text[x[0]:x[1]])) or 'connector' in x[2] and x[2]['connector']!='implicit', x[1]-x[0]), reverse=True)
    chosen=[]
    for st,en,obj in cands:
        if any(not (en<=a or st>=b) for a,b,_ in chosen):
            continue
        chosen.append((st,en,obj))
    return sorted(chosen)

def _context_ok(text, start):
    prefix = text[:start].strip()
    if not prefix:
        return True
    # Do not treat mana/activation costs, chapter prefixes, or arbitrary
    # clause punctuation as list-introducing context.
    if prefix[-1] in '};:+—–-]':
        return False
    if prefix.endswith(','):
        # A list may begin right after a trigger/condition comma when it starts
        # with an explicit quantifier/determiner ("..., up to one target ...").
        if (re.search(r'(?i)\b(?:when|whenever|if|as long as|for each|until)\b', prefix)
                and re.match(r'(?i)^(?:up to|one or more|a|an|target|another|other|each)\b', text[start:start+24])):
            return True
    # These slots expect a non-list object in the current grammar; leave the
    # source text intact so the existing parser can handle it.
    if re.search(r'(?i)(?:\bput(?:\s+a)?|\breveal)$', prefix):
        return False
    return bool(ALLOWED_PREFIX_END.search(prefix))


def protect(text):
    """Replace captured list spans with opaque LISTTOK terminals."""
    cs=capture(text); out=[]; pos=0
    for st,en,obj in cs:
        if not _context_ok(text, st):
            continue
        if obj.get('kind') == 'property' and all(_core(x).lower() in COLORS for x in obj.get('items', [])):
            continue
        out.append(text[pos:st])
        raw=json.dumps(obj, separators=(',',':'), ensure_ascii=False).encode()
        out.append('@@L'+raw.hex()+'@@')
        pos=en
    out.append(text[pos:])
    return ''.join(out)

def decode(tok):
    """Decode a LISTTOK produced by :func:`protect`."""
    return json.loads(bytes.fromhex(tok[3:-2]).decode())

