# runtime package

from .__main__ import libmain, __version__
from . import common, api, pattern as pat, compiler, sim

DistProcess = sim.DistProcess
import_da = api.import_da
__all__ = ["__version__", "pat", "api", "libmain", "compiler", "DistProcess",
           "import_da"]

for name in common.api_registry.keys():
    globals()[name] = common.api_registry[name]
    __all__.append(name)
