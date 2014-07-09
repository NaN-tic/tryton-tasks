import bootstrap
import utils
from .scm import *
import patch
import tryton
from invoke import Collection
import reviewboard
import tests
import config
import gal
import tryton_component
import project
import bbucket
import userdoc
import quilt

ns = Collection()
ns.add_task(clone)
ns.add_task(status)
ns.add_task(resolve)
ns.add_task(diff)
ns.add_task(summary)
ns.add_task(outgoing)
ns.add_task(push)
ns.add_task(pull)
ns.add_task(update)
ns.add_task(repo_list)
ns.add_task(fetch)
ns.add_task(unknown)
ns.add_task(stat)
ns.add_task(branch)
ns.add_task(missing_branch)
ns.add_task(create_branch)
ns.add_task(compare_branches)
ns.add_task(module_diff)
ns.add_task(add2virtualenv)
ns.add_task(increase_version)
ns.add_task(revision)
ns.add_task(clean)
ns.add_collection(Collection.from_module(bootstrap), 'bs')
ns.add_collection(Collection.from_module(utils))
ns.add_collection(Collection.from_module(patch))
ns.add_collection(Collection.from_module(tryton))
ns.add_collection(Collection.from_module(tests))
ns.add_collection(Collection.from_module(reviewboard), 'rb')
ns.add_collection(Collection.from_module(config))
ns.add_collection(Collection.from_module(gal))
ns.add_collection(Collection.from_module(tryton_component), 'component')
ns.add_collection(Collection.from_module(project), 'project')
ns.add_collection(Collection.from_module(bbucket), 'bb')
ns.add_collection(Collection.from_module(userdoc), 'doc')
ns.add_collection(Collection.from_module(quilt))


