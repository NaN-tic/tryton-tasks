import bootstrap
import utils
from .scm import *
import patch

from invoke import Collection


ns = Collection()
ns.add_task(clone)
ns.add_task(status)
ns.add_task(diff)
ns.add_task(summary)
ns.add_task(outgoing)
ns.add_task(pull)
ns.add_task(update)
ns.add_task(repo_list)
ns.add_collection(Collection.from_module(bootstrap), 'bs')
ns.add_collection(Collection.from_module(utils))
ns.add_collection(Collection.from_module(patch))
