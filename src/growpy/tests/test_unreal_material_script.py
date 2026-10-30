"""import_batch_98_materials: the parent-material lookup.

XRFF_Twin keeps no MA_Foliage_Trees copy at db_path; the batch must fall back
to the PVE plugin's own master rather than abort.
"""

import ast

from growpy.io.unreal.pve_asset_script import DEFAULT_MASTER_MATERIAL
from growpy.io.unreal.unreal_material_script import _build_material_script


def test_falls_back_to_the_plugin_master():
    text = _build_material_script(
        "/Game/Generated/Trees",
        {},
        parent_material_path="/Game/00_XRFF/20_DigitalTwinDatabase/MA_Foliage_Trees",
    )
    ast.parse(text)  # the template renders to valid python
    assert (
        'PARENT_MATERIAL_PATH = "/Game/00_XRFF/20_DigitalTwinDatabase/MA_Foliage_Trees"'
        in text
    )
    assert f'PLUGIN_MATERIAL_PATH = "{DEFAULT_MASTER_MATERIAL}"' in text
    # the configured copy is tried first, the plugin only when it is absent
    assert text.index("does_asset_exist(PARENT_MATERIAL_PATH)") < text.index(
        "does_asset_exist(PLUGIN_MATERIAL_PATH)"
    )
