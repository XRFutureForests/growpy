
""" In the add-on's preferences you can change the language,
    the twigs and bark textures folders, and several other options.
    Copyright 2014 - 2025, Wybren van Keulen, The Grove """


import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatProperty

from .Languages.Translation import t
from .Twigs import list_twigs
from .Textures import list_textures


class GROVE22_Preferences(AddonPreferences):
    """ The preferences can be found in Blender > Edit > Preferences > Add-ons > 3D View: Grove 2.2. """

    bl_idname = __package__

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    edition: EnumProperty(
        name="Edition",
        items={
            ('STARTER', 'Starter', 'Starter edition'),
            ('INDIE', 'Indie', 'Indie edition'),
            ('STUDIO', 'Studio', 'Studio edition'),
            ('FALLBACK', 'Fallback', 'Fallback for when no core module is installed')
        },
        default='INDIE')

    is_trial: BoolProperty(
        name="Trial version",
        default=False,
        options={'HIDDEN'})

    refresh_textures: BoolProperty(
        name="Refresh Textures List",
        default=True,
        options={'HIDDEN'})

    refresh_twigs: BoolProperty(
        name="Refresh Twigs List",
        default=True,
        options={'HIDDEN'})

    def tag_refresh_twigs(self, context):
        """ Set a flag to refresh the list of twigs the next time the twigs menu is filled. """

        self.refresh_twigs = True
        if self.twigs_path.startswith('//'):
            self.twigs_path = bpy.path.abspath(self.twigs_path)

        # Changing to another folder, check each grove collection and set the twig picker to t('twig_pick_objects')
        try:
            for collection in bpy.data.collections:
                if 'GROVE22_Properties' in collection and collection.GROVE22_Properties.unique_id != '':
                    collection.GROVE22_Properties.twig_menu = list_twigs(context)[0][0]
        except:
            pass

    def tag_refresh_textures(self, context):
        """ Set a flag to refresh the list of textures the next time the textures menu is filled. """

        self.refresh_textures = True
        if self.textures_path.startswith('//'):
            self.textures_path = bpy.path.abspath(self.textures_path)

        # Changing to another folder, check each grove collection and set the texture picker to the first item
        # in the list. This also fixes the bug when selecting a folder with less textures than the previous folder,
        # that would set the twig_menu to a value that is no longer in the textures_menu.
        try:
            for collection in bpy.data.collections:
                if 'GROVE22_Properties' in collection and collection.GROVE22_Properties.unique_id != '':
                    collection.GROVE22_Properties.texture_bark = list_textures(context)[0][0]
        except:
            pass

    presets_path: StringProperty(
        name=t('presets_path'),
        description=t('presets_path_tt'),
        subtype='DIR_PATH')

    textures_path: StringProperty(
        name=t('textures_path'),
        description=t('textures_path_tt'),
        subtype='DIR_PATH',
        update=tag_refresh_textures)

    twigs_path: StringProperty(
        name=t('twigs_path'),
        description=t('twigs_path_tt'),
        subtype='DIR_PATH',
        update=tag_refresh_twigs)

    use_adaptive_units: BoolProperty(
        name=t('use_adaptive_units'),
        default=True,
        description=t('use_adaptive_units_tt'))

    use_scientific_names: BoolProperty(
        name=t('use_scientific_names'),
        default=False,
        description=t('use_scientific_names_tt'))

    widget_scale: FloatProperty(
        name=t('widget_scale'), description=t('widget_scale_tt'),
        default=1.0, min=0.2, soft_max=2.0, step=10, precision=1,
        update=None)

    recent_files: StringProperty(
        name='recent_files',
        description='recent_files_tt')

    def update_language(self, context):
        """ Grove's user preferences allow you to pick a language. This sets Blender's overall language,
            but if international fonts is enabled, but Interface and Tooltips below are disabled,
            only Grove's interface is translated.

            When selecting (or setting by script) a new language, the three options for Interface,
            Tooltips and New Data are all automatically set, which is not what I want.
            So before setting the language, save the state for these 3 options, set the language and reset the states.
            Put this in a try statement, because things will probably change! """

        preferences = context.preferences.view

        try:
            use_translate_tooltips = preferences.use_translate_tooltips
            use_translate_interface = preferences.use_translate_interface
            use_translate_new_dataname = preferences.use_translate_new_dataname
        except AttributeError:
            pass

        language = self.language
        if bpy.app.version[0] == 4 and bpy.app.version[1] < 4:
            if language == 'zh_HANT':
                language = 'zh_CN'
            if language == 'zh_HANS':
                language = 'zh_TW'
        preferences.language = self.language

        try:
            preferences.use_translate_tooltips = use_translate_tooltips
            preferences.use_translate_interface = use_translate_interface
            preferences.use_translate_new_dataname = use_translate_new_dataname
        except AttributeError:
            pass

        bpy.ops.script.reload()

    languages = [
        ('en_US', 'English', 'English'),
        ('es', 'Español', 'Spanish'),
        ('it_IT', 'Italiano', 'Italian'),
        ('ja_JP', '日本語', 'Japanese'),
        ('zh_HANS', '简体中文', 'Simplified Chinese'),
        ('zh_HANT', '繁體中文', 'Traditional Chinese'),
        ('fr_FR', 'Français', 'French'),
        ('de_DE', 'Deutsch', 'German'),
        ('pt_PT', 'Português', 'Portuguese'),
        ('nl_NL', 'Nederlands', 'Dutch'),
        ('ko_KR', '한국어', 'Korean')]

    language: EnumProperty(
        name=t('language'), description=t('language_tt'),
        items=languages,
        default='en_US',
        update=update_language)

    def draw(self, _):
        """ Draw the interface of the preferences panel. """

        layout = self.layout
        layout.use_property_split = True

        layout.prop(self, 'language', expand=False)
        layout.prop(self, 'twigs_path')
        layout.prop(self, 'textures_path')
        layout.prop(self, 'presets_path')
        layout.prop(self, 'widget_scale')
        layout.prop(self, 'use_adaptive_units')
        layout.prop(self, 'use_scientific_names')

        layout.separator()
