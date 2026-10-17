"""Parse-tree structure for the resolver — **thin wrapper** over `ptree`.

Records come from the same single parse as the mention spans:

    {"start", "end", "node", "role", "verb", "predicate", "in_condition"}

`structure()` reads the cache only and never parses, so evaluation paths cannot
accidentally trigger an Earley parse. Build the cache with:

    python ptree.py --build --data FDN.json
    python ptree.py --build --sample coref_standard.json --limit 240
    python ptree.py --status

Torch-free.
"""
import sys

BASE = __file__.rsplit("/", 1)[0]
sys.path.insert(0, BASE)

import ptree


def structure(text):
    """Cached records for `text`, or [] (never parses)."""
    return ptree.structure(text)


def has_structure(text):
    return ptree.has_structure(text)


def lookup(recs, start, end=None):
    return ptree.lookup(recs, start, end)


def precompute(texts, workers=None, quiet=False):
    return ptree.precompute(texts, workers=workers, quiet=quiet)


def save_cache():
    ptree.save_cache()


def _load_cache():
    return ptree._load_cache()


def _key(text):
    return ptree.key(text)


def main():
    import argparse
    from setdata import card_text

    ap = argparse.ArgumentParser()
    ap.add_argument("card", nargs="+")
    args = ap.parse_args()
    for name in args.card:
        text = card_text(name)
        if not text:
            print(f"card not found: {name}")
            continue
        print(text)
        for r in structure(text):
            print(f"  {r['start']:3}-{r['end']:3} {str(r['node']):<12} "
                  f"verb={str(r['verb']):<14} role={str(r['role']):<8} "
                  f"pred={r['predicate']} cond={r['in_condition']}")


if __name__ == "__main__":
    main()
