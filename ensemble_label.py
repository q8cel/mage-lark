#!/usr/bin/env python3
"""Label a sample with 3 independent local annotators (ensemble yardstick).

Input: JSON list of {card, text, surface, start, end} (see strat_sample.py).
Output: JSONL-ish JSON list with a vote per case:
    {card, surface, votes:[{config,pick}], majority, agreement, resolved:bool}

Resumable: results are appended and re-read on restart.
"""
import argparse, json, os, re, sys, time, urllib.request
from urllib.error import URLError
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/home/q6/Documents/mage-attn")
import refs
from setdata import card_text

EP = "http://127.0.0.1:9000/v1/chat/completions"
MODEL = "/models/Qwen3.8-27B-UD-Q6_K.gguf"
SYS = ("You resolve anaphora in Magic: The Gathering oracle text. Given a card's text, "
       "one anaphor occurrence, and a numbered list of earlier mentions, reply with JSON "
       '{"antecedent": <index>}, or -1 if none of the listed mentions is the antecedent.')
SYS_STEP = (SYS + " First work out the game semantics of the clause, checking type, "
            "number and recency, then answer.")
CONFIGS = [("low", None, "plain"),
           ("high", {"reasoning_effort": "high"}, "plain"),
           ("step", None, "step")]


DOWN = {"streak": 0}


class ServerDown(Exception):
    pass


def healthy():
    try:
        with urllib.request.urlopen(EP.replace("/v1/chat/completions", "/health"),
                                    timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def call(prompt, sysmsg, extra, tries=4):
    body = {"model": MODEL, "temperature": 0, "max_tokens": 1500,
            "messages": [{"role": "system", "content": sysmsg},
                         {"role": "user", "content": prompt}]}
    if extra:
        body["chat_template_kwargs"] = extra
    data = json.dumps(body).encode()
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(EP, data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)["choices"][0]["message"].get("content") or ""
        except Exception as e:
            last = e
            # A refused connection means the server is gone; retrying 12 times per
            # case just burns the night (that is exactly what happened once).
            if isinstance(e, URLError) and "refused" in str(e):
                DOWN["streak"] += 1
                if DOWN["streak"] >= 3:
                    raise ServerDown("llama-server is not listening")
            time.sleep(2 * (k + 1))
    raise last


def one_case(case):
    text = case.get("text") or card_text(case["card"])
    if not text:
        return None
    pool = [m for m in refs.build(text) if m["end"] <= case["start"]]
    if not pool:
        return None
    listing = "\n".join(f"  [{i}] {m['surface']!r} ({m['head_type']}, {m['number']})"
                        for i, m in enumerate(pool))
    ctx = text[max(0, case["start"] - 220):case["start"]]
    # Only the window up to the anaphor matters, and it keeps prompts small (the
    # full card text made calls slow and risks the server's 8k context).
    window = text[max(0, case["start"] - 1100):min(len(text), case["start"] + 220)]
    prompt = (f"CARD TEXT (window around the anaphor):\n{window}\n\n"
              f"ANAPHOR OCCURRENCE: {case['surface']!r}\n"
              f"CONTEXT BEFORE IT: ...{ctx}\n\nEARLIER MENTIONS:\n{listing}\n\n"
              'Which mention is its antecedent? Reply {"antecedent": <index>} or -1.')
    votes = []
    for name, extra, style in CONFIGS:
        try:
            content = call(prompt, SYS_STEP if style == "step" else SYS, extra)
            m = re.search(r'\{[^{}]*"antecedent"[^{}]*\}', content)
            idx = json.loads(m.group(0))["antecedent"] if m else None
            pick = (pool[idx]["surface"] if isinstance(idx, int) and 0 <= idx < len(pool)
                    else None)
            votes.append({"config": name, "pick": pick})
        except Exception as e:
            votes.append({"config": name, "pick": None, "error": type(e).__name__})
            if isinstance(e, ServerDown):
                DOWN["streak"] += 1
    picks = [v["pick"] for v in votes if v["pick"]]
    majority, agree = None, 0
    for p in set(picks):
        n = sum(1 for q in picks if q.lower() == p.lower())
        if n > agree:
            majority, agree = p, n
    return {**{k: case.get(k) for k in ("card", "surface", "start", "end", "kind")},
            "teacher": case.get("teacher"), "votes": votes,
            "majority": majority, "agreement": agree, "votes_n": len(picks)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    cases = json.load(open(args.input))
    raw = json.load(open(args.out)) if os.path.exists(args.out) else []
    # keep the best entry per case; entries with fewer than 2 votes are retried
    done, best = [], {}
    for d in raw:
        k = (d.get("card"), d.get("surface"), d.get("start"))
        if not k[0]:
            continue
        if (d.get("votes_n") or 0) >= 2:
            if k not in best or (d.get("votes_n") or 0) > (best[k].get("votes_n") or 0):
                best[k] = d
    done = list(best.values())
    have = set(best)
    todo = [c for c in cases if (c.get("card"), c.get("surface"), c.get("start")) not in have]
    print(f"cases {len(cases)}, done {len(done)}, todo {len(todo)}", flush=True)
    if not healthy():
        print("ABORT: llama-server is not answering on " + EP, flush=True)
        print("       start it with ~/teacher.sh, then re-run this command; "
              "completed cases are kept.", flush=True)
        return
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(one_case, todo), 1):
            if r:
                done.append(r)
            if DOWN["streak"] > 12:
                json.dump(done, open(args.out, "w"))
                print(f"ABORT: server stopped answering after {i}/{len(todo)}; "
                      f"saved {len(done)} cases", flush=True)
                return
            if i % 15 == 0:
                json.dump(done, open(args.out, "w"))
                print(f"  {i}/{len(todo)}", flush=True)
    json.dump(done, open(args.out, "w"))
    print("finished", flush=True)


if __name__ == "__main__":
    main()
