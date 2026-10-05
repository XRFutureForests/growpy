"""growpy-pve-catalog: the generated editor script and its ``--no-load`` switch."""

from __future__ import annotations

import ast

from growpy.tools.pve_catalog import (
    DEFAULT_CATALOG,
    catalog_rows,
    parse_tree_id,
    rows_to_csv,
    write_ue_script,
)

MANIFEST = {
    "graphs": [
        {
            "graph_asset": "/Game/Generated/Trees/Graphs/PVG_EuropeanBeech_1",
            "meshes": [
                {
                    "mesh_name": "SK_EuropeanBeech_r07_h05m",
                    "asset": "/Game/Generated/Trees/Catalog/european_beech/SK_EuropeanBeech_r07_h05m",
                    "species": "european_beech",
                    "tree_id": "r07_h05m",
                    "dbh_cm": 7.04,
                },
                {
                    "mesh_name": "SK_EuropeanBeech_r10_h10m",
                    "asset": "/Game/Generated/Trees/Catalog/european_beech/SK_EuropeanBeech_r10_h10m",
                    "species": "european_beech",
                    "tree_id": "r10_h10m",
                    "dbh_cm": 17.2,
                },
            ],
        }
    ]
}


def _script(tmp_path, **kwargs) -> str:
    manifest_path = tmp_path / "pve_export_manifest.json"
    path = write_ue_script(
        manifest_path,
        catalog_rows(MANIFEST),
        catalog=DEFAULT_CATALOG,
        set_pcg=False,
        **kwargs,
    )
    return path.read_text(encoding="utf-8")


class TestCatalogRows:
    def test_one_row_per_mesh_with_radius_and_height_from_the_tree_id(self):
        rows = catalog_rows(MANIFEST)
        assert [(r["Radius"], r["Height"]) for r in rows] == [(7, 5.0), (10, 10.0)]
        assert rows[0]["Species"] == "European Beech"

    def test_no_r00_row_unless_the_manifest_has_one(self):
        # the stand ladder is r07/r10 since 2026-10-05 (XRFF-522)
        assert all(r["Radius"] != 0 for r in catalog_rows(MANIFEST))

    def test_parse_tree_id(self):
        assert parse_tree_id("r07_h25m") == (7.0, 25.0)

    def test_csv_header_and_row_names(self):
        lines = rows_to_csv(catalog_rows(MANIFEST)).splitlines()
        assert lines[0] == "---,SkeletalMesh,Species,Height,DBH,Radius"
        assert lines[1].startswith("SK_EuropeanBeech_r07_h05m,")


class TestEditorScript:
    def test_loads_meshes_by_default(self, tmp_path):
        text = _script(tmp_path)
        assert "LOAD_MESHES = True" in text
        ast.parse(text)  # the template renders to valid python

    def test_no_load_switches_the_bounds_read_off(self, tmp_path):
        text = _script(tmp_path, load_meshes=False)
        assert "LOAD_MESHES = False" in text
        ast.parse(text)

    def test_load_asset_sits_behind_the_switch(self, tmp_path):
        """A cold-cache mesh BUILDS on load (~5 min); the switch must guard it."""
        text = _script(tmp_path, load_meshes=False)
        guard = text.index("if not LOAD_MESHES:")
        first_mesh_load = text.index("mesh = eal.load_asset(path)")
        assert guard < first_mesh_load
