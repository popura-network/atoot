Quickstart
==========

A general information about asynchronous I/O in Python can be found in the `standard library documentation`_.

.. _standard library documentation: https://docs.python.org/3/library/asyncio.html

Installation
------------

::

   pip install -U atoot


Register an application and get the authentication token
--------------------------------------------------------

The first thing we will need to do is to register an application, in order to be able to generate access tokens later. The application can be created like so:

.. code-block:: python

   instance = "botsin.space"

   async with aiohttp.ClientSession() as session:
      client_id, client_secret = await atoot.MastodonAPI.create_app(session, 
         instance, client_name="test_bot", 
         client_website="https://example.com/")

      print(client_id, client_secret)


In the above example, we specify the client name and website, which will be shown on statuses if applicable. 

These *client_id* and *client_secret* values will be used to generate access tokens, so they should be cached for later use. 

Now that we have an application, let's obtain an access token that will authenticate our requests as that client application. 

There are 2 ways to get access token:

1) Visit the special URL with your browser, which can be generated like so:

.. code-block:: python

   login_url = atoot.MastodonAPI.browser_login_url(instance, client_id)
   print(login_url)

It will display access token after user authentication.

2) Use username and password to generate access_token without a browser:

.. code-block:: python

   instance = "botsin.space"
   client_id, client_secret = "...", "..."
   username, password = "example@email.com", "Pa$$w0rd"

   async with aiohttp.ClientSession() as session:
      access_token = await atoot.MastodonAPI.login(session, instance, 
         client_id, client_secret, username=username, password=password)
      print(access_token)

Once you have the access token, save it in your local cache. 

Use the authenticated client
----------------------------

With an access token you may use every other API method, for example:

.. code-block:: python

    instance = "botsin.space"
    access_token = "SAVED_ACCESS_TOKEN_VALUE"

    async with atoot.client(instance, access_token=access_token) as c:
        # Retrieve your account information
        print(await c.verify_account_credentials())
        # Create a status 
        print(await c.create_status(status="Hello world!"))
        # Get 3 pages of a local timeline
        print(await c.get_n_pages(c.public_timeline(local=True), n=3))

Pagination
----------

In this example, the script gets 3 pages of Gargron's statuses:

.. code-block:: python

    async with atoot.client(instance, access_token=access_token) as c:
        # Search for Gargron's account
        accs = await c.account_search("@Gargron@mastodon.social")
        if len(accs) > 0:
            gargron = accs[0]

            # Fetch the first page of his statuses
            statuses = await c.account_statuses(gargron)
            print(statuses)
            page = 1

            # Fetch the next page if there is one
            while statuses.next and page <= 3:
                statuses = await c.get_next(statuses)
                print(statuses)
                page += 1

            # the other way to do the same is to use a shortcut function
            statuses = await c.get_n_pages(c.account_statuses(gargron), n=3)
            # you can also get all available results (beware API rate limits!)
            statuses = await c.get_all(c.account_statuses(gargron))

