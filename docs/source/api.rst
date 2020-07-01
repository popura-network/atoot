.. _api:

Developer Interface
===================

.. module:: atoot

This page of the documentation will cover all methods and classes available to the developer.

Context manager
---------------

.. autofunction:: client

Core Interface
--------------

.. automethod:: MastodonAPI.create
.. automethod:: MastodonAPI.close

.. automethod:: MastodonAPI.create_app
.. automethod:: MastodonAPI.browser_login_url
.. automethod:: MastodonAPI.login
.. automethod:: MastodonAPI.revoke_token
.. automethod:: MastodonAPI.verify_app_credentials
.. automethod:: MastodonAPI.register_account

Accounts
--------

.. automethod:: MastodonAPI.verify_account_credentials
.. automethod:: MastodonAPI.update_account_credentials
.. automethod:: MastodonAPI.account
.. automethod:: MastodonAPI.account_statuses
.. automethod:: MastodonAPI.account_follow
.. automethod:: MastodonAPI.account_unfollow
.. automethod:: MastodonAPI.account_search

Statuses
--------

.. automethod:: MastodonAPI.create_status
.. automethod:: MastodonAPI.delete_status
.. automethod:: MastodonAPI.view_status
.. automethod:: MastodonAPI.status_context
.. automethod:: MastodonAPI.status_favourite
.. automethod:: MastodonAPI.status_unfavourite
.. automethod:: MastodonAPI.status_boost
.. automethod:: MastodonAPI.status_unboost

Media
-----

.. automethod:: MastodonAPI.upload_attachment
.. automethod:: MastodonAPI.update_attachment

Timelines
---------

.. automethod:: MastodonAPI.public_timeline
.. automethod:: MastodonAPI.hashtag_timeline
.. automethod:: MastodonAPI.home_timeline
.. automethod:: MastodonAPI.list_timeline

Notifications
-------------

.. automethod:: MastodonAPI.get_notifications
.. automethod:: MastodonAPI.get_notification
.. automethod:: MastodonAPI.clear_notifications
.. automethod:: MastodonAPI.clear_notification

Streaming API
-------------

.. automethod:: MastodonAPI.streaming

Pagination
----------

Every list of entities (i.e. list of Status objects) returned by the API can be 
used with the following pagination methods.

.. automethod:: MastodonAPI.get_next
.. automethod:: MastodonAPI.get_previous
.. automethod:: MastodonAPI.get_n_pages
.. automethod:: MastodonAPI.get_all


Exceptions
----------

.. autoexception:: atoot.MastodonError
.. autoexception:: atoot.NetworkError
.. autoexception:: atoot.ApiError
.. autoexception:: atoot.ClientError
.. autoexception:: atoot.UnauthorizedError
.. autoexception:: atoot.ForbiddenError
.. autoexception:: atoot.NotFoundError
.. autoexception:: atoot.ConflictError
.. autoexception:: atoot.GoneError
.. autoexception:: atoot.UnprocessedError
.. autoexception:: atoot.RatelimitError
.. autoexception:: atoot.ServerError
.. autoexception:: atoot.UnavailableError
