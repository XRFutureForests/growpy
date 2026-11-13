"""Catalog backup: what is kept, incremental copies and the manifest."""

import csv

from growpy.tools import catalog_backup as cb


def test_keep_forest_takes_ladders_and_plans_only():
    keep = cb.keep_forest
    assert keep(
        "european_beech/r07/European_Beech_r07_h20m_d22cm_full_growth_data.json"
    )
    assert keep("european_beech/r07/European_Beech_r07_h20m_d22cm_full_icon_top.png")
    assert keep("european_beech/species_info.json")
    assert keep("unreal_scripts_european_beech_2026-11-13/pve_export_manifest.json")
    assert not keep("norway_spruce/r07/norway_spruce_h20m_d22cm_stems_skeletal.usda")
    assert not keep(
        "norway_spruce/r07/Norway_Spruce_r07_h20m_d22cm_full_growth_data.carve.json"
    )
    assert not keep("european_beech/r07_pre_2026-11-13/x_full_growth_data.json")
    assert not keep("export_beech_2026-11-13.log")


def test_backup_copies_changes_only_and_writes_hashes(tmp_path):
    src = tmp_path / "src"
    (src / "a").mkdir(parents=True)
    (src / "a" / "x.json").write_text("one", encoding="utf-8")
    (src / "skip.usda").write_text("big", encoding="utf-8")
    srcs = [(src, "growpy/forest", lambda r: not r.endswith(".usda"))]
    dst = tmp_path / "share"
    assert cb.backup(srcs, dst, dry_run=True) == (1, 1, 3)
    assert not dst.exists()
    assert cb.backup(srcs, dst) == (1, 1, 3)
    assert (dst / "growpy/forest/a/x.json").read_text(encoding="utf-8") == "one"
    assert cb.backup(srcs, dst)[1] == 0  # unchanged: nothing copied
    with (dst / "MANIFEST_keep.csv").open(encoding="utf-8") as fh:
        (row,) = list(csv.DictReader(fh))
    assert row["path"] == "growpy/forest/a/x.json" and len(row["sha256"]) == 64
