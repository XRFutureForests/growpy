"""Material instance assignment script generation for Unreal Engine imports.

Extracted from unreal_scripts.py to isolate the MA_Foliage_Trees MIC
assignment logic from the import/cleanup script generators.

Generates Unreal Python code that creates per-species Material Instance
Constants (MICs) from a parent foliage material and assigns them to
imported SkeletalMesh / StaticMesh assets.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _build_material_script(
    project_path: str,
    species_colors: dict[str, dict[str, tuple[float, float, float, float]]],
    parent_material_path: str | None = None,
    species_twig_map: dict[str, str] | None = None,
    twig_params: dict[str, dict[str, list[float]]] | None = None,
) -> str:
    """Build Unreal Python code that assigns MA_Foliage_Trees-derived MICs to imports.

    Per species creates two Material Instance Constants under
    ``{IMPORT_PATH}/Materials/``:

    * ``MI_<species>_Leaves`` with static switch ``DefaultLit Trunk = False``,
      ``BaseColor Tint Leaves`` (+ ``Translucency Tint Leaves``) set from the
      CSV, and the per-species leaf BaseColor/Normal textures wired onto
      whichever texture parameters the parent material exposes for leaves.
    * ``MI_<species>_Trunk`` with static switch ``DefaultLit Trunk = True``,
      ``BaseColor Tint`` set from the CSV, and the per-species bark
      BaseColor/Normal textures wired the same way.

    Then walks all imported SkeletalMesh / StaticMesh assets and assigns
    the appropriate MIC to each material slot. Foliage is detected via
    ``Instances/`` path membership or slot/material names containing
    foliage/twig/leaf keywords.
    """
    if parent_material_path is None:
        # Fallback only. Callers should pass the configured [unreal] db_path
        # (the reusable-template dir, e.g. /Game/Templates) -- see
        # generate_unreal_import_script. This default expects the master
        # material duplicated into the project because the plugin's own content
        # path is fragile across UE versions/mount state
        # (docs/guides/unreal-import.md troubleshooting), but it does NOT match
        # a project that keeps MA_Foliage_Trees alongside ST_TreeCatalogEntry
        # in the template dir, which is the normal layout.
        parent_material_path = f"{project_path}/Materials/MA_Foliage_Trees"
    # Leaf textures and foliage meshes live under Instances/ and are named
    # after the TWIG ASSET, not the tree: douglas fir's foliage is
    # "pacific_silver_fir_*". Emit the reverse map so those assets can be
    # resolved back to every species that uses them (one twig serves several:
    # PacificSilverFirTwig covers douglas fir, silver fir and Norway spruce).
    twig_to_species: dict[str, list[str]] = {}
    for species, folder in (species_twig_map or {}).items():
        base = str(folder)
        for suffix in ("_twigs_combined_skeletal", "_twigs_combined", "_twigs"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        twig_to_species.setdefault(base, []).append(species)
    twig_map_json = json.dumps(twig_to_species, indent=2)
    # Parameters the master exposes but has no texture slot for, derived from
    # maps the Grove ships and nothing used: the leaf underside's average
    # colour drives BaseColor Tint Leaf Backside. 28 of the Grove's 46 twig
    # assets are top/bottom pairs, so this is the only route their two-sided
    # information has into the material.
    twig_params_json = json.dumps(twig_params or {}, indent=2)

    colors_json = json.dumps(
        {s: {k: list(v) for k, v in d.items()} for s, d in species_colors.items()},
        indent=2,
    )
    return f'''"""
GrowPy batch: assign MA_Foliage_Trees material instances - Auto-generated

Execute in Unreal Engine:
  exec(open(__file__).read())
"""

import unreal
import gc

print("=" * 60)
print("GrowPy Post-Import: Assign MA_Foliage_Trees Material Instances")
print("=" * 60)

IMPORT_PATH = "{project_path}"
MATERIALS_PATH = IMPORT_PATH + "/Materials"
PARENT_MATERIAL_PATH = "{parent_material_path}"

# Species color data sourced from config/tree_asset_lookup.csv (linear RGBA).
SPECIES_COLORS = {colors_json}

_FOLIAGE_TOKENS = ("foliage", "twig", "leaf", "leaves")
_BARK_TOKENS = ("bark", "trunk", "stem", "wood")

# twig asset base -> every species that uses it. Assets under Instances/ are
# named after the TWIG, not the tree, so this is the only way back to a species.
TWIG_TO_SPECIES = {twig_map_json}
TWIG_EXTRA_PARAMS = {twig_params_json}
_ASSET_PREFIXES = ("SKM_", "PHYS_", "SKEL_", "SK_", "SM_", "MI_", "M_", "T_")


def _strip_prefix(name):
    for pfx in _ASSET_PREFIXES:
        if name.startswith(pfx):
            return name[len(pfx):]
    return name


def _species_from_instances_name(asset_name):
    """Every tree species an Instances/ asset belongs to.

    "T_pacific_silver_fir_foliage_diffuse_top" -> ["douglas_fir", "silver_fir",
    "norway_spruce"]. The prefix has to go first: keeping it yielded
    "T_pacific_silver_fir", which matched no species, so every leaf texture was
    dropped and MI_<species>_Leaves inherited the master's default texture --
    which is why leaves rendered with the bark image on them.
    """
    stem = _strip_prefix(str(asset_name))
    for token in ("_twigs_combined", "_foliage_", "_foliage", "_twig"):
        idx = stem.find(token)
        if idx > 0:
            base = stem[:idx]
            hit = TWIG_TO_SPECIES.get(base)
            if hit:
                return list(hit)
            # A twig asset the map does not know: fall back to treating the
            # base as a species name, which is right when they coincide.
            return [base]
    return []

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
editor_asset_lib = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

parent_mat = editor_asset_lib.load_asset(PARENT_MATERIAL_PATH)
if parent_mat is None:
    unreal.log_error(
        f"Parent material not found: {{PARENT_MATERIAL_PATH}} -- aborting."
    )
else:
    print(f"Parent material: {{PARENT_MATERIAL_PATH}}")

    if not editor_asset_lib.does_directory_exist(MATERIALS_PATH):
        editor_asset_lib.make_directory(MATERIALS_PATH)


def _to_linear_color(rgba):
    r, g, b, a = rgba
    return unreal.LinearColor(float(r), float(g), float(b), float(a))


def _set_static_switch(mic, name, value):
    """Set a static switch parameter using whichever API the UE version exposes."""
    try:
        mel.set_material_instance_static_switch_parameter_value(mic, name, bool(value))
        return True
    except Exception:
        pass
    try:
        sps = mic.get_editor_property("static_parameters")
        switches = list(sps.get_editor_property("static_switch_parameters") or [])
        found = False
        for sw in switches:
            if str(sw.get_editor_property("parameter_info").get_editor_property("name")) == name:
                sw.set_editor_property("value", bool(value))
                sw.set_editor_property("override", True)
                found = True
                break
        if not found:
            new_sw = unreal.StaticSwitchParameter()
            info = new_sw.get_editor_property("parameter_info")
            info.set_editor_property("name", name)
            new_sw.set_editor_property("value", bool(value))
            new_sw.set_editor_property("override", True)
            switches.append(new_sw)
        sps.set_editor_property("static_switch_parameters", switches)
        mic.set_editor_property("static_parameters", sps)
        return True
    except Exception as e:
        unreal.log_warning(f"Could not set static switch '{{name}}': {{e}}")
    return False


# Reference instances to clone. MA_Foliage_Trees exposes 38 scalars, 20 vectors
# and 19 switches; an instance created from the factory leaves nearly all of
# them at master defaults, and those defaults are not a usable configuration --
# Health Offset defaults to 0.0, which applies the master's red
# "Health Color Overlay" at full strength. Reconstructing Epic's setup
# parameter by parameter was tried and repeatedly produced wrong colour
# (magenta leaves, green bark). Cloning their shipped instance and overriding
# only textures and species tint renders correctly on our meshes -- verified in
# the editor 2026-09-08 with our own packed beech atlas.
_REFERENCE_MIC = {{
    "leaves": "/Game/Megaplant_Library/Tree_Norway_Spruce/Materials/"
              "MI_Norway_Spruce_Foliage_01",
    "trunk": "/Game/Megaplant_Library/Tree_Norway_Spruce/Materials/"
             "MI_Norway_Spruce_Bark_01",
}}


# Package paths of instances that inherited Epic's configuration this run.
_CLONED = set()

# The BaseColor tints in MA_Foliage_Trees are not plain colours: their alpha
# carries a blend amount, so writing a species RGB with a made-up alpha changes
# behaviour rather than hue (bark went red, leaves magenta, and zeroing alpha
# turned a summer beech autumn-orange). A cloned instance keeps Epic's values
# untouched and species identity comes from the textures instead.


def _is_cloned(mic):
    return mic is not None and mic.get_path_name().split(".")[0] in _CLONED


def _create_mic(name, parent, sub_path="", role=None):
    full_path = MATERIALS_PATH + ("/" + sub_path if sub_path else "") + "/" + name
    if editor_asset_lib.does_asset_exist(full_path):
        mic = editor_asset_lib.load_asset(full_path)
    else:
        ref = _REFERENCE_MIC.get(role or "")
        mic = None
        if ref and editor_asset_lib.does_asset_exist(ref):
            # Duplicate rather than create: inherits a configuration that is
            # known to render, instead of ~70 unset parameters.
            mic = editor_asset_lib.duplicate_asset(ref, full_path)
            if mic is not None:
                _CLONED.add(full_path)
                print(f"  [ok] {{name}} cloned from {{ref.split('/')[-1]}}")
        if mic is None:
            if ref:
                unreal.log_warning(
                    f"reference instance {{ref}} unavailable; {{name}} falls back "
                    "to master defaults and will need its parameters checked"
                )
            factory = unreal.MaterialInstanceConstantFactoryNew()
            mic = asset_tools.create_asset(
                name,
                MATERIALS_PATH + ("/" + sub_path if sub_path else ""),
                unreal.MaterialInstanceConstant,
                factory,
            )
    if mic is None:
        return None
    if full_path not in _CLONED:
        # Only a factory-built instance needs its parent assigned. A clone
        # already points at the master its reference used -- the PVE plugin's
        # /ProceduralVegetationEditor/.../MA_Foliage_Trees. Re-pointing it at
        # the project's same-named copy under /Game/Templates silently swaps
        # the graph underneath: every parameter name still resolves, so the
        # instances compare identical, but the tree renders violet.
        try:
            mel.set_material_instance_parent(mic, parent)
        except Exception as e:
            unreal.log_warning(f"Could not set parent on {{name}}: {{e}}")
    return mic


def _set_vector(mic, name, rgba):
    try:
        mel.set_material_instance_vector_parameter_value(mic, name, _to_linear_color(rgba))
        return True
    except Exception as e:
        unreal.log_warning(f"Could not set vector '{{name}}': {{e}}")
    return False


def _set_scalar(mic, name, value):
    try:
        mel.set_material_instance_scalar_parameter_value(mic, name, float(value))
        return True
    except Exception as e:
        unreal.log_warning(f"Could not set scalar '{{name}}': {{e}}")
    return False


# Surface response, read off MegaPlants' own MI_Norway_Spruce_Bark_01 /
# _Foliage_01. Nothing was overridden before, so every MIC sat on the master's
# defaults and bark rendered as polished chrome -- flat, mirror-like and
# smeared along the trunk UVs. These are species-independent response curves;
# colour stays with the per-species tints from the CSV.
# Health Offset gates the master's "Health Color Overlay", whose default is
# (0.118, 0.004, 0.0) -- red. The parameter's own default is 0.0, which applies
# that overlay at full strength, so every tree rendered with a red cast: the
# beech trunk came out red and the fir needles yellow. MegaPlants sets 5.0 on
# its foliage instance and we set nothing. Verified in the editor 2026-09-08:
# 5.0 turns the fir green and the beech trunk from red to green.
_HEALTH_OFFSET = 5.0

_TRUNK_SCALARS = {{
    "Roughness Min": 0.5,
    "Roughness Max": 1.0,
    "Roughness Contrast": 1.0,
    "Roughness Strength": 1.0,
    "Roughness AO": 5.0,
    "Specular": 1.0782,
    "Specular AO": 0.8,
    "Specular Desaturation": 1.0,
    "Normal Strength": 1.5,
    "Health Offset": _HEALTH_OFFSET,
}}
_LEAF_SCALARS = {{
    "Roughness Min": 0.25,
    "Roughness Contrast": 1.4,
    "Roughness Leaves Strength": 6.0,
    "Roughness Leaf Backside": 1.1,
    "Roughness Health Mask": 1.0,
    "Normal Strength": 1.0,
    "Translucency Mask Threshold": 2.0,
    "Health Offset": _HEALTH_OFFSET,
}}


def _ensure_virtual(texture):
    """Make a texture virtual-texture streamed, as MA_Foliage_Trees requires.

    The PVE master samples through virtual texture samplers, and every
    MegaPlants texture it ships is authored that way. Feeding it a
    non-virtual texture is not an error UE refuses -- it logs
    "expects texture ... to be Virtual" and the sampler returns garbage,
    which renders as a colour that changes on every recompile (magenta,
    violet, neon green). Enabling it here keeps the requirement attached to
    the material that imposes it, whichever step imported the texture.
    """
    if texture is None:
        return
    try:
        if not texture.get_editor_property("virtual_texture_streaming"):
            texture.set_editor_property("virtual_texture_streaming", True)
            editor_asset_lib.save_loaded_asset(texture)
            print(f"  [ok] {{texture.get_name()}}: virtual texture streaming on")
    except Exception as e:
        unreal.log_warning(f"Could not make {{texture.get_name()}} virtual: {{e}}")


def _set_texture(mic, name, texture):
    try:
        _ensure_virtual(texture)
        mel.set_material_instance_texture_parameter_value(mic, name, texture)
        return True
    except Exception as e:
        unreal.log_warning(f"Could not set texture '{{name}}': {{e}}")
    return False


def _classify_texture_param(name):
    """Map a master-material texture parameter name to a role, or None if unrecognized."""
    lname = name.lower()
    is_leaf = "leaf" in lname
    if "normal" in lname:
        return "leaf_normal" if is_leaf else "trunk_normal"
    if any(tok in lname for tok in ("basecolor", "diffuse", "albedo", "color")):
        return "leaf_diffuse" if is_leaf else "trunk_diffuse"
    return None


# Discover which texture parameters the parent material exposes so per-species
# bark/leaf textures (BaseColor + Normal) can be wired onto the MICs below,
# instead of falling back to the parent material's defaults.
TEXTURE_PARAM_NAMES = {{}}  # role -> parameter name on the parent material
if parent_mat is not None:
    try:
        all_tex_params = [str(p) for p in (mel.get_texture_parameter_names(parent_mat) or [])]
    except Exception as e:
        unreal.log_warning(f"Could not list texture parameters on parent material: {{e}}")
        all_tex_params = []
    print(f"Parent material texture parameters: {{all_tex_params}}")
    for p in all_tex_params:
        role = _classify_texture_param(p)
        if role is None:
            print(f"  [skip] unrecognized texture parameter '{{p}}'")
            continue
        if role in TEXTURE_PARAM_NAMES:
            print(f"  [skip] duplicate role '{{role}}' for '{{p}}' (already using '{{TEXTURE_PARAM_NAMES[role]}}')")
            continue
        TEXTURE_PARAM_NAMES[role] = p
        print(f"  [ok] texture role '{{role}}' -> parameter '{{p}}'")

    # MA_Foliage_Trees exposes exactly two texture parameters, "Base Color" and
    # "Normal", shared by bark and leaves and switched apart by the
    # "DefaultLit Trunk" static switch -- MegaPlants' own foliage instance sets
    # plain "Base Color" too. Neither name contains "leaf", so both classify as
    # trunk roles and the leaf roles never exist; the leaf MIC was then left
    # with no texture at all and inherited the master's default, which is why
    # leaves rendered carrying the bark image. The leaf MIC is a separate
    # instance, so pointing the leaf textures at the same parameter names is
    # correct rather than a workaround.
    for leaf_role, trunk_role in (("leaf_diffuse", "trunk_diffuse"),
                                  ("leaf_normal", "trunk_normal")):
        if leaf_role not in TEXTURE_PARAM_NAMES and trunk_role in TEXTURE_PARAM_NAMES:
            TEXTURE_PARAM_NAMES[leaf_role] = TEXTURE_PARAM_NAMES[trunk_role]
            print(
                f"  [ok] texture role '{{leaf_role}}' -> parameter "
                f"'{{TEXTURE_PARAM_NAMES[leaf_role]}}' (shared with {{trunk_role}})"
            )


# ----------------------------------------------------------------------
# Step 1: collect imported species by scanning mesh assets.
# ----------------------------------------------------------------------
species_found = set()
all_assets = []
if parent_mat is not None:
    all_assets = asset_registry.get_assets_by_path(IMPORT_PATH, recursive=True)

mesh_assets = []  # (asset_data, pkg_path, asset_class)
for ad in all_assets:
    try:
        cls = str(ad.asset_class_path.asset_name)
    except Exception:
        try:
            cls = str(ad.asset_class)
        except Exception:
            cls = ""
    if cls not in ("SkeletalMesh", "StaticMesh"):
        continue
    pkg = str(ad.package_name)
    if pkg.startswith(MATERIALS_PATH):
        continue
    mesh_assets.append((ad, pkg, cls))

    # Derive species standardized-name from path
    rel = pkg[len(IMPORT_PATH):].lstrip("/") if pkg.startswith(IMPORT_PATH) else pkg
    parts = rel.split("/")
    if parts and parts[0] == "Instances":
        name = str(ad.asset_name)
        for token in ("_foliage_", "_twigs_combined_", "_foliage"):
            idx = name.find(token)
            if idx > 0:
                species_found.add(name[:idx])
                break
    elif parts:
        species_found.add(parts[0])

print(f"Found {{len(mesh_assets)}} mesh assets covering {{len(species_found)}} species")


# Collect per-species Texture2D assets (bark/leaf BaseColor + Normal) so they
# can be wired onto the MICs in Step 2. Bark textures are named
# "<...>_bark"/"<...>_bark_normal"; leaf textures keep their original Grove
# filename, so a generic "normal" token is used to split diffuse vs. normal.
species_textures = {{}}  # species -> {{"trunk_diffuse"/"trunk_normal"/"leaf_diffuse"/"leaf_normal": asset_data}}
for ad in all_assets:
    try:
        cls = str(ad.asset_class_path.asset_name)
    except Exception:
        try:
            cls = str(ad.asset_class)
        except Exception:
            cls = ""
    if cls != "Texture2D":
        continue
    pkg = str(ad.package_name)
    if pkg.startswith(MATERIALS_PATH):
        continue

    rel = pkg[len(IMPORT_PATH):].lstrip("/") if pkg.startswith(IMPORT_PATH) else pkg
    parts = rel.split("/")
    if parts and parts[0] == "Instances":
        # One twig serves several species, so a leaf texture belongs to all of
        # them, not one.
        owners = _species_from_instances_name(str(ad.asset_name))
    elif parts:
        owners = [parts[0]]
    else:
        owners = []
    owners = [sp for sp in owners if sp in species_found]
    if not owners:
        continue

    name_lower = str(ad.asset_name).lower()
    if "_bark_normal" in name_lower:
        role = "trunk_normal"
    elif "_bark" in name_lower:
        role = "trunk_diffuse"
    elif any(tok in name_lower for tok in ("normal", "_nrm", "_norm")):
        role = "leaf_normal"
    else:
        role = "leaf_diffuse"
    # The packed *_pve_basecolor / *_pve_normal maps are the ones the master
    # actually wants: colour+alpha and normal+translucency in the two texture
    # parameters it exposes, the same contract MegaPlants ships as _CA/_NT.
    # The raw Grove maps are RGB JPEGs with no alpha at all, so they cannot
    # drive opacity or subsurface. Prefer packed, and let it override a raw map
    # already registered for this role.
    packed = "_pve_" in name_lower
    for sp in owners:
        bucket = species_textures.setdefault(sp, {{}})
        if packed or role not in bucket:
            bucket[role] = ad

print(f"Found textures for {{len(species_textures)}} species")

# ----------------------------------------------------------------------
# Step 2: create MICs per species.
# ----------------------------------------------------------------------
mic_cache = {{}}  # species -> {{"leaves": mic, "trunk": mic}}
if parent_mat is not None:
    for species in sorted(species_found):
        colors = SPECIES_COLORS.get(species)
        if not colors:
            print(f"  [skip] no color data for '{{species}}'")
            continue
        entry = {{}}
        leaf_rgba = colors.get("leaf")
        bark_rgba = colors.get("bark")
        tex_bucket = species_textures.get(species, {{}})
        if leaf_rgba is not None:
            mic_l = _create_mic(f"MI_{{species}}_Leaves", parent_mat, role="leaves")
            if mic_l is not None:
                # A cloned instance already carries a rendering configuration
                # that works; overriding tints and scalars on top of it is what
                # produced magenta leaves and red bark. Only the textures --
                # the actual species signal -- are swapped in.
                if not _is_cloned(mic_l):
                    _set_static_switch(mic_l, "DefaultLit Trunk", False)
                    _set_vector(mic_l, "BaseColor Tint Leaves", leaf_rgba)
                    _set_vector(mic_l, "Translucency Tint Leaves", leaf_rgba)
                    for _sn, _sv in _LEAF_SCALARS.items():
                        _set_scalar(mic_l, _sn, _sv)
                if not _is_cloned(mic_l):
                    for _twig, _extra in TWIG_EXTRA_PARAMS.items():
                        if species in TWIG_TO_SPECIES.get(_twig, []):
                            for _pn, _pv in _extra.items():
                                _set_vector(mic_l, _pn, list(_pv) + [1.0])
                                print(f"  [ok] {{species}}: {{_pn}} from {{_twig}}")
                leaf_diff = tex_bucket.get("leaf_diffuse")
                if leaf_diff is not None and "leaf_diffuse" in TEXTURE_PARAM_NAMES:
                    _set_texture(mic_l, TEXTURE_PARAM_NAMES["leaf_diffuse"], leaf_diff.get_asset())
                leaf_norm = tex_bucket.get("leaf_normal")
                if leaf_norm is not None and "leaf_normal" in TEXTURE_PARAM_NAMES:
                    _set_texture(mic_l, TEXTURE_PARAM_NAMES["leaf_normal"], leaf_norm.get_asset())
                mel.update_material_instance(mic_l)
                editor_asset_lib.save_loaded_asset(mic_l)
                entry["leaves"] = mic_l
        if bark_rgba is not None:
            mic_t = _create_mic(f"MI_{{species}}_Trunk", parent_mat, role="trunk")
            if mic_t is not None:
                if not _is_cloned(mic_t):
                    _set_static_switch(mic_t, "DefaultLit Trunk", True)
                    _set_vector(mic_t, "BaseColor Tint", bark_rgba)
                    for _sn, _sv in _TRUNK_SCALARS.items():
                        _set_scalar(mic_t, _sn, _sv)
                trunk_diff = tex_bucket.get("trunk_diffuse")
                if trunk_diff is not None and "trunk_diffuse" in TEXTURE_PARAM_NAMES:
                    _set_texture(mic_t, TEXTURE_PARAM_NAMES["trunk_diffuse"], trunk_diff.get_asset())
                trunk_norm = tex_bucket.get("trunk_normal")
                if trunk_norm is not None and "trunk_normal" in TEXTURE_PARAM_NAMES:
                    _set_texture(mic_t, TEXTURE_PARAM_NAMES["trunk_normal"], trunk_norm.get_asset())
                mel.update_material_instance(mic_t)
                editor_asset_lib.save_loaded_asset(mic_t)
                entry["trunk"] = mic_t
        if entry:
            mic_cache[species] = entry
            print(
                f"  [ok] {{species}}: "
                f"{{'Leaves' if 'leaves' in entry else '-'}} / "
                f"{{'Trunk' if 'trunk' in entry else '-'}}"
            )

print(f"Created/updated MICs for {{len(mic_cache)}} species")

# ----------------------------------------------------------------------
# Step 3: assign MICs to mesh material slots.
# ----------------------------------------------------------------------
def _slot_is_foliage(pkg_path, slot_name, material_name):
    if "/Instances/" in pkg_path:
        return True
    # Classify on the SLOT name alone. The slot name is fixed at import
    # (MI_douglas_fir_bark_0 / MI_pacific_silver_fir_0) whereas the material
    # name is whatever this pass last assigned -- so including it makes the
    # test self-defeating: once a slot wrongly holds MI_<species>_Trunk, the
    # bark token matches the material name and it stays Trunk forever. Fall
    # back to the material name only when there is no slot name at all.
    probe = (slot_name or material_name or "").lower()
    if any(tok in probe for tok in _BARK_TOKENS):
        return False
    if any(tok in probe for tok in _FOLIAGE_TOKENS):
        return True
    # Default to foliage, not bark. A tree assembly carries exactly two slots
    # and the foliage one is named after the TWIG ASSET's species, not after
    # the foliage: douglas fir's is MI_pacific_silver_fir_0, common ash's is
    # MI_one_leaved_ash_0 ("leaved" does not contain "leaf" or "leaves"), scots
    # pine's is MI_scots_pine_0. None of them match a foliage token, so with a
    # bark default every leaf slot on all 99 trees was assigned the Trunk
    # material and the crowns rendered as bark. Bark slots are reliably named
    # MI_<species>_bark, so testing for bark is the side that can be matched.
    return True


def _species_for_asset(pkg_path, asset_name, known=None):
    """Species whose material instances this asset should use.

    A shared twig belongs to several species -- pacific_silver_fir foliage is
    used by douglas_fir, silver_fir and norway_spruce -- so taking owners[0]
    picked a species that is not part of a scoped run and the asset was skipped
    entirely. With external references the twig library assets keep their own
    material, so skipping them leaves the needles on UsdPreviewSurface instead
    of the PVE master. Prefer an owner this run actually built instances for.
    """
    rel = pkg_path[len(IMPORT_PATH):].lstrip("/") if pkg_path.startswith(IMPORT_PATH) else pkg_path
    parts = rel.split("/")
    if parts and parts[0] == "Instances":
        owners = _species_from_instances_name(asset_name)
        if not owners:
            return None
        if known:
            for owner in owners:
                if owner in known:
                    return owner
        return owners[0]
    if parts:
        return parts[0]
    return None


def _iter_slots(mesh, cls):
    """Yield (index, slot_name, material_interface) and return setter callable."""
    if cls == "SkeletalMesh":
        prop = "materials"
        struct_cls = unreal.SkeletalMaterial
    else:
        prop = "static_materials"
        struct_cls = unreal.StaticMaterial
    slots = list(mesh.get_editor_property(prop) or [])
    return prop, struct_cls, slots


assigned_count = 0
skipped_count = 0
for ad, pkg, cls in mesh_assets:
    species = _species_for_asset(pkg, str(ad.asset_name), mic_cache)
    if species is None or species not in mic_cache:
        skipped_count += 1
        continue
    mesh = editor_asset_lib.load_asset(pkg)
    if mesh is None:
        skipped_count += 1
        continue
    prop, struct_cls, slots = _iter_slots(mesh, cls)
    if not slots:
        skipped_count += 1
        continue

    changed = False
    for slot in slots:
        slot_name = str(slot.get_editor_property("material_slot_name") or "")
        cur_mat = slot.get_editor_property("material_interface")
        cur_name = str(cur_mat.get_name()) if cur_mat is not None else ""
        is_foliage = _slot_is_foliage(pkg, slot_name, cur_name)
        mic = mic_cache[species].get("leaves" if is_foliage else "trunk")
        if mic is None:
            # fall back to whichever exists
            mic = mic_cache[species].get("trunk") or mic_cache[species].get("leaves")
        if mic is None:
            continue
        if cur_mat is not mic:
            slot.set_editor_property("material_interface", mic)
            changed = True

    if changed:
        mesh.set_editor_property(prop, slots)
        editor_asset_lib.save_loaded_asset(mesh)
        assigned_count += 1

gc.collect()
unreal.SystemLibrary.collect_garbage()

print("")
print("=" * 60)
print(
    f"Material assignment complete: {{assigned_count}} meshes updated, "
    f"{{skipped_count}} skipped"
)
print("=" * 60)
'''


# Unreal Python preamble for configuring nanite assemblies after import.
# Included in species batch scripts to set fallback mesh, quality settings, etc.
