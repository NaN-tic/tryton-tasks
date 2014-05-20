Managing Code Reviews and Tryton tasks
--------------------------------------

Creating a codereview (to reviewboard and Tryton)::

  $ invoke project.upload_review -p modules/project_component -t 000086

Downloading a review::


  $ invoke project.fetch -t 000086

Per tancar un codereview::

  $ invoke project.close -t 000086
