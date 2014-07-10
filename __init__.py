from .scm import ScmCollection as ns
from .bootstrap import BootstrapCollection
from .config import ConfigCollection
import utils

import patch
import tryton
from invoke import Collection
import reviewboard
import tests
import gal
import tryton_component
import project
import bbucket
import userdoc
import quilt

ns.add_collection(BootstrapCollection, 'bs')
ns.add_collection(Collection.from_module(utils))
ns.add_collection(Collection.from_module(patch))
ns.add_collection(Collection.from_module(tryton))
ns.add_collection(Collection.from_module(tests))
ns.add_collection(Collection.from_module(reviewboard), 'rb')
ns.add_collection(ConfigCollection)
ns.add_collection(Collection.from_module(gal))
ns.add_collection(Collection.from_module(tryton_component), 'component')
ns.add_collection(Collection.from_module(project), 'project')
ns.add_collection(Collection.from_module(bbucket), 'bb')
ns.add_collection(Collection.from_module(userdoc), 'doc')
ns.add_collection(Collection.from_module(quilt))
