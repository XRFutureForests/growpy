"""Create per-species PVE material instances, the way MegaPlants does.

Run inside the editor via `growpy-ue-exec`.

MegaPlants' structure, read off Tree_Norway_Spruce: three material instances per
species -- Foliage, Bark, Decorations -- and ALL of them parent to the single
`MA_Foliage_Trees` master in the ProceduralVegetationEditor plugin, except
Decorations which parents to the species' own Bark instance. Bark and foliage
are separated by static switches on one master, not by different masters.

    MI_<Species>_Foliage_01     -> MA_Foliage_Trees
    MI_<Species>_Bark_01        -> MA_Foliage_Trees
    MI_<Species>_Decorations_01 -> MI_<Species>_Bark_01

The master carries everything asked for: `Seasons` + Season Color 1/2 for
season, `Health Offset` / `Health Color Overlay` / `change Roughness via Health`
for health, two_sided=True plus the Leaf Backside controls, and the Translucency
family for subsurface. It is BLEND_MASKED, which is one of the only two blend
modes Nanite supports.

The master takes exactly two textures -- Base Color (colour+opacity) and Normal
(normal+translucency) -- which is what `growpy-pack-pve-textures` produces. A
species with no packed normal simply leaves that parameter at the master's
default rather than being given a flat stand-in.

This creates and configures the instances only. Assigning them onto imported
mesh slots is a separate step, because which slot is bark and which is foliage
depends on how a given assembly was imported.
"""

import unreal

PVE_MASTER = (
    "/ProceduralVegetationEditor/SampleAssets/Materials/MasterMaterials/"
    "MA_Foliage_Trees"
)
# The plugin master is the parent MegaPlants itself uses. `/Game/Templates/
# MA_Foliage_Trees` is a local copy kept so the assets survive the plugin being
# disabled; it is the fallback, not the default.
FALLBACK_MASTER = "/Game/Templates/MA_Foliage_Trees"

TARGET_ROOT = "/Game/GrowpyMaterials"
TWIG_TEXTURE_ROOT = "/Game/GrowpyTextures"


def _load_master():
    master = unreal.EditorAssetLibrary.load_asset(PVE_MASTER)
    if master is not None:
        return master, PVE_MASTER
    master = unreal.EditorAssetLibrary.load_asset(FALLBACK_MASTER)
    if master is not None:
        unreal.log_warning(
            "PVE plugin master not found; falling back to the Templates copy. "
            "Instances will not track plugin updates."
        )
        return master, FALLBACK_MASTER
    return None, None


def _make_instance(name, parent, folder):
    """Create (or reuse) a material instance under `folder` parented to `parent`."""
    path = f"{folder}/{name}"
    existing = unreal.EditorAssetLibrary.load_asset(path)
    if existing is not None:
        existing.set_editor_property("parent", parent)
        return existing

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.MaterialInstanceConstantFactoryNew()
    mi = tools.create_asset(name, folder, unreal.MaterialInstanceConstant, factory)
    if mi is None:
        unreal.log_error(f"could not create {path}")
        return None
    mi.set_editor_property("parent", parent)
    return mi


def _set_scalar(mi, name, value):
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        mi, name, value
    )


def _set_switch(mi, name, value):
    try:
        unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(
            mi, name, value
        )
    except Exception as exc:  # noqa: BLE001 -- reported, never fatal
        unreal.log_warning(f"switch '{name}' not set on {mi.get_name()}: {exc}")


def _set_texture(mi, name, texture_path):
    tex = unreal.EditorAssetLibrary.load_asset(texture_path)
    if tex is None:
        return False
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
        mi, name, tex
    )
    return True


def make_species_materials(species_label, basecolor=None, normal=None):
    """Create the Foliage/Bark/Decorations trio for one species."""
    master, master_path = _load_master()
    if master is None:
        unreal.log_error("no MA_Foliage_Trees master found; nothing created")
        return {}

    folder = f"{TARGET_ROOT}/{species_label}"
    made = {}

    foliage = _make_instance(f"MI_{species_label}_Foliage_01", master, folder)
    if foliage is not None:
        # Seasons and health are the reasons for using this master at all.
        _set_switch(foliage, "Seasons", True)
        _set_switch(foliage, "change Roughness via Health", True)
        _set_switch(foliage, "Tint Leaf Backside", True)
        _set_switch(foliage, "flip Backside Normal", True)
        _set_switch(foliage, "use Distance Based Translucency", True)
        _set_scalar(foliage, "Health Offset", 0.0)
        if basecolor:
            _set_texture(foliage, "Base Color", basecolor)
        if normal:
            _set_texture(foliage, "Normal", normal)
        made["foliage"] = foliage

    bark = _make_instance(f"MI_{species_label}_Bark_01", master, folder)
    if bark is not None:
        # Bark is the same master with the trunk path switched on and the
        # foliage-only behaviour off.
        _set_switch(bark, "DefaultLit Trunk", True)
        _set_switch(bark, "Seasons", False)
        _set_switch(bark, "mask out Branches", False)
        made["bark"] = bark

    if bark is not None:
        decorations = _make_instance(
            f"MI_{species_label}_Decorations_01", bark, folder
        )
        if decorations is not None:
            made["decorations"] = decorations

    for mi in made.values():
        unreal.MaterialEditingLibrary.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)

    unreal.log(
        f"{species_label}: created {len(made)} instance(s) under {folder} "
        f"parented to {master_path}"
    )
    return made


if __name__ == "__main__":
    # Default run: the eleven dataset species, textures wired later once the
    # packed maps have been imported.
    for label in (
        "Common_Ash",
        "Douglas_Fir",
        "European_Beech",
        "European_Oak",
        "Norway_Spruce",
        "Scots_Pine",
        "Silver_Birch",
        "Silver_Fir",
        "Small_Leaved_Linden",
        "Sycamore_Maple",
        "Wild_Cherry",
    ):
        make_species_materials(label)
    print("=== PVE MATERIALS DONE ===")
