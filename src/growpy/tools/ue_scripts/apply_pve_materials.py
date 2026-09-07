"""Convert imported trees onto the PVE master material, for every species.

Run inside the editor via `growpy-ue-exec`. Completes the three steps that
`make_pve_materials.py` deliberately left apart, and that nothing wired up:

1. create ``MI_<Species>_Foliage_01`` / ``_Bark_01`` under ``MA_Foliage_Trees``;
2. wire the Base Color and Normal textures the assemblies already import;
3. re-point every imported skeletal mesh slot onto them.

Why this matters, measured 2026-09-07 against the shipped MegaPlants library:
the USD import gives every tree a ``UsdPreviewSurface`` instance that is
``two_sided = False`` and ``BLEND_OPAQUE``. One-sided culls roughly half of
every needle and leaf card, so a crown that carries the right leaf area by
Forrester (douglas fir at h15m measured 0.99 of target) still renders as a
black silhouette. Opaque discards the alpha channel that every foliage texture
carries, so leaf outlines fall back to the coarse polygon boundary -- the
"jagged edges" on ash. ``MA_Foliage_Trees`` is two-sided, ``BLEND_MASKED`` and
subsurface, which is what MegaPlants uses on every part.

Parameters are seeded from a MegaPlants instance because Epic overrides ~20 per
instance and the import overrode none, leaving every response curve at the
master default. Scalars and neutral (grey/white) vectors carry over as-is;
species-coloured vectors are skipped, since Norway spruce's blue-grey tint on
ash would be worse than a default. Those remain per-species tuning work and are
listed at the end of a run.

Three cautions learned the hard way:

* ``get_editor_property("materials")`` returns a COPY. Mutating its entries and
  setting the array back writes unchanged structs and reports success. Build
  fresh ``SkeletalMaterial`` values and read them back.
* Loading and re-saving every Nanite skeletal mesh in one pass exhausted VRAM
  and took the editor down with ``DXGI_ERROR_DEVICE_REMOVED``. Hence
  ``BATCH_LIMIT`` and the periodic ``collect_garbage()``; run repeatedly until
  it reports 0 queued.
* The slot role is read from the CURRENT material's name, so a mesh already
  converted is detected and skipped -- the pass is idempotent.
"""

import unreal

BATCH_LIMIT = 20
GC_EVERY = 5

ROOT = "/Game/Assets/TheGrove"
TARGET_ROOT = "/Game/GrowpyMaterials"
PVE_MASTER = ("/ProceduralVegetationEditor/SampleAssets/Materials/"
              "MasterMaterials/MA_Foliage_Trees")
FALLBACK_MASTER = "/Game/Templates/MA_Foliage_Trees"

# Any MegaPlants pair works as the seed; spruce is the one shipped complete.
SEED_BARK = ("/Game/Megaplant_Library/Tree_Norway_Spruce/Materials/"
             "MI_Norway_Spruce_Bark_01")
SEED_FOLIAGE = ("/Game/Megaplant_Library/Tree_Norway_Spruce/Materials/"
                "MI_Norway_Spruce_Foliage_01")

# Norway spruce hues -- copying these onto another species is worse than the
# master default. Per-species tuning, tracked separately.
SPECIES_COLOURED = {
    "BaseColor Tint",
    "BaseColor Noise Tint",
    "Season Color 1",
    "Season Color 2",
    "Translucency Tint",
    "Translucency Controls",
}

ar = unreal.AssetRegistryHelpers.get_asset_registry()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary


def _title(species):
    return "_".join(part.capitalize() for part in species.split("_"))


def _load_master():
    for path in (PVE_MASTER, FALLBACK_MASTER):
        master = eal.load_asset(path)
        if master is not None:
            return master, path
    return None, None


def _instance(name, parent, folder):
    path = "%s/%s" % (folder, name)
    mi = eal.load_asset(path)
    if mi is None:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
    if mi is not None:
        mi.set_editor_property("parent", parent)
    return mi


def _switch(mi, name, value):
    try:
        mel.set_material_instance_static_switch_parameter_value(mi, name, value)
    except Exception as exc:  # noqa: BLE001 -- reported, never fatal
        unreal.log_warning("switch %r not set on %s: %s" % (name, mi.get_name(), exc))


def _is_neutral(colour):
    """Grey or white: a strength control rather than a hue."""
    return (abs(colour.r - colour.g) < 0.02) and (abs(colour.g - colour.b) < 0.02)


def _seed_from(source_path, target, kind):
    """Copy MegaPlants' scalar and neutral-vector overrides onto `target`."""
    source = eal.load_asset(source_path)
    if source is None or target is None:
        return set()

    for entry in source.get_editor_property("scalar_parameter_values"):
        name = str(entry.get_editor_property(
            "parameter_info").get_editor_property("name"))
        mel.set_material_instance_scalar_parameter_value(
            target, name, float(entry.get_editor_property("parameter_value")))

    skipped = set()
    for entry in source.get_editor_property("vector_parameter_values"):
        name = str(entry.get_editor_property(
            "parameter_info").get_editor_property("name"))
        colour = entry.get_editor_property("parameter_value")
        # Bark's BaseColor Tint is a neutral 0.5 grey -- a brightness control,
        # not a hue -- so it carries over even though the name is on the list.
        coloured = name in SPECIES_COLOURED and not (kind == "bark"
                                                     and _is_neutral(colour))
        if coloured or not _is_neutral(colour):
            skipped.add("%s (%s)" % (name, kind))
            continue
        mel.set_material_instance_vector_parameter_value(target, name, colour)
    return skipped


def _textures_for(species):
    """Classify the Texture2D assets this species' assemblies already import."""
    found = {"foliage_diffuse": None, "foliage_normal": None, "bark": None}
    path = "%s/%s" % (ROOT, species)
    ar.scan_paths_synchronous([path], True)
    for asset in ar.get_assets_by_path(path, True):
        if str(asset.asset_class_path.asset_name) != "Texture2D":
            continue
        name = str(asset.asset_name).lower()
        pkg = str(asset.package_name)
        if "bark" in name:
            found["bark"] = found["bark"] or pkg
        elif "normal" in name:
            found["foliage_normal"] = found["foliage_normal"] or pkg
        elif "diffuse" in name or "foliage" in name:
            found["foliage_diffuse"] = found["foliage_diffuse"] or pkg
    return found


def build_materials(species):
    """Create and configure the Foliage/Bark pair for one species."""
    master, master_path = _load_master()
    if master is None:
        unreal.log_error("no MA_Foliage_Trees master found")
        return None, None, set()

    label = _title(species)
    folder = "%s/%s" % (TARGET_ROOT, label)
    tex = _textures_for(species)
    skipped = set()

    foliage = _instance("MI_%s_Foliage_01" % label, master, folder)
    if foliage is not None:
        for name, value in (("Seasons", True),
                            ("change Roughness via Health", True),
                            ("Tint Leaf Backside", True),
                            ("flip Backside Normal", True),
                            ("use Distance Based Translucency", True)):
            _switch(foliage, name, value)
        skipped |= _seed_from(SEED_FOLIAGE, foliage, "foliage")
        for param, key in (("Base Color", "foliage_diffuse"), ("Normal", "foliage_normal")):
            if tex[key]:
                texture = eal.load_asset(tex[key])
                if texture is not None:
                    mel.set_material_instance_texture_parameter_value(
                        foliage, param, texture)
        mel.update_material_instance(foliage)
        eal.save_loaded_asset(foliage)

    bark = _instance("MI_%s_Bark_01" % label, master, folder)
    if bark is not None:
        _switch(bark, "DefaultLit Trunk", True)
        _switch(bark, "Seasons", False)
        skipped |= _seed_from(SEED_BARK, bark, "bark")
        if tex["bark"]:
            texture = eal.load_asset(tex["bark"])
            if texture is not None:
                mel.set_material_instance_texture_parameter_value(
                    bark, "Base Color", texture)
        mel.update_material_instance(bark)
        eal.save_loaded_asset(bark)

    unreal.log("%s: materials under %s (master %s)" % (species, folder, master_path))
    return foliage, bark, skipped


def repoint(species, foliage, bark, budget):
    """Re-point this species' skeletal mesh slots. Returns (done, queued)."""
    if foliage is None or bark is None:
        return 0, 0
    wanted = {foliage.get_name(), bark.get_name()}
    path = "%s/%s" % (ROOT, species)
    ar.scan_paths_synchronous([path], True)

    done = queued = 0
    for asset in ar.get_assets_by_path(path, True):
        if str(asset.asset_class_path.asset_name) != "SkeletalMesh":
            continue
        mesh = eal.load_asset(str(asset.package_name))
        if mesh is None:
            continue

        current = mesh.get_editor_property("materials")
        if all((entry.get_editor_property("material_interface") is not None
                and entry.get_editor_property(
                    "material_interface").get_name() in wanted)
               for entry in current):
            continue

        if done >= budget:
            queued += 1
            continue

        replacement = []
        for entry in current:
            existing = entry.get_editor_property("material_interface")
            name = existing.get_name().lower() if existing else ""
            slot = unreal.SkeletalMaterial()
            slot.set_editor_property("material_interface",
                                     bark if "bark" in name else foliage)
            slot.set_editor_property(
                "material_slot_name", entry.get_editor_property("material_slot_name"))
            replacement.append(slot)

        mesh.set_editor_property("materials", replacement)
        eal.save_loaded_asset(mesh)

        check = mesh.get_editor_property("materials")
        applied = all(
            (e.get_editor_property("material_interface") is not None
             and e.get_editor_property("material_interface").get_name() in wanted)
            for e in check)
        if not applied:
            unreal.log_warning("slots did not apply on %s" % asset.asset_name)
        done += 1
        if done % GC_EVERY == 0:
            unreal.SystemLibrary.collect_garbage()

    return done, queued


def main():
    ar.scan_paths_synchronous([ROOT], True)
    species = sorted({str(a.package_name).split("/")[4]
                      for a in ar.get_assets_by_path(ROOT, True)
                      if len(str(a.package_name).split("/")) > 5})
    if not species:
        print("no species found under %s" % ROOT)
        return

    print("=" * 66)
    print("PVE material conversion -- %d species under %s" % (len(species), ROOT))
    print("=" * 66)

    budget = BATCH_LIMIT
    total_done = total_queued = 0
    all_skipped = set()

    for name in species:
        foliage, bark, skipped = build_materials(name)
        all_skipped |= skipped
        done, queued = repoint(name, foliage, bark, budget - total_done)
        total_done += done
        total_queued += queued
        print("  %-24s re-pointed %2d, queued %3d" % (name, done, queued))

    unreal.SystemLibrary.collect_garbage()
    print("")
    print("re-pointed %d this run, %d still queued" % (total_done, total_queued))
    if total_queued:
        print("run again until queued reaches 0")
    if all_skipped:
        print("\nleft at master defaults, need per-species colour tuning:")
        for name in sorted(all_skipped):
            print("    %s" % name)
    print("=== PVE MATERIAL CONVERSION DONE ===")


main()
