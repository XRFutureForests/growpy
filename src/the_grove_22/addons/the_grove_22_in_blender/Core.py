""" Try importing the simulation core, or return a fallback to prevent errors.

    Copyright 2014 - 2025, Wybren van Keulen, The Grove """

from platform import system, machine
from importlib import import_module

def import_core():
    try:
        return __import__("the_grove_22_core")
    except ImportError:
        return import_module(".Fallback", package=__package__)
