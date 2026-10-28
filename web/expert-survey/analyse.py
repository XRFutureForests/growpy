"""Analyse the expert survey answers against the item key.

    python web/expert-survey/analyse.py answers/

``answers/`` holds one JSON per respondent session: the survey server's files (copied from
dt.unr ``/media/data/xrff-survey/<survey>/``), files respondents downloaded, or documents
exported from the claude.ai page database (one JSON object each, or a JSON list of them).
The key is ``items_key.csv`` next to this script. Writes ``results/answers.csv`` (one row per rated tree) and
``results/summary.md``.

What it reports:
- species recognition: share of first answers naming the intended species, per kind
  (catalog / real) and species, and the confusion table;
- real vs generated: mean realness (1 = surely generated, 5 = surely real) per kind, and the
  AUC of telling real from generated (0.5 = experts cannot tell them apart);
- naturalness and typicality per species, catalog minus real where both exist;
- what looks off: flaw tag shares per catalog species;
- retest: agreement of the two repeated items per respondent;
- owner ranking: expert ratings of the trees the owner ranked on 2026-10-28.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def load_sessions(folder: Path) -> list[dict]:
    sessions = []
    for f in sorted(folder.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for s in data if isinstance(data, list) else [data]:
            if s.get("answers"):
                sessions.append(s)
    return sessions


def answers_frame(sessions: list[dict]) -> pd.DataFrame:
    rows = []
    for s in sessions:
        prof = s.get("profile") or {}
        for entry, a in s["answers"].items():
            rows.append(dict(
                session=s["session"], set=s["set"], finished=bool(s.get("finished")),
                field=prof.get("field"), years=prof.get("years"), winter_id=prof.get("winter_id"),
                code=a["code"], repeat=bool(a.get("repeat")), position=a.get("position"),
                species_guess=a.get("species"), conf=a.get("conf"), real=a.get("real"),
                natural=a.get("natural"), typical=a.get("typical"), flaws=";".join(a.get("flaws") or []),
                situation=a.get("situation"), comment=a.get("comment", ""), ms=a.get("ms"),
                saw_side="side" in (a.get("views") or []),
            ))
    return pd.DataFrame(rows)


def md(frame: pd.DataFrame, index: bool = True) -> str:
    """Markdown table without the optional tabulate dependency."""
    f = frame.reset_index() if index else frame
    cols = [" / ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in f.columns]
    rows = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    rows += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in f.itertuples(index=False)]
    return "\n".join(rows)


def auc(pos: pd.Series, neg: pd.Series) -> float:
    """Probability that a real tree gets a higher realness rating than a generated one (ties 0.5)."""
    if pos.empty or neg.empty:
        return float("nan")
    p, n = pos.to_numpy()[:, None], neg.to_numpy()[None, :]
    return float(((p > n).sum() + 0.5 * (p == n).sum()) / (p.size * n.size))


def main(argv: list[str]) -> int:
    folder = Path(argv[0]) if argv else HERE / "responses"
    sessions = load_sessions(folder)
    if not sessions:
        print(f"no answers in {folder}")
        return 1
    key = pd.read_csv(HERE / "items_key.csv")
    df = answers_frame(sessions).merge(key, on="code", how="left", suffixes=("", "_key"))
    df["group"] = df.kind.map(lambda k: "real" if "real" in k else "generated")
    df["correct"] = df.species_guess == df.species_key
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    df.to_csv(out / "answers.csv", index=False)

    first = df[~df.repeat]
    lines = [f"# Expert survey results\n", f"{len(sessions)} respondents, {len(first)} ratings "
             f"({first.code.nunique()} trees). Realness: 1 = surely generated, 5 = surely real. "
             "Naturalness and typicality: 1-5.\n"]

    by = first.groupby(["species_key", "group"]).agg(
        n=("code", "size"), species_correct=("correct", "mean"), realness=("real", "mean"),
        natural=("natural", "mean"), typical=("typical", "mean"),
    ).round(2)
    by.to_csv(out / "by_species.csv")
    lines += ["## Per species and group\n", md(by), ""]

    gen, real = first[first.group == "generated"], first[first.group == "real"]
    lines += ["## Real vs generated\n",
              f"- realness, generated: {gen.real.mean():.2f}; real: {real.real.mean():.2f}",
              f"- AUC real vs generated: {auc(real.real, gen.real):.2f} (0.5 = indistinguishable)",
              f"- species named correctly, generated: {gen.correct.mean():.0%}; real: {real.correct.mean():.0%}", ""]

    wide = by.reset_index().pivot(index="species_key", columns="group", values=["natural", "typical"])
    if ("typical", "real") in wide.columns:
        gap = (wide.xs("generated", axis=1, level=1) - wide.xs("real", axis=1, level=1)).round(2)
        lines += ["## Catalog minus real (negative = catalog looks worse)\n", md(gap.dropna()), ""]

    conf = pd.crosstab(first.species_key, first.species_guess)
    conf.to_csv(out / "species_confusion.csv")
    lines += ["## Species confusion (rows: intended, columns: named)\n", md(conf), ""]

    flaws = gen.assign(flaw=gen.flaws.str.split(";")).explode("flaw")
    flaws = flaws[flaws.flaw.astype(bool)]
    share = (flaws.groupby(["species_key", "flaw"]).size() / gen.groupby("species_key").size()).rename("share")
    top = share.reset_index().sort_values(["species_key", "share"], ascending=[True, False]).groupby("species_key").head(4)
    top.to_csv(out / "flaws_generated.csv", index=False)
    lines += ["## Most named flaws on generated trees (share of ratings)\n", md(top.round(2), index=False), ""]

    rep = df[df.repeat][["session", "code", "species_guess", "real", "typical"]].merge(
        first[["session", "code", "species_guess", "real", "typical"]], on=["session", "code"], suffixes=("_2", "_1"))
    if not rep.empty:
        lines += ["## Retest (same tree twice per respondent)\n",
                  f"- {len(rep)} pairs; same species: {(rep.species_guess_1 == rep.species_guess_2).mean():.0%}; "
                  f"realness within 1 step: {((rep.real_1 - rep.real_2).abs() <= 1).mean():.0%}; "
                  f"typicality within 1 step: {((rep.typical_1 - rep.typical_2).abs() <= 1).mean():.0%}", ""]

    ranked = first[first.kind.str.startswith("ranked")].groupby(["code", "kind", "stage"]).agg(
        n=("code", "size"), realness=("real", "mean"), typical=("typical", "mean"), natural=("natural", "mean")).round(2)
    if not ranked.empty:
        lines += ["## Trees from the owner's blind ranking (stage = owner rank)\n", md(ranked), ""]

    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"-> {out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
