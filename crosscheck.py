#!/usr/bin/env python3
"""LLM cross-check: find which real cards are parsed WRONG.

For each already-parsed sentence, independently ask the SAME model (fresh
context, via the local router) to decode the sentence into a fixed schema
(same verb vocabulary as ours, so outputs are comparable). Compare the two
structures field-by-field. Disagreements = candidate silent-parse bugs,
emitted as an actionable (sentence, field, mine, llm) list.

It reuses the interpreted-output cache built by content_check.py (no re-parse),
and caches every LLM response so re-runs / scaling are incremental.

Usage:
  python crosscheck.py                 # stratified sample of classic parsed sents
  python crosscheck.py --n 60          # limit sample size
  python crosscheck.py --all           # every parsed sentence (slow; run in bg)
  LLM_ENDPOINT=http://host:port/chat/completions LLM_MODEL=Name python crosscheck.py
"""
import sys, os, json, time, hashlib, threading, argparse
from concurrent.futures import ThreadPoolExecutor
import urllib.request
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from setdata import load
from preprocess import segment
import invariant_check

ENDPOINT = os.environ.get('LLM_ENDPOINT', 'http://127.0.0.1:8080/chat/completions')
MODEL    = os.environ.get('LLM_MODEL', 'Qwen3.8-27B-UD-Q6_K')

VERBS = ("static_keyword create_token deal_damage draw gain_life lose_life "
         "gain_poison put_counter remove_counter tap untap sacrifice search return "
         "exile attach enchant cast play counter put reveal scry shuffle look fight "
         "gain_control distribute copy become stat_change stat_define enters destroy "
         "discard mill prevent_damage double choose change_target attack extra_turns "
         "no_max_hand_size pay end_turn other")
ZONES = ("battlefield hand library graveyard exile stack")

SYSTEM = ("You are an expert on Magic: The Gathering rules text. Read the oracle "
          "sentence and identify the KEY ACTION it performs. Reply with ONLY a "
          "JSON object, no prose, no markdown.")

def prompt_for(sent):
    return (f"Sentence: {sent}\n"
            "Return a JSON object with exactly these keys:\n"
            f'  "verb": one of [{VERBS}]\n'
            '  "amount": the main numeric amount (cards, damage, life, counters) or null\n'
            '  "keywords": [ MTG keywords present, e.g. "flying", "trample", "first strike" ]\n'
            f'  "zones": [ any of [{ZONES}] that the sentence acts in or references ]\n'
            'If it is a static description or cost with no clear action, use verb "static_keyword" or "other".')

def extract_json(text):
    start = text.find('{')
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except Exception:
                    return None
    return None

# ---- persistent LLM response cache ----
def _llm_cache_path():
    return os.path.join(BASE, '.cache', f'llm_{MODEL.replace("/", "_")}.json')
_llm = {}
_llm_lock = threading.Lock()
def _load_llm_cache():
    global _llm
    p = _llm_cache_path()
    if os.path.exists(p):
        try:
            _llm = json.load(open(p))
        except Exception:
            _llm = {}
def _save_llm_cache():
    with _llm_lock:
        json.dump(_llm, open(_llm_cache_path(), 'w'))

def llm_decode(sent):
    key = hashlib.sha1(sent.encode()).hexdigest()[:16]
    with _llm_lock:
        if key in _llm:
            return _llm[key]
    body = json.dumps({"model": MODEL, "temperature": 0, "top_p": 1, "max_tokens": 900,
                       "messages": [{"role": "system", "content": SYSTEM},
                                    {"role": "user", "content": prompt_for(sent)}]}).encode()
    j = None
    for _ in range(3):
        try:
            req = urllib.request.Request(ENDPOINT, data=body,
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=200) as r:
                d = json.load(r)
            j = extract_json(d['choices'][0]['message'].get('content', ''))
            break
        except Exception:
            time.sleep(2)
    with _llm_lock:
        if j is not None:      # don't cache failures -> they get retried next run
            _llm[key] = j
    return j

# ---- extract comparable fields from OUR output ----
def my_fields(out):
    verbs, amounts, kws, zones = set(), set(), set(), set()
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == 'verb' and isinstance(v, str):
                    verbs.add(v)
                elif k == 'amount' and isinstance(v, int):
                    amounts.add(v)
                elif k == 'zone' and isinstance(v, str):
                    zones.add(v.lower())
                elif k in ('keyword',) and isinstance(v, str):
                    kws.add(v.lower())
                elif k in ('keywords', 'kw') and isinstance(v, list):
                    for x in v:
                        if isinstance(x, str):
                            kws.add(x.lower())
                        elif isinstance(x, list):
                            for y in x:
                                if isinstance(y, str):
                                    kws.add(y.lower())
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(out)
    return verbs, amounts, kws, zones

# verb confusions that are NOT real errors
ALIASES = {
    'stat_change': {'become', 'stat_define', 'other'},
    'become': {'stat_change'},
    'put': {'return', 'search', 'attach', 'other'},
    'return': {'put'},
    'search': {'look', 'reveal', 'put'},
    'look': {'search', 'reveal'},
    'reveal': {'search', 'look'},
    'enters': {'other', 'create_token'},
    'counter': {'other'},
    'stat_define': {'stat_change'},
    'other': {'static_keyword'},
    'static_keyword': {'other'},
}
def verb_ok(mine, llm):
    for m in mine:
        if llm == m or llm in ALIASES.get(m, set()) or m in ALIASES.get(llm, set()):
            return True
    return False

def compare(sent, out, llm, types_lower):
    issues = []
    if llm is None:
        return [('llm_failed', '-', '-')]
    verbs, amounts, kws, zones = my_fields(out)
    # verb: advisory (finer-grained taxonomy; the LLM is often the imprecise one)
    lverb = (llm.get('verb') or '').lower()
    if lverb and not verb_ok(verbs, lverb):
        issues.append(('verb~', f"mine={sorted(verbs) or '-'}", f"llm={lverb}"))
    lamt = llm.get('amount')
    if isinstance(lamt, int) and amounts and lamt not in amounts:
        issues.append(('amount', f"mine={sorted(amounts)}", f"llm={lamt}"))
    # keyword: drop LLM "keywords" that are actually card TYPE words (e.g. "avatar")
    lk = {str(x).lower() for x in (llm.get('keywords') or [])
          if isinstance(x, str) and str(x).lower() not in types_lower}
    mk = lk - kws
    if mk:
        issues.append(('keyword', f"llm={sorted(mk)}", f"mine={sorted(kws) or '-'}"))
    # zone: drop "battlefield" (the default zone; its absence is correct)
    lz = {str(x).lower() for x in (llm.get('zones') or [])
          if isinstance(x, str) and str(x).lower() != 'battlefield'}
    mz = lz - zones
    if mz:
        issues.append(('zone~', f"llm={sorted(mz)}", f"mine={sorted(zones) or '-'}"))
    return issues

# ---- locate our output cache (built by content_check.py) ----
def _fhash(p):
    return hashlib.sha1(open(p, 'rb').read()).hexdigest()[:12]
def load_my_outputs():
    """Return {sentence: my_output_dict} from the content_check output cache."""
    candidates = [os.path.join(BASE, '.cache', f)
                  for f in os.listdir(os.path.join(BASE, '.cache'))
                  if f.startswith('out_')]
    if not candidates:
        return {}
    blob = json.load(open(sorted(candidates, key=os.path.getmtime)[-1]))
    out = {}
    for s, b in blob.items():
        if b and not b.startswith('\x00'):
            try:
                out[s] = json.loads(b)
            except Exception:
                pass
    return out

def stratify(unique, per_type=30):
    """Up to per_type sentences per top-level 'type', for category coverage."""
    by_type = {}
    for s in unique:
        by_type.setdefault(None, []).append(s)
    # re-bucket by the type found in my output is done in main; here simple split
    return list(unique)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('data', nargs='?', default='classic.json')
    ap.add_argument('--n', type=int, default=120, help='max sentences to cross-check')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--workers', type=int, default=3)
    args = ap.parse_args()

    my_out = load_my_outputs()
    if not my_out:
        print("No output cache found. Run content_check.py once first to build it."); sys.exit(1)
    _, types, _, _ = load(args.data)
    types_lower = {t.lower() for t in types}
    _load_llm_cache()
    print(f"my outputs: {len(my_out)}   llm cache: {len(_llm)}   endpoint={ENDPOINT} model={MODEL}")

    sents = list(my_out.keys())
    def bucket(s):
        ls = s.lower()
        for tag, pat in [('triggered', ('when ', 'whenever', 'at the beginning', 'at the start', 'at end of')),
                         ('activated', (': ', 'tap:')),
                         ('loyalty', ('[+1]', '[+2]', '[−1]', '[-1]'))]:
            if any(p in ls for p in pat):
                return tag
        return 'static'
    # ALWAYS include the invariant-flagged (parsed-wrong) sentences, then fill the
    # budget with bucket-stratified randoms to discover NEW mis-parses the free
    # invariant checker cannot see (wrong verb/amount that still looks well-formed).
    fl = invariant_check.flagged(my_out)
    flagged_set = set(fl)
    rest = [s for s in sents if s not in flagged_set]
    by_b = {}
    for s in rest:
        by_b.setdefault(bucket(s), []).append(s)
    if args.all:
        sample = sents
    else:
        budget = max(0, args.n - len(flagged_set))
        per = max(1, budget // max(1, len(by_b)))
        fill = []
        for b in ('triggered', 'activated', 'loyalty', 'static'):
            fill += by_b.get(b, [])[:per]
        sample = sorted(flagged_set) + fill[:budget]
    print(f"sample: {len(sample)}  (invariant-flagged: {len(flagged_set)} always included; "
          f"+ {len(sample)-len(flagged_set)} random-sampled)")

    todo = [s for s in sample if hashlib.sha1(s.encode()).hexdigest()[:16] not in _llm]
    print(f"to-call LLM: {len(todo)}   (cached: {len(sample)-len(todo)})")

    done = [0]
    def work(s):
        j = llm_decode(s)
        done[0] += 1
        if done[0] % 10 == 0:
            _save_llm_cache()
            print(f"  ...{done[0]}/{len(todo)}", flush=True)
        return j

    if todo:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(work, todo))
        _save_llm_cache()

    # compare
    rows = []
    n_flag = 0
    for s in sample:
        llm = _llm.get(hashlib.sha1(s.encode()).hexdigest()[:16])
        issues = compare(s, my_out[s], llm, types_lower)
        if issues:
            n_flag += 1
            for field, mine, llm_v in issues:
                rows.append((s, field, mine, llm_v))
    hard = [r for r in rows if not r[1].endswith('~')]
    adv  = [r for r in rows if r[1].endswith('~')]
    print(f"\n== {n_flag}/{len(sample)} sampled sentences DISAGREE with the independent decode ==")
    print(f"   (hard flags: {len(hard)} rows; advisory verb: {len(adv)} rows)")
    from collections import Counter
    fc = Counter(r[1] for r in hard)
    for f, c in fc.most_common():
        print(f"  {c:4d}  {f}")

    print(f"\n== invariant-flagged sentences ({len(flagged_set)}) -- LLM decode = suggested fix ==")
    for s in sorted(flagged_set, key=lambda x: (fl[x], x)):
        llm = _llm.get(hashlib.sha1(s.encode()).hexdigest()[:16])
        if llm:
            hint = f"llm_verb={llm.get('verb','?')}"
            if isinstance(llm.get('amount'), int):
                hint += f" amount={llm.get('amount')}"
        else:
            hint = "LLM_FAILED (will retry)"
        print(f"  [{','.join(fl[s])}] {hint}")
        print(f"      {s}")

    with open('crosscheck_missing.tsv', 'w') as fh:
        for s, field, mine, llm_v in rows:
            fh.write(f"{field}\t{mine}\t{llm_v}\t{s}\n")
    print(f"\n[dumped {len(rows)} disagreement rows to crosscheck_missing.tsv]")
    print("\n== examples (up to 6) ==")
    for s, field, mine, llm_v in rows[:6]:
        print(f"\n  [{field}] {mine} | {llm_v}\n    {s}")

if __name__ == '__main__':
    main()
