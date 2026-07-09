"""Nanite assembly configuration script generation for Unreal Engine.

Extracted from unreal_scripts.py to isolate the Nanite post-import
configuration logic (fallback mesh, quality settings, voxelization)
from the import/cleanup script generators.

Voxelization itself is handled by the standalone
growpy_nanite_voxelize.py script after UE restart.
"""

import logging

logger = logging.getLogger(__name__)

_NANITE_CONFIG_PREAMBLE = '''

# ---------------------------------------------------------------------------
# Nanite assembly post-import configuration.
# Voxelization is NOT applied here -- use growpy_nanite_voxelize.py after
# restarting UE to avoid VRAM accumulation during batch import.
# DynamicWind data is delivered via separate wind JSON files.
# UE has no DynamicWindSkeletonAPI USD schema -- wind must be applied
# post-import (not via USD attributes).
# ---------------------------------------------------------------------------

def _set_nanite_shape_voxelize(mesh, label):
    """Set Nanite shape preservation to Voxelize using multiple strategies.

    ENaniteShapePreservation: None=0, PreserveArea=1, Voxelize=2
    The exact Python API varies by UE version, so we try several approaches.
    """
    _strategies = []

    # Strategy A: Enum without E prefix (UE 5.4+ Python reflection)
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property(
            "shape_preservation",
            unreal.NaniteShapePreservation.VOXELIZE,
        )
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"enum_no_e: {_e}")

    # Strategy B: Enum with E prefix
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property(
            "shape_preservation",
            unreal.ENaniteShapePreservation.VOXELIZE,
        )
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"enum: {_e}")

    # Strategy C: Type introspection -- read current value, construct enum(2)
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _cur = _ns.get_editor_property("shape_preservation")
        _enum_cls = type(_cur)
        _ns.set_editor_property("shape_preservation", _enum_cls(2))
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"introspect: {_e}")

    # Strategy D: Qualified enum path string
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property(
            "shape_preservation", "NaniteShapePreservation::Voxelize",
        )
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"qualified: {_e}")

    # Strategy E: Integer via set_editor_property
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property("shape_preservation", 2)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"int: {_e}")

    # Strategy F: Direct attribute assignment on struct copy
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.shape_preservation = 2
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        _strategies.append(f"attr: {_e}")

    # Strategy G: C++ getter/setter methods (StaticMesh only)
    try:
        _ns = mesh.get_nanite_settings()
        _ns.shape_preservation = 2
        mesh.set_nanite_settings(_ns)
        mesh.notify_nanite_settings_changed()
        return True
    except Exception as _e:
        _strategies.append(f"methods: {_e}")

    unreal.log_warning(f"Could not set shape preservation for {label}")
    for _s in _strategies:
        unreal.log_warning(f"    {_s}")
    return False


def _reduce_nanite_fallback(mesh, label, percent=1.0):
    """Reduce Nanite fallback mesh triangle percentage to save VRAM."""
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property("fallback_percent_triangles", percent)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception:
        pass
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.fallback_percent_triangles = percent
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        unreal.log_warning(f"Could not set fallback triangle % for {label}: {_e}")
    return False


def _set_nanite_property(mesh, label, prop_name, value):
    """Set a single property on the mesh nanite_settings struct.

    Tries set_editor_property first, then direct attribute assignment.
    Returns True on success.
    """
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property(prop_name, value)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception:
        pass
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        setattr(_ns, prop_name, value)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        unreal.log_warning(f"Could not set {prop_name} for {label}: {_e}")
    return False


def _set_nanite_fallback_target(mesh, label, target_name):
    """Set Nanite fallback_target enum (PercentTriangles / RelativeError / Auto).

    Without this, UE may default to a heuristic that ignores
    fallback_percent_triangles entirely. Tries enum then int fallback.
    """
    _name_map = {
        "percent_triangles": ("PERCENT_TRIANGLES", 0),
        "relative_error": ("RELATIVE_ERROR", 1),
        "auto": ("AUTO", 2),
    }
    _enum_name, _enum_int = _name_map.get(
        (target_name or "percent_triangles").lower(),
        ("PERCENT_TRIANGLES", 0),
    )
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _enum_cls = getattr(unreal, "NaniteFallbackTarget", None)
        if _enum_cls is not None and hasattr(_enum_cls, _enum_name):
            _ns.set_editor_property(
                "fallback_target", getattr(_enum_cls, _enum_name)
            )
            mesh.set_editor_property("nanite_settings", _ns)
            return True
    except Exception:
        pass
    try:
        _ns = mesh.get_editor_property("nanite_settings")
        _ns.set_editor_property("fallback_target", _enum_int)
        mesh.set_editor_property("nanite_settings", _ns)
        return True
    except Exception as _e:
        unreal.log_warning(
            f"Could not set fallback_target for {label}: {_e}"
        )
    return False


def _configure_nanite_assembly(mesh, label, nanite_cfg=None):
    """Configure a nanite assembly after USD import.

    Reduces fallback mesh VRAM and applies Nanite build settings from
    nanite_cfg dict. Voxelization is handled separately by the standalone
    growpy_nanite_voxelize.py script (run after UE restart).
    """
    if nanite_cfg is None:
        nanite_cfg = {}

    # NaniteAssemblyRootAPI on the USD already builds Nanite during import.
    # Do NOT re-enable or call modify(True) here -- that would trigger a
    # second Nanite build whose deferred memory accumulates across files
    # and causes OOM.  We only configure fallback / quality settings
    # which are stored as metadata and applied on the next manual rebuild.

    # NOTE: voxelization removed from batch imports -- it triggers a Nanite
    # rebuild per mesh that accumulates VRAM.  Use the standalone
    # growpy_nanite_voxelize.py script after restarting UE instead.

    # CRITICAL: set fallback_target BEFORE fallback_percent_triangles, else
    # UE may interpret the percent under the wrong heuristic.
    _set_nanite_fallback_target(
        mesh, label,
        nanite_cfg.get("fallback_target", "percent_triangles"),
    )

    _reduce_nanite_fallback(
        mesh, label, percent=nanite_cfg.get("fallback_percent", 0.01),
    )

    _fallback_rel = nanite_cfg.get("fallback_relative_error", 1.0)
    _set_nanite_property(
        mesh, label, "fallback_relative_error", _fallback_rel,
    )

    _trim_err = nanite_cfg.get("trim_relative_error", 0.0)
    if _trim_err > 0.0:
        _set_nanite_property(mesh, label, "trim_relative_error", _trim_err)

    _residency = nanite_cfg.get("target_residency_kb", 0)
    _set_nanite_property(
        mesh, label, "target_minimum_residency_in_kb", _residency,
    )

    if nanite_cfg.get("lerp_uvs", True):
        _set_nanite_property(mesh, label, "lerp_u_vs", True)

    _max_edge = nanite_cfg.get("max_edge_length_factor", 0.0)
    if _max_edge > 0.0:
        _set_nanite_property(mesh, label, "max_edge_length_factor", _max_edge)

    # Implicit tangents save build time + storage; only set true if asset
    # actually depends on baked tangents (rare for vegetation).
    _set_nanite_property(
        mesh, label, "explicit_tangents",
        bool(nanite_cfg.get("explicit_tangents", False)),
    )

    _pos_prec = nanite_cfg.get("position_precision", -1)
    if _pos_prec is not None and _pos_prec >= 0:
        _set_nanite_property(mesh, label, "position_precision", int(_pos_prec))

    _norm_prec = nanite_cfg.get("normal_precision", -1)
    if _norm_prec is not None and _norm_prec >= 0:
        _set_nanite_property(mesh, label, "normal_precision", int(_norm_prec))

    # NOTE: mesh.modify(True) is intentionally NOT called.  The USD
    # NaniteAssemblyRootAPI already built Nanite during import; calling
    # modify(True) would trigger a deferred rebuild whose memory
    # accumulates across files and causes OOM on large batches.
'''


