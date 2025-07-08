""" Load the platform specific module and make it take the place of this module. """

from os.path import dirname, join
import sys
from importlib.util import spec_from_file_location, module_from_spec

from platform import system, machine

module_name = 'fallback'

if system() == 'Windows':
    module_name = 'the_grove_22_core_windows.pyd'
elif system() == 'Linux':
    module_name = 'the_grove_22_core_linux.so'
elif system() == 'Darwin':
    if machine() == 'arm64':
        module_name = 'the_grove_22_core_macos.so'
    else:
        module_name = 'the_grove_22_core_macos_intel.so'

module_path = join(dirname(__file__), module_name)
spec = spec_from_file_location(__name__, module_path)
module = module_from_spec(spec)
sys.modules[__name__] = module
spec.loader.exec_module(module)