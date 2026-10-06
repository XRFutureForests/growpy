"""Convert a QSM point graph (GraphML) to the growth-JSON layout the lab tools read (XRFF-535).

A scanned tree arrives as an undirected graph of points with a position and a radius
(BioDiv-3DTrees ``*_cor_graph.graphml``: ``pos_x``, ``pos_y``, ``pos_z`` with z up, and
``radius`` in metres). growpy's descriptor and audit tools read the generated trees'
growth JSON: y-up metres, the trunk as the first primitive, every other branch a polyline
with a parent branch and a hierarchy number. This converts the one into the other, so a
real tree and a generated tree go through IDENTICAL code.

The decomposition is the usual QSM rule: root the graph at its lowest point, and at every
fork the child with the larger subtree (ties: the larger radius) continues the parent's
branch; every other child starts a new branch one order higher. A branch shares its first
point with the node it grows from.

    growpy-qsm-to-growth graphs/*.graphml --out-dir real/
    growpy-structure-descriptors real/
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_NS = {"g": "http://graphml.graphdrawing.org/xmlns"}


def read_graphml(
    path: Path,
) -> tuple[dict[str, tuple[float, float, float, float]], list[tuple[str, str]]]:
    """``{node id: (x, y, z, radius)}`` and the edge list; z is up in the file."""
    root = ET.parse(path).getroot()
    names = {k.get("id"): k.get("attr.name") for k in root.findall("g:key", _NS)}
    graph = root.find("g:graph", _NS)
    nodes = {}
    for node in graph.findall("g:node", _NS):
        values = {
            names[d.get("key")]: float(d.text) for d in node.findall("g:data", _NS)
        }
        nodes[node.get("id")] = (
            values["pos_x"],
            values["pos_y"],
            values["pos_z"],
            values["radius"],
        )
    edges = [(e.get("source"), e.get("target")) for e in graph.findall("g:edge", _NS)]
    return nodes, edges


def to_growth_json(nodes: dict, edges: list[tuple[str, str]]) -> dict:
    """The growth-JSON dict for one QSM graph (y-up metres, ground at y = 0)."""
    adjacency: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    root = min(nodes, key=lambda n: nodes[n][2])
    parent = {root: None}
    order = [root]
    for node in order:  # breadth-first, builds the rooted tree
        for nxt in adjacency[node]:
            if nxt not in parent:
                parent[nxt] = node
                order.append(nxt)
    children: dict[str, list[str]] = {n: [] for n in order}
    for n in order[1:]:
        children[parent[n]].append(n)
    size = dict.fromkeys(order, 1)
    for n in reversed(order[1:]):  # subtree sizes, leaves first
        size[parent[n]] += size[n]

    def key(
        n,
    ):  # the child that continues the branch: the bigger subtree (TreeQSM radii are too noisy)
        return (size[n], nodes[n][3])

    z0 = nodes[root][2]
    index = {n: i for i, n in enumerate(order)}
    positions = [
        [nodes[n][0], nodes[n][2] - z0, nodes[n][1]] for n in order
    ]  # (x, z up -> y up, y)
    radii = [[nodes[n][3], 0.0] for n in order]

    branches: list[list[int]] = []
    branch_parent: list[int] = []
    hierarchy: list[int] = []
    owner: dict[
        str, int
    ] = {}  # which branch a node lies on (the first one to reach it)
    stack = [(root, None, 1)]  # (first node, parent branch, hierarchy)
    while stack:
        start, parent_branch, level = stack.pop()
        number = len(branches)
        line = [start] if parent_branch is None else [parent[start], start]
        branches.append([])
        branch_parent.append(-1 if parent_branch is None else parent_branch)
        hierarchy.append(level)
        node = start
        while True:
            owner.setdefault(node, number)
            kids = children[node]
            if not kids:
                break
            main = max(kids, key=key)
            for other in kids:
                if other != main:
                    stack.append((other, number, level + 1))
            line.append(main)
            node = main
        branches[number] = [index[n] for n in line]
    return {
        "points": {
            "positions": positions,
            "attributes": {"budLateralMeristem": {"values": radii}},
        },
        "primitives": {
            "points": branches,
            "attributes": {
                "branchNumber": {"values": list(range(len(branches)))},
                "branchParentNumber": {"values": branch_parent},
                "branchHierarchyNumber": {"values": hierarchy},
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("graphs", nargs="+", type=Path, help="GraphML files")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for path in args.graphs:
        nodes, edges = read_graphml(path)
        data = to_growth_json(nodes, edges)
        stem = path.name.replace("_cor_graph.graphml", "").replace(".graphml", "")
        out = args.out_dir / f"{stem}_growth_data.json"
        out.write_text(json.dumps(data), encoding="utf-8")
        print(
            f"{path.name}: {len(nodes)} nodes, {len(data['primitives']['points'])} branches -> {out.name}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
