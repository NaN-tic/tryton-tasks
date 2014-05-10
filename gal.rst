Managing demo databases
=======================

Galatea allows you to easily create and store demo tryton databases. It is a
command line application integrated with NaN·tic’s tryton-tasks utilities which
use the invoke application.

With Galatea every action we make to a sample database is stored so it can later
be reused and thus it is possible to create two different databases (one for
demonstrating project management and another one for demonstrating production
but reusing the accounting installation and configuration stuff by doing it only
once). In fact, not only the action is stored, but the full database, so it is
very quick to go back and execute new commands to a previous database.

Just take a look at the sample session to get a quick introduction.


Sample session
--------------

First let’s create a new database with English as default language::

  $ invoke gal.create --language en_US

Let’s make all modules to install Catalan and Spanish languages too::

  $ invoke gal.set_active_languages -l ca_ES,es_ES

And now let’s install party module (and its dependencies)::

  $ invoke gal.install_modules -m party

Now, we can install the purchase module::

  $ invoke gal.install_modules -m purchase

Now let’s store this database with a name we can reuse with our trytond
instance::

  $ invoke gal.get demo_purchase

So that's it so far. Now you have a PostgreSQL database named *demo_database*
available for using with a standard Tryton client and server which will have the
purchase module with Catalan, Spanish and English languages installed, with the
latter as the default one.

Let’s say that we want another sample database without the purchase module but
with the sale one. For that, we need to go to galatea’s mercurial repository and
move to the revision where we installed the party module. This way, we do not
need to create a new database, install languages and party module again::

  $ cd gal
  gal$ hg log -f
  changeset:   3:5a1da489cd2a
  tag:         tip
  user:        Albert Cervera i Areny <albert@nan-tic.com>
  date:        Fri Apr 25 17:06:04 2014 +0200
  files:       gal.sql
  description:
  ["install_modules", {"modules": "purchase"}]

  changeset:   2:5354aa108fef
  user:        Albert Cervera i Areny <albert@nan-tic.com>
  date:        Fri Apr 25 17:01:36 2014 +0200
  files:       gal.sql
  description:
  ["install_modules", {"modules": "party"}]

  changeset:   1:46f004319b92
  user:        Albert Cervera i Areny <albert@nan-tic.com>
  date:        Fri Apr 25 17:00:04 2014 +0200
  files:       gal.sql
  description:
  ["set_active_languages", {"lang_codes": "en_US,es_ES"}]

  changeset:   0:d0dcff4675dd
  user:        Albert Cervera i Areny <albert@nan-tic.com>
  date:        Fri Apr 25 16:59:47 2014 +0200
  files:       gal.sql
  description:
  ["create", {"password": null, "language": "ca_ES"}]

So we need to move to changeset 2 so we do::

  gal$ hg update 2
  gal$ cd ..

And now we can install the sale module on top of the database which has party
module installed (changeset 2)::

  $ invoke gal.install_modules sale

And now we can see the log again::

  $ cd gal
  gal$ hg log -f
  changeset:   4:123cb2a0cdc6
  tag:         tip
  parent:      2:5354aa108fef
  user:        Albert Cervera i Areny <albert@nan-tic.com>
  date:        Fri Apr 25 17:10:35 2014 +0200
  files:       gal.sql
  description:
  ["install_modules", {"modules": "sale"}]

  changeset:   2:5354aa108fef
  user:        Albert Cervera i Areny <albert@nan-tic.com>
  date:        Fri Apr 25 17:01:36 2014 +0200
  files:       gal.sql
  description:
  ["install_modules", {"modules": "party"}]

  changeset:   1:46f004319b92
  user:        Albert Cervera i Areny <albert@nan-tic.com>
  date:        Fri Apr 25 17:00:04 2014 +0200
  files:       gal.sql
  description:
  ["set_active_languages", {"lang_codes": "en_US,es_ES"}]

  changeset:   0:d0dcff4675dd
  user:        Albert Cervera i Areny <albert@nan-tic.com>
  date:        Fri Apr 25 16:59:47 2014 +0200
  files:       gal.sql
  description:
  ["create", {"password": null, "language": "ca_ES"}]

Now we can keep the current database::

  $ invoke gal.get demo_sale

Now we can start the server, open the client and modify anything we want from
demo_sale or demo_purchase databases. If we later want to import this modified
database into gal as a new version, we can do it by simply executing::

  $ invoke gal.set demo_sale

Now we can see the last commit (instead of the full log of the current head) by
using::

  $ cd gal
  gal$ hg parent
  changeset:   7:c122f040f645
  tag:         tip
  user:        Albert Cervera i Areny <albert@nan-tic.com>
  date:        Fri Apr 25 18:18:10 2014 +0200
  files:       gal.sql
  description:
  ["set", {}]

.. Note:: As Galatea cannot know what you did to the database before importing
   it, it will not be possible to replay this tree path in the future.


Galfile
-------

By using invoke gal.build it is also possible to create a database using a
configuration file. For example, the following file will create a new database
with Catalan as default language, install the demo_base module, create a company
named nan-tic, add 100 parties and store the result in a database named
my_new_database::

  create(language='ca_ES')
  install_modules(modules='demo_base')
  create_company(name='nan-tic')
  create_parties(count=100)
  get(name='my_new_database')

So to run it simply store this in a file named Galfile and run::

  $ invoke gal.build

or give it another name and run::

  $ invoke gal.build filename

The result will be the same as if you had invoked each command individually and
thus each step will be a new commit in the gal repository.

If you executed several commands in a clean gal repository, you can also get the
Galfile necessary for reproducing all the steps again in the same or another
machine without the need of sharing all the repository. It is also very useful
if you want to change some parameters or steps. Simply type::

  $ invoke gal.galfile

And you'll get the file in standard output so you can store it easily::

  $ invoke gal.galfile > Galfile


Other commands
--------------

We're adding new gal commands all the time and are not documented here. However,
you can easily get the list of all the available ones with::

  $ invoke -l | grep " gal"

and get more information about any of them with::

  $ invoke --help gal.command

All of them should have a proper explanation of what they do.
