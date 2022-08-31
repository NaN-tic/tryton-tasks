#!/usr/bin/env python
from .scm import ScmCollection as ns
from .bootstrap import BootstrapCollection
from .config import ConfigCollection
from .utils import UtilsCollection
from .tryton import TrytonCollection
from .patches import QuiltCollection
from .sao import SaoCollection

try:
    import trytond
except ImportError:
    trytond = None

ns.add_collection(BootstrapCollection, 'bs')
ns.add_collection(UtilsCollection, 'utils')
ns.add_collection(ConfigCollection, 'config')
ns.add_collection(QuiltCollection, 'quilt')
ns.add_collection(SaoCollection, 'sao')
if trytond:
    ns.add_collection(TrytonCollection, 'tryton')
