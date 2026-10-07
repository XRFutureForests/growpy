"""A stochastic branching model fitted to real trees (QSMs read from MTG files), and the
pieces its L-Py generator (``branching.lpy``) draws from.

What happens along an axis is a sequence: each axis (trunk, first-order limbs) is cut into
ten equal parts of its length, and a part takes the strongest event among the laterals
leaving it (none < short < long < fork, the descriptors' ``_event`` rule, so the model
speaks the same language as the S descriptors). The sequence is modelled as a
position-dependent first-order Markov chain:

    P(event in decile k | event in decile k-1, order, k)

estimated Bayesian-style: Dirichlet pseudo-counts (``PRIOR``) pull a height class towards
the chain of all height classes of its species, so thin classes borrow strength and full
ones speak for themselves.

What the events look like is not parameterised but resampled from the real trees (an
empirical, nonparametric distribution, which keeps the correlations between a lateral's
length, direction and shape):

``compositions``  the laterals a decile actually carried, keyed by (order, decile, event):
                  how many, of which kinds and where in the decile, with its strongest event
``laterals``      real laterals keyed by (order, zone along the parent, event): length over
                  the parent's length, horizontal divergence (from the previous sibling
                  on the trunk, from the parent's heading on a limb) and the 3D path
                  along the branch (20 elevations and azimuths)
``trunks``        real stems' 3D paths (their lean, bend and wander)

Pools fall back from the height class to the species, then to all zones / deciles, when a
key has fewer than ``MIN_POOL`` examples.
"""

from __future__ import annotations

import math
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from growpy.structure.descriptors import (
    MIN_LATERAL_M,
    MIN_PARENT_M,
    SYMBOLS,
    _arc,
    _at,
    _event,
    _laterals,
    _model,
    _polyline,
)
from growpy.structure.prototypes import N_POINTS

DECILES = 10
SUBSTEPS = (N_POINTS - 1) // DECILES  # internodes per decile when generating (2)
ZONES = 5  # lateral pools by position along the parent (fifths)
MAX_ORDER = 2  # the common prune keeps orders 0-2
PRIOR = 5.0  # Dirichlet pseudo-counts towards the species-wide chain
MIN_POOL = 20
MIN_GENERATED_M = 0.3  # generated laterals shorter than the prune threshold are dropped
LPY_FILE = Path(__file__).with_name("branching.lpy")


# --- extraction -------------------------------------------------------------------------


def _resample(points: np.ndarray, n: int = N_POINTS) -> np.ndarray:
    arc = _arc(points)
    s = np.linspace(0, arc[-1], n)
    return np.column_stack([np.interp(s, arc, points[:, i]) for i in range(3)])


def elevations(points: np.ndarray) -> np.ndarray:
    """Elevation (degrees above horizontal) of the ``N_POINTS - 1`` equal-arc segments of a
    polyline."""
    d = np.diff(_resample(points), axis=0)
    return np.degrees(np.arctan2(d[:, 2], np.hypot(d[:, 0], d[:, 1])))


def headings(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Elevation (degrees above horizontal) and azimuth (degrees, unwrapped, relative to
    the first segment) of the ``N_POINTS - 1`` equal-arc segments of a polyline: the
    branch's full 3D path, which the rule set replays segment by segment."""
    d = np.diff(_resample(points), axis=0)
    elev = np.degrees(np.arctan2(d[:, 2], np.hypot(d[:, 0], d[:, 1])))
    az = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    return elev, np.degrees(az - az[0])


def _heading(points: np.ndarray, at: float = 0.0, span: float = 0.3) -> np.ndarray:
    """Direction over ``span`` (share of the arc) starting at arc share ``at``."""
    arc = _arc(points)
    a = _at(points, arc, at * arc[-1])
    b = _at(points, arc, min(arc[-1], (at + span) * arc[-1]))
    return b - a


def _signed_deg(a: np.ndarray, b: np.ndarray) -> float:
    """Signed horizontal angle from ``a`` to ``b`` (degrees, counter-clockwise)."""
    if np.hypot(*a[:2]) < 1e-9 or np.hypot(*b[:2]) < 1e-9:
        return float("nan")
    return math.degrees(
        math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1])
    )


def tree_events(work: pd.DataFrame) -> dict:
    """Sequences, lateral records and the stem's heading profile of one tree (a pruned
    working frame, e.g. ``mtg_io.from_mtg``). A decile's composition lists its laterals as
    (event, position within the decile) pairs, so real node clustering survives."""
    tree = _model(work)
    laterals = [b for b in _laterals(tree) if b.length >= MIN_LATERAL_M]
    kids: dict[int, list] = defaultdict(list)
    for b in laterals:
        kids[b.parent_axis].append(b)
    seqs, records = [], []
    for a, rows in tree.axes.items():
        order = int(tree.axis_order[rows[0]])
        length = float(tree.length[rows].sum())
        if order >= MAX_ORDER or length < MIN_PARENT_M:
            continue
        parent_pts = _polyline(tree, rows)
        events = [0] * DECILES
        comps: list[list[tuple]] = [[] for _ in range(DECILES)]
        previous_azimuth = None
        for b in sorted(kids[a], key=lambda b: b.attach_arc):
            r = min(max(b.attach_arc / b.parent_len, 0.0), 0.999)
            d = int(r * DECILES)
            e = _event(tree, b)
            events[d] = max(events[d], e)
            comps[d].append((e, round(r * DECILES - d, 3)))
            head = _heading(b.points)
            if order == 0:  # around the trunk: divergence from the previous sibling
                az = (
                    math.degrees(math.atan2(head[1], head[0]))
                    if np.hypot(*head[:2]) > 1e-9
                    else float("nan")
                )
                dphi = (
                    (az - previous_azimuth) % 360
                    if previous_azimuth is not None and np.isfinite(az)
                    else float("nan")
                )
                if np.isfinite(az):
                    previous_azimuth = az
            else:  # on a limb: relative to the limb's heading where it leaves
                dphi = _signed_deg(_heading(parent_pts, max(0.0, r - 0.05), 0.1), head)
            elev, azim = headings(b.points)
            records.append(
                {
                    "order": order + 1,
                    "zone": int(r * ZONES),
                    "event": e,
                    "len_rel": b.length / b.parent_len,
                    "dphi": dphi,
                    "elev": elev,
                    "azim": azim,
                }
            )
        seqs.append(
            {
                "order": order,
                "events": events,
                "comps": [tuple(sorted(c, key=lambda x: x[1])) for c in comps],
            }
        )
    trunk_elev, trunk_azim = headings(_polyline(tree, tree.axes[0]))
    return {
        "height_m": float(tree.end[:, 2].max()),
        "seqs": seqs,
        "laterals": records,
        "trunk_elev": trunk_elev,
        "trunk_azim": trunk_azim,
    }


# --- the model ----------------------------------------------------------------------------


def _counts(trees: list[dict]) -> np.ndarray:
    """Transition counts [order, decile, previous, next]; decile 0 starts from 'none'."""
    c = np.zeros((MAX_ORDER, DECILES, len(SYMBOLS), len(SYMBOLS)))
    for t in trees:
        for s in t["seqs"]:
            prev = 0
            for k, e in enumerate(s["events"]):
                c[s["order"], k, prev, e] += 1
                prev = e
    return c


def _pools(trees: list[dict]) -> tuple[dict, dict, list]:
    comps: dict = defaultdict(list)
    lats: dict = defaultdict(list)
    for t in trees:
        for s in t["seqs"]:
            for k, (e, comp) in enumerate(zip(s["events"], s["comps"], strict=True)):
                if e:
                    comps[(s["order"], k, e)].append(comp)
        for r in t["laterals"]:
            lats[(r["order"], r["zone"], r["event"])].append(r)
    trunks = [(t["trunk_elev"], t["trunk_azim"]) for t in trees]
    return dict(comps), dict(lats), trunks


@dataclass
class BranchingModel:
    species_key: str
    height_class: str
    n_trees: int
    height_m: float
    chain: np.ndarray  # P[order, decile, previous, next]
    comps: dict
    comps_species: dict
    lats: dict
    lats_species: dict
    trunks: list
    rng: np.random.Generator = field(default_factory=np.random.default_rng, repr=False)

    # sampling, as the L-Py rules call it
    def seed(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)

    def step(self, order: int, k: int, prev: int) -> int:
        if order >= MAX_ORDER:
            return 0
        return int(self.rng.choice(len(SYMBOLS), p=self.chain[order, k, prev]))

    def _pick(self, pools: list[list]):
        for pool in pools:
            if len(pool) >= MIN_POOL or (pool and pool is pools[-1]):
                return pool[self.rng.integers(len(pool))]
        merged = [x for pool in pools for x in pool]
        return merged[self.rng.integers(len(merged))] if merged else None

    def composition(self, order: int, k: int, e: int) -> tuple:
        if e == 0:
            return ()
        near = [
            x
            for kk in range(DECILES)
            for x in self.comps_species.get((order, kk, e), [])
        ]
        comp = self._pick(
            [
                self.comps.get((order, k, e), []),
                self.comps_species.get((order, k, e), []),
                near,
            ]
        )
        return comp if comp is not None else ((e, 0.5),)

    def lateral(self, order: int, zone: int, e: int) -> dict | None:
        near = [
            x for z in range(ZONES) for x in self.lats_species.get((order, z, e), [])
        ]
        return self._pick(
            [
                self.lats.get((order, zone, e), []),
                self.lats_species.get((order, zone, e), []),
                near,
            ]
        )

    def trunk(self) -> tuple[np.ndarray, np.ndarray]:
        """A real stem's (elevations, azimuths) profile."""
        return self.trunks[self.rng.integers(len(self.trunks))]

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        rng, self.rng = self.rng, None
        try:
            path.write_bytes(pickle.dumps(self))
        finally:
            self.rng = rng
        return path

    @staticmethod
    def load(path: Path) -> BranchingModel:
        m = pickle.loads(Path(path).read_bytes())
        m.rng = np.random.default_rng()
        return m

    def chain_table(self) -> pd.DataFrame:
        """The fitted chain as a long table (order, decile, previous, next, probability)."""
        rows = []
        for o in range(MAX_ORDER):
            for k in range(DECILES):
                for i, prev in enumerate(SYMBOLS):
                    for j, nxt in enumerate(SYMBOLS):
                        rows.append(
                            {
                                "order": o,
                                "decile": k + 1,
                                "previous": prev,
                                "next": nxt,
                                "p": float(self.chain[o, k, i, j]),
                            }
                        )
        return pd.DataFrame(rows)


def fit(
    group: list[dict],
    species: list[dict],
    species_key: str,
    height_class: str,
    prior: float = PRIOR,
) -> BranchingModel:
    """Fit a height class (``group``) against its whole species (``species``)."""
    cs = _counts(species)
    p_species = (cs + 1.0) / (cs.sum(axis=-1, keepdims=True) + len(SYMBOLS))
    cg = _counts(group)
    chain = (cg + prior * p_species) / (cg.sum(axis=-1, keepdims=True) + prior)
    comps, lats, trunks = _pools(group)
    comps_s, lats_s, _ = _pools(species)
    return BranchingModel(
        species_key=species_key,
        height_class=height_class,
        n_trees=len(group),
        height_m=float(np.median([t["height_m"] for t in group])),
        chain=chain,
        comps=comps,
        comps_species=comps_s,
        lats=lats,
        lats_species=lats_s,
        trunks=trunks,
    )


# --- generation ---------------------------------------------------------------------------


def head_up(elevation_deg: float, azimuth_deg: float) -> tuple[float, ...]:
    """``SetHead`` arguments (heading, up) for an elevation and azimuth, with the up vector
    in the vertical plane, so that L-Py's ``^(d)`` raises the elevation by exactly d."""
    t, p = math.radians(elevation_deg), math.radians(azimuth_deg)
    h = (math.cos(t) * math.cos(p), math.cos(t) * math.sin(p), math.sin(t))
    u = (-math.sin(t) * math.cos(p), -math.sin(t) * math.sin(p), math.cos(t))
    return (*h, *u)


def generate(
    model: BranchingModel,
    height_m: float | None = None,
    seed: int = 0,
    derivation_length: int = 3 * DECILES + 2,
):
    """Run the L-Py rule set once; returns the derived L-string."""
    import openalea.lpy as lpy

    model.seed(seed)
    ls = lpy.Lsystem()
    ls.setCode(
        LPY_FILE.read_text(encoding="utf-8"),
        {
            "model": model,
            "HEIGHT": float(height_m or model.height_m),
            "DERIVATION": derivation_length,
            "SUBSTEPS": SUBSTEPS,
            "ZONES": ZONES,
            "MIN_LEN": MIN_GENERATED_M,
            "head_up": head_up,
            "rng": model.rng,
        },
    )
    return ls, ls.derive()


def lstring_cylinders(lstring) -> pd.DataFrame:
    """Cylinders of a derived L-string, by a turtle that mirrors L-Py's for the modules the
    rule set emits (``F``, ``^``, ``@R``, ``[``, ``]``): start/end, parent row, order."""
    pos = np.zeros(3)
    h = np.array([0.0, 0.0, 1.0])
    u = np.array([1.0, 0.0, 0.0])
    last, order = -1, 0
    stack = []
    start, end, parent, orders = [], [], [], []
    for m in lstring:
        name = m.name
        if name == "F":
            nxt = pos + h * float(m[0])
            start.append(pos.copy())
            end.append(nxt.copy())
            parent.append(last)
            orders.append(order)
            last = len(start) - 1
            pos = nxt
        elif name == "^":
            a = math.radians(float(m[0]))
            h, u = h * math.cos(a) + u * math.sin(a), u * math.cos(a) - h * math.sin(a)
        elif name == "@R":
            h = np.array([float(m[i]) for i in range(3)])
            u = np.array([float(m[i]) for i in range(3, 6)])
        elif name == "[":
            stack.append((pos.copy(), h.copy(), u.copy(), last, order))
            order += 1
        elif name == "]":
            pos, h, u, last, order = stack.pop()
    return pd.DataFrame(
        {
            "parent": parent,
            "start_x": [p[0] for p in start],
            "start_y": [p[1] for p in start],
            "start_z": [p[2] for p in start],
            "end_x": [p[0] for p in end],
            "end_y": [p[1] for p in end],
            "end_z": [p[2] for p in end],
            "order": orders,
        }
    )
