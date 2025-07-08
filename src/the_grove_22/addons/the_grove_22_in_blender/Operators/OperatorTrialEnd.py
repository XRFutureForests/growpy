
""" Open up a web page with instructions on how to install The Grove Core.

    Copyright 2023 - 2025, Wybren van Keulen, The Grove """

from bpy.types import Operator
from ..Languages.Translation import t
from webbrowser import open as open_url_in_browser


class GROVE22_OT_TrialEnd(Operator):

    bl_idname = "the_grove_22.trial_end"
    bl_label = t('trial_end')
    bl_description = t('trial_end_tt')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        open_url_in_browser("https://www.thegrove3d.com/buy/")

        return {"FINISHED"}
