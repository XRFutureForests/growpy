"""Compare board: build a compare level from a named set, photograph each tree.

``growpy-ue-compare`` (cleanup class E step 2, owner 2026-11-19) replaces
compare_session.sh and the set if-blocks of build_compare_conifers.py. The sets
are data in ``config/compare_sets.toml`` (``[compare]``). One invocation drives
one ``growpy-ue-session``:

1. ``ue_scripts/compare_level.py`` builds the level (one row per source, labels,
   studio dome);
2. per context (light | dark | forest): ``ue_scripts/compare_context.py`` sets
   the backdrop, then ``ue_scripts/compare_capture.py`` photographs every tree
   (tick-driven) until ``<out>/<context>/DONE``;
3. ``compare_context.py`` in mode ``save`` saves the scratch level; the session quits.

Usage::

    growpy-ue-compare pine12
    growpy-ue-compare e124 --contexts light forest --lock editor-compare
    growpy-ue-compare fleck --param variant=2 --contexts dark
    growpy-ue-compare catalog --variants <twig-tune variants.txt>

The editor scripts run in the editor's own Python, which has no growpy: the set is
resolved here and the editor reads only the job JSON (``<out>/compare_job.json``).
Project, engine and lock folder: as ``growpy-ue-session`` (arguments or its env).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

SETS_FILE = Path("config/compare_sets.toml")
SHOTS_ROOT = Path("data/output/forest/compare_shots")
UE_SCRIPTS = Path(__file__).resolve().parent / "ue_scripts"
CONTEXTS = ("light", "dark", "forest")

TOP_KEYS = {"level", "forest_neighbours", "sets"}
SET_KEYS = {"description", "rows", "contexts", "neighbours", "assembly_tris"}
ROW_KEYS = {"label", "tag", "assets", "pattern", "cells", "variants", "optional"}
NEIGHBOUR_KEYS = {"asset", "dx", "dy"}

BUILD_TIMEOUT = 1500.0
CONTEXT_TIMEOUT = 600.0
CAPTURE_TIMEOUT = 1200.0  # ~100 shots x 4-12 s; today's session gave up after 20 min


# ------------------------------------------------------------------ sets --


@dataclass(frozen=True)
class Tree:
    asset: str
    tag: str

    @property
    def actor(self) -> str:
        """The tree's actor label suffix (``COMPARE_<tag>_<mesh>``) and shot name."""
        return f"{self.tag}_{self.asset.rsplit('/', 1)[1]}"


@dataclass(frozen=True)
class Row:
    label: str
    trees: tuple[Tree, ...]
    optional: bool = False


@dataclass(frozen=True)
class CompareSet:
    name: str
    level: str
    rows: tuple[Row, ...]
    contexts: tuple[str, ...]
    neighbours: tuple[tuple[str, float, float], ...]
    assembly_tris: bool = False
    notes: tuple[str, ...] = ()


def _unknown(where: str, data: dict, allowed: set[str]) -> None:
    extra = sorted(set(data) - allowed)
    if extra:
        raise ValueError(f"{where}: unknown key(s) {extra}; allowed {sorted(allowed)}")


def load_sets(path: Path = SETS_FILE) -> dict:
    """The ``[compare]`` table, structure checked: unknown keys, empty rows, one
    source per row, known contexts, neighbour entries."""
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    if set(data) != {"compare"}:
        raise ValueError(f"{path}: expected one [compare] table, got {sorted(data)}")
    top = data["compare"]
    _unknown(f"{path} [compare]", top, TOP_KEYS)
    if "level" not in top or not top.get("sets"):
        raise ValueError(f"{path}: [compare] needs level and at least one set")
    for n in top.get("forest_neighbours", []):
        _neighbour(f"{path} forest_neighbours", n)
    for name, spec in top["sets"].items():
        where = f"{path} set {name!r}"
        _unknown(where, spec, SET_KEYS)
        if not spec.get("rows"):
            raise ValueError(f"{where}: no rows")
        bad = [c for c in spec.get("contexts", []) if c not in CONTEXTS]
        if bad:
            raise ValueError(f"{where}: unknown context(s) {bad}; known {CONTEXTS}")
        for n in spec.get("neighbours", []):
            _neighbour(where, n)
        for i, row in enumerate(spec["rows"]):
            rwhere = f"{where} row {i + 1} ({row.get('label', '?')!r})"
            _unknown(rwhere, row, ROW_KEYS)
            if not row.get("label"):
                raise ValueError(f"{rwhere}: no label")
            sources = [k for k in ("assets", "pattern", "variants") if k in row]
            if len(sources) != 1:
                raise ValueError(
                    f"{rwhere}: needs exactly one of assets / pattern / variants, "
                    f"got {sources}"
                )
            if "pattern" in row and (
                "{cell}" not in row["pattern"] or not row.get("cells")
            ):
                raise ValueError(f"{rwhere}: a pattern needs {{cell}} and cells")
            if "cells" in row and "pattern" not in row:
                raise ValueError(f"{rwhere}: cells without a pattern")
            if "assets" in row and not row["assets"]:
                raise ValueError(f"{rwhere}: empty assets")
            for asset in row.get("assets", []) + [row.get("pattern", "/")]:
                if not asset.startswith("/"):
                    raise ValueError(f"{rwhere}: not a content path: {asset!r}")
    return top


def _neighbour(where: str, n: dict) -> None:
    _unknown(f"{where} neighbour", n, NEIGHBOUR_KEYS)
    if set(n) != NEIGHBOUR_KEYS:
        raise ValueError(f"{where}: a neighbour needs asset, dx, dy, got {sorted(n)}")


def tree_tag(row_tag: str, asset: str) -> str:
    """A twig-tune asset (``/TwigTune/<arm>/``) is tagged by its arm, as before."""
    if "/TwigTune/" in asset:
        return asset.split("/TwigTune/")[1].split("/")[0]
    return row_tag


def read_variants(path: Path) -> list[str]:
    """The mesh column of a twig-tune variants file (``<variant> <graph> <mesh>``)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [parts[2] for parts in (ln.split() for ln in lines) if len(parts) >= 3]


def resolve_set(
    name: str,
    path: Path = SETS_FILE,
    *,
    variants: Path | None = None,
    params: dict[str, str] | None = None,
) -> CompareSet:
    """A set's rows as asset lists, tags and labels filled in.

    A ``variants`` row needs ``variants`` (the file); without it the row is left
    out and named in ``notes``. Raises on an unknown set, a missing label
    parameter, or a tag collision (two trees of the set under one actor label).
    """
    top = load_sets(path)
    if name not in top["sets"]:
        raise ValueError(f"no set {name!r} in {path}; sets: {sorted(top['sets'])}")
    spec = top["sets"][name]
    params = params or {}
    meshes = read_variants(variants) if variants else None
    rows, notes = [], []
    for row in spec["rows"]:
        try:
            label = row["label"].format_map(params)
        except KeyError as err:
            raise ValueError(
                f"set {name!r}: label {row['label']!r} needs --param {err.args[0]}=..."
            ) from None
        if "assets" in row:
            assets = list(row["assets"])
        elif "pattern" in row:
            assets = [row["pattern"].replace("{cell}", c) for c in row["cells"]]
        elif meshes is None:
            notes.append(f"row {label!r} left out: it reads a --variants file")
            continue
        else:
            assets = [m for m in meshes if row["variants"] in m]
        tag = row.get("tag") or label.split()[0]
        trees = tuple(Tree(a, tree_tag(tag, a)) for a in assets)
        rows.append(Row(label, trees, bool(row.get("optional", False))))
    seen: dict[str, str] = {}
    for row in rows:
        for tree in row.trees:
            if tree.actor in seen:
                raise ValueError(
                    f"set {name!r}: tag collision, {tree.actor!r} in rows "
                    f"{seen[tree.actor]!r} and {row.label!r}; give one row its own tag"
                )
            seen[tree.actor] = row.label
    neighbours = spec.get("neighbours", top.get("forest_neighbours", []))
    return CompareSet(
        name=name,
        level=top["level"],
        rows=tuple(rows),
        contexts=tuple(spec.get("contexts", ["light"])),
        neighbours=tuple(
            (n["asset"], float(n["dx"]), float(n["dy"])) for n in neighbours
        ),
        assembly_tris=bool(spec.get("assembly_tris", False)),
        notes=tuple(notes),
    )


# ------------------------------------------------------------------- job --


@dataclass
class CompareJob:
    """What the editor scripts read: the resolved set and where to write."""

    set: str
    sets_file: str
    out: str
    level: str
    rows: list[dict]
    neighbours: list[list]
    assembly_tris: bool = False
    contexts: list[str] = field(default_factory=lambda: ["light"])
    crown_base: dict[str, float] = field(default_factory=dict)
    limb: dict[str, float] = field(default_factory=dict)
    base: bool = False
    sweep: list[list] = field(default_factory=list)

    @classmethod
    def for_set(cls, cset: CompareSet, sets_file: Path, out: Path, contexts, **extra):
        return cls(
            set=cset.name,
            sets_file=str(Path(sets_file).resolve()),
            out=str(Path(out).resolve()),
            level=cset.level,
            rows=[
                {
                    "label": r.label,
                    "optional": r.optional,
                    "trees": [{"asset": t.asset, "tag": t.tag} for t in r.trees],
                }
                for r in cset.rows
            ],
            neighbours=[list(n) for n in cset.neighbours],
            assembly_tris=cset.assembly_tris,
            contexts=list(contexts),
            **extra,
        )

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")
        return path

    @classmethod
    def read(cls, path: Path) -> CompareJob:
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


# ----------------------------------------------------------------- steps --


def write_stub(path: Path, script: str, job: Path, mode: str | None = None) -> Path:
    """A one-call editor script: runs the packaged ``script`` with JOB (and MODE)."""
    init = {"JOB": str(job)} if mode is None else {"JOB": str(job), "MODE": mode}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "import runpy\n"
        f"runpy.run_path({str(UE_SCRIPTS / script)!r}, init_globals={init!r}, "
        "run_name='__main__')\n",
        encoding="utf-8",
    )
    return path


def session_steps(job_path: Path, out: Path, contexts) -> list[str]:
    """The ``growpy-ue-session`` step arguments: build, per context backdrop +
    capture until its DONE, then save the scratch level."""
    stubs = out / "steps"
    level = write_stub(stubs / "1_level.py", "compare_level.py", job_path)
    argv = ["--run", str(level), str(BUILD_TIMEOUT)]
    for i, ctx in enumerate(contexts, 2):
        ctx_stub = write_stub(
            stubs / f"{i}_{ctx}_context.py", "compare_context.py", job_path, ctx
        )
        shot_stub = write_stub(
            stubs / f"{i}_{ctx}_capture.py", "compare_capture.py", job_path, ctx
        )
        argv += ["--run", str(ctx_stub), str(CONTEXT_TIMEOUT)]
        argv += [
            "--run-until-done",
            str(shot_stub),
            str(out / ctx / "DONE"),
            str(CAPTURE_TIMEOUT),
        ]
    save = write_stub(
        stubs / f"{len(contexts) + 2}_save.py", "compare_context.py", job_path, "save"
    )
    argv += ["--run", str(save), str(CONTEXT_TIMEOUT)]
    return argv


# ------------------------------------------------------------------- cli --


def _params(items: list[str]) -> dict[str, str]:
    out = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise SystemExit(f"--param wants key=value, got {item!r}")
        out[key] = value
    return out


def _sweep(path: Path | None) -> list[list]:
    if path is None:
        return []
    return [
        ln.split() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="growpy-ue-compare",
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("set", help="set name in the sets file")
    parser.add_argument(
        "--contexts",
        nargs="+",
        choices=CONTEXTS,
        help="backdrops in order (default: the set's, else light)",
    )
    parser.add_argument(
        "--out", type=Path, help=f"shot folder (default {SHOTS_ROOT}/<stamp>)"
    )
    parser.add_argument(
        "--sets", type=Path, default=SETS_FILE, help=f"sets file (default {SETS_FILE})"
    )
    parser.add_argument(
        "--variants", type=Path, help="twig-tune variants file for variants rows"
    )
    parser.add_argument("--param", action="append", default=[], metavar="KEY=VALUE",
                        help="a label parameter, e.g. variant=2")  # fmt: skip
    parser.add_argument(
        "--crown-base",
        type=Path,
        help="JSON mesh name -> crown base (m) for the crown view",
    )
    parser.add_argument(
        "--limb",
        type=Path,
        help="JSON mesh name -> height (m) of a limb-end close-up view (E131)",
    )
    parser.add_argument(
        "--base",
        action="store_true",
        help="a stem-base close-up per tree: eye height 1.6 m, 3.5 m away (E147)",
    )
    parser.add_argument(
        "--sweep",
        type=Path,
        help="exposure test tiles: '<label part> <bias> <brightness>' lines",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write the job and steps, start no editor",
    )
    for opt in ("--project", "--engine", "--lock-dir", "--lock", "--purpose"):
        parser.add_argument(opt, help="passed to growpy-ue-session")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cset = resolve_set(
            args.set, args.sets, variants=args.variants, params=_params(args.param)
        )
    except (ValueError, OSError) as err:
        print(f"growpy-ue-compare: {err}", file=sys.stderr)
        return 2
    for note in cset.notes:
        print(f"note: {note}")
    contexts = args.contexts or list(cset.contexts)
    out = (args.out or SHOTS_ROOT / time.strftime("%Y%m%d_%H%M")).resolve()
    crown = (
        json.loads(args.crown_base.read_text(encoding="utf-8"))
        if args.crown_base
        else {}
    )
    job = CompareJob.for_set(
        cset, args.sets, out, contexts, crown_base=crown,
        limb=json.loads(args.limb.read_text(encoding="utf-8")) if args.limb else {},
        sweep=_sweep(args.sweep),
        base=args.base,
    )
    job_path = job.write(out / "compare_job.json")
    steps = session_steps(job_path, out, contexts)
    trees = sum(len(r.trees) for r in cset.rows)
    print(
        f"set {cset.name}: {len(cset.rows)} row(s), {trees} tree(s), "
        f"contexts {', '.join(contexts)}"
    )
    print(f"job -> {job_path}")
    if args.dry_run:
        print("growpy-ue-session " + " ".join(steps))
        return 0
    from growpy.tools import ue_session

    session_argv = [
        a
        for opt in ("project", "engine", "lock_dir", "lock", "purpose")
        if getattr(args, opt)
        for a in ("--" + opt.replace("_", "-"), getattr(args, opt))
    ]
    rc = ue_session.main(session_argv + steps)
    for ctx in contexts:
        done = out / ctx / "DONE"
        status = (
            done.read_text(encoding="utf-8").strip() if done.is_file() else "no DONE"
        )
        print(f"{ctx} shots -> {out / ctx} ({status})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
