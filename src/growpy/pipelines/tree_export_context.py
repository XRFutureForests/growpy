"""Per-tree export state threaded through forest_stages.py's stage functions.

Extracted from the body of `generate_forest_stages()` (XRFF-289) so each
export side effect (assembly, wind JSON, PVE JSON, previews, icons, static
derivation) can be an independently testable function taking a single
`TreeExportContext` argument.

One instance is built per tree. Its variant-scoped fields (`model`,
`variant_name`, `variant_idx`, `twig_density`, `tree_dir`, `file_prefix`,
`usd_path`, `twig_placements`, `export_success`, `static_path`) are
reassigned once per density-variant iteration -- see
`generate_forest_stages()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from growpy.config.core import GrowPyConfig


@dataclass
class TreeExportContext:
    # Fixed for the tree's whole export (all variants share these).
    cfg: GrowPyConfig
    species_name: str
    species_clean: str
    fid: int
    tree_idx: int
    height: float
    grove_dbh: float
    skeleton: Any
    bones_info: list
    twig_usd_map: dict
    instances_dir: Path
    timer: Any
    grove: Any = None  # species' grove instance, for PVE JSON
    use_skeletal: bool = True
    use_static_only: bool = False
    skip_validation: bool = False
    include_grove_attributes: bool = False
    skip_pve_json: bool = False

    # Set by resolve_target_dbh() / compute_radial_scale(); shared by all
    # variants of this tree.
    target_dbh_m: float | None = None
    dbh_from_csv: bool = False
    filename_dbh: float = 0.0
    radial_scale: float = 1.0
    dims_suffix: str = ""

    # Reassigned once per density-variant iteration.
    model: Any = None
    # Same tree built with build_cutoff_thickness=0, so the twigs the cutoff
    # deleted can be recovered rather than approximated. None when unavailable.
    precut_model: Any = None
    variant_name: str | None = None
    variant_idx: int = 0
    twig_density: float | None = None
    tree_dir: Path | None = None
    file_prefix: str = ""

    # Set by export_assembly(); read by the later stage functions and by
    # generate_forest_stages() to track exported files.
    usd_path: Path | None = None
    twig_placements: dict = field(default_factory=dict)
    export_success: bool = False
    static_path: str | None = None
