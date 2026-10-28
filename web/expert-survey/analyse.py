"""Analyse the tree look survey (XRFF-593): votes + item store -> summary and per-tree scores.

    python analyse.py <votes.jsonl> [--items items] [--out results]

Copy the votes from dt.unr first (``/media/data/xrff-survey/tree-look-2026-10/votes.jsonl``).

Ratings are centred per device (rating minus that rater's mean), because people use a 1-5
scale differently; devices with fewer than ``--min-device`` votes keep their raw rating minus
the overall mean. Writes

- ``summary.md``: per species, real against generated: votes, mean rating, mean centred
  rating and the AUC (chance that a random real tree is rated above a random generated tree;
  0.5 = raters cannot tell them apart); the same per source group (dataset, catalog, regrow
  arm), per role, and the "what looked off" flags per kind;
- ``items_scored.csv``: one row per tree with its source, votes, mean rating, a 95 % interval
  and a verdict: ``reference`` (real tree, at least ``--min-votes`` votes, interval above 3.5),
  ``implausible`` (interval below 2.5), ``open`` (too few votes or undecided). This is the
  list to pick reference geometries from, and to see which generated trees fail.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def auc(real: pd.Series, gen: pd.Series) -> float:
    """P(real > generated) + half the ties (Mann-Whitney U / n1 n2)."""
    if real.empty or gen.empty:
        return float("nan")
    r = pd.concat([real, gen]).rank()
    u = r.iloc[: len(real)].sum() - len(real) * (len(real) + 1) / 2
    return u / (len(real) * len(gen))


def md(df: pd.DataFrame) -> str:
    """A Markdown table without the optional ``tabulate`` dependency."""
    cols = [str(c) for c in df.columns]
    rows = [["" if x is None or (isinstance(x, float) and math.isnan(x)) else str(x) for x in r] for r in df.itertuples(index=False)]
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(r) + " |" for r in rows])


def table(v: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = v.groupby(by)
    out = pd.DataFrame({"votes": g.size(), "trees": g.id.nunique(), "mean": g.rating.mean().round(2),
                        "centred": g.centred.mean().round(2)})
    return out.reset_index()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("votes", type=Path)
    p.add_argument("--items", type=Path, default=HERE / "items")
    p.add_argument("--out", type=Path, default=HERE / "results")
    p.add_argument("--min-device", type=int, default=5)
    p.add_argument("--min-votes", type=int, default=10)
    a = p.parse_args()

    items = {}
    for line in (a.items / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        m = json.loads(line)
        items[m["id"]] = m
    recs = [json.loads(line) for line in a.votes.read_text(encoding="utf-8").splitlines() if line.strip()]
    v = pd.DataFrame([r for r in recs if r.get("type") == "vote"])
    if v.empty:
        print("no votes yet")
        return 0
    v = v[v.id.isin(items)].copy()
    v["species"] = v.id.map(lambda i: items[i]["species_key"])
    per_dev = v.groupby("d").rating.agg(["mean", "size"])
    overall = v.rating.mean()
    v["centred"] = v.rating - v.d.map(lambda d: per_dev.at[d, "mean"] if per_dev.at[d, "size"] >= a.min_device else overall)

    flags = defaultdict(list)  # the last flags record per device and tree counts
    for r in recs:
        if r.get("type") == "flags" and r["id"] in items:
            flags[(r["d"], r["id"])] = r["flags"]

    a.out.mkdir(parents=True, exist_ok=True)
    lines = [f"# Tree look survey: {len(v)} votes, {v.d.nunique()} devices, {v.id.nunique()} of {len(items)} trees rated", ""]

    rows = []
    for sp, s in v.groupby("species"):
        real, gen = s[s.kind == "real"].centred, s[s.kind == "generated"].centred
        rows.append({"species": sp, "votes real": len(real), "votes generated": len(gen),
                     "mean real": round(s[s.kind == "real"].rating.mean(), 2),
                     "mean generated": round(s[s.kind == "generated"].rating.mean(), 2),
                     "centred real - generated": round(real.mean() - gen.mean(), 2) if len(real) and len(gen) else None,
                     "AUC": round(auc(real, gen), 3)})
    lines += ["## Real against generated, per species",
              "AUC 0.5 = raters cannot tell generated from real; 1.0 = every real tree above every generated one.", "",
              md(pd.DataFrame(rows)), ""]
    lines += ["## Per source group", "", md(table(v, ["species", "kind", "group"])), ""]
    if "role" in v:
        lines += ["## Per role", "", md(table(v.fillna({"role": "unknown"}), ["role", "kind"])), ""]
    if flags:
        f = pd.DataFrame([{"kind": items[i]["kind"], "flag": fl} for (_, i), fls in flags.items() for fl in fls])
        if not f.empty:
            lines += ["## What looked off (last choice per rater and tree)", "",
                      md(f.groupby(["kind", "flag"]).size().rename("count").reset_index()), ""]

    scored = []
    for i, s in v.groupby("id"):
        m, n = items[i], len(s)
        mean, sd = s.rating.mean(), s.rating.std(ddof=1) if n > 1 else float("nan")
        half = 1.96 * sd / math.sqrt(n) if n > 1 else float("nan")
        lo, hi = mean - half, mean + half
        verdict = "open"
        if n >= a.min_votes and lo > 3.5 and m["kind"] == "real":
            verdict = "reference"
        elif n >= a.min_votes and hi < 2.5:
            verdict = "implausible"
        src = m["source"]
        scored.append({"id": i, "species": m["species_key"], "kind": m["kind"], "group": m["group"],
                       "tree_uid": src.get("tree_uid"), "height_m": m["height_m"], "votes": n,
                       "mean": round(mean, 2), "centred": round(s.centred.mean(), 2),
                       "ci_low": round(lo, 2), "ci_high": round(hi, 2), "verdict": verdict,
                       "flags": ";".join(sorted({fl for (_, j), fls in flags.items() if j == i for fl in fls}))})
    scored = pd.DataFrame(scored).sort_values(["species", "kind", "mean"], ascending=[True, True, False])
    scored.to_csv(a.out / "items_scored.csv", index=False)
    lines += ["## Verdicts per tree", f"`reference`: real, >= {a.min_votes} votes, 95 % interval above 3.5; "
              f"`implausible`: interval below 2.5. Full list: `items_scored.csv`.", "",
              md(scored.groupby(["species", "kind", "verdict"]).size().rename("trees").reset_index()), ""]
    (a.out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(v)} votes -> {a.out / 'summary.md'}, {a.out / 'items_scored.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
