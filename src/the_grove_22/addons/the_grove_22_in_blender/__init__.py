
# Copyright 2014 - 2025, Wybren van Keulen, F12 / The Grove
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# The Grove in Blender (the Blender add-on) is licensed under the terms of the Apache 2.0 license.
# The Grove Core module is not bundled, and has its own license separate from the Blender add-on.

bl_info = {
    "name": "The Grove 2.2 in Blender",
    "author": "Wybren van Keulen, The Grove",
    "version": (2, 2, 0),
    "blender": (3, 6, 4),
    "location": "View3D > Add > Grove",
    "description": "Grow true to nature 3D trees.",
    "warning": "",
    "wiki_url": "https://www.thegrove3d.com/learn/",
    "category": "3D View"}

from importlib import reload
from os.path import join, dirname, exists
from json import load

from bpy.utils import register_class, unregister_class


# Enable coding in an external editor. Below lines enable reloading the add-on in Blender.
if "bpy" not in locals():
    from .Languages import Translation
    from . import Languages
    from . import Preferences
    from . import Properties
    from . import Panels
    from . import Turntable
    from .Operators import OperatorSelectLinkedBranches
    from .Operators import OperatorSelectThicker
    from .Operators import OperatorDisableOutline
    from .Operators import OperatorSetBackground
    from .Operators import OperatorGrow
    from .Operators import OperatorGrowTogether
    from .Operators import OperatorRegrow
    from .Operators import OperatorZoom
    from .Operators import OperatorPrune
    from .Operators import OperatorBend
    from .Operators import OperatorTweakSurround
    from .Operators import OperatorTweakShade
    from .Operators import OperatorPlant
    from .Operators import OperatorRoots
    from .Operators import OperatorDraw
    from .Operators import OperatorBuild
    from .Operators import OperatorBuildSkeleton
    from .Operators import OperatorSmooth
    from .Operators import OperatorAnimateWind
    from .Operators import OperatorFile
    from .Operators import OperatorRestart
    from .Operators import OperatorSetTexturesPath
    from .Operators import OperatorSetTwigsPath
    from .Operators import OperatorInstructions
    from .Operators import OperatorTrialEnd
    from .Operators import OperatorAdd
    from .Operators import OperatorReplant
    from .Operators import OperatorTurntable
    from .Operators import OperatorImportExport
    from . import Presets
    from . import Twigs
    from . import Textures
    from . import File
    from .Interface import Interface
    from .Interface import Canvas

else:
    reload(Translation)
    reload(Languages)

    language = bpy.context.preferences.view.language

    match language:
        case 'de_DE':
            reload(Languages.de_DE)
        case 'es':
            reload(Languages.es)
        case 'es_ES':
            reload(Languages.es)
        case 'fr_FR':
            reload(Languages.fr_FR)
        case 'it_IT':
            reload(Languages.it_IT)
        case 'ja_JP':
            reload(Languages.ja_JP)
        case 'ko_KR':
            reload(Languages.ko_KR)
        case 'nl_NL':
            reload(Languages.nl_NL)
        case 'pt_PT':
            reload(Languages.pt_PT)
        case 'zh_CN':
            reload(Languages.zh_CN)
        case 'zh_TW':
            reload(Languages.zh_TW)
        case _:
            reload(Languages.en_US)

    reload(Preferences)
    reload(Properties)

    # Free icons loaded from within panels.
    bpy.utils.previews.remove(Panels.PanelGrove.icons)
    bpy.utils.previews.remove(Panels.PanelSimulate.icons)
    reload(Panels)

    reload(OperatorSelectLinkedBranches)
    reload(OperatorSelectThicker)
    reload(OperatorDisableOutline)
    reload(OperatorSetBackground)
    reload(OperatorGrow)
    reload(OperatorGrowTogether)
    reload(OperatorRegrow)
    reload(OperatorZoom)
    reload(OperatorPrune)
    reload(OperatorBend)
    reload(OperatorTweakSurround)
    reload(OperatorTweakShade)
    reload(OperatorPlant)
    reload(OperatorRoots)
    reload(OperatorDraw)
    reload(OperatorBuild)
    reload(OperatorBuildSkeleton)
    reload(OperatorSmooth)
    reload(OperatorAnimateWind)
    reload(OperatorFile)
    reload(OperatorRestart)
    reload(OperatorSetTexturesPath)
    reload(OperatorSetTwigsPath)
    reload(OperatorInstructions)
    reload(OperatorTrialEnd)
    reload(OperatorAdd)
    reload(OperatorReplant)
    reload(Presets)
    reload(Twigs)
    reload(Textures)
    reload(File)
    reload(Interface)
    reload(Canvas)
    reload(Turntable)
    reload(OperatorTurntable)
    reload(OperatorImportExport)

import bpy

icons = None

def add_operator_to_mesh_menu(self, context):
    """ Called by Blender when filling the Add > Mesh menu. """

    self.layout.separator()
    self.layout.operator(OperatorAdd.GROVE22_OT_Add.bl_idname, text="Grove", icon_value=icons["IconLogo"].icon_id)

classes = (
    OperatorGrow.GROVE22_OT_Grow,
    OperatorGrowTogether.GROVE22_OT_GrowTogether,
    OperatorRegrow.GROVE22_OT_Regrow,
    OperatorZoom.GROVE22_OT_Zoom,
    OperatorPrune.GROVE22_OT_Prune,
    OperatorBend.GROVE22_OT_Bend,
    OperatorTweakSurround.GROVE22_OT_TweakSurround,
    OperatorTweakShade.GROVE22_OT_TweakShade,
    OperatorPlant.GROVE22_OT_Plant,
    OperatorRoots.GROVE22_OT_Roots,
    OperatorDraw.GROVE22_OT_Draw,
    OperatorBuild.GROVE22_OT_Build,
    OperatorBuildSkeleton.GROVE22_OT_BuildSkeleton,
    OperatorSmooth.GROVE22_OT_Smooth,
    OperatorAnimateWind.GROVE22_OT_AnimateWind,
    OperatorFile.GROVE22_OT_File,
    Properties.GROVE22_Properties,
    Panels.PanelPresets,
    Panels.PanelTwigs,
    Panels.PanelTwigsMore,
    Panels.PanelSimulate,
    Panels.PanelRecord,
    Panels.PanelSow,
    Panels.PanelReact,
    Panels.PanelSurround,
    Panels.PanelStake,
    Panels.PanelAutoPrune,
    Panels.PanelFlow,
    Panels.PanelDrop,
    Panels.PanelAdd,
    Panels.PanelGrow,
    Panels.PanelTurn,
    Panels.PanelThicken,
    Panels.PanelBend,
    Panels.PanelShade,
    Panels.PanelBuild,
    Panels.PanelBuildMesh,
    Panels.PanelBuildTexture,
    Panels.PanelBuildBase,
    Panels.PanelEdit,
    Panels.PanelGrove,
    Preferences.GROVE22_Preferences,
    OperatorSetTexturesPath.GROVE22_OT_SetTexturesPath,
    OperatorSetTwigsPath.GROVE22_OT_SetTwigsPath,
    OperatorInstructions.GROVE22_OT_Instructions,
    OperatorTrialEnd.GROVE22_OT_TrialEnd,
    OperatorSelectLinkedBranches.GROVE22_OT_SelectLinkedBranches,
    OperatorSelectThicker.GROVE22_OT_SelectThicker,
    OperatorTurntable.GROVE22_OT_Turntable,
    OperatorDisableOutline.GROVE22_OT_DisableOutline,
    OperatorSetBackground.GROVE22_OT_SetBackground,
    OperatorRestart.GROVE22_OT_Restart,
    OperatorAdd.GROVE22_OT_Add,
    OperatorReplant.GROVE22_OT_Replant,
    Presets.GROVE22_OT_Preset_Remove,
    Presets.GROVE22_OT_Preset_Cancel,
    Presets.GROVE22_OT_Preset_Rename,
    Presets.GROVE22_OT_Preset_Save,
    Presets.GROVE22_OT_Preset_Overwrite,
    Presets.GROVE22_OT_Preset_Import,
    OperatorImportExport.GROVE22_OT_Export_Grove,
    OperatorImportExport.GROVE22_OT_Import_Grove,
)


def create_manual_map():
    """ Right clicking an interface widget lists an option for online manual. """

    manual_map = (
        ('bpy.ops.the_grove_22.grow', '/learn/grow'),
        ('bpy.ops.the_grove_22.regrow', '/learn/grow'),
        ('bpy.ops.the_grove_22.prune', '/learn/shade-drop-and-prune'),
        ('bpy.ops.the_grove_22.bend', '/releases/the-grove-release-9'),
        ('bpy.ops.the_grove_22.draw', '/releases/the-grove-release-10'),
        ('bpy.ops.the_grove_22.plant', '/learn/grow'),
        ('bpy.ops.the_grove_22.file', '/learn/simulation-files'),
        ('bpy.ops.the_grove_22.roots', '/releases/the-grove-release-11'),
        ('bpy.ops.the_grove_22.build', '/learn/build'),
        ('bpy.ops.the_grove_22.*', '/learn'),
        ('bpy.types.grove22_properties.simulation_scale', '/learn/twigs'),
        ('bpy.types.grove22_properties.turn*', '/learn/turn'),
        ('bpy.types.grove22_properties.shade*', '/learn/shade-drop-and-prune'),
        ('bpy.types.grove22_properties.drop*', '/learn/shade-drop-and-prune'),
        ('bpy.types.grove22_properties.auto_prune*', '/learn/shade-drop-and-prune'),
        ('bpy.types.grove22_properties.thicken*', '/learn/bend'),
        ('bpy.types.grove22_properties.bend*', '/learn/bend'),
        ('bpy.types.grove22_properties.react*', '/learn/react'),
        ('bpy.types.grove22_properties.record*', '/learn/animate-growth-and-wind'),
        ('bpy.types.grove22_properties.twig*', '/learn/twigs'),
        ('bpy.types.grove22_properties.*', '/learn/'),
    )

    return 'https://www.thegrove3d.com', manual_map

def configure():
    """ Initialize the presets, textures and twigs paths.
        If a path is empty, try getting the path from config.json for a studio-wide configuration.
        If config.json does not exist, try setting the default path, if it exists. """

    preferences = bpy.context.preferences.addons[__package__].preferences
    path = join(dirname(__file__), "config.json")
    if not exists(path):
        return

    config = {}
    try:
        with open(path, 'r') as preset_file:
            config = load(preset_file)
    except IOError:
        pass

    if preferences.twigs_path == '':
        if 'twigs_path' in config and config['twigs_path'] != "":
            if exists(config['twigs_path']):
                preferences.twigs_path = config['twigs_path']
                print('The Grove - Found config.json, set twigs_path to: ' + config['twigs_path'])
            else:
                print('WARNING! The twigs_path in config.json points to a non-existing folder.')
    if preferences.twigs_path == '':
        default_path = join(dirname(dirname(dirname(__file__))), "twigs")
        if exists(default_path):
            preferences.twigs_path = default_path
            print('The Grove - Set twigs_path to default location at: ' + default_path)

    if preferences.textures_path == '':
        if 'textures_path' in config and config['textures_path'] != "":
            if exists(config['textures_path']):
                preferences.textures_path = config['textures_path']
                print('The Grove - Found config.json, set textures_path to: ' + config['textures_path'])
            else:
                print('WARNING! The textures_path in config.json points to a non-existing folder.')
    if preferences.textures_path == '':
        default_path = join(dirname(dirname(dirname(__file__))), "textures")
        if exists(default_path):
            preferences.textures_path = default_path
            print('The Grove - Set textures_path to default location at: ' + default_path)

    if preferences.presets_path == '':
        if 'presets_path' in config and config['presets_path'] != "":
            if exists(config['presets_path']):
                preferences.presets_path = config['presets_path']
                print('The Grove - Found config.json, set presets_path to: ' + config['presets_path'])
            else:
                print('WARNING! The presets_path in config.json points to a non-existing folder.')
    if preferences.presets_path == '':
        default_path = join(dirname(dirname(dirname(__file__))), "presets")
        if exists(default_path):
            preferences.presets_path = default_path
            print('The Grove - Set presets_path to default location at: ' + default_path)


def register():
    """ Called once at Blender startup. """

    global icons
    icons = bpy.utils.previews.new()
    icons_directory = join(join(dirname(__file__), "Resources"), "IconsBright")
    icons.load("IconLogo", join(icons_directory, "IconLogo.png"), 'IMAGE')

    for cls in classes:
        register_class(cls)

    bpy.types.Collection.GROVE22_Properties = bpy.props.PointerProperty(type=Properties.GROVE22_Properties)
    bpy.types.VIEW3D_MT_add.append(add_operator_to_mesh_menu)
    bpy.utils.register_manual_map(create_manual_map)

    from .Core import import_core
    the_grove_core = import_core()

    if hasattr(the_grove_core, 'is_fallback'):
        bpy.context.preferences.addons[__package__].preferences.edition = 'FALLBACK'
    else:
        bpy.context.preferences.addons[__package__].preferences.edition = the_grove_core.about.edition.upper()
        if hasattr(the_grove_core.about, 'is_trial'):
            bpy.context.preferences.addons[__package__].preferences.is_trial = the_grove_core.about.is_trial

    configure()


def unregister():
    """ Cleanup. """

    bpy.types.VIEW3D_MT_add.remove(add_operator_to_mesh_menu)
    bpy.utils.previews.remove(icons)

    for cls in reversed(classes):
        unregister_class(cls)

    bpy.utils.unregister_manual_map(create_manual_map)
