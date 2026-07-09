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
        # Project-local copy (see docs/guides/unreal-import.md troubleshooting):
        # the plugin's own content path is fragile across UE versions/mount
        # state, so we expect the master material duplicated into the project.
        parent_material_path = f"{project_path}/Materials/MA_Foliage_Trees"
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


def _create_mic(name, parent, sub_path=""):
    full_path = MATERIALS_PATH + ("/" + sub_path if sub_path else "") + "/" + name
    if editor_asset_lib.does_asset_exist(full_path):
        mic = editor_asset_lib.load_asset(full_path)
    else:
        factory = unreal.MaterialInstanceConstantFactoryNew()
        mic = asset_tools.create_asset(
            name,
            MATERIALS_PATH + ("/" + sub_path if sub_path else ""),
            unreal.MaterialInstanceConstant,
            factory,
        )
    if mic is None:
        return None
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


def _set_texture(mic, name, texture):
    try:
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
    species = None
    if parts and parts[0] == "Instances":
        name = str(ad.asset_name)
        for token in ("_foliage_", "_twigs_combined_", "_foliage"):
            idx = name.find(token)
            if idx > 0:
                species = name[:idx]
                break
    elif parts:
        species = parts[0]
    if species is None or species not in species_found:
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
    species_textures.setdefault(species, {{}}).setdefault(role, ad)

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
            mic_l = _create_mic(f"MI_{{species}}_Leaves", parent_mat)
            if mic_l is not None:
                _set_static_switch(mic_l, "DefaultLit Trunk", False)
                _set_vector(mic_l, "BaseColor Tint Leaves", leaf_rgba)
                _set_vector(mic_l, "Translucency Tint Leaves", leaf_rgba)
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
            mic_t = _create_mic(f"MI_{{species}}_Trunk", parent_mat)
            if mic_t is not None:
                _set_static_switch(mic_t, "DefaultLit Trunk", True)
                _set_vector(mic_t, "BaseColor Tint", bark_rgba)
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
    probe = ((slot_name or "") + " " + (material_name or "")).lower()
    return any(tok in probe for tok in _FOLIAGE_TOKENS)


def _species_for_asset(pkg_path, asset_name):
    rel = pkg_path[len(IMPORT_PATH):].lstrip("/") if pkg_path.startswith(IMPORT_PATH) else pkg_path
    parts = rel.split("/")
    if parts and parts[0] == "Instances":
        for token in ("_foliage_", "_twigs_combined_", "_foliage"):
            idx = asset_name.find(token)
            if idx > 0:
                return asset_name[:idx]
        return None
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
    species = _species_for_asset(pkg, str(ad.asset_name))
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
