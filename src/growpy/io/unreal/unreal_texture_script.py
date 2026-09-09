"""Import the textures the USD import does not bring in by itself.

Two sets of maps exist on disk that no mesh references, so nothing imports them
and the material pass then has nothing to wire:

* **bark normal maps.** The Grove ships one beside almost every bark diffuse
  (48 of its 97 texture files). Only the diffuse is referenced by the exported
  USD, so trunks arrived with no normal map at all and rendered as polished
  chrome.
* **packed PVE twig maps.** ``MA_Foliage_Trees`` takes colour+alpha in Base
  Color and normal+translucency in Normal -- the ``_CA``/``_NT`` contract
  MegaPlants ships. ``pack_pve_textures`` builds them during twig conversion,
  but the USD references the raw Grove diffuse, which is an RGB JPEG with no
  alpha at all.

Both are imported here, before ``import_batch_98_materials`` assigns them.

Compression follows MegaPlants' own settings rather than a guess:

===================  ===================  ======  =============================
map                  compression          sRGB    why
===================  ===================  ======  =============================
bark normal          ``TC_NORMALMAP``     off     no alpha to preserve
packed Base Color    ``TC_DEFAULT``       on      ordinary colour, keeps alpha
packed Normal        ``TC_MASKS``         off     ``TC_NORMALMAP`` is BC5, two
                                                  channels -- it would discard
                                                  the translucency in the alpha
===================  ===================  ======  =============================
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


_TEXTURE_SCRIPT = '''"""
GrowPy batch: import auxiliary textures - Auto-generated

Bark normal maps and packed PVE twig maps: on disk, referenced by no mesh, so
the USD import never brings them in. Must run before the material batch.
"""

import os

import unreal

print("=" * 60)
print("GrowPy Post-Import: Import Auxiliary Textures")
print("=" * 60)

IMPORT_PATH = "{project_path}"
INSTANCES_PATH = IMPORT_PATH + "/Instances"
TEXTURES_DIR = r"{textures_dir}"
TWIGS_DIR = r"{twigs_dir}"

ar = unreal.AssetRegistryHelpers.get_asset_registry()
eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
ar.scan_paths_synchronous([IMPORT_PATH], True)


def _task(src, folder, name):
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", src)
    t.set_editor_property("destination_path", folder)
    t.set_editor_property("destination_name", name)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", True)
    return t


def _configure(task, kind):
    done = 0
    for path in (task.get_editor_property("imported_object_paths") or []):
        tex = eal.load_asset(str(path).split(".")[0])
        if tex is None:
            continue
        if kind == "bark_normal":
            tex.set_editor_property(
                "compression_settings",
                unreal.TextureCompressionSettings.TC_NORMALMAP)
            tex.set_editor_property("srgb", False)
        elif kind == "packed_normal":
            # TC_MASKS, not TC_NORMALMAP: BC5 keeps two channels and would drop
            # the translucency this map carries in its alpha.
            tex.set_editor_property(
                "compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
            tex.set_editor_property("srgb", False)
        else:
            tex.set_editor_property(
                "compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
            tex.set_editor_property("srgb", True)
        tex.set_editor_property("compression_no_alpha", False)
        tex.set_editor_property("virtual_texture_streaming", True)
        eal.save_loaded_asset(tex)
        done += 1
    return done


# --- bark normals: beside each species' existing bark diffuse ---------------
bark_targets = {{}}
for a in ar.get_assets_by_path(IMPORT_PATH, True):
    if str(a.asset_class_path.asset_name) != "Texture2D":
        continue
    name = str(a.asset_name)
    lname = name.lower()
    if "_bark" not in lname or "normal" in lname:
        continue
    pkg = str(a.package_name)
    rel = pkg[len(IMPORT_PATH):].lstrip("/")
    parts = rel.split("/")
    if not parts or parts[0] == "Instances":
        continue
    bark_targets[(parts[0], pkg.rsplit("/", 1)[0])] = name

bark_tasks = []
for (species, folder), diffuse in sorted(bark_targets.items()):
    stem = diffuse[2:] if diffuse.startswith("T_") else diffuse
    src = os.path.join(TEXTURES_DIR, stem + "_normal.jpg")
    if os.path.exists(src):
        bark_tasks.append(_task(src, folder, "T_" + stem + "_normal"))

# --- packed PVE twig maps: beside each twig asset's leaf textures ------------
twig_folders = {{}}
for a in ar.get_assets_by_path(INSTANCES_PATH, True):
    if str(a.asset_class_path.asset_name) != "Texture2D":
        continue
    pkg = str(a.package_name)
    top = pkg[len(INSTANCES_PATH):].lstrip("/").split("/")[0]
    base = top
    for suffix in ("_twigs_combined_skeletal", "_twigs_combined", "_twigs"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    twig_folders.setdefault(base, pkg.rsplit("/", 1)[0])

packed_tasks = []
if os.path.isdir(TWIGS_DIR):
    for asset_dir in sorted(os.listdir(TWIGS_DIR)):
        tex_dir = os.path.join(TWIGS_DIR, asset_dir, "textures")
        if not os.path.isdir(tex_dir):
            continue
        for fname in sorted(os.listdir(tex_dir)):
            if "_pve_" not in fname or not fname.endswith(".png"):
                continue
            stem = os.path.splitext(fname)[0]
            base = stem.split("_twig_pve_")[0]
            folder = twig_folders.get(base)
            if folder is None:
                print("  no UE folder for %s" % fname)
                continue
            kind = "packed_normal" if "normal" in stem else "packed_basecolor"
            packed_tasks.append(
                (kind, _task(os.path.join(tex_dir, fname), folder, "T_" + stem)))

print("bark normals: %d   packed PVE maps: %d"
      % (len(bark_tasks), len(packed_tasks)))

if bark_tasks:
    tools.import_asset_tasks(bark_tasks)
if packed_tasks:
    tools.import_asset_tasks([t for _, t in packed_tasks])

n = sum(_configure(t, "bark_normal") for t in bark_tasks)
n += sum(_configure(t, kind) for kind, t in packed_tasks)

print("")
print("=" * 60)
print("Auxiliary textures imported and configured: %d" % n)

# MA_Foliage_Trees samples through virtual texture samplers, and UE does not
# refuse a non-virtual texture -- it logs "expects texture ... to be Virtual"
# and the sampler returns garbage, which renders as a colour that changes on
# every recompile. Power-of-two sizing alone does not get auto-VT on import, and
# the USD import creates its own textures that this batch never touched, so
# sweep every texture under the import path rather than only the ones above.
ar.scan_paths_synchronous([IMPORT_PATH], True)
vt_done = 0
vt_skipped = 0
for a in ar.get_assets_by_path(IMPORT_PATH, True):
    if str(a.asset_class_path.asset_name) != "Texture2D":
        continue
    tex = eal.load_asset(str(a.package_name))
    if tex is None:
        continue
    try:
        if tex.get_editor_property("virtual_texture_streaming"):
            vt_skipped += 1
            continue
        tex.set_editor_property("virtual_texture_streaming", True)
        eal.save_loaded_asset(tex)
        vt_done += 1
    except Exception as e:
        print("  [warn] %s: %s" % (a.asset_name, e))
print("Virtual texture streaming: %d converted, %d already virtual"
      % (vt_done, vt_skipped))
print("=" * 60)
'''


def generate_texture_import_script(
    output_dir: Path,
    project_path: str = "/Game/Assets/TheGrove",
    textures_dir: Path | None = None,
    twigs_dir: Path | None = None,
) -> Path:
    """Write the batch that imports bark normals and packed PVE twig maps.

    Numbered 97 so it lands before ``import_batch_98_materials``, which needs
    these textures to exist before it can wire them onto the MICs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / "import_batch_97_textures.py"

    root = Path("data/assets")
    body = _TEXTURE_SCRIPT.format(
        project_path=project_path,
        textures_dir=str((textures_dir or root / "textures").resolve()).replace(
            "\\", "/"
        ),
        twigs_dir=str((twigs_dir or root / "twigs").resolve()).replace("\\", "/"),
    )
    script_path.write_text(body, encoding="utf-8")
    logger.info("Generated auxiliary texture import script: %s", script_path)
    return script_path
