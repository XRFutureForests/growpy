# ruff: noqa: E501, E731, C408, C416
"""E144 offline half: T3D of PVE graphs (from ue_scripts/pve59_dump.py) -> one JSON per graph + comparison tables.

    python -m growpy.tools.pve59_extract <extract dir>      (default data/output/pve59_extract)

A T3D omits values equal to the class default, so every distributor field is filled from the plugin headers'
defaults (FPVParametric*/FPVHormone* structs, UE 5.8 and 5.9 identical) before it is compared. Internal analysis of
third-party packs: the output stays under data/output, never in a public commit.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

DEFAULT_DIR = Path("data/output/pve59_extract")

# ------------------------------------------------------------------ UE text values

KEY_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*(?:\(\d+\))?)=")
BIG = 300_000  # property text longer than this is kept as a length only (embedded growth data)


def parse_val(s: str, i: int = 0):
    """Parse one UE property value starting at s[i]; returns (value, next index)."""
    if s[i] == "(":
        i += 1
        items = []
        while s[i] != ")":
            m = KEY_RE.match(s, i)
            key = None
            if m:
                key = m.group(1)
                i = m.end()
            v, i = parse_val(s, i)
            items.append((key, v))
            if s[i] == ",":
                i += 1
        i += 1
        if items and all(k is None for k, _ in items):
            return [v for _, v in items], i
        d = {}
        for k, v in items:
            if k is None:
                d.setdefault("_list", []).append(v)
            elif re.search(r"\(\d+\)$", k):
                d.setdefault(re.sub(r"\(\d+\)$", "", k), []).append(v)
            else:
                d[k] = v
        return d, i
    if s[i] == '"':
        j = i + 1
        while s[j] != '"' or s[j - 1] == "\\":
            j += 1
        return s[i + 1 : j], j + 1
    j = i
    depth = 0
    while j < len(s) and not (depth == 0 and s[j] in ",)"):
        depth += s[j] == "("
        depth -= s[j] == ")"
        j += 1
    tok = s[i:j]
    for conv in (int, float):
        try:
            return conv(tok), j
        except ValueError:
            pass
    return {"True": True, "False": False}.get(tok, tok), j


def read_t3d(path: Path) -> str:
    b = path.read_bytes()
    return b.decode(
        "utf-16" if b[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8", errors="replace"
    )


def parse_t3d(path: Path) -> dict:
    """Nodes (settings class + non-default props), edges (upstream pin -> downstream pin), pin labels, asset-level props."""
    text = read_t3d(path)
    nodes: dict[str, dict] = {}
    pins: dict[str, str] = {}
    edges: list[dict] = []
    stack: list[dict] = []
    for ln in text.splitlines():
        t = ln.strip()
        m = re.match(
            r'Begin Object (?:Class=\S+ )?Name="([^"]+)"(?: Archetype="[^"]*")? ExportPath="([^"]*)"',
            t,
        )
        if m:
            name, ep = m.groups()
            cm = re.match(r"/Script/([A-Za-z]+)\.(\w+)'", ep)
            stack.append(
                {
                    "name": name,
                    "ep": ep,
                    "mod": cm.group(1) if cm else "",
                    "cls": cm.group(2) if cm else "",
                    "props": {},
                }
            )
            continue
        if t.startswith("End Object"):
            o = stack.pop()
            parts = (
                o["ep"].rstrip("'\"").split("'")[-1].split(":")[-1].split(".")
            )  # graph . node . obj
            if o["mod"] == "ProceduralVegetation" and len(parts) >= 3:
                nodes[parts[-2]] = {
                    "class": o["cls"],
                    "settings_object": o["name"],
                    "props": o["props"],
                }
            elif o["cls"] == "PCGPin" and len(parts) >= 3:
                lab = o["props"].get("Properties", {})
                if isinstance(lab, dict) and "Label" in lab:
                    pins[f"{parts[-2]}.{o['name']}"] = lab["Label"]
            elif o["cls"] == "PCGEdge" and "InputPin" in o["props"]:
                a = o["props"]["InputPin"].rstrip("'").split(":")[-1].split(".")
                b2 = o["props"]["OutputPin"].rstrip("'").split(":")[-1].split(".")
                edges.append(
                    {"from": a[-2], "from_pin": a[-1], "to": b2[-2], "to_pin": b2[-1]}
                )
            elif o["cls"] == "PCGNode" and len(parts) >= 2:
                nodes.setdefault(parts[-1], {"class": "PCGNode", "props": {}})[
                    "node_props"
                ] = o["props"]
            continue
        if stack and "=" in t and not t.startswith("Begin"):
            k, v = t.split("=", 1)
            if len(v) > BIG:
                val = f"<{len(v)} chars>"
            else:
                try:
                    val, _ = parse_val(v)
                except Exception:
                    val = v
            km = re.match(r"(\w+)\((\d+)\)$", k)
            if km:
                stack[-1]["props"].setdefault(km.group(1), []).append(val)
            else:
                stack[-1]["props"][k] = val
    for e in edges:
        e["from_label"] = pins.get(f"{e['from']}.{e['from_pin']}")
        e["to_label"] = pins.get(f"{e['to']}.{e['to_pin']}")
    refs = sorted(
        set(
            re.findall(r'"?(/(?:Game|ProceduralVegetationEditor)/[A-Za-z0-9_/]+)', text)
        )
    )
    return {"source": path.name, "nodes": nodes, "edges": edges, "refs": refs}


# ------------------------------------------------------------------ distributor normalisation


def ramp(d) -> list | str:
    """EditorCurveData keys -> [[t, v], ...]; empty keys = the struct's constructor default."""
    try:
        keys = d["EditorCurveData"].get("Keys")
    except (KeyError, AttributeError, TypeError):
        return "default"
    if not keys:
        return "default"
    return [[k.get("Time", 0.0), k.get("Value", 0.0)] for k in keys]


def g(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def normalise_distributor(props: dict) -> dict:
    mode = props.get("Mode", "HormoneBasedSettings")
    out = {"mode": mode}
    if mode == "ParametricSettings":
        P = props.get("ParametricSettings", {})
        sp, ph, an, sc = (
            g(P, k, default={})
            for k in (
                "SpacingSettings",
                "PhyllotaxySettings",
                "AngleSettings",
                "ScaleSettings",
            )
        )
        out |= {
            "density": sp.get("BranchDensity", 45),
            "rel_start": sp.get("RelativeStart", 0.0),
            "rel_end": sp.get("RelativeEnd", 1.0),
            "gen_start": sp.get("StartGeneration", 0)
            if sp.get("LimitStartGeneration")
            else None,
            "gen_end": sp.get("EndGeneration", 0)
            if sp.get("LimitEndGeneration")
            else None,
            "spacing_basis": sp.get("SpacingBasis", "Plant"),
            "spacing_ramp": ramp(sp.get("SpacingRamp")),
            "phyllotaxy": f"{ph.get('PhyllotaxyType', 'Spiral')}/{ph.get('PhyllotaxyFormation', 'Octastichous')}",
            "single_bud_tip": ph.get("bSingleBudTip", True),
            "phyllo_add_angle": ph.get("PhyllotaxyAdditionalAngle", 0.0),
            "node_buds": [ph.get("MinimumNodeBuds", 2), ph.get("MaximumNodeBuds", 3)],
            "rotation": an.get("Rotation", 0.0),
            "axil": an.get("AxilAngle", 35.0),
            "axil_random": [
                an.get("RandomizeAxilAngleMinimum", 0.0),
                an.get("RandomizeAxilAngleMaximum", 0.0),
            ],
            "axil_ramp_basis": an.get("AxilAngleRampBasis", "Plant"),
            "axil_ramp": ramp(an.get("AxilAngleRamp")),
            "scale_basis": sc.get("ScaleRampBasis", "Plant"),
            "base_scale": sc.get("BaseScale", 1.0),
            "branch_scale_impact": sc.get("BranchScaleImpact", 0.0),
            "scale_random": [
                sc.get("RandomizeScaleMinimum", 1.0),
                sc.get("RandomizeScaleMaximum", 1.0),
            ],
            "scale_ramp": ramp(sc.get("ScaleRamp"))
            if ramp(sc.get("ScaleRamp")) != "default"
            else [[0.0, 1.0], [1.0, 0.1]],
        }
    else:
        H = props.get("HormoneBasedSettings", {})
        ds, sc, an, ph = (
            g(H, k, default={})
            for k in (
                "DistributionSettings",
                "ScaleSettings",
                "AngleSettings",
                "PhyllotaxySettings",
            )
        )
        out |= {
            "ethylene": ds.get("EthyleneThreshold", 0.85),
            "instance_spacing": ds.get("InstanceSpacing", 0.3),
            "spacing_ramp": ramp(ds.get("InstanceSpacingRamp")),
            "spacing_ramp_effect": ds.get("InstanceSpacingRampEffect", 0.0),
            "max_per_branch": ds.get("MaxPerBranch", -1),
            "base_scale": sc.get("BaseScale", 1.0),
            "min_scale": sc.get("MinScale", 0.5),
            "max_scale": sc.get("MaxScale", 1.0),
            "scale_random": [
                sc.get("RandomScaleMin", 1.0),
                sc.get("RandomScaleMax", 1.0),
            ],
            "branch_scale_impact": sc.get("BranchScaleImpact", 0.0),
            "scale_ramp": ramp(sc.get("ScaleRamp")),
            "axil": an.get("AxilAngle", 35.0)
            if an.get("OverrideAxilAngle", True)
            else "inherited",
            "axil_ramp": ramp(an.get("AxilAngleRamp")),
            "axil_ramp_upper": an.get("AxilAngleRampUpperValue", 45.0),
            "axil_ramp_effect": an.get("AxilAngleRampEffect", 0.0),
            "phyllotaxy": f"{ph.get('PhyllotaxyType', 'Alternate')}/{ph.get('PhyllotaxyFormation', 'Octastichous')}",
            "single_bud_tip": ph.get("bSingleBudTip", True),
            "node_buds": [ph.get("MinimumNodeBuds", 2), ph.get("MaximumNodeBuds", 3)],
        }
    V = props.get("VectorSettings", {})
    out["aim"] = [
        (
            v.get("Vector1") if v.get("bDualVectors") else None,
            v.get("Vector2", "BranchUpFlatten"),
            v.get("Vector2Strength", 1.0),
            v.get("BlendAttribute", "PlantGradient"),
        )
        for v in g(V, "AimVectorSettings", "AimVectors", default=[])
    ]
    out["face"] = [
        (
            v.get("Vector1") if v.get("bDualVectors") else None,
            v.get("Vector2", "Branch"),
            v.get("Vector2Strength", 1.0),
        )
        for v in g(V, "FaceVectorSettings", "FaceVectors", default=[])
    ]
    out["rpy"] = [
        (v.get("Mode", "Roll"), v.get("MinStrength", 0.0), v.get("MaxStrength", 0.0))
        for v in g(V, "RollPitchYawSettings", "RollPitchYaw", default=[])
    ]
    C = props.get("ConditionSettings", {})
    out["conditions"] = {
        k: dict(Weight=v.get("Weight", 1.0), Offset=v.get("Offset", 0.0))
        for k, v in C.items()
        if isinstance(v, dict)
        and k
        in ("Light", "Scale", "UpAlignment", "Tip", "Health", "Height", "Generation")
    }
    out["cond_cutoff"] = [C.get("CutoffThreshold", 0.3), C.get("MinimumCandidates", 1)]
    return out


def chain_order(nodes: dict, edges: list) -> list[str]:
    """Topological order of node names along the (linear) chain; branches appended in edge order."""
    down = {e["from"]: [] for e in edges}
    indeg = dict.fromkeys(nodes, 0)
    for e in edges:
        down.setdefault(e["from"], []).append(e["to"])
        indeg[e["to"]] = indeg.get(e["to"], 0) + 1
    ready = [n for n in indeg if indeg[n] == 0]
    out = []
    while ready:
        n = ready.pop(0)
        out.append(n)
        for m in down.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
    return out


def mesh_pkg(path: str) -> str:
    return path.split(".")[0]


def summarise(t: dict, mesh_tags: dict) -> dict:
    nodes, edges = t["nodes"], t["edges"]
    order = chain_order(nodes, edges)
    ups = lambda n: [e for e in edges if e["to"] == n]  # noqa: E731
    out = {
        "order": [(n, nodes[n]["class"]) for n in order if n in nodes],
        "distributors": [],
        "other": {},
    }
    for n in order:
        c = nodes.get(n)
        if not c:
            continue
        cls, p = c["class"], c["props"]
        if cls == "PVFoliageDistributorSettings":
            d = normalise_distributor(p)
            d["node"] = n
            pal = [
                nodes[e["from"]]
                for e in ups(n)
                if nodes.get(e["from"], {}).get("class") == "PVFoliagePaletteSettings"
            ]
            parts = []
            for pc in pal:
                infos = pc["props"].get("FoliageInfos", [])
                for info in infos:
                    info = dict(info) if isinstance(info, dict) else {"Mesh": str(info)}
                    mp = mesh_pkg(info.get("Mesh", ""))
                    info["tags"] = {
                        k: v for k, v in mesh_tags.get(mp, {}).items() if k != "class"
                    }
                    parts.append(info)
            d["parts"] = parts
            out["distributors"].append(d)
        elif cls != "PCGTrivialSettings":
            out["other"][n] = {"class": cls, "props": p}
    out["order_chain"] = [n for n, _ in out["order"]]
    return out


# ------------------------------------------------------------------ tables


def ramp_s(r) -> str:
    return r if isinstance(r, str) else ">".join(f"{t:g}:{v:g}" for t, v in r)


def layer_row(name: str, i: int, d: dict) -> dict:
    row = {
        "graph": name,
        "layer": i,
        "node": d["node"],
        "mode": d["mode"].replace("Settings", ""),
    }
    keys = (
        "density",
        "rel_start",
        "rel_end",
        "gen_start",
        "gen_end",
        "spacing_basis",
        "spacing_ramp",
        "ethylene",
        "instance_spacing",
        "max_per_branch",
        "base_scale",
        "scale_basis",
        "scale_random",
        "scale_ramp",
        "min_scale",
        "max_scale",
        "branch_scale_impact",
        "phyllotaxy",
        "single_bud_tip",
        "node_buds",
        "axil",
        "axil_random",
        "axil_ramp",
        "rotation",
        "aim",
        "face",
        "rpy",
        "conditions",
        "cond_cutoff",
    )
    for k in keys:
        v = d.get(k)
        row[k] = (
            ramp_s(v)
            if k.endswith("ramp") and v is not None
            else (json.dumps(v) if isinstance(v, (list, dict)) else v)
        )
    row["n_parts"] = len(d["parts"])
    row["parts"] = "; ".join(
        p.get("Mesh", "").split("/")[-1].split(".")[0] for p in d["parts"]
    )
    tri = [p["tags"].get("Triangles") for p in d["parts"] if p.get("tags")]
    row["part_triangles"] = ",".join(str(x) for x in tri if x)
    row["part_extra"] = json.dumps(
        [{k: v for k, v in p.items() if k not in ("Mesh", "tags")} for p in d["parts"]][
            :3
        ]
    )
    return row


def main(argv=None) -> int:
    root = Path((argv or sys.argv[1:] or [DEFAULT_DIR])[0])
    raw = root / "raw"
    dump = json.loads((raw / "dump.json").read_text(encoding="utf-8"))
    mesh_tags = dump.get("mesh_tags", {})
    (root / "graphs").mkdir(exist_ok=True)
    rows, summary, growth = [], {}, {}
    for pkg, info in dump["assets"].items():
        if info.get("growth_data"):
            growth[pkg] = {
                "file_mb": info.get("file_mb"),
                **info["growth_data"],
                "t3d": info.get("t3d"),
            }
        if not info.get("t3d"):
            continue
        name = pkg.strip("/").replace("/", "__")
        t = parse_t3d(Path(info["t3d"]))
        s = (
            summarise(t, mesh_tags)
            if info["class"] == "ProceduralVegetation"
            else {"order": [], "distributors": [], "other": {}}
        )
        rec = {
            "asset": pkg,
            "class": info["class"],
            "export_nodes": info.get("export_nodes"),
            "refs": t["refs"],
            "edges": t["edges"],
            "summary": s,
            "nodes": {n: v for n, v in t["nodes"].items()},
        }
        (root / "graphs" / f"{name}.json").write_text(
            json.dumps(rec, indent=1, default=str), encoding="utf-8"
        )
        summary[pkg] = {
            "layers": len(s["distributors"]),
            "other": {k: v["class"] for k, v in s["other"].items()},
        }
        for i, d in enumerate(s["distributors"]):
            rows.append(layer_row(pkg.split("/")[-1], i, d))
    if rows:
        with open(
            root / "distributor_layers.csv", "w", newline="", encoding="utf-8"
        ) as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (root / "growth_data.json").write_text(
        json.dumps(growth, indent=1), encoding="utf-8"
    )
    (root / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(len(summary), "assets,", len(rows), "distributor layers ->", root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
