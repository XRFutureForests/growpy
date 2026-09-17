"""Tests for the TAMF record emitted next to every exported tree asset."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from growpy.io import tamf
from growpy.utils import allometry

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "tamf.schema.json"


class _Skeleton:
    """Duck-typed Grove skeleton: a trunk with a crown above 6 m."""

    def __init__(self):
        rng = np.random.default_rng(7)
        trunk = np.column_stack([np.zeros(60), np.zeros(60), np.linspace(0.0, 6.0, 60)])
        crown = np.column_stack(
            [
                rng.uniform(-2.5, 2.5, 400),
                rng.uniform(-2.5, 2.5, 400),
                rng.uniform(6.0, 15.0, 400),
            ]
        )
        self.points = np.vstack([trunk, crown])


def _ctx(tmp_path, **overrides):
    base = {
        "cfg": SimpleNamespace(export_mode="unreal"),
        "species_name": "European beech",
        "species_clean": "european_beech",
        "fid": 1,
        "tree_idx": 0,
        "height": 15.0,
        "grove_dbh": 0.30,
        "skeleton": _Skeleton(),
        "surround_radius_m": 8.0,
        "cycle": 42,
        "target_dbh_m": 0.22,
        "dbh_from_csv": False,
        "filename_dbh": 0.22,
        "radial_scale": 0.7333,
        "variant_name": None,
        "twig_density": 0.75,
        "tree_dir": tmp_path,
        "file_prefix": "European_Beech_r08_h15m_d22cm_full",
        "usd_path": tmp_path / "European_Beech_r08_h15m_d22cm_full_assembly.usda",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def beech_allometry(tmp_path, monkeypatch):
    """A written allometry artifact for European beech, in a temp store."""
    store = tmp_path / "allometry"
    store.mkdir()
    monkeypatch.setattr(allometry, "get_allometry_dir", lambda: store)
    allometry._allometry_cache.clear()
    record = {
        "species": "european_beech",
        "common_name": "European beech",
        "source": {
            "table_id": None,
            "surrogate": False,
            "title": "Store: european_beech_de_si2_normal.csv",
            "yield_class": None,
            "region": "DE",
            "site_index": 2.0,
        },
        "height_dbh_model": {
            "a": 0.0021,
            "b": 1.52,
            "r_squared": 0.991,
            "n_points": 11,
        },
        "height_range_m": [8.0, 33.0],
    }
    (store / "european_beech.json").write_text(json.dumps(record))
    yield record
    allometry._allometry_cache.clear()


class TestBuildRecord:
    def test_states_what_was_calibrated_and_nothing_more(
        self, tmp_path, beech_allometry
    ):
        ctx = _ctx(tmp_path)
        rec = tamf.build_tamf_record(ctx, asset_format="usd", asset_path=ctx.usd_path)

        assert rec["tamf_version"] == tamf.TAMF_VERSION
        assert rec["asset"]["id"] == ctx.file_prefix
        assert rec["asset"]["units"] == "m" and rec["asset"]["up_axis"] == "Z"
        assert rec["species"]["scientific_name"] == "Fagus sylvatica"
        assert rec["source"]["kind"] == "generated"
        stage = rec["growth_stage"]
        assert stage["height_m"] == 15.0
        assert stage["dbh_cm"] == 22.0
        assert stage["age_years"] is None  # pacing is disabled: no age is derived
        assert stage["growth_cycles"] == 42
        assert stage["competition_context"] == "surround"
        assert stage["surround_radius_m"] == 8.0
        cal = stage["calibration"]
        assert cal["source"] == "yield_table"
        assert cal["quantity"] == "dbh_from_height"
        assert cal["function"] == "power_law"
        assert cal["parameters"] == {"a": 0.0021, "b": 1.52}
        assert cal["height_range_m"] == [8.0, 33.0]
        assert cal["age_pacing"] == "disabled"

    def test_crown_metrics_from_skeleton(self, tmp_path, beech_allometry):
        rec = tamf.build_tamf_record(
            _ctx(tmp_path), asset_format="usd", asset_path=None
        )
        s = rec["structure"]
        assert 4.0 < s["crown_base_height_m"] < 8.0
        assert s["crown_tip_height_m"] == pytest.approx(15.0, abs=0.05)
        assert 3.0 < s["crown_diameter_m"] < 6.0
        assert s["leaf_area_m2"] is None and s["stem_volume_m3"] is None

    def test_open_grown_and_no_skeleton(self, tmp_path, beech_allometry):
        ctx = _ctx(tmp_path, surround_radius_m=0.0, skeleton=None)
        rec = tamf.build_tamf_record(
            ctx, asset_format="pve_growth_json", asset_path=None
        )
        assert rec["growth_stage"]["competition_context"] == "open_grown"
        assert rec["growth_stage"]["surround_radius_m"] is None
        assert rec["structure"]["crown_base_height_m"] is None

    def test_csv_dbh_is_not_attributed_to_the_table(self, tmp_path, beech_allometry):
        ctx = _ctx(tmp_path, dbh_from_csv=True, filename_dbh=0.41)
        rec = tamf.build_tamf_record(ctx, asset_format="usd", asset_path=None)
        assert rec["growth_stage"]["dbh_cm"] == 41.0
        assert rec["growth_stage"]["calibration"]["source"] == "inventory"

    def test_matches_published_schema(self, tmp_path, beech_allometry):
        jsonschema = pytest.importorskip("jsonschema")
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        rec = tamf.build_tamf_record(
            _ctx(tmp_path), asset_format="usd", asset_path=None
        )
        jsonschema.validate(rec, schema)

    def test_required_keys_present_without_jsonschema(self, tmp_path, beech_allometry):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        rec = tamf.build_tamf_record(
            _ctx(tmp_path), asset_format="usd", asset_path=None
        )
        for key in schema["required"]:
            assert key in rec
        for block in ("asset", "species", "source", "growth_stage", "structure"):
            for key in schema["properties"][block]["required"]:
                assert key in rec[block], f"{block}.{key}"
            assert set(rec[block]) <= set(schema["properties"][block]["properties"]), (
                block
            )


class TestWriteStage:
    def test_sidecar_and_usd_custom_data(self, tmp_path, beech_allometry):
        from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

        ensure_pxr_with_unreal_schema()
        Usd = pytest.importorskip("pxr.Usd")
        UsdGeom = pytest.importorskip("pxr.UsdGeom")
        ctx = _ctx(tmp_path)
        stage = Usd.Stage.CreateNew(str(ctx.usd_path))
        root = UsdGeom.Xform.Define(stage, "/Tree").GetPrim()
        stage.SetDefaultPrim(root)
        stage.GetRootLayer().Save()

        tamf.write_tamf(ctx)

        sidecar = tmp_path / f"{ctx.file_prefix}.tamf.json"
        assert sidecar.exists()
        on_disk = json.loads(sidecar.read_text(encoding="utf-8"))
        assert on_disk["growth_stage"]["dbh_cm"] == 22.0

        reopened = Usd.Stage.Open(str(ctx.usd_path))
        data = reopened.GetDefaultPrim().GetCustomDataByKey("tamf")
        assert data["tamf_version"] == tamf.TAMF_VERSION
        assert data["growth_stage"]["height_m"] == 15.0
        # None leaves are dropped for USD, kept in the JSON.
        assert "age_years" not in data["growth_stage"]
        assert on_disk["growth_stage"]["age_years"] is None

    def test_growth_json_route_names_the_json_asset(self, tmp_path, beech_allometry):
        ctx = _ctx(
            tmp_path, cfg=SimpleNamespace(export_mode="growth_json_only"), usd_path=None
        )
        tamf.write_tamf(ctx)
        rec = json.loads((tmp_path / f"{ctx.file_prefix}.tamf.json").read_text())
        assert rec["asset"]["format"] == "pve_growth_json"
        assert rec["asset"]["path"] == f"{ctx.file_prefix}_growth_data.json"

    def test_failure_never_raises(self, tmp_path, beech_allometry):
        ctx = _ctx(tmp_path, tree_dir=tmp_path / "missing" / "dir")
        tamf.write_tamf(ctx)  # directory absent -> logged, not raised
