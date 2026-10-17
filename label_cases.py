#!/usr/bin/env python3
"""Build anaphor-resolution cases and label them with a teacher LLM.

For every anaphor occurrence in a card, we emit the sentence text, the anaphor
span, and the candidate-mention list, then ask a teacher LLM which candidate the
anaphor refers to. The teacher is used ONLY to produce a dataset; it is never
part of the runtime resolver.

Cases are built with pure lexical/regex logic (anaphora.find_anaphors,
mentions.candidate_mentions) -- no parse, no model, so this runs anywhere.

Output (default coref_dataset.json): a list of cards, each with its anaphors and
the teacher's chosen antecedent per anaphor.

Usage:
  python label_cases.py --dry-run "Nine-Lives Familiar"
  LLM_ENDPOINT=http://127.0.0.1:8080/v1/chat/completions LLM_MODEL=mistral \\
      python label_cases.py --limit 50 --workers 4
"""
import argparse
import hashlib
import json
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from anaphora import find_anaphors
from mentions import candidate_mentions
from preprocess import normalize_names, strip_reminders
from setdata import load

ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://127.0.0.1:8080/v1/chat/completions")
MODEL = os.environ.get("LLM_MODEL", "local-model")
CACHE = os.path.join(BASE, ".cache", "label_cases")

SYSTEM = (
    "You are an expert Magic: The Gathering rules judge. Given card text, a list "
    "of anaphors (pronouns such as it/its/they/them/their, or 'the rest'), and a "
    "numbered list of candidate mentions, decide for EACH anaphor which single "
    "candidate it refers to. Resolve each anaphor independently -- two anaphors "
    "may refer to different things. Reply with ONLY a JSON object, no prose."
)


def card_texts(data_path):
    items, types, names, sets = load(data_path)
    out = []
    for name, text, code in items:
        t = " ".join(normalize_names(strip_reminders(text), names).split())
        if t:
            out.append((name, t))
    return out


def build_case(name, text, parser=True):
    return {
        "card": name,
        "text": text,
        "anaphors": find_anaphors(text),
        "candidates": candidate_mentions(text, parser=parser),
    }


def _context(text, span, w=48):
    s, e = span
    return f"...{text[max(0, s - w):s]}[[{text[s:e]}]]{text[e:e + w]}..."


def anaphor_candidates(case):
    """Per anaphor: global candidate indices to offer, excluding the anaphor's
    own occurrence (a mention can never be its own antecedent)."""
    per = []
    for a in case["anaphors"]:
        per.append([j for j, c in enumerate(case["candidates"])
                    if c["end"] <= a["start"] or c["start"] >= a["end"]])
    return per


def prompt_for(case):
    per = anaphor_candidates(case)
    lines = [f"CARD: {case['card']}", "TEXT:", case["text"], "",
             "Resolve EACH anaphor below independently (they may refer to DIFFERENT things).",
             "Each anaphor has its OWN candidate list; answer with the LOCAL index.", ""]
    for i, a in enumerate(case["anaphors"]):
        lines.append(f"ANAPHOR [{i}] \"{a['surface']}\"  context: {_context(case['text'], (a['start'], a['end']))}")
        if per[i]:
            joined = "  ".join(f"[{k}] \"{case['candidates'][j]['surface']}\"" for k, j in enumerate(per[i]))
            lines.append(f"    candidates: {joined}")
        else:
            lines.append("    candidates: (none)")
    n = len(case["anaphors"])
    lines += ["",
              "Use -1 if an anaphor's candidate list has no valid antecedent.",
              f"Include exactly {n} entries (anaphor indices 0..{n - 1}).",
              'Reply JSON only: {"resolutions":[{"anaphor":0,"antecedent":1,"confidence":0.9}, ...]}']
    return "\n".join(lines)


def extract_json(text):
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


_llm_lock = threading.Lock()


def llm_call(case):
    prompt = prompt_for(case)
    key = hashlib.sha1((MODEL + "\n" + prompt).encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key + ".json")
    with _llm_lock:
        if os.path.exists(path):
            try:
                return json.load(open(path))
            except Exception:
                pass
    body = json.dumps({
        "model": MODEL, "temperature": 0, "top_p": 1, "max_tokens": 1500,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
    }).encode()
    result = None
    for _ in range(3):
        try:
            req = urllib.request.Request(ENDPOINT, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.load(r)
            result = extract_json(d["choices"][0]["message"].get("content", ""))
            break
        except Exception:
            time.sleep(2)
    if result is not None:
        os.makedirs(CACHE, exist_ok=True)
        with _llm_lock:
            json.dump(result, open(path, "w"))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", nargs="?", default="FDN.json")
    ap.add_argument("--limit", type=int, default=0, help="max cards (0 = all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--parse-workers", type=int, default=0,
                    help="processes for the parser-mention precompute (0 = cpu-1)")
    ap.add_argument("--out", default=os.path.join(BASE, "coref_dataset.json"))
    ap.add_argument("--bench", action="store_true",
                    help="only process cards in coref_benchmark.json")
    ap.add_argument("--no-parser", action="store_true",
                    help="use regex-only candidate mentions (skip the grammar)")
    ap.add_argument("--dedup", action="store_true",
                    help="keep one case per unique card text (saves LLM calls)")
    ap.add_argument("--dry-run", metavar="CARD", help="print the prompt for one card and exit")
    args = ap.parse_args()

    cards = card_texts(args.data)

    if args.bench:
        bench = json.load(open(os.path.join(BASE, "coref_benchmark.json")))
        want = {b[0] for b in bench}
        cards = [(n, t) for n, t in cards if n in want]

    if args.dry_run:
        for name, text in cards:
            if name.lower() == args.dry_run.lower():
                print(prompt_for(build_case(name, text, parser=not args.no_parser)))
                return
        print("card not found")
        return

    if args.limit:
        cards = cards[:args.limit]
    cards = [(n, t) for n, t in cards if find_anaphors(t)]
    if args.dedup:
        seen = set()
        cards = [(n, t) for n, t in cards if not (t in seen or seen.add(t))]
    use_parser = not args.no_parser
    if use_parser:
        from pmentions import precompute
        n = precompute([t for _, t in cards], workers=args.parse_workers or None)
        print(f"parser mentions: {n} newly cached")
    cases = [build_case(n, t, parser=use_parser) for n, t in cards]
    cases = [c for c in cases if c["anaphors"] and c["candidates"]]
    n_anaphors = sum(len(c["anaphors"]) for c in cases)
    print(f"cards={len(cases)}  anaphor-occurrences={n_anaphors}  "
          f"endpoint={ENDPOINT} model={MODEL}")

    done = [0]

    def work(case):
        resp = llm_call(case)
        done[0] += 1
        if done[0] % 25 == 0:
            print(f"  ...{done[0]}/{len(cases)}", flush=True)
        return case, resp

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(work, cases))

    dataset = []
    n_ok = n_fail = n_none = 0
    for case, resp in results:
        per = anaphor_candidates(case)
        res = {r.get("anaphor"): r for r in (resp or {}).get("resolutions", []) if isinstance(r, dict)}
        rec = {"card": case["card"], "text": case["text"],
               "candidates": case["candidates"], "anaphors": []}
        for i, a in enumerate(case["anaphors"]):
            r = res.get(i)
            if r is None:
                n_fail += 1
                ant = None
            else:
                loc = r.get("antecedent")
                if isinstance(loc, int) and 0 <= loc < len(per[i]):
                    ant = per[i][loc]          # map local -> global candidate index
                    n_ok += 1
                elif loc == -1:
                    ant = -1
                    n_none += 1
                else:
                    ant = None
                    n_fail += 1
            rec["anaphors"].append({**a, "antecedent": ant,
                                    "confidence": (r or {}).get("confidence")})
        dataset.append(rec)

    json.dump(dataset, open(args.out, "w"), indent=1)
    print(f"labeled={n_ok}  none(-1)={n_none}  unparsed/failed={n_fail}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
