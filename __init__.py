#!/usr/bin/env python
from .scm import ScmCollection as ns
from .bootstrap import BootstrapCollection
from .config import ConfigCollection
from .utils import UtilsCollection
from .tryton import TrytonCollection
from .project import ProjectCollection
from .patches import QuiltCollection
from .gal import GalCollection
from .pypi import PypiCollection
from .startup import StartupCollection
from .sao import SaoCollection
from .database import DatabaseCollection
from .features import FeatureCollection

ns.add_collection(BootstrapCollection, 'bs')
ns.add_collection(UtilsCollection, 'utils')
ns.add_collection(ConfigCollection, 'config')
ns.add_collection(TrytonCollection, 'tryton')
ns.add_collection(ProjectCollection, 'project')
ns.add_collection(QuiltCollection, 'quilt')
ns.add_collection(GalCollection, 'gal')
ns.add_collection(PypiCollection, 'pypi')
ns.add_collection(StartupCollection, 'startup')
ns.add_collection(SaoCollection, 'sao')
ns.add_collection(DatabaseCollection, 'database')
ns.add_collection(FeatureCollection, 'features')
