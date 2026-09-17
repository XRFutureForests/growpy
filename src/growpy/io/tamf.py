"""Tree Asset Metadata Format (TAMF) records for exported tree assets.

TAMF is the asset-side exchange component of the Digital Forest Twin profile
(publications/full/digital-forest-twin-standard): one record per exported
asset stating which species and growth stage the geometry represents, what
calibration produced that stage, which competition context was assumed, the
structural quantities the geometry embodies, and the geometric contract it
was exported under. A consumer holding only the asset and this record can
place it and judge it without opening the geometry.

One record is emitted per exported stage as ``<file_prefix>.tamf.json``
next to the asset, on every export route (USD assembly, PVE growth JSON,
Helios OBJ). On the USD route the same record is also written as custom
metadata on the stage's default prim under the key ``tamf``. The schema is
``schemas/tamf.schema.json`` at the repository root.

Honesty rules, so the record never claims more than the pipeline did:

* ``age_years`` is ``null``. Yield-table height--age pacing exists in growpy
  but is disabled (``config/growth_models.toml``); stages are captured by
  height milestone and no age is derived.
* ``calibration`` names exactly what the yield table calibrated: the
  height--DBH power law realised at export (``quantity`` =
  ``dbh_from_height``), with its parameters, fit quality and fitted height
  range, read from the species' allometry artifact.
* ``leaf_area_m2`` and ``stem_volume_m3`` are ``null``: foliage is placed by
  PVE inside Unreal on the production route, so growpy cannot state a
  per-tree leaf area, and no stem-volume integration is implemented.
"""

from __future__ import annotations

import json
import logging
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from growpy.utils.allometry import load_species_allometry

if TYPE_CHECKING:
    from growpy.pipelines.tree_export_context import TreeExportContext

logger = logging.getLogger(__name__)

TAMF_VERSION = "0.2"
SIDECAR_SUFFIX = ".tamf.json"
USD_CUSTOM_DATA_KEY = "tamf"

# Asset formats by export route; the sidecar name is the same for all three.
FORMAT_USD = "usd"
FORMAT_PVE_GROWTH_JSON = "pve_growth_json"
FORMAT_OBJ = "obj"

_git_sha_cache: str | None | bool = False


def _growpy_process_string() -> str:
    """``growpy <version> (<short sha>) / The Grove <version>``, best effort."""
    global _git_sha_cache
    try:
        from importlib.metadata import version

        gp_version = version("growpy")
    except Exception:  # pragma: no cover - metadata missing in odd installs
        gp_version = "unknown"
    if _git_sha_cache is False:
        try:
            _git_sha_cache = (
                subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=Path(__file__).resolve().parent,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                ).stdout.strip()
                or None
            )
        except Exception:
            _git_sha_cache = None
    sha = f" ({_git_sha_cache})" if _git_sha_cache else ""
    return f"growpy {gp_version}{sha} / The Grove"


def _species_block(ctx: TreeExportContext) -> dict[str, Any]:
    """Scientific name, common name and GBIF key from the species lookup."""
    from growpy.config.paths import _find_species_row

    try:
        row = _find_species_row(ctx.species_name, use_gbif=False)
    except Exception:  # unknown species: keep the name the pipeline used
        return {
            "scientific_name": None,
            "common_name": ctx.species_name,
            "gbif_taxon_key": None,
        }
    key = row.get("GBIF Key")
    try:
        gbif = int(key) if key not in (None, "") and not _isnan(key) else None
    except (TypeError, ValueError):
        gbif = None
    return {
        "scientific_name": _str_or_none(row.get("Scientific Name")),
        "common_name": _str_or_none(row.get("Common Name")) or ctx.species_name,
        "gbif_taxon_key": gbif,
    }


def _isnan(value: Any) -> bool:
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _str_or_none(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    return text or None


def _calibration_block(ctx: TreeExportContext) -> dict[str, Any]:
    """What the yield table actually calibrated, from the allometry artifact.

    A CSV-supplied DBH overrides the allometry; the record says so instead of
    attributing the diameter to a table that did not produce it.
    """
    if ctx.dbh_from_csv:
        return {
            "source": "inventory",
            "quantity": "dbh_measured",
            "age_pacing": "disabled",
        }
    record = load_species_allometry(ctx.species_name) or {}
    source = record.get("source") or {}
    model = record.get("height_dbh_model") or {}
    if not model:
        return {
            "source": "none",
            "quantity": "dbh_from_simulation",
            "age_pacing": "disabled",
        }
    block: dict[str, Any] = {
        "source": "yield_table",
        "reference": source.get("title"),
        "region": source.get("region"),
        "site_index": source.get("site_index"),
        "surrogate": bool(source.get("surrogate", False)),
        "quantity": "dbh_from_height",
        "function": "power_law",
        "parameters": {"a": model.get("a"), "b": model.get("b")},
        "r_squared": model.get("r_squared"),
        "height_range_m": record.get("height_range_m"),
        "age_pacing": "disabled",
    }
    return block


def _structure_block(ctx: TreeExportContext) -> dict[str, Any]:
    """Crown bounds from the skeleton point cloud; nulls where unknown."""
    block: dict[str, Any] = {
        "crown_base_height_m": None,
        "crown_tip_height_m": None,
        "crown_projection_area_m2": None,
        "crown_diameter_m": None,
        "leaf_area_m2": None,
        "stem_volume_m3": None,
    }
    skeleton = ctx.skeleton
    if skeleton is None or getattr(skeleton, "points", None) is None:
        return block
    try:
        from growpy.utils.crown_geometry import compute_crown_geometry

        geom = compute_crown_geometry(skeleton, views=("top",))
    except Exception as err:  # degenerate skeletons must not fail the export
        logger.debug("TAMF crown geometry skipped for %s: %s", ctx.file_prefix, err)
        return block
    top = geom.views["top"]
    area = float(top.concave_hull_area_m2)
    block.update(
        {
            "crown_base_height_m": round(float(geom.crown_base_height_m), 3),
            "crown_tip_height_m": round(float(geom.crown_tip_height_m), 3),
            "crown_projection_area_m2": round(area, 3),
            # Equivalent-circle diameter of the plan-view crown footprint.
            "crown_diameter_m": round(2.0 * math.sqrt(area / math.pi), 3)
            if area > 0
            else None,
        }
    )
    return block


def build_tamf_record(
    ctx: TreeExportContext,
    *,
    asset_format: str,
    asset_path: Path | None,
) -> dict[str, Any]:
    """Assemble the TAMF record for the asset ``ctx`` has just exported."""
    radius = ctx.surround_radius_m
    competition = "surround" if radius and radius > 0 else "open_grown"
    dbh_m = ctx.filename_dbh if ctx.filename_dbh else ctx.grove_dbh
    record: dict[str, Any] = {
        "tamf_version": TAMF_VERSION,
        "asset": {
            "id": ctx.file_prefix,
            "format": asset_format,
            "path": asset_path.name if asset_path is not None else None,
            "units": "m",
            "up_axis": "Z",
            "origin": "stem_base",
            # CityGML representation LoD (docs/level-of-detail-vocabulary.md in
            # digital-twin-db): a procedural 3D morphology, instanced.
            "level_of_detail": "LoD3",
            "geometry_class": "implicit",
        },
        "species": _species_block(ctx),
        "source": {
            "kind": "generated",
            "tree_entity_id": None,
            "process": _growpy_process_string(),
            "dataset": "growpy-synthetic-forest",
            "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "growth_stage": {
            "height_m": round(float(ctx.height), 3),
            "dbh_cm": round(float(dbh_m) * 100.0, 1) if dbh_m else None,
            "age_years": None,
            "growth_cycles": ctx.cycle,
            "calibration": _calibration_block(ctx),
            "competition_context": competition,
            "surround_radius_m": float(radius) if competition == "surround" else None,
        },
        "structure": _structure_block(ctx),
        "extensions": {
            "x-growpy": {
                "variant": ctx.variant_name,
                "twig_density": ctx.twig_density,
                "radial_scale": round(float(ctx.radial_scale), 4),
                "dbh_from_csv": bool(ctx.dbh_from_csv),
                "fid": ctx.fid,
            }
        },
    }
    return record


def sidecar_path(ctx: TreeExportContext) -> Path:
    return ctx.tree_dir / f"{ctx.file_prefix}{SIDECAR_SUFFIX}"


def write_tamf_sidecar(ctx: TreeExportContext, record: dict[str, Any]) -> Path:
    path = sidecar_path(ctx)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def _usd_safe(value: Any) -> Any:
    """USD customData cannot hold None: drop null leaves, recurse into dicts."""
    if isinstance(value, dict):
        return {k: _usd_safe(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_usd_safe(v) for v in value if v is not None]
    return value


def attach_tamf_to_usd(usd_path: Path, record: dict[str, Any]) -> bool:
    """Write the record as ``customData["tamf"]`` on the stage's default prim."""
    try:
        from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

        ensure_pxr_with_unreal_schema()
        from pxr import Usd
    except ImportError:  # pragma: no cover - pxr is a runtime dependency
        logger.warning("pxr unavailable; TAMF not attached to %s", usd_path.name)
        return False
    stage = Usd.Stage.Open(str(usd_path))
    if stage is None:
        logger.warning("Could not open %s to attach TAMF", usd_path.name)
        return False
    prim = stage.GetDefaultPrim()
    if not prim or not prim.IsValid():
        logger.warning("%s has no default prim; TAMF not attached", usd_path.name)
        return False
    prim.SetCustomDataByKey(USD_CUSTOM_DATA_KEY, _usd_safe(record))
    stage.GetRootLayer().Save()
    return True


def _asset_format_for(ctx: TreeExportContext) -> tuple[str, Path | None]:
    mode = getattr(ctx.cfg, "export_mode", "unreal")
    if mode == "helios":
        return FORMAT_OBJ, ctx.usd_path
    if mode == "growth_json_only":
        return (
            FORMAT_PVE_GROWTH_JSON,
            ctx.tree_dir / f"{ctx.file_prefix}_growth_data.json",
        )
    return FORMAT_USD, ctx.usd_path


def write_tamf(ctx: TreeExportContext) -> None:
    """Export stage: sidecar on every route, USD custom data on the USD route.

    Never raises -- a metadata failure must not void a finished asset export.
    """
    try:
        asset_format, asset_path = _asset_format_for(ctx)
        record = build_tamf_record(
            ctx, asset_format=asset_format, asset_path=asset_path
        )
        path = write_tamf_sidecar(ctx, record)
        if (
            asset_format == FORMAT_USD
            and asset_path is not None
            and asset_path.exists()
        ):
            attach_tamf_to_usd(asset_path, record)
        logger.debug("TAMF written: %s", path.name)
    except Exception as err:
        logger.warning("TAMF record failed for %s: %s", ctx.file_prefix, err)
