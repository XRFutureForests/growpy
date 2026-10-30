"""growpy-export-budget: the PCG join rule, the scenario budget and the per-tree table."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pandas as pd
import pytest

from growpy.tools import export_budget as eb

BONES = {
    "SK_EuropeanBeech_r07_h10m": 1000,
    "SK_EuropeanBeech_r07_h20m": 2000,
    "SK_EuropeanBeech_r10_h20m": 3000,
    "SK_DouglasFir_r07_h30m": 4000,
    "SK_SmallLeavedLinden_r07_h05m": 500,
}


def tree(species, h, x, y=0.0, status=None, variant=2, year=2025, code=10):
    return {
        "species_name": species,
        "height_m": h,
        "original_x": x,
        "original_y": y,
        "tree_status_id": status,
        "variant_id": variant,
        "simulation_year": year,
        "scenario_code": code,
    }


def test_mesh_names():
    assert eb.parse_mesh("SK_SmallLeavedLinden_r07_h05m") == (
        "small_leaved_linden",
        7,
        5,
    )
    assert eb.parse_mesh("SKM_Branch_A") is None
    cat = eb.build_catalog(BONES)
    assert cat["Small-leaved Linden"] == {(7, 5): "SK_SmallLeavedLinden_r07_h05m"}
    assert set(cat["European Beech"]) == {(7, 10), (7, 20), (10, 20)}


def test_stage_and_radius_class():
    rule = eb.SpawnRule()
    assert eb.height_stage(12.4, rule) == 10
    assert eb.height_stage(12.5, rule) == 15  # round half up, as FMath::RoundToDouble
    assert eb.height_stage(2.0, rule) == 5
    assert eb.height_stage(60.0, rule) == 45
    assert eb.radius_class(850, rule) == 7
    assert eb.radius_class(851, rule) == 10
    assert eb.radius_class(float("inf"), rule) == 10


def test_pick_mesh_falls_back_to_nearest_cell():
    cat = eb.build_catalog(BONES)
    assert eb.pick_mesh(cat, "European Beech", 20, 7) == "SK_EuropeanBeech_r07_h20m"
    # missing stage: same radius class, closest stage, the smaller on a tie
    assert eb.pick_mesh(cat, "European Beech", 15, 7) == "SK_EuropeanBeech_r07_h10m"
    assert eb.pick_mesh(cat, "European Beech", 45, 7) == "SK_EuropeanBeech_r07_h20m"
    # missing radius class: any class of the species
    assert eb.pick_mesh(cat, "Douglas Fir", 30, 10) == "SK_DouglasFir_r07_h30m"
    assert eb.pick_mesh(cat, "Wild Service Tree", 20, 7) is None


def test_place_step_status_dead_and_stand_in():
    rule = eb.SpawnRule()
    cat = eb.build_catalog(BONES)
    rows = [
        tree("European Beech", 20, 0.0),
        tree("European Beech", 20, 5.0),  # within 8.5 m -> r07
        tree("European Beech", 20, 100.0),  # alone -> r10
        tree("European Larch", 30, 160.0),  # stand-in Douglas Fir
        tree("European Beech", 10, 200.0, status=4),  # dead: static twin
        tree("European Beech", 10, 300.0, status=5),  # harvested: not placed
        tree("Wild Service Tree", 10, 205.0),
    ]
    step = eb.place_step(rows, cat, rule)
    assert step["placed"] == 6
    assert step["dead"] == 1
    assert step["meshes"] == {
        "SK_EuropeanBeech_r07_h20m": 2,
        "SK_EuropeanBeech_r10_h20m": 1,
        "SK_DouglasFir_r07_h30m": 1,
    }
    assert step["unmatched"] == {"Wild Service Tree": 1}


@pytest.fixture
def twin_cache(tmp_path):
    site = tmp_path / "cache" / "SITE"
    site.mkdir(parents=True)
    base = [tree("European Beech", 10, 0.0), tree("European Beech", 10, 5.0)]
    later = [
        tree("European Beech", 20, 0.0, status=1, variant=7, year=2050),
        tree("European Beech", 20, 5.0, status=1, variant=7, year=2050),
    ]
    thin = [
        tree("European Beech", 20, 0.0, status=1, variant=9, year=2050, code=20),
        tree("European Beech", 20, 5.0, status=5, variant=9, year=2050, code=20),
        tree("Douglas Fir", 30, 2.0, status=1, variant=9, year=2050, code=20),
    ]
    (site / "TreeDataCache.json").write_text(json.dumps(base + later))
    (site / "TreeData_20Cache.json").write_text(json.dumps(base + thin))
    (site / "TreeData_21Cache.json").write_text(json.dumps({"code": "57014"}))
    return tmp_path / "cache"


def test_scenario_table(twin_cache):
    steps, meshes = eb.scenario_table(twin_cache, BONES, eb.SpawnRule())
    key = steps.set_index(["scenario_code", "year"])
    assert len(steps) == 4  # the error body of _21 is skipped
    assert key.loc[(10, 2025), "bones"] == 1000
    assert key.loc[(10, 2050), "bones"] == 2000
    # thinning: the beech neighbour is harvested, the fir 2 m away keeps r07
    assert key.loc[(20, 2050), "bones"] == 2000 + 4000
    assert key.loc[(20, 2050), "trees_placed"] == 2
    pct = round(100 * 16 * 6000 / eb.SLOTS, 1)
    assert key.loc[(20, 2050), "buffer_pct"] == pct
    # switch into 20/2050: full = 6000 + the heavier source (10/2050, 2000);
    # shared meshes once: worst source is 20/2025 (beech h10 + 6000 = 7000)
    assert key.loc[(20, 2050), "switch_pct"] == round(100 * 16 * 8000 / eb.SLOTS, 1)
    assert key.loc[(20, 2050), "switch_union_pct"] == round(
        100 * 16 * 7000 / eb.SLOTS, 1
    )
    assert set(steps.gate) == {"ok"}
    assert len(meshes) == 5


def test_gate_flags():
    row = SimpleNamespace(
        bones=70_000,
        distinct_meshes=31,
        buffer_pct_with_floor=101.0,
        switch_pct=120.0,
        switch_union_pct=90.0,
    )
    assert eb.gate_step(row) == "bones>65k meshes>30 buffer>100% switch>100%?"


def test_tree_rows_plan_and_triangles(tmp_path, monkeypatch):
    import growpy.config.pve_calibration as cal

    monkeypatch.setattr(
        cal,
        "load_pve_calibration",
        lambda: SimpleNamespace(bone_reduction_per_species={"european_beech": 0.6}),
    )
    forest = tmp_path / "forest"
    r07 = forest / "european_beech" / "r07"
    r07.mkdir(parents=True)
    growth = {"points": {"positions": [[0, 0, 0]] * 5}, "primitives": {"points": [[0, 1], [1, 2]]}}  # fmt: skip
    for h in (10, 20):
        (r07 / f"European_Beech_r07_h{h}m_d15cm_full_growth_data.json").write_text(
            json.dumps(growth)
        )
    floor = {"points": {"positions": [[0, 0, 0]] * 4}, "primitives": {"points": [[0, 1]]}}  # fmt: skip
    (r07 / "European_Beech_r07_h10m_d15cm_full_growth_data.floor.json").write_text(
        json.dumps(floor)
    )
    inst = forest / "Instances"
    inst.mkdir()
    (inst / "leaf_a_static.usda").write_text("int[] faceVertexCounts = [3, 4, 4]\n")
    (inst / "leaf_b_static.usda").write_text("int[] faceVertexCounts = [3]\n")
    plan = forest / "unreal_scripts" / "pve_export_manifest.json"
    plan.parent.mkdir()
    palette = ["/Game/F/SM_leaf_a_ZUP", "/Game/F/SM_leaf_b_ZUP"]
    meshes = [
        {
            "mesh_name": f"SK_EuropeanBeech_r07_h{h}m",
            "growth_json": str(r07 / f"European_Beech_r07_h{h}m_d15cm_full_growth_data.floor.json"),
            "predicted_instances": 100,
            "capped": False,
        }
        for h in (10, 20)
    ]  # fmt: skip
    plan.write_text(
        json.dumps({"graphs": [{"palette_meshes": palette, "meshes": meshes}]})
    )
    # h20 regrown after the plan: its plan counts are stale
    stale = r07 / "European_Beech_r07_h20m_d15cm_full_growth_data.json"
    t = plan.stat().st_mtime + 60
    os.utime(stale, (t, t))
    bones = {"SK_EuropeanBeech_r07_h10m": 3000, "SK_EuropeanBeech_r07_h20m": 1000}
    df = eb.tree_rows(bones, forest, plan).set_index("mesh")
    h10, h20 = df.loc["SK_EuropeanBeech_r07_h10m"], df.loc["SK_EuropeanBeech_r07_h20m"]
    assert h10.bone_reduction == 0.6
    assert (h10.points, h10.branches) == (4, 1)  # the crown-floor copy the graph reads
    assert bool(h10.plan_current) and h10.parts_plan == 100
    assert (h10.part_tris_min, h10.part_tris_max) == (1, 5)
    assert (h10.tris_lo, h10.tris_hi) == (100, 500)
    assert h10.gate == "bones>2166/mesh"
    assert not bool(h20.plan_current) and pd.isna(h20.parts_plan)
    assert h20.unique_parts == 2 and h20.gate == "ok"


def test_main_writes_the_tables(tmp_path, twin_cache, monkeypatch):
    import growpy.config.pve_calibration as cal

    monkeypatch.setattr(
        cal,
        "load_pve_calibration",
        lambda: SimpleNamespace(bone_reduction_per_species={}),
    )
    bones = tmp_path / "bones.json"
    bones.write_text(json.dumps({k: str(v) for k, v in BONES.items()}))
    out = tmp_path / "out"
    rc = eb.main(
        [
            "--twin-cache", str(twin_cache), "--bones", str(bones),
            "--forest-dir", str(tmp_path / "none"), "--out-dir", str(out),
            "--measured", "SITE:10:2025=0.4", "--floor-bones", "100",
        ]
    )  # fmt: skip
    assert rc == 0
    steps = pd.read_csv(out / "export_budget_scenarios.csv")
    assert steps.measured_pct.notna().sum() == 1
    first = steps.iloc[0]
    assert first.buffer_pct_with_floor == round(100 * 16 * 1100 / eb.SLOTS, 1)
    for name in ("trees", "species", "meshes"):
        assert (out / f"export_budget_{name}.csv").is_file()
