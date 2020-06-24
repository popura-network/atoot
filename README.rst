=====
atoot
=====

*atoot* is a Python library providing an easy way to create Mastodon API applications.

Key features
============

- Python 3 library
- Asynchronous networking with asyncio and aiohttp
- Every API method is implemented https://docs.joinmastodon.org/methods/
- Client as a context manager
- Results pagination

Requirements
============

- aiohttp
- pytest (for tests)

Getting started
===============

Install
-------

::

   pip install atoot


Use
---

Basic usage example:

.. code-block:: python

   import atoot
   import asyncio

   async def mastodon_bot():
       instance = "botsin.space"
       access_token = "YOUR_APPLICATION_ACCESS_TOKEN"

       client = await atoot.MastodonAPI.create(instance, access_token=access_token)
       resp = await client.verify_account_credentials()
       print(resp)
       await client.close()

   asyncio.run(mastodon_bot())


Using client as a context manager, get 5 pages of home timeline and all notifications:

.. code-block:: python

   async def mastodon_bot():
       instance = "botsin.space"
       access_token = "YOUR_APPLICATION_ACCESS_TOKEN"

       async with atoot.client(instance, access_token=access_token) as c:
           home = await c.get_n_pages(c.home_timeline(limit=20), n=5)
           print("Home timeline:", home)

           notifs = await c.get_all(c.get_notifications())
           print("Notifications:", notifs)


License
=======

MIT
