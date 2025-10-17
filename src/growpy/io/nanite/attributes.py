"""Nanite USD attribute functions."""

from pathlib import Path


def add_nanite_attributes_to_usd(usd_path: Path, is_foliage: bool = False) -> bool:
    """Add Nanite-specific USD attributes to exported USD file.

    Args:
        usd_path: Path to USD file
        is_foliage: Whether this is foliage requiring Preserve Area

    Returns:
        Success status
    """
    from pxr import Sdf, Usd, UsdGeom

    stage = Usd.Stage.Open(str(usd_path))
    if not stage:
        return False

    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            prim.CreateAttribute("unrealNanite", Sdf.ValueTypeNames.Token).Set("enable")
            if is_foliage:
                prim.CreateAttribute("unrealNanitePreserveArea", Sdf.ValueTypeNames.Bool).Set(True)

    stage.GetRootLayer().Save()
    return True
