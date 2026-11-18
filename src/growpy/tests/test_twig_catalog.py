"""Twig catalog (XRFF-684): entries, checks, catalog build."""

import tomllib

from growpy.tools import twig_catalog as tc


def _entry(**kw):
    e = {"id": "european_beech__c_m1", "species": "european_beech", "part_kind": "compound",
         "size_bin": "M", "cut_diameter_mm": [6.0, 12.0], "source": "compound",
         "source_ref": "compound_parts/c.usda", "licence": "own"}  # fmt: skip
    e.update(kw)
    return e


def test_check_entry_bins_and_sources(tmp_path):
    (tmp_path / "compound_parts").mkdir()
    (tmp_path / "compound_parts" / "c.usda").write_text("x")
    assert tc.check_entry(_entry(), tmp_path) == []
    assert any(
        "outside bin M" in p
        for p in tc.check_entry(_entry(cut_diameter_mm=[6.0, 14.0]), tmp_path)
    )
    assert any(
        "not sized" in p for p in tc.check_entry(_entry(cut_diameter_mm=[]), tmp_path)
    )
    assert any(
        "part_kind" in p for p in tc.check_entry(_entry(part_kind="leaf"), tmp_path)
    )
    assert any(
        "missing" in p for p in tc.check_entry(_entry(source_ref="nope.usda"), tmp_path)
    )
    # third-party parts in UE content (E116): a /Game/ path, no file under data/assets
    mp = _entry(
        source="megaplants",
        source_ref="/Game/Megaplant_Library/Tree_Baltic_Pine/Instances/Branch_01",
        licence=tc.SOURCES["megaplants"],
        size_bin="-",
    )
    assert tc.check_entry(mp, tmp_path) == []


def test_build_writes_the_catalog_and_entries_for_finds_a_palette(tmp_path):
    root, assets = tmp_path / "twigs", tmp_path / "assets"
    (assets / "compound_parts").mkdir(parents=True)
    (assets / "compound_parts" / "c.usda").write_text("x")
    tc.write_entry(_entry(), root)
    catalog = tmp_path / "catalog.toml"
    entries, problems = tc.build(root, catalog, assets)
    assert list(entries) == ["european_beech__c_m1"] and problems == {}
    got = tomllib.loads(catalog.read_text(encoding="utf-8"))["twigs"][
        "european_beech__c_m1"
    ]
    assert got["size_bin"] == "M" and got["cut_diameter_mm"] == [6.0, 12.0]
    assert tc.entries_for("european_beech", "compound", catalog) == [
        "european_beech__c_m1"
    ]
    assert tc.entries_for("european_beech", "twigs", catalog) == []


def test_merge_palette_renames_parts_by_bin_and_keeps_the_unbinned_manifest(tmp_path):
    import json

    root, assets = tmp_path / "twigs", tmp_path / "assets"
    (assets / "compound_parts").mkdir(parents=True)
    old = assets / "compound_parts" / "european_beech_pve_palette.json"
    old.write_text(json.dumps({"prototypes": []}))
    for b in ("S", "M"):
        bake = assets / f"bake_{b}"
        bake.mkdir()
        for suffix in ("_static.usda", "_skeletal.usda", "_leaf_area_geom.json"):
            (bake / f"european_beech_compound_p01{suffix}").write_text(b + " def Xform \"european_beech_compound_p01\"")
        (bake / "european_beech_pve_palette.json").write_text(json.dumps({"prototypes": [
            {"name": "european_beech_compound_p01", "file": "european_beech_compound_p01_static.usda",
             "leaf_area_m2": 0.1}]}))  # fmt: skip
        tc.write_entry(_entry(id=f"european_beech__cut{b}_p01", size_bin=b,
                              source_ref=f"bake_{b}/european_beech_compound_p01_static.usda"), root)  # fmt: skip
    manifest = tc.merge_palette("european_beech", root, assets)
    d = json.loads(manifest.read_text())
    assert [p["name"] for p in d["prototypes"]] == [
        "european_beech_compound_S_p01", "european_beech_compound_M_p01"]  # fmt: skip
    assert d["prototypes"][1]["cut_diameter_mm"] == [6.0, 12.0]
    # the prim is renamed with the file: UE names the imported mesh after it
    assert (manifest.parent / "european_beech_compound_M_p01_skeletal.usda").read_text() == (
        'M def Xform "european_beech_compound_M_p01"')
    assert (manifest.parent / "european_beech_compound_M_p01_leaf_area_geom.json").read_text().startswith("M ")
    assert old.with_suffix(".unbinned.json").is_file()
