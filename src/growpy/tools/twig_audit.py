"""Audit where the PVE plan puts foliage, offline, for every catalog cell (XRFF-525).

Placement defects of the PVE catalog -- rolled-edge-on sprays, twigs on the
self-pruned lower trunk, a bare leader with one lonely spray, upturned shaded
tips -- were each found by eye in the editor after the numbers said the crown
was fine (XRFF-392). This reads what the plan will build and reports, per tree:

* instances per layer (main, apex, tip cap), simulated with the validated
  offline model of PVE's distributor (``pve_distributor_model``);
* foliage per metre of side-branch wood in each tenth of the tree's height, and
  the top band against the mid-crown (``top_band_ratio``);
* the leader above the top first-order branch: its length and how many sprays
  sit on it (``leader_sprays_per_m``);
* the share of side branches that left their parent sideways and ended up
  pointing up (``upturned``, the 'candle' metric of the conifer turn-up lane).

Each cell is judged against ``config/twig_audit.toml``, per growth habit. The
input is the plan's ``growpy_pve_graphs.py`` -- the chain specs themselves, so
the audit measures what the graph builder will build and cannot drift from the
plan -- plus the growth JSONs those chains name. No editor is needed.

    growpy-twig-audit data/output/forest/unreal_scripts
    growpy-twig-audit <plan dir> --species douglas_fir --out report.json
    growpy-twig-audit <plan dir> --no-fail          # report, exit 0

Not measured here: the orientation of each spray (roll about the branch axis,
angle to the growth direction). The offline model places instances and scales
them; it does not model the Aim/Face vector blend, so orientation still needs a
look in the editor.
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import math
import re
import sys
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from growpy.io.unreal.pve_distributor_model import (
    Placement,
    simulate_placements,
)
from growpy.io.unreal.pve_graph_builder import DistributorSpec
from growpy.io.unreal.pve_offline_solve import LeaderSpan, leader_span

logger = logging.getLogger(__name__)

BANDS = 10
UPTURN_MIN_SPAN_M = 0.5  # shorter side branches are twigs, not shoots
UPTURN_TAIL_M = 0.3  # direction of the last 30 cm of a shoot
UPTURN_MAX_FROM_UP = 30.0  # a tip within 30 deg of vertical points up
UPTURN_MIN_LEAVE = 50.0  # ...and it left its parent more than 50 deg off it
_KEY = re.compile(r"Time=([-\d.eE+]+),Value=([-\d.eE+]+)")
_TREE_ID = re.compile(r"^r(\d+)_h(\d+)m$")
DEFAULT_THRESHOLDS = Path("config/twig_audit.toml")


# --- reading the plan ---------------------------------------------------------


def parse_ue_curve(text: str | None) -> tuple[tuple[float, float], ...] | None:
    """``(EditorCurveData=(Keys=((...Time=0.0,Value=1.0),...)))`` -> ``((t, v), ...)``."""
    if not text:
        return None
    keys = tuple((float(t), float(v)) for t, v in _KEY.findall(text))
    return keys or None


def load_chains(graphs_script: Path) -> list[dict]:
    """Every chain spec of a plan, exactly as the graph builder will receive it."""
    for line in Path(graphs_script).read_text(encoding="utf-8").splitlines():
        if line.startswith("GRAPHS = "):
            graphs = ast.literal_eval(line[len("GRAPHS = ") :])
            return [chain for graph in graphs for chain in graph["chains"]]
    raise ValueError(f"{graphs_script}: no 'GRAPHS = ' literal -- not a growpy PVE graph script")


def distributor_from_literal(spec: dict) -> DistributorSpec:
    """A ``DistributorSpec`` from a chain or layer dict of the graph script.

    Only the fields the placement model reads are carried over; the pose
    (aim, face, jitter) is orientation and is not modelled offline.
    """
    scale_ramp = parse_ue_curve(spec.get("scale_ramp"))
    band = spec.get("generation_band")
    return DistributorSpec(
        branch_density=int(spec["branch_density"]),
        spacing_basis=spec.get("spacing_basis", "BRANCH"),
        relative_start=float(spec.get("relative_start", 0.0)),
        relative_end=float(spec.get("relative_end", 1.0)),
        phyllotaxy_type=spec.get("phyllotaxy_type", "SPIRAL"),
        node_buds=tuple(spec.get("node_buds", (1, 1))),
        single_bud_tip=bool(spec.get("single_bud_tip", True)),
        base_scale=float(spec.get("base_scale", 1.0)),
        scale_ramp_basis=spec.get("scale_ramp_basis", "PLANT"),
        scale_ramp=(scale_ramp[0][1], scale_ramp[-1][1]) if scale_ramp else (1.0, 1.0),
        spacing_ramp=parse_ue_curve(spec.get("spacing_ramp")),
        face=None,
        generation_band=tuple(band) if band is not None else None,
    )


def tree_id_of(mesh_name: str) -> str:
    """``SK_DouglasFir_r10_h35m`` -> ``r10_h35m``."""
    return "_".join(mesh_name.split("_")[-2:])


def species_of(growth_json: str | Path) -> str:
    """Standardized species name from the ``<species>/r<NN>/`` export layout."""
    return Path(growth_json).parent.parent.name


# --- the skeleton ---------------------------------------------------------------


def _unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / n for c in v]


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _len(v) -> float:
    return math.sqrt(sum(c * c for c in v))


def _angle_from_up(direction) -> float:
    """Degrees from +Y (the growth JSON is y-up, metres)."""
    return math.degrees(math.acos(max(-1.0, min(1.0, direction[1]))))


def _tail_direction(pts, want_m: float):
    end = pts[-1]
    for i in range(len(pts) - 2, -1, -1):
        if _len(_sub(end, pts[i])) >= want_m:
            return _unit(_sub(end, pts[i]))
    return _unit(_sub(end, pts[0]))


def _head_direction(pts, want_m: float):
    start = pts[0]
    for i in range(1, len(pts)):
        if _len(_sub(pts[i], start)) >= want_m:
            return _unit(_sub(pts[i], start))
    return _unit(_sub(pts[-1], start))


@dataclass(frozen=True)
class Skeleton:
    height_m: float
    side_branches: int
    upturned: float
    tips_up: float
    # The trunk above its topmost first-order branch, measured ALONG the trunk
    # (a curved leader is longer than the height it gains) -- the same
    # definition the plan builds its leader layer from.
    leader: LeaderSpan | None
    band_branch_m: tuple[float, ...]


def measure_skeleton(growth_json: Path | str) -> Skeleton:
    """Upturned shoots, the leader, and side-branch wood per tenth of the height."""
    data = json.loads(Path(growth_json).read_text(encoding="utf-8"))
    pos = data["points"]["positions"]
    prims = data["primitives"]["points"]
    hier = data["primitives"]["attributes"]["branchHierarchyNumber"]["values"]
    ys = [p[1] for p in pos]
    y_lo, y_hi = min(ys), max(ys)
    height = y_hi - y_lo
    side = turned = tips_up = 0
    wood = [0.0] * BANDS
    for p, idx in enumerate(prims):
        if p == 0 or hier[p] <= 1 or len(idx) < 2:  # hierarchy 1 = the trunk
            continue
        pts = [pos[i] for i in idx]
        span = 0.0
        for a, b in zip(pts, pts[1:], strict=False):
            seg = _len(_sub(b, a))
            span += seg
            if height > 1e-6:
                frac = ((a[1] + b[1]) / 2.0 - y_lo) / height
                wood[min(max(int(frac * BANDS), 0), BANDS - 1)] += seg
        if span < UPTURN_MIN_SPAN_M:
            continue
        side += 1
        if _angle_from_up(_tail_direction(pts, UPTURN_TAIL_M)) < UPTURN_MAX_FROM_UP:
            tips_up += 1
            if _angle_from_up(_head_direction(pts, UPTURN_TAIL_M)) > UPTURN_MIN_LEAVE:
                turned += 1
    return Skeleton(
        height_m=height,
        side_branches=side,
        upturned=turned / side if side else 0.0,
        tips_up=tips_up / side if side else 0.0,
        leader=leader_span(growth_json),
        band_branch_m=tuple(wood),
    )


# --- placements -----------------------------------------------------------------


def band_of(height_fraction: float) -> int:
    return min(max(int(height_fraction * BANDS), 0), BANDS - 1)


def band_counts(placements: list[Placement]) -> list[int]:
    counts = [0] * BANDS
    for placement in placements:
        counts[band_of(placement.height)] += 1
    return counts


def leader_placements(placements: list[Placement], skeleton: Skeleton) -> int:
    """Instances on the trunk (generation 1) above the topmost first-order branch."""
    if skeleton.leader is None:
        return 0
    return sum(
        1
        for p in placements
        if p.generation == 1 and p.along_branch >= skeleton.leader.start_along - 1e-6
    )


def top_band_ratio(counts: list[int], wood: tuple[float, ...]) -> float | None:
    """Foliage per metre of side branch in the top tenth, over the mid-crown's.

    1.0 is an even crown. The mid-crown is the 40-70 % bands, where a conifer's
    foliage is at its fullest. ``None`` when either has no wood to measure.
    """
    def density(bands) -> float | None:
        metres = sum(wood[b] for b in bands)
        if metres <= 1e-6:
            return None
        return sum(counts[b] for b in bands) / metres

    top, mid = density([BANDS - 1]), density([4, 5, 6])
    if top is None or mid is None or mid <= 0.0:
        return None
    return top / mid


# --- thresholds ------------------------------------------------------------------


@dataclass(frozen=True)
class Thresholds:
    conifers: frozenset[str]
    conifer: dict
    broadleaf: dict

    def habit(self, species: str) -> str:
        return "conifer" if species in self.conifers else "broadleaf"

    def for_habit(self, habit: str) -> dict:
        return self.conifer if habit == "conifer" else self.broadleaf


def load_thresholds(path: Path | None = None) -> Thresholds:
    """``config/twig_audit.toml`` (or ``path``); follows the config directory."""
    candidates = [path] if path else []
    try:
        from growpy.config.core import _find_config_dir

        config_dir = _find_config_dir()
        if config_dir is not None:
            candidates.append(Path(config_dir) / "twig_audit.toml")
    except Exception:  # noqa: BLE001 -- fall back to the repo-relative default
        pass
    candidates.append(DEFAULT_THRESHOLDS)
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            raw = tomllib.loads(Path(candidate).read_text(encoding="utf-8"))
            return Thresholds(
                conifers=frozenset(raw.get("habits", {}).get("conifer", ())),
                conifer=dict(raw.get("conifer", {})),
                broadleaf=dict(raw.get("broadleaf", {})),
            )
    raise FileNotFoundError("config/twig_audit.toml not found; pass --thresholds")


# --- one tree ----------------------------------------------------------------------


@dataclass
class TreeAudit:
    mesh_name: str
    species: str
    tree_id: str
    habit: str
    height_m: float
    instances: int
    layer_instances: list[int]
    upturned: float
    tips_up: float
    leader_m: float | None
    leader_instances: int
    leader_sprays_per_m: float | None
    top_band_ratio: float | None
    band_instances: list[int]
    band_branch_m: list[float]
    failures: list[str] = field(default_factory=list)


def judge(audit: TreeAudit, limits: dict) -> list[str]:
    """Which thresholds this cell misses, as short readable strings."""
    out: list[str] = []
    if audit.habit == "conifer":
        cap = limits.get("upturned_max")
        if cap is not None and audit.upturned > cap:
            out.append(f"upturned {audit.upturned:.1%} > {cap:.0%}")
        floor = limits.get("leader_sprays_per_m_min")
        min_leader = limits.get("leader_min_m", 0.0)
        if (
            floor is not None
            and audit.leader_m is not None
            and audit.leader_m >= min_leader
            and (audit.leader_sprays_per_m or 0.0) < floor
        ):
            out.append(
                f"leader {audit.leader_instances} spray(s) on {audit.leader_m:.2f} m "
                f"= {audit.leader_sprays_per_m:.1f}/m < {floor:g}/m"
            )
    floor = limits.get("top_band_ratio_min")
    if floor is not None and audit.top_band_ratio is not None and audit.top_band_ratio < floor:
        out.append(f"top band {audit.top_band_ratio:.2f} of mid-crown < {floor:g}")
    return out


def audit_chain(chain: dict, thresholds: Thresholds, growth_json: Path | None = None) -> TreeAudit:
    path = Path(growth_json or chain["growth_json"])
    species = species_of(path)
    habit = thresholds.habit(species)
    skeleton = measure_skeleton(path)

    layers = [chain, *chain.get("layers", [])]
    all_placements: list[Placement] = []
    per_layer: list[int] = []
    for spec in layers:
        placed = simulate_placements(path, distributor_from_literal(spec))
        per_layer.append(len(placed))
        all_placements.extend(placed)

    counts = band_counts(all_placements)
    leader_n = leader_placements(all_placements, skeleton)
    leader_m = skeleton.leader.length_m if skeleton.leader else None
    leader_density = leader_n / leader_m if leader_m and leader_m > 0 else None
    audit = TreeAudit(
        mesh_name=chain["mesh_name"],
        species=species,
        tree_id=tree_id_of(chain["mesh_name"]),
        habit=habit,
        height_m=round(skeleton.height_m, 2),
        instances=len(all_placements),
        layer_instances=per_layer,
        upturned=round(skeleton.upturned, 4),
        tips_up=round(skeleton.tips_up, 4),
        leader_m=None if leader_m is None else round(leader_m, 2),
        leader_instances=leader_n,
        leader_sprays_per_m=None if leader_density is None else round(leader_density, 2),
        top_band_ratio=(
            None
            if (ratio := top_band_ratio(counts, skeleton.band_branch_m)) is None
            else round(ratio, 3)
        ),
        band_instances=counts,
        band_branch_m=[round(m, 2) for m in skeleton.band_branch_m],
    )
    audit.failures = judge(audit, thresholds.for_habit(habit))
    return audit


# --- command line -------------------------------------------------------------------


def _resolve_graphs_script(target: Path) -> Path:
    return target if target.is_file() else target / "growpy_pve_graphs.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "plan",
        type=Path,
        nargs="?",
        default=Path("data/output/forest/unreal_scripts"),
        help="plan directory (or its growpy_pve_graphs.py)",
    )
    parser.add_argument("--species", nargs="*", help="standardized names; default all")
    parser.add_argument("--thresholds", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="JSON report (default: <plan>/twig_audit.json)")
    parser.add_argument("--no-fail", action="store_true", help="always exit 0")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    script = _resolve_graphs_script(args.plan)
    thresholds = load_thresholds(args.thresholds)
    chains = load_chains(script)
    wanted = set(args.species or [])
    audits: list[TreeAudit] = []
    skipped: list[str] = []
    for chain in chains:
        path = Path(chain["growth_json"])
        if wanted and species_of(path) not in wanted:
            continue
        if not path.exists():
            skipped.append(f"{chain['mesh_name']}: {path} not found")
            continue
        audits.append(audit_chain(chain, thresholds))
        logger.debug("audited %s", chain["mesh_name"])

    audits.sort(key=lambda a: (a.species, int(_TREE_ID.match(a.tree_id).group(1)), a.height_m))
    print(
        f"{'tree':<34}{'habit':<10}{'h m':>6}{'inst':>8}{'upturn':>8}{'leader m':>9}"
        f"{'sprays':>7}{'/m':>6}{'top/mid':>8}  verdict"
    )
    print("-" * 110)
    for a in audits:
        sprays_m = "-" if a.leader_sprays_per_m is None else f"{a.leader_sprays_per_m:.1f}"
        leader = "-" if a.leader_m is None else f"{a.leader_m:.2f}"
        top = "-" if a.top_band_ratio is None else f"{a.top_band_ratio:.2f}"
        verdict = "ok" if not a.failures else "; ".join(a.failures)
        print(
            f"{a.mesh_name:<34}{a.habit:<10}{a.height_m:>6.1f}{a.instances:>8}"
            f"{a.upturned:>8.1%}{leader:>9}{a.leader_instances:>7}{sprays_m:>6}{top:>8}  {verdict}"
        )
    failing = [a for a in audits if a.failures]
    print("-" * 110)
    print(f"{len(audits)} cell(s) audited, {len(failing)} failing")
    for line in skipped:
        logger.warning("skipped: %s", line)

    report = args.out or script.parent / "twig_audit.json"
    report.write_text(
        json.dumps(
            {
                "plan": str(script),
                "cells": [asdict(a) for a in audits],
                "failing": [a.mesh_name for a in failing],
                "skipped": skipped,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    logger.info("report: %s", report)
    if not audits:
        logger.error("nothing audited")
        return 1
    return 0 if (args.no_fail or not failing) else 1


if __name__ == "__main__":
    sys.exit(main())
