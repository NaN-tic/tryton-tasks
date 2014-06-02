Task usefull for version migration
----------------------------------


Find modules that doesn't have the old version branch::

  $ invoke missing_branch -b 3.0

Create a branch for old version (only if not exists). It will discard all
changes in the working copy::

  $ invoke create_branch -b 3.0

Push all new branches::

  $ invoke push -c config/nan-tic-unstable.cfg --new-branches

Note that the parameter --new-branches is required to push new created branches.
If not especified mercurial will fail on pushing.

Show all commits from first branch that doesn't exist on second branch::

  $ invoke compare_branches -f 3.0 -s default


Increase version of new migrated modules::

  $ invoke increase_version 3.2.0 -c config/nan-tic-unstable.cfg
