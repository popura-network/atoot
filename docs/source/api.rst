.. _api:

Developer Interface
===================

.. module:: atoot

This page of the documentation will cover all methods and classes available to the developer.

Core Interface
--------------

.. automethod:: MastodonAPI.create
.. automethod:: MastodonAPI.close

.. automethod:: MastodonAPI.get_next
.. automethod:: MastodonAPI.get_previous
.. automethod:: MastodonAPI.get_n_pages
.. automethod:: MastodonAPI.get_all

.. automethod:: MastodonAPI.create_app
.. automethod:: MastodonAPI.browser_login_url
.. automethod:: MastodonAPI.login
.. automethod:: MastodonAPI.revoke_token
.. automethod:: MastodonAPI.verify_app_credentials
.. automethod:: MastodonAPI.register_account

.. automethod:: MastodonAPI.verify_account_credentials
.. automethod:: MastodonAPI.update_account_credentials

Context manager
---------------

.. autofunction:: client


Exceptions
----------

.. autoexception:: atoot.MastodonError
