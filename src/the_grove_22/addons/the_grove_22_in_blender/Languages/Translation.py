
""" Copyright 2017 - 2025, Wybren van Keulen, The Grove
    The Grove in Blender's very own translation system. """

import bpy
from importlib import import_module
from .en_US import dictionary as dictionary_fallback


language = bpy.context.preferences.view.language

# Blender 4.4 changed the Chinese language identifiers.
if language == 'zh_CN':
    language = 'zh_HANT'
if language == 'zh_TW':
    language = 'zh_HANS'

if language in ['ja_JP', 'zh_HANT', 'zh_HANS', 'es', 'fr_FR', 'it_IT', 'pt_PT', 'de_DE', 'nl_NL', 'ko_KR']:
    dictionary = import_module("." + language, package=__package__).dictionary
else:
    dictionary = import_module(".en_US", package=__package__).dictionary


def t(phrase: str):
    """ Translate the give phrase into Blender's current language. """

    if phrase in dictionary:
        phrase_translated = dictionary[phrase]
    elif phrase in dictionary_fallback:
        print("Missing translation for: " + str(phrase))
        phrase_translated = dictionary_fallback[phrase]
    else:
        # Missing translation.
        return phrase

    # Blender adds a period to the end of tooltips, so to prevent double periods at the end, strip the existing period.
    if phrase.endswith('_tt') and phrase_translated.endswith('.'):
        return phrase_translated[:-1]
    else:
        return phrase_translated
