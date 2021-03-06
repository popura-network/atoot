#!/usr/bin/python3
import asyncio
import uuid
import time

from collections import UserList
from urllib.parse import urlencode
from contextlib import asynccontextmanager, suppress

import aiohttp

__useragent__ = "atoot/1.x; (+https://github.com/popura-network/atoot)"
SCOPES = 'read write follow'
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'

def str_bool(b):
    """Convert boolean to a string, in the way expected by the API."""
    return "true" if b else "false"

def get_id(item):
    """Return id of an item if it's a dict"""
    if type(item) == dict and "id" in item:
        return item["id"]
    else:
        return item

class ResponseList(UserList):
    """List-like datatype for Mastodon API results pagination"""

    def __init__(self, data, method=None, **kwargs):
        self.data = data
        self.method = method
        self.kwargs = kwargs
        self.next = None
        self.previous = None


class MastodonAPI:

    @classmethod
    async def create(cls, instance, client_id=None, client_secret=None, 
            access_token=None, use_https=True, session=None):
        """Async factory method. 

        :param instance: domain name of an instance, i.e. 'mastodon.social'
        :param client_id: (optional) 
        :param client_secret: (optional) 
        :param access_token: (optional) 
        :param use_https: (optional) set False to use plain text http
        :param session: (optional) aiohttp.ClientSession instance
        :return: MastodonAPI instance.

        Usage::

        >>> c = await atoot.MastodonAPI.create("botsin.space", access_token="...")
        >>> print(await c.verify_account_credentials())
        >>> await c.close()
        """
        self = cls()
        self.instance = instance
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = access_token
        self.base_url = "http%s://%s" % ("s" if use_https else "", self.instance)
        self.session = session if session else aiohttp.ClientSession(
                headers={"user-agent": __useragent__})
        return self

    def __init__(self):
        self.instance = None
        self.client_id = None
        self.client_secret = None
        self._access_token = None
        self.base_url = None
        self.session = None

        self.ratelimit_limit = "300"
        self.ratelimit_remaining = "300"
        self.ratelimit_reset = None
        self.ratelimit_server_date = None
        self.ratelimit_lastcall = None

    def get_access_token(self):
        return self._access_token

    async def close(self):
        """Close all network connections and shut down MastodonAPI"""
        await self.session.close()

    def _set_ratelimit_params(self, r):
        if "X-RateLimit-Limit" in r.headers: 
            self.ratelimit_limit = r.headers["X-RateLimit-Limit"]
        if "X-RateLimit-Remaining" in r.headers: 
            self.ratelimit_remaining = r.headers["X-RateLimit-Remaining"]
        if "X-RateLimit-Reset" in r.headers: 
            self.ratelimit_reset = r.headers["X-RateLimit-Reset"]
        if "Date" in r.headers: 
            self.ratelimit_server_date = r.headers["Date"]

        self.ratelimit_lastcall = time.time()

    async def __api_request(self, method, url, use_json=False, 
            headers={}, params=None, files=None):
        content = None
        url = self.base_url + url

        if self._access_token:
            headers["Authorization"] = "Bearer " + self._access_token

        kwargs = dict(headers=headers)
        if use_json == True:
            kwargs["json"] = params
        else:
            if method == self.session.get:
                kwargs["params"] = params
            else:
                kwargs["data"] = params

        try:
            r = await method(url, **kwargs)
        except Exception as e:
            raise NetworkError("Could not complete request: %s" % e)

        async with r:
            self._set_ratelimit_params(r)
            await check_exception(r)

            try:
                content = await r.json()
            except Exception as e:
                raise ApiError("Can't parse JSON reply: %s" % e)

            if type(content) == list:
                content = ResponseList(content, method=method, 
                                       params=params, headers=headers)
                if "next" in r.links and "url" in r.links["next"]:
                    content.next = r.links["next"]["url"].path_qs
                if "previous" in r.links and "url" in r.links["previous"]:
                    content.previous = r.links["previous"]["url"].path_qs

        return content

    async def get_next(self, response):
        """Get next page of paginated results

        :param response: ResponseList

        Usage::

        >>> page1 = await client.public_timeline()
        >>> if page1.next:
        >>>     page2 = await client.get_next(page1)
        """
        if not response.next:
            raise ValueError("No next page")
        return await self.__api_request(response.method, response.next,
                                        **response.kwargs)

    async def get_previous(self, response):
        """Get previous page of paginated results (see MastodonAPI.get_next)

        :param response: ResponseList
        """
        if not response.previous:
            raise ValueError("No previous page")
        return await self.__api_request(response.method, response.previous,
                                        **response.kwargs)

    async def get_n_pages(self, task, n=1):
        """A shortcut function to get up to N number of pages from a paginated task.

        :param task: a coroutine which returns a paginated list of objects
        :param n: (optional) number of pages to get

        Usage::

        >>> statuses = await client.get_n_pages(client.public_timeline(), n=5)
        """
        resp = await task
        results = resp.copy()
        p = 1

        while resp.next and p < n:
            resp = await self.get_next(resp)
            results.extend(resp)
            p += 1

        return results

    async def get_all(self, task):
        """A shortcut function to get all results from a paginated task.

        :param task: a coroutine which returns a paginated list of objects

        Usage::

        >>> notifs = await client.get_all(client.get_notifications())
        """
        resp = await task
        results = resp.copy()

        while resp.next:
            resp = await self.get_next(resp)
            results.extend(resp)

        return results

    async def get(self, url, **kwargs):
        return await self.__api_request(self.session.get, url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.__api_request(self.session.post, url, **kwargs)

    async def put(self, url, **kwargs):
        return await self.__api_request(self.session.put, url, **kwargs)

    async def patch(self, url, **kwargs):
        return await self.__api_request(self.session.patch, url, **kwargs)

    async def delete(self, url, **kwargs):
        return await self.__api_request(self.session.delete, url, **kwargs)

    async def _account_info(self, account, info="", **kwargs):
        return await self.get(
                '/api/v1/accounts/%s/%s' % (get_id(account), info), **kwargs)

    async def _account_action(self, account, action):
        return await self.post(
                '/api/v1/accounts/%s/%s' % (get_id(account), action))

    async def _status_info(self, status, info="", **kwargs):
        return await self.get(
                '/api/v1/statuses/%s/%s' % (get_id(status), info), **kwargs)

    async def _status_action(self, status, action):
        return await self.post(
                '/api/v1/statuses/%s/%s' % (get_id(status), action))

    @staticmethod
    async def create_app(session, instance, use_https=True, scopes=SCOPES,
            client_name="atoot", client_website=None):
        """Create a new application to obtain OAuth2 credentials.
        
        :param session: aiohttp.ClientSession instance
        :param instance: domain name of an instance, i.e. 'mastodon.social'
        :param use_https: (optional) set False to use plain text http
        :param scopes: (optional) application scope, default is 'read write follow'
        :param client_name: (optional) 
        :param client_website: (optional) 
        :return: client_id and client_secret values.

        Usage:

        >>> async with aiohttp.ClientSession() as session:
        >>>    client_id, client_secret = await atoot.MastodonAPI.create_app(session, 
        >>>       "botsin.space", client_name="test_bot", 
        >>>       client_website="https://example.com/")
        >>>    print(client_id, client_secret)
        """

        params = {
            'client_name': client_name, 'scopes': scopes,
            'redirect_uris': REDIRECT_URI,
        }
        if client_website: params["website"] = client_website
        url = 'http%s://%s/api/v1/apps' % ("s" if use_https else "", instance) 
        r = await session.post(url, params=params)
        async with r:
            await check_exception(r)

            try:
                res = await r.json()
            except Exception as e:
                raise ApiError("Can't parse JSON reply: %s" % e)

        assert "client_id" in res, "Invalid JSON reply"
        assert "client_secret" in res, "Invalid JSON reply"
        return (res["client_id"], res["client_secret"])

    @staticmethod
    def browser_login_url(instance, client_id, use_https=True):
        """Returns a URL for manual log in via browser
        
        :param instance: domain name of an instance, i.e. 'mastodon.social'
        :param client_id:
        :param use_https: (optional) set False to use plain text http
        """
        return "http{}://{}/oauth/authorize/?{}".format(
            "s" if use_https else "", instance,
            urlencode({
                "response_type": "code", "client_id": client_id,
                "redirect_uri": REDIRECT_URI, "scope": SCOPES
            })
        )

    ## REST API

    @staticmethod
    async def login(session, instance, client_id, client_secret, 
            use_https=True, username=None, password=None, oauth_code=None, 
            scope=SCOPES):
        """Login to the MastodonAPI instance. 
         
        :param session: aiohttp.ClientSession instance
        :param instance: domain name of an instance, i.e. 'mastodon.social'
        :param client_id:
        :param client_secret:
        :param use_https: (optional) set False to use plain text http
        :param username: (optional) e-mail of your account
        :param password: (optional) password of your account
        :param oauth_code: (optional) code from a browser_login_url page
        :param scope: (optional) application scope, default is 'read write follow'
        :return: OAuth access_code. Store this access_token for later use with authenticated client.
        """
        params = {
            "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI, "scope": scope,
        }

        if username and password:
            params["grant_type"] = "password"
            params['username'] = username
            params['password'] = password
        elif oauth_code:
            params["grant_type"] = "authorization_code"
            params["code"] = oauth_code
        else:
            params["grant_type"] = "client_credentials"

        url = "http%s://%s/oauth/token" % ("s" if use_https else "", instance)
        r = await session.post(url, params=params)
        async with r:
            await check_exception(r)

            try:
                res = await r.json()
            except Exception as e:
                raise ApiError("Can't parse JSON reply: %s" % e)

        assert "access_token" in res, "Invalid JSON reply"
        return res["access_token"]

    async def revoke_token(self, client_id, client_secret, token):
        """Revoke an access token to make it no longer valid for use.
        """
        params = {"client_id": client_id, "client_secret": client_secret, 
                "token": token}
        return await self.post("/oauth/revoke", params=params)

    async def verify_app_credentials(self):
        """Confirm that the app's OAuth2 credentials work."""
        return await self.get('/api/v1/apps/verify_credentials')

    ### Methods concerning user accounts and related information.

    async def register_account(self, username, email, password, agreement, 
            locale, reason=None, params={}):
        """Creates a user and account records. 

        :return: Returns an account access token for the app that initiated the request. The app should save this token for later, and should wait for the user to confirm their account by  clicking a link in their email inbox.
        """
        if reason: params["reason"] = reason
        params["username"] = username
        params["email"] = email
        params["password"] = password
        params["agreement"] = str_bool(agreement)
        params["locale"] = locale
        return await self.post('/api/v1/accounts', params=params)

    async def verify_account_credentials(self):
        """Test to make sure that the user token works. 
        
        :return: user's own Account with Source
        """
        return await self.get('/api/v1/accounts/verify_credentials')

    async def update_account_credentials(self, discoverable=None, bot=None, 
            display_name=None, note=None,  avatar=None, header=None, 
            locked=None, fields_attributes=None, params={}):
        """Update the user's display and preferences.

        :param discoverable: (optional) Whether the account should be shown in the profile directory.
        :param bot: (optional) Whether the account has a bot flag.
        :param display_name: (optional) The display name to use for the profile.
        :param note: (optional) The account bio.
        :param avatar: (optional) Avatar image encoded using multipart/form-data
        :param header: (optional) Header image encoded using multipart/form-data
        :param locked: (optional) Whether manual approval of follow requests is required.
        :param fields_attributes: (optional) Profile metadata name and value. (By default, max 4 fields and 255 characters per property/value)
        """
        if discoverable is not None: 
            params["discoverable"] = str_bool(discoverable)
        if bot is not None: params["bot"] = str_bool(bot)
        if display_name: params["display_name"] = display_name
        if note: params["note"] = note
        if avatar: params["avatar"] = open(avatar, "rb")
        if header: params["header"] = open(header, "rb")
        if locked is not None: params["locked"] = str_bool(locked)
        if fields_attributes: params["fields_attributes"] = fields_attributes
        return await self.patch('/api/v1/accounts/update_credentials', 
                params=params)

    async def account(self, account):
        """View information about a profile.

        :param account: Account object or id string
        :return: Account object
        """
        return await self._account_info(account)

    async def account_statuses(self, account):
        """Statuses posted to the given account. 

        :param account: Account object or id string
        :return: a list of statuses
        """
        return await self._account_info(account, 'statuses')

    async def account_followers(self, account, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self._account_info(account, 'followers', params=params)

    async def account_following(self, account, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self._account_info(account, 'following', params=params)

    async def account_lists(self, account):
        return await self._account_info(account, 'lists')

    async def account_identity_proofs(self, account):
        return await self._account_info(account, 'identity_proofs')

    async def account_follow(self, account):
        """Follow the given account."""
        return await self._account_action(account, "follow")

    async def account_unfollow(self, account):
        """Unfollow the given account."""
        return await self._account_action(account, "unfollow")

    async def account_block(self, account):
        return await self._account_action(account, "block")

    async def account_unblock(self, account):
        return await self._account_action(account, "unblock")

    async def account_mute(self, account):
        return await self._account_action(account, "mute")

    async def account_unmute(self, account):
        return await self._account_action(account, "unmute")

    async def account_pin(self, account):
        return await self._account_action(account, "pin")

    async def account_unpin(self, account):
        return await self._account_action(account, "unpin")

    async def account_relationships(self, ids):
        return await self.get('/api/v1/accounts/relationships', 
                              params=[("id", i,) for i in ids])

    async def account_search(self, query, limit=None, resolve=None, 
                                   following=None):
        """Search for matching accounts by username or display name.
        
        :param query: What to search for
        :param limit: Maximum number of results. Defaults to 40. 
        :param resolve: Attempt WebFinger lookup. Defaults to false. Use this when query is an exact address.
        :param following: Only who the user is following. Defaults to false.
        :return: a list of Accounts
        """
        return await self.get('/api/v1/accounts/search', params={'q': query})

    ### Accounts/misc
    async def bookmarks(self, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self.get('/api/v1/bookmarks', params=params)

    async def favourites(self, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self.get('/api/v1/favourites', params=params)

    async def mutes(self, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self.get('/api/v1/mutes', params=params)

    async def blocks(self, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self.get('/api/v1/blocks', params=params)

    async def domain_blocks(self, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self.get('/api/v1/domain_blocks', params=params)

    async def all_filters(self): 
        return await self.get('/api/v1/filters')

    async def view_filter(self, _filter):
        return await self.get('/api/v1/filters/%s' % get_id(_filter))

    async def create_filter(self, phrase, context, params={}):
        params["phrase"] = phrase
        params["context"] = context
        return await self.post('/api/v1/filters', params=params)

    async def update_filter(self, _filter, phrase=None, context=None, params={}):
        if phrase: params["phrase"] = phrase
        if context: params["context"] = context
        return await self.put('/api/v1/filters/%s' % get_id(_filter),
                              params=params)

    async def remove_filter(self, _filter):
        return await self.delete('/api/v1/filters/%s' % get_id(_filter))

    async def create_report(self, account, params={}):
        params["account_id"] = get_id(account)
        return await self.post('/api/v1/reports', params=params)

    async def follow_requests(self, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self.get('/api/v1/follow_requests', params=params)

    async def accept_follow_request(self, account):
        return await self.post(
                '/api/v1/follow_requests/{}/authorize' % get_id(account))

    async def reject_follow_request(self, account):
        return await self.post(
                '/api/v1/follow_requests/{}/reject' % get_id(account))

    async def endorsements(self, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self.get('/api/v1/endorsements', params=params)

    async def featured_tags(self):
        return await self.get('/api/v1/featured_tags')

    async def create_featured_tag(self, name):
        return await self.post('/api/v1/featured_tags', params={"name": name})

    async def delete_featured_tag(self, tag):
        return await self.delete('/api/v1/featured_tags/%s' % get_id(tag))

    async def suggested_featured_tags(self):
        return await self.get('/api/v1/featured_tags/suggestions')

    async def preferences(self):
        return await self.get('/api/v1/preferences')

    async def suggestions(self, limit=40):
        return await self.get('/api/v1/suggestions', params={'limit': limit})

    async def remove_suggestion(self, account):
        return await self.delete("/api/v1/suggestions/%s" % get_id(account))

    ### Statuses

    async def create_status(
        self, params={}, status=None, media_ids=None,
        poll_options=[], poll_expires_in=None, 
        poll_multiple=None, poll_hide_totals=None,
        in_reply_to_id=None, sensitive=False, spoiler_text=None,
        visibility='public', scheduled_at=None, language=None,
    ):
        """
        Posts a new status.

        :param status: (optional) Text content of the status. If media_ids is provided, this becomes optional. Attaching a poll is optional while status is provided.
        :param media_ids: (optional) Array of Attachment ids to be attached as media. If provided, status becomes optional, and poll cannot be used.
        :param poll_options: (optional) Array of possible answers. If provided, media_ids cannot be used, and poll[expires_in] must be provided.
        :param poll_expires_in: (optional) Duration the poll should be open, in seconds. If provided, media_ids cannot be used, and poll[options] must be provided.
        :param poll_multiple: (optional) Allow multiple choices?
        :param poll_hide_totals: (optional) Hide vote counts until the poll ends?
        :param in_reply_to_id: (optional) ID of the status being replied to, if status is a reply
        :param sensitive: (optional) Mark status and attached media as sensitive?
        :param spoiler_text: (optional) Text to be shown as a warning or subject before the actual content. Statuses are generally collapsed behind this field.
        :param visibility: (optional) Visibility of the posted status. Enumerable oneOf public, unlisted, private, direct.
        :param scheduled_at: (optional) ISO 8601 Datetime at which to schedule a status. Providing this paramter will cause ScheduledStatus to be returned instead of Status. Must be at least 5 minutes in the future.
        :param language: (optional) ISO 639 language code for this status.
        :type poll_multiple: bool
        :type poll_hide_totals: bool
        :type sensitive: bool
        :return: Status object. When scheduled_at is present, ScheduledStatus is returned instead.
        """

        # Idempotency key assures the same status is not posted multiple times
        # if the request is retried.
        headers = {"Idempotency-Key": uuid.uuid4().hex}

        if status: params["status"] = status
        if media_ids: params["media_ids"] = media_ids
        if poll_options: 
            params["poll"] = {"options": poll_options, 
                    "expires_in": poll_expires_in}
            if poll_multiple is not None: 
                params["poll"]["multiple"] = str_bool(poll_multiple)
            if poll_hide_totals is not None: 
                params["poll"]["hide_totals"] = str_bool(poll_hide_totals)

        if in_reply_to_id: params["in_reply_to_id"] = in_reply_to_id
        params["sensitive"] = str_bool(sensitive)
        if spoiler_text: params["spoiler_text"] = spoiler_text
        params["visibility"] = visibility
        if scheduled_at: params["scheduled_at"] = scheduled_at
        if language: params["language"] = language

        return await self.post('/api/v1/statuses', params=params, 
                use_json=True, headers=headers)

    async def delete_status(self, status):
        """
        Deletes a status.

        :param status: Status object or id string
        """
        return await self.delete('/api/v1/statuses/%s' % get_id(status))

    async def view_status(self, status):
        """View information about a status."""
        return await self._status_info(status)

    async def status_context(self, status):
        """View statuses above and below this status in the thread."""
        return await self._status_info(status, 'context')

    async def status_reblogged_by(self, status):
        return await self._status_info(status, 'reblogged_by')

    async def status_favourited_by(self, status):
        return await self._status_info(status, 'favourited_by')

    async def status_favourite(self, status):
        """Add a status to your favourites list."""
        return await self._status_action(status, "favourite")

    async def status_unfavourite(self, status):
        """Remove a status from your favourites list."""
        return await self._status_action(status, "unfavourite")

    async def status_boost(self, status):
        """Reshare a status."""
        return await self._status_action(status, "reblog")

    async def status_unboost(self, status):
        """Undo a reshare of a status."""
        return await self._status_action(status, "unreblog")

    async def status_bookmark(self, status):
        return await self._status_action(status, "bookmark")

    async def status_unbookmark(self, status):
        return await self._status_action(status, "unbookmark")

    async def status_mute(self, status):
        return await self._status_action(status, "mute")

    async def status_unmute(self, status):
        return await self._status_action(status, "unmute")

    async def status_pin(self, status):
        return await self._status_action(status, "pin")

    async def status_unpin(self, status):
        return await self._status_action(status, "unpin")

    ### Statuses/Misc
    async def upload_attachment(self, fileobj, params={}, description=None, 
                           focal=None):
        """Creates an attachment to be used with a new status.

        :param fileobj: file object, i.e. fileobj=open('image.jpg', 'rb')
        :param description: A plain-text description of the media, for accessibility purposes.
        :param focal: Two floating points (x,y), comma-delimited, ranging from -1.0 to 1.0
        """
        params["file"] = fileobj
        if description: params["description"] = description
        if focal: params["focal"] = focal
        return await self.post('/api/v1/media', params=params)

    async def update_attachment(self, attachment, fileobj=None, params={}, 
            description=None, focal=None):
        """Update an Attachment, before it is attached to a status and posted.
        """
        if fileobj: params["file"] = fileobj
        if description: params["description"] = description
        if focal: params["focal"] = focal
        return await self.put('/api/v1/media/%s' % get_id(attachment), 
                              params=params)

    async def view_poll(self, poll):
        return await self.get('/api/v1/polls/%s' % get_id(poll))

    async def vote_poll(self, poll, choices):
        return await self.post('/api/v1/polls/%s/votes' % get_id(poll), 
                params={"choices": choices})

    async def scheduled_statuses(self, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self.get('/api/v1/scheduled_statuses', params=params)

    async def view_scheduled_status(self, status):
        return await self.get('/api/v1/scheduled_statuses/%s' % get_id(status))

    async def create_scheduled_status(self, status, date):
        return await self.put('/api/v1/scheduled_statuses/%s' % get_id(status),
                params={"scheduled_at": date})

    async def cancel_scheduled_status(self, status, date):
        return await self.delete('/api/v1/scheduled_statuses/{}' % get_id(status))

    ### Timelines
    async def public_timeline(self, params={}, limit=None, 
            local=None, only_media=None):
        """View statuses from the public timeline

        :param limit: Maximum number of results to return. Defaults to 20.
        :param local: If true, return only local statuses. Defaults to false.
        :param only_media: If true, return only statuses with media attachments. Defaults to false.
        :returns: List of Statuses
        """
        if limit: params["limit"] = limit
        if local is not None: params["local"] = str_bool(local)
        if only_media is not None: params["only_media"] = str_bool(only_media)
        return await self.get('/api/v1/timelines/public', params=params)

    async def hashtag_timeline(self, hashtag, params={}, limit=None, 
            local=None, only_media=None):
        """View public statuses containing the given hashtag.

        :param hashtag: Content of a #hashtag, not including # symbol.
        :param limit: Maximum number of results to return. Defaults to 20.
        :param local: If true, return only local statuses. Defaults to false.
        :param only_media: If true, return only statuses with media attachments. Defaults to false.
        :returns: List of Statuses
        """
        if limit: params["limit"] = limit
        if local is not None: params["local"] = str_bool(local)
        if only_media is not None: params["only_media"] = str_bool(only_media)
        return await self.get('/api/v1/timelines/tag/%s' % hashtag, 
                params=params)

    async def home_timeline(self, params={}, limit=None, local=None):
        """View statuses from followed users.

        :param limit: Maximum number of results to return. Defaults to 20.
        :param local: If true, return only local statuses. Defaults to false.
        :returns: List of Statuses
        """
        if limit: params["limit"] = limit
        if local is not None: params["local"] = str_bool(local)
        return await self.get('/api/v1/timelines/home', params=params)

    async def list_timeline(self, _list, params={}, limit=None):
        """View statuses in the given list timeline.

        :param _list: Local ID of the list in the database.
        :param limit: Maximum number of results to return. Defaults to 20.
        :param local: If true, return only local statuses. Defaults to false.
        :returns: List of Statuses
        """
        if limit: params["limit"] = limit
        return await self.get('/api/v1/timelines/list/%s' % get_id(_list), 
                params=params)

    ### Timelines/Misc

    async def conversations(self, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self.get('/api/v1/conversations', params=params)

    async def remove_conversation(self, conversation):
        return await self.delete(
                '/api/v1/conversations/%s' % get_id(conversation)) 

    async def mark_conversation_read(self, conversation):
        return await self.post(
                '/api/v1/conversations/%s/read' % get_id(conversation)) 

    async def lists(self):
        return await self.get('/api/v1/lists')

    async def show_list(self, _list):
        return await self.get('/api/v1/lists/%s' % get_id(_list)) 

    async def create_list(self, title):
        return await self.post('/api/v1/lists', params={"title": title})

    async def update_list(self, _list, title):
        return await self.put('/api/v1/lists/%s' % get_id(_list), 
                              params={"title": title})

    async def delete_list(self, _list):
        return await self.delete('/api/v1/lists/%s' % get_id(_list)) 

    async def list_accounts(self, _list, params={}, limit=None):
        if limit: params["limit"] = limit
        return await self.get('/api/v1/lists/%s/accounts' % get_id(_list),
                params=params) 

    async def list_accounts_add(self, _list, accounts):
        account_ids = [get_id(a) for a in accounts]
        return await self.post('/api/v1/lists/%s/accounts' % get_id(_list), 
                params={"account_ids": account_ids}, use_json=True)

    async def list_accounts_remove(self, _list, accounts):
        account_ids = [get_id(a) for a in accounts]
        return await self.delete('/api/v1/lists/%s/accounts' % get_id(_list), 
                params={"account_ids": account_ids}, use_json=True)

    async def markers_get(self):
        return await self.get('/api/v1/markers')

    async def markers_set(self, params={}):
        return await self.post('/api/v1/markers', params=params, use_json=True)


    def streaming(self, stream, list_filter=None, tag_filter=None):
        """Asynchronous context manager for using websocket streaming API

        :params stream: one of the following: user, public, public:local, hashtag, hashtag:local, list, direct
        :return: aiohttp.ClientWebSocketResponse object

        Usage::

            async with client.streaming("user") as ws:
                async for msg in ws:
                    print(msg.json())

        """
        ws_url =  "{}/api/v1/streaming/?stream={}&access_token={}".format(
                self.base_url, stream, self._access_token)
        if list_filter: ws_url += "&list=%s" % list_filter
        if tag_filter: ws_url += "&tag=%s" % tag_filter
        return self.session.ws_connect(ws_url)

    async def streaming_handler(self, stream, handler, **kwargs):
        with suppress(asyncio.CancelledError):
            async with self.streaming(stream, **kwargs) as ws:
                async for msg in ws:
                    await handler(self, msg)

    ### Notifications

    async def get_notifications(self, params={}, limit=None, exclude_types=None,
                                account=None):
        """Receive notifications for activity on your account or statuses.

        :param limit: Maximum number of results to return (default 20)
        :param exclude_types: Array of types to exclude (follow, favourite, reblog, mention, poll)
        :param account: Return only notifications received from this account
        :return: List of notifications
        """
        if limit: params["limit"] = limit
        if exclude_types: params["exclude_types"] = exclude_types
        if account: params["account_id"] = get_id(account)
        return await self.get('/api/v1/notifications', params=params)

    async def get_notification(self, notification):
        """View information about a notification with a given ID.

        :param notification: 
        :return: Notification object
        """
        return await self.get('/api/v1/notifications/%s' % get_id(notification))

    async def clear_notifications(self):
        """Clear all notifications from the server."""
        await self.post('/api/v1/notifications/clear')

    async def clear_notification(self, notification):
        """Clear a single notification from the server."""
        return await self.post(
                '/api/v1/notifications/%s/dismiss' % get_id(notification))

    ### Search

    async def search(self, query, params={}, limit=None, account=None,
            search_type=None, exclude_unreviewed=None, resolve=None, 
            following=None):
        params["q"] = query
        if limit: params["limit"] = limit
        if account: params["account_id"] = get_id(account)
        if search_type: params["search_type"] = search_type
        if exclude_unreviewed is not None: 
            params["exclude_unreviewed"] = str_bool(exclude_unreviewed)
        if resolve is not None: params["resolve"] = str_bool(resolve)
        if following is not None: params["following"] = str_bool(following)
        return await self.get('/api/v2/search', params=params)

    ### Instances

    async def get_instance(self):
        return await self.get('/api/v1/instance')

    async def instance_peers(self):
        return await self.get('/api/v1/instance/peers')

    async def instance_activity(self):
        return await self.get('/api/v1/instance/activity')

    ### Instances/Misc

    async def trending_tags(self, limit=None):
        return await self.get('/api/v1/trends', params={"limit": limit})

    async def profile_directory(self, params={}, offset=None, limit=None,
            order=None, local=None):
        if offset: params["offset"] = offset
        if limit: params["limit"] = limit
        if order: params["order"] = order
        if local is not None: params["local"] = str_bool(local)
        return await self.get('/api/v1/directory', params=params)

    async def get_custom_emojis(self):
        return await self.get('/api/v1/custom_emojis')

    ### Admin

    async def admin_accounts(self, local=None, remote=None, 
                by_domain=None, active=None, pending=None, disabled=None, 
                silenced=None, suspended=None, username=None, display_name=None, 
                email=None, ip=None, staff=None, params={}):
        if local is not None: params["local"] = str_bool(local)
        if remote is not None: params["remote"] = str_bool(remote)
        if by_domain: params["by_domain"] = by_domain
        if active is not None: params["active"] = str_bool(active)
        if pending is not None: params["pending"] = str_bool(pending)
        if disabled is not None: params["disabled"] = str_bool(disabled)
        if silenced is not None: params["silenced"] = str_bool(silenced)
        if suspended is not None: params["suspended"] = str_bool(suspended)
        if username: params["username"] = username
        if display_name: params["display_name"] = display_name
        if email: params["email"] = email
        if ip: params["ip"] = ip
        if staff is not None: params["staff"] = str_bool(staff)
        return self.get("/api/v1/admin/accounts", params=params)

    async def admin_view_account(self, account):
        return self.get("/api/v1/admin/accounts/%s" % get_id(account))

    async def admin_account_action(self, account, action=None, report=None, 
            warning=None, text=None, notification=None, params={}):
        if action: params["action"] = action
        if report: params["report_id"] = get_id(report)
        if warning: params["warning_preset_id"] = warning
        if text: params["text"] = text
        if notification is not None: 
            params["send_email_notification"] = str_bool(notification)
        return self.post("/api/v1/admin/accounts/%s/action" % get_id(account), 
                params=params)

    async def admin_account_approve(self, account):
        return self.post("/api/v1/admin/accounts/%s/approve" % get_id(account))

    async def admin_account_reject(self, account):
        return self.post("/api/v1/admin/accounts/%s/reject" % get_id(account))

    async def admin_account_enable(self, account):
        return self.post("/api/v1/admin/accounts/%s/enable" % get_id(account))

    async def admin_account_unsilence(self, account):
        return self.post("/api/v1/admin/accounts/%s/unsilence" % get_id(account))

    async def admin_account_unsuspend(self, account):
        return self.post("/api/v1/admin/accounts/%s/unsuspend" % get_id(account))


    async def admin_reports(self, resolved=None, account=None, 
            target_account=None, params={}):
        if resolved is not None: params["resolved"] = str_bool(resolved)
        if account: params["account_id"] = get_id(account)
        if target_account: params["target_account_id"] = get_id(target_account)
        return self.get("/api/v1/admin/reports", params=params)

    async def admin_view_report(self, report):
        return self.get("/api/v1/admin/reports/%s" % get_id(report))

    async def admin_report_self_assign(self, report):
        return self.post(
                "/api/v1/admin/reports/%s/assign_to_self" % get_id(report))

    async def admin_report_unassign(self, report):
        return self.post("/api/v1/admin/reports/%s/unassign" % get_id(report))

    async def admin_report_resolve(self, report):
        return self.post("/api/v1/admin/reports/%s/resolve" % get_id(report))

    async def admin_report_reopen(self, report):
        return self.post("/api/v1/admin/reports/%s/reopen" % get_id(report))

    ### Proofs

    async def get_proofs(self, params={}, provider=None, username=None):
        if provider: params["provider"] = provider
        if username: params["username"] = username
        return await self.get('/api/proofs', params=params)

    ### OEmbed

    async def oembed(self, url, params={}, maxwidth=None, maxheight=None):
        params["url"] = url
        if maxwidth: params["maxwidth"] = maxwidth
        if maxheight: params["maxheight"] = maxheight
        return await self.get('/api/oembed', params=params)

@asynccontextmanager
async def client(*args, **kwargs):
    """Context manager for using MastodonAPI object. Arguments are the same as
    for :meth:`atoot.MastodonAPI.create` factory method.

    Usage::

        async with atoot.client(instance, access_token=access_token) as c:
            # Retrieve your account information
            print(await c.verify_account_credentials())
            # Create a status 
            print(await c.create_status(status="Hello world!"))
            # Get 3 pages of a local timeline
            print(await c.get_n_pages(c.public_timeline(local=True), n=3))
    """
    c = await MastodonAPI.create(*args, **kwargs)
    try:
        yield c
    finally:
        await c.close()

async def check_exception(r):
    if r.status >= 400:
        error_message = "Exception has occured"
        try:
            content = await r.json()
            error_message = content["error"]
        except:
            try:
                error_message = await r.text()
            except:
                pass

        if r.status == 401:
            ExceptionType = UnauthorizedError
        elif r.status == 403:
            ExceptionType = ForbiddenError
        elif r.status == 404:
            ExceptionType = NotFoundError
        elif r.status == 409:
            ExceptionType = ConflictError
        elif r.status == 410:
            ExceptionType = GoneError
        elif r.status == 422:
            ExceptionType = UnprocessedError
        elif r.status == 429:
            ExceptionType = RatelimitError
        elif r.status == 503:
            ExceptionType = UnavailableError
        elif r.status < 500:
            ExceptionType = ClientError
        else:
            ExceptionType = ServerError

        raise ExceptionType(r.status, r.reason, error_message)

class MastodonError(Exception):
    """Base class for all mastodon exceptions"""

class NetworkError(MastodonError):
    pass

class ApiError(MastodonError):
    pass

class ClientError(MastodonError):
    pass

class UnauthorizedError(ClientError):
    pass

class ForbiddenError(ClientError):
    pass

class NotFoundError(ClientError):
    pass

class ConflictError(ClientError):
    pass

class GoneError(ClientError):
    pass

class UnprocessedError(ClientError):
    pass

class RatelimitError(ClientError):
    pass

class ServerError(MastodonError):
    pass

class UnavailableError(MastodonError):
    pass
