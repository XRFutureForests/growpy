
""" Save and load groves as a serialized data string attached to the grove collection.

    Since release 4.2, Blender supports custom properties only of simple Python types like strings and numbers.
    It interpretes byte arrays as strings, and null characters will prematurely end the data.
    This happens when writing the data to a custom property, existing properties can still be read.
    To fix this, encode the data to base64.

    Copyright (c) 2018 - 2025, Wybren van Keulen, The Grove. """

import gzip
import base64

from .Core import import_core
the_grove_core = import_core()


def save_grove(grove, grove_collection):
    """ Save a serialized json string attached to the grove collection. """

    data = the_grove_core.io.grove_to_json_string(grove)
    bytes = data.encode('utf-8')
    compressed_data = gzip.compress(bytes, compresslevel=1)
    data_string = base64.b64encode(compressed_data).decode('utf-8')
    grove_collection['grove'] = data_string


def load_grove(grove_collection):
    """ Read and deserialized the data string stored in the grove collection, for further editing. """
    
    data_string = grove_collection['grove']
    if type(data_string) is bytes:
        # Although it can no longer be written, it can still be read.
        compressed_data = data_string
    else:
        # Blender 4.2 and higher, data is encoded base64 to a regular Python string.
        compressed_data = base64.b64decode(data_string.encode('utf-8'))

    data = gzip.decompress(compressed_data).decode('utf-8')
    grove = the_grove_core.io.grove_from_json_string(data)
    return grove
