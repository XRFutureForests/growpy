# ruff: noqa: E501
"""E144: per-graph distributor comparison table (comparison.md + comparison.csv) from pve59_extract's graphs/*.json.

    python -m growpy.tools.pve59_compare <extract dir> [<pve_export_manifest.json>]

One row per graph, distributor layers aggregated (min / median / max), parts from the registry tags. The E143 row also
carries the plan values of the pve_export_manifest (what growpy asked for). Internal analysis of third-party packs.
"""

from __future__ import annotations

import csv
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/output/pve59_extract")
PICK = [  # (label, graph json stem suffix)
    ("GV maple (Simple_Maple)", "PVE_GV_Simple_Maple"),
    ("GV conifer", "PVE_GV_Conifer"),
    ("GV sycamore (58 variations)", "PVE_GV_SycamoreMaple"),
    ("GV oak 01 (34)", "PVE_GV_EnglishOak_01"),
    ("GV oak 02 (18)", "PVE_GV_EnglishOak_02"),
    ("GV oak 03 (10)", "PVE_GV_EnglishOak_03"),
    ("MP Norway maple", "PVE_Norway_Maple_Forest_01"),
    ("MP European beech", "PVE_European_Beech_01"),
    ("MP English oak", "PVE_English_Oak_Forest_01"),
    ("MP silver birch", "PVE_Silver_Birch_01"),
    ("MP Yoshino cherry", "PVE_Yoshino_Cherry_01"),
    ("MP hornbeam", "PVE_Tree_Hornbeam_01"),
    ("MP Norway spruce", "PVE_Norway_Spruce_01"),
    ("MP Baltic pine", "PVE_Baltic_Pine_01"),
    ("OURS E143 au04s2 h20", "PVG_SycamoreMaple_1"),
]


def rng(v, f="{:g}"):
    v = [x for x in v if isinstance(x, (int, float))]
    if not v:
        return "-"
    return (
        f.format(min(v))
        if min(v) == max(v)
        else f"{f.format(min(v))}..{f.format(st.median(v))}..{f.format(max(v))}"
    )


def ramp_kind(r):
    if r == "default" or r is None:
        return "default"
    a, b = r[0][1], r[-1][1]
    return (
        "flat"
        if abs(a - b) < 1e-6
        else (f"rising {a:g}>{b:g}" if b > a else f"falling {a:g}>{b:g}")
    )


def parts_info(layers, tags):
    meshes = {}
    for d in layers:
        for p in d["parts"]:
            if p.get("Mesh"):
                meshes[p["Mesh"].split(".")[0]] = p.get("tags", {})
    tri = [int(t["Triangles"]) for t in meshes.values() if t.get("Triangles")]
    size = []
    for t in meshes.values():
        if t.get("ApproxSize"):
            x = [float(s) for s in t["ApproxSize"].split("x")]
            size.append(max(x))
    return len(meshes), tri, size


rows = []
for label, stem in PICK:
    f = next(iter((ROOT / "graphs").glob(f"*__{stem}.json")), None)
    if not f:
        continue
    g = json.loads(f.read_text(encoding="utf-8"))
    L = g["summary"]["distributors"]
    P = [d for d in L if d["mode"] == "ParametricSettings"]
    H = [d for d in L if d["mode"] != "ParametricSettings"]
    n_parts, tri, size = parts_info(L, None)
    row = {
        "graph": label,
        "layers": len(L),
        "parametric": len(P),
        "hormone": len(H),
        "density": rng([d["density"] for d in P], "{:g}"),
        "rel_start": rng([d["rel_start"] for d in P], "{:.2f}"),
        "rel_end": rng([d["rel_end"] for d in P], "{:.2f}"),
        "gen_start": ",".join(
            sorted({str(d["gen_start"]) for d in P if d["gen_start"] is not None})
        )
        or "-",
        "gen_end": ",".join(
            sorted({str(d["gen_end"]) for d in P if d["gen_end"] is not None})
        )
        or "-",
        "basis": ",".join(sorted({d["spacing_basis"] for d in P})) or "-",
        "base_scale": rng([d["base_scale"] for d in L], "{:.2f}"),
        "scale_ramp": ",".join(
            f"{k}x{v}"
            for k, v in Counter(ramp_kind(d["scale_ramp"]) for d in L).most_common(3)
        ),
        "scale_random": ",".join(
            sorted({f"{d['scale_random'][0]:g}-{d['scale_random'][1]:g}" for d in L})[
                :3
            ]
        ),
        "axil": rng([d["axil"] for d in L], "{:.0f}"),
        "axil_random": ",".join(
            sorted(
                {
                    f"{d['axil_random'][0]:g}..{d['axil_random'][1]:g}"
                    for d in P
                    if d["axil_random"] != [0.0, 0.0]
                }
            )
        )
        or "-",
        "phyllotaxy": ",".join(
            f"{k}x{v}" for k, v in Counter(d["phyllotaxy"] for d in L).most_common(2)
        ),
        "aim": ",".join(
            f"{k}x{v}"
            for k, v in Counter(a[1] for d in L for a in d["aim"]).most_common(3)
        )
        or "-",
        "face": ",".join(
            f"{k}x{v}"
            for k, v in Counter(a[1] for d in L for a in d["face"]).most_common(3)
        )
        or "-",
        "conditions": ",".join(
            f"{k}x{v}"
            for k, v in Counter(
                c
                for d in L
                for c, v2 in d["conditions"].items()
                if v2.get("Weight", 1) != 0
            ).most_common(5)
        )
        or "-",
        "rpy": ",".join(
            f"{k}x{v}"
            for k, v in Counter(r[0] for d in L for r in d["rpy"]).most_common(3)
        )
        or "-",
        "parts": n_parts,
        "part_tris": rng(tri, "{:.0f}"),
        "part_max_cm": rng(size, "{:.0f}"),
    }
    oth = g["summary"]["other"]
    for k, v in oth.items():
        pr = v["props"]
        if v["class"] == "PVCarveSettings":
            row["carve"] = json.dumps(pr, default=str)[:160]
        if v["class"] == "PVGravitySettings":
            row["gravity"] = json.dumps(pr, default=str)[:160]
        if v["class"] == "PVBoneReductionSettings":
            row["bone_reduction"] = json.dumps(pr, default=str)[:160]
        if v["class"] == "PVRemoveBranchesSettings":
            row["remove_branches"] = json.dumps(pr, default=str)[:160]
        if v["class"] == "PVExportSettings":
            ex = pr.get("ExportSettings", {})
            row["export"] = json.dumps(
                {
                    k: ex.get(k)
                    for k in (
                        "ExportMeshType",
                        "NaniteShapePreservation",
                        "bCreateNaniteFoliage",
                        "CollisionGeneration",
                    )
                    if k in ex
                },
                default=str,
            )
    rows.append(row)

man = (
    json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    if len(sys.argv) > 2
    else {"graphs": [{"meshes": [{}]}]}
)  # optional: the plan manifest to quote
m = man["graphs"][0]["meshes"][0]
plan = {
    k: m.get(k)
    for k in (
        "branch_density",
        "relative_start",
        "base_scale",
        "randomize_scale",
        "randomize_axil_angle",
        "spacing_ramp",
        "layers",
        "instances_per_branch",
        "predicted_instances",
        "branches",
        "height_m",
    )
}
(ROOT / "comparison.json").write_text(
    json.dumps({"rows": rows, "our_plan_manifest_r1_au04s2_h20": plan}, indent=1),
    encoding="utf-8",
)
keys = []
for r in rows:
    for k in r:
        if k not in keys:
            keys.append(k)
with open(ROOT / "comparison.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=keys)
    w.writeheader()
    w.writerows(rows)
md = ["| " + " | ".join(keys[:19]) + " |", "|" + "---|" * 19]
for r in rows:
    md.append("| " + " | ".join(str(r.get(k, "")) for k in keys[:19]) + " |")
md += ["", "Our E143 plan (pve_export_manifest, r1 au04s2 h20): " + json.dumps(plan)]
(ROOT / "comparison.md").write_text("\n".join(md), encoding="utf-8")
print(len(rows), "graphs ->", ROOT / "comparison.md")
