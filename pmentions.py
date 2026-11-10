"""Parser-based candidate mentions — **deprecated shim** over `ptree`.

Kept so existing callers (`mentions.candidate_mentions`, `label_cases`,
datasets already built) keep working unchanged. The parsing, caching and regex
fallback all live in `ptree.py` now: one parse per text yields both mention
spans and structure, instead of two parses with different `Lark` flags.

    python ptree.py --build --data FDN.json      # rebuild the span/structure cache
    python ptree.py --status                     # cache coverage

`precompute`/`save_cache` are re-exported for `label_cases`.
"""
import sys

BASE = __file__.rsplit("/", 1)[0]
sys.path.insert(0, BASE)

import ptree

MENTION_NODES = ptree.MENTION_NODES


def parser_mentions(text):
    """Mentions from the parse tree; regex fallback for unparseable segments."""
    return ptree.mentions(text)


def precompute(texts, workers=None, quiet=False):
    return ptree.precompute(texts, workers=workers, quiet=quiet)


def save_cache():
    ptree.save_cache()


def _compute(text):
    """Raw (uncached) records — kept for backwards compatibility."""
    return ptree._compute(text)


def main():
    import argparse
    from preprocess import normalize_names, strip_reminders
    from setdata import load

    ap = argparse.ArgumentParser()
    ap.add_argument("card", nargs="*", help="card names (default: whole FDN.json)")
    ap.add_argument("--data", default="FDN.json")
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()

    items, _, names, _ = load(args.data)
    by_name = {n: t for n, t, _ in items}
    if args.card:
        raw = [by_name.get(c) or by_name.get(c.lower()) for c in args.card]
    else:
        raw = [t for _, t, _ in items]
    from setdata import normalize_text
    texts = [normalize_text(t, names) for t in raw if t]
    texts = [t for t in texts if t]
    n = precompute(texts, workers=args.workers or None, quiet=True)
    print(f"computed {n} new / {len(texts)} texts -> {ptree.cache_path()}")


if __name__ == "__main__":
    main()
