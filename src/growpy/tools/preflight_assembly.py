"""Resolve every reference in an assembly USD before it is handed to UE (XRFF-367).

A dangling reference does not fail the write and does not fail
``Usd.Stage.Open`` -- the prim simply composes to nothing. Unreal reports it as
a warning::

    LogUsd: Warning: In </beech_compound_n001/european_beech_stems>:
      Could not open asset @...

and then, one line later, dies inside the Nanite hierarchy encoder::

    Assertion failed: INode.PartIndex == ((uint32) 0xffffffff)
      [NaniteBuilder/Private/Encode/NaniteEncodeHierarchy.cpp:115]

A single-instance assembly was enough to trigger it, so this is not a size
problem. Two ways to author one by accident:

* ``assembly_export`` always writes the stems reference as ``./<name>.usda``
  relative to the assembly's own directory (unlike prototypes, which use
  ``rel_to_twigs``), so writing the assembly to a different folder than the
  stems silently breaks it.
* the referenced PRIM path is derived from the filename -- ``stem`` minus
  ``_static``/``_skeletal`` -- so renaming a file without renaming its root prim
  breaks it just as quietly.

The flattened triangle estimate is reported alongside because that number, not
part size, governs import cost: UE builds the Nanite fallback by flattening
instances x part triangles, and the measured ladder runs 0.6M in 68 s, 3.0M in
about two hours and 378M into an int32 overflow crash (XRFF-364).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Above this the fallback build stops being a wait and starts being an outage:
# 3.0M measured at ~2 h. Reported, not enforced -- the caller decides.
FLATTENED_TRIANGLE_WARN = 3_000_000


def _ensure_pxr() -> None:
    from ..utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()


def _reference_items(prim: Any) -> list:
    """Every reference authored on a prim, prepended and added alike."""
    refs = prim.GetMetadata("references")
    if not refs:
        return []
    return list(getattr(refs, "prependedItems", [])) + list(
        getattr(refs, "addedItems", [])
    )


def check_assembly(usd_path: Path) -> dict[str, Any]:
    """Resolve an assembly's references and estimate its import cost.

    Returns:
        A report dict with ``errors`` (unresolved files and missing target
        prims), ``references``, ``instances``, ``prototypes``,
        ``mean_prototype_triangles`` and ``flattened_triangles``.
    """
    _ensure_pxr()

    from pxr import Usd, UsdGeom

    report: dict[str, Any] = {
        "file": str(usd_path),
        "errors": [],
        "references": [],
        "instances": 0,
        "prototypes": 0,
        "mean_prototype_triangles": 0.0,
        "flattened_triangles": 0.0,
    }

    if not usd_path.is_file():
        report["errors"].append(f"assembly not found: {usd_path}")
        return report

    stage = Usd.Stage.Open(str(usd_path))
    if stage is None:
        report["errors"].append(f"cannot open stage: {usd_path}")
        return report

    for prim in stage.Traverse():
        for item in _reference_items(prim):
            asset = item.assetPath
            if not asset:
                continue
            target = (usd_path.parent / asset).resolve()
            entry = {
                "prim": str(prim.GetPath()),
                "asset": asset,
                "target": str(target),
                "prim_path": str(item.primPath) if item.primPath else "",
                "resolved": target.is_file(),
                "target_prim_found": False,
            }
            if not entry["resolved"]:
                report["errors"].append(
                    f"{prim.GetPath()} -> {asset}: file does not exist"
                )
            else:
                sub = Usd.Stage.Open(str(target))
                inner = None
                if sub is not None:
                    inner = (
                        sub.GetPrimAtPath(item.primPath)
                        if item.primPath
                        else sub.GetDefaultPrim()
                    )
                if inner is not None and inner.IsValid():
                    entry["target_prim_found"] = True
                else:
                    report["errors"].append(
                        f"{prim.GetPath()} -> {asset}: prim "
                        f"{item.primPath or '<defaultPrim>'} not found inside it"
                    )
            report["references"].append(entry)

    instancer_prim = next(
        (p for p in stage.Traverse() if p.GetTypeName() == "PointInstancer"), None
    )
    if instancer_prim is not None:
        instancer = UsdGeom.PointInstancer(instancer_prim)
        positions = instancer.GetPositionsAttr().Get() or []
        proto_indices = list(instancer.GetProtoIndicesAttr().Get() or [])
        targets = instancer.GetPrototypesRel().GetTargets()

        triangles = []
        for target in targets:
            prim = stage.GetPrimAtPath(target)
            triangles.append(
                sum(
                    len(UsdGeom.Mesh(m).GetFaceVertexCountsAttr().Get() or [])
                    for m in Usd.PrimRange(prim)
                    if m.GetTypeName() == "Mesh"
                )
            )

        report["instances"] = len(positions)
        report["prototypes"] = len(targets)
        report["prototype_triangles"] = triangles
        mean = sum(triangles) / len(triangles) if triangles else 0.0
        report["mean_prototype_triangles"] = mean
        if proto_indices and triangles:
            # The real total, once every instance's assigned prototype is
            # known. instances x mean is the estimate you are left with when
            # the assignment is thrown away (XRFF-365) -- both are reported.
            report["flattened_triangles"] = float(
                sum(triangles[i] for i in proto_indices if i < len(triangles))
            )
        else:
            report["flattened_triangles"] = len(positions) * mean
        report["flattened_triangles_if_random"] = len(positions) * mean

    return report


def log_report(report: dict[str, Any]) -> None:
    logger.info("=== %s ===", Path(report["file"]).name)
    for entry in report["references"]:
        if entry["resolved"] and entry["target_prim_found"]:
            state = "OK  "
        elif entry["resolved"]:
            state = "PRIM"
        else:
            state = "MISS"
        logger.info("  %s %s -> %s", state, entry["prim"], entry["asset"])
    if report["prototypes"]:
        logger.info(
            "  instances=%d prototypes=%d mean_tris=%.0f flattened=%.2fM",
            report["instances"],
            report["prototypes"],
            report["mean_prototype_triangles"],
            report["flattened_triangles"] / 1e6,
        )
        if report["flattened_triangles"] > FLATTENED_TRIANGLE_WARN:
            logger.warning(
                "  %.2fM flattened triangles: the Nanite fallback build is "
                "superlinear here -- 3.0M measured at ~2 h (XRFF-364)",
                report["flattened_triangles"] / 1e6,
            )
    for error in report["errors"]:
        logger.error("  ERROR %s", error)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve every reference in an assembly USD before UE import."
    )
    parser.add_argument("assembly", type=Path, nargs="+")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    failed = 0
    for path in args.assembly:
        report = check_assembly(path)
        log_report(report)
        failed += len(report["errors"])

    if failed:
        logger.error("\n%d unresolved reference(s)", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
