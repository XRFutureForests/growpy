"""
Generate a UE Python script that deletes the per-tree ``SK_*_stems`` meshes.

The USD import produces two skeletal meshes per tree: the assembly, which
carries the Nanite geometry and the twig part references, and a ``_stems``
mesh, which is the welded woody source the assembly was built from. Only the
assembly is used at runtime.

Measured on ``Douglas_Fir_r16_h15m_d21cm_full_assembly`` (UE 5.8):

* ``SK_douglas_fir_stems`` is 498.47 MB of the folder's 638.6 MB (78%);
* it has **zero** hard referencers;
* its only two soft referencers are its own ``PHYS_``/``SKEL_`` siblings,
  which point at it through the editor-only ``PreviewSkeletalMesh``;
* the assembly's hard dependency closure is 8 packages and does not contain
  it -- the assembly hard-references ``PHYS_``, ``SKEL_`` and the materials,
  and soft-references its eight foliage parts.

So the mesh never loads at runtime and can be dropped once the assembly
exists. Deleting it leaves the two preview pointers dangling, which UE
tolerates: the skeleton and physics editors simply open without a preview.

The generated script re-derives that safety argument per asset rather than
trusting the name, because the foliage parts are *also* soft-referenced --
by the assembly, which needs them. A blanket "no hard referencers" rule would
delete the tree's foliage.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


_PRUNE_SCRIPT_BODY = '''"""
GrowPy prune import intermediates - Auto-generated.

Deletes the ``SK_*_stems`` skeletal meshes under IMPORT_PATH once their
assembly has been built. Run AFTER all import batches.

Execute in Unreal Engine:
1. Right-click > "Execute Python File in Unreal"
2. Or: exec(open(r"{script_path}").read())
"""

import os
import unreal


IMPORT_PATH = "{import_path}"
DRY_RUN = {dry_run}

_registry = unreal.AssetRegistryHelpers.get_asset_registry()
_content = unreal.SystemLibrary.get_project_content_directory()

_HARD = unreal.AssetRegistryDependencyOptions(
    include_soft_package_references=False,
    include_hard_package_references=True,
    include_searchable_names=False,
    include_soft_management_references=False,
    include_hard_management_references=False,
)
_SOFT = unreal.AssetRegistryDependencyOptions(
    include_soft_package_references=True,
    include_hard_package_references=False,
    include_searchable_names=False,
    include_soft_management_references=False,
    include_hard_management_references=False,
)


def _asset_class(asset_data):
    try:
        return str(asset_data.asset_class_path.asset_name)
    except Exception:
        try:
            return str(asset_data.asset_class)
        except Exception:
            return ""


def _size_mb(package_name):
    path = os.path.join(_content, str(package_name).replace("/Game/", "") + ".uasset")
    try:
        return os.path.getsize(path) / 1048576.0
    except OSError:
        return 0.0


def _is_own_preview_sibling(referencer, stem_name):
    """True if `referencer` is the PHYS_/SKEL_ asset derived from this mesh.

    ``SK_<x>_stems`` produces ``PHYS_<x>_stems`` and ``SKEL_<x>_stems_skel``.
    Both hold it only through the editor-only PreviewSkeletalMesh pointer.
    """
    base = stem_name[3:] if stem_name.startswith("SK_") else stem_name
    leaf = str(referencer).split("/")[-1]
    return leaf in ("PHYS_" + base, "SKEL_" + base + "_skel")


def _prunable(asset_data):
    """Re-derive the safety argument for one candidate.

    Returns (ok, reason). A mesh is prunable only when it is a ``_stems`` mesh,
    nothing hard-references it, and every soft referencer is one of its own
    preview siblings.

    The name test is load-bearing, not cosmetic. A tree assembly is the
    top-level asset, so *nothing* references it and it passes the referencer
    test on its own -- verified 2026-09-04, where the predicate without this
    guard accepted SK_douglas_fir_r16_h15m_d21cm_full_assembly. Keep the check
    here rather than only in the caller's filter, so loosening the search
    cannot turn this into a tree-deleter.
    """
    name = str(asset_data.asset_name)
    pkg = asset_data.package_name

    if not name.endswith("_stems"):
        return False, "not a _stems mesh"

    hard = _registry.get_referencers(pkg, _HARD) or []
    if hard:
        return False, "%d hard referencer(s): %s" % (
            len(hard), ", ".join(str(h).split("/")[-1] for h in hard[:3])
        )

    soft = _registry.get_referencers(pkg, _SOFT) or []
    outside = [s for s in soft if not _is_own_preview_sibling(s, name)]
    if outside:
        return False, "soft-referenced from outside: %s" % ", ".join(
            str(s).split("/")[-1] for s in outside[:3]
        )

    return True, "%d preview-only referencer(s)" % len(soft)


def main():
    print("=" * 60)
    print("GrowPy prune import intermediates")
    print("=" * 60)
    if DRY_RUN:
        print("*** DRY RUN - nothing will be deleted ***")

    candidates = []
    for asset_data in _registry.get_assets_by_path(IMPORT_PATH, recursive=True):
        if "SkeletalMesh" not in _asset_class(asset_data):
            continue
        name = str(asset_data.asset_name)
        if not name.endswith("_stems"):
            continue
        candidates.append(asset_data)

    candidates.sort(key=lambda a: str(a.package_name))
    print("Found %d _stems mesh(es) under %s" % (len(candidates), IMPORT_PATH))
    if not candidates:
        return

    deleted = 0
    kept = 0
    failed = 0
    freed_mb = 0.0

    for asset_data in candidates:
        name = str(asset_data.asset_name)
        pkg = str(asset_data.package_name)
        size = _size_mb(pkg)

        ok, reason = _prunable(asset_data)
        if not ok:
            kept += 1
            print("  KEEP   %-42s %8.2f MB  (%s)" % (name, size, reason))
            continue

        if DRY_RUN:
            deleted += 1
            freed_mb += size
            print("  WOULD  %-42s %8.2f MB  (%s)" % (name, size, reason))
            continue

        try:
            if unreal.EditorAssetLibrary.delete_asset(pkg):
                deleted += 1
                freed_mb += size
                print("  DELETE %-42s %8.2f MB" % (name, size))
            else:
                failed += 1
                unreal.log_warning("[Prune] delete_asset returned False: %s" % pkg)
        except Exception as exc:
            failed += 1
            unreal.log_error("[Prune] %s: %s" % (name, exc))

    print("")
    print("=" * 60)
    print(
        "Prune complete: %d removed, %d kept, %d failed -- %.1f MB freed"
        % (deleted, kept, failed, freed_mb)
    )
    print("=" * 60)


main()
'''


def generate_prune_intermediates_script(
    output_dir: Path,
    import_path: str = "/Game/Assets/TheGrove",
    dry_run: bool = False,
) -> Path:
    """Write the UE Python script that prunes ``SK_*_stems`` meshes.

    Args:
        output_dir: Where to write the .py script (typically ``unreal_scripts/``).
        import_path: UE Content Browser base path for tree assets.
        dry_run: If True, the script reports what it would delete and stops.

    Returns:
        Path to the written script.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / "growpy_prune_intermediates.py"

    body = _PRUNE_SCRIPT_BODY.format(
        script_path=str(script_path.resolve()).replace("\\", "/"),
        import_path=import_path,
        dry_run=str(bool(dry_run)),
    )

    script_path.write_text(body, encoding="utf-8")
    logger.info("Generated prune intermediates script: %s", script_path)
    return script_path
