import atoot
from aiohttp import web
pytest_plugins = 'aiohttp.pytest_plugin'
# https://docs.aiohttp.org/en/v0.22.0/testing.html#pytest-example

async def sample(request):
    assert request.headers["Authorization"] == 'Bearer test'
    return web.json_response({})

def create_app(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/api/v1/accounts/verify_credentials', sample)
    return app

async def test_verify_credentials(aiohttp_client, loop):
    cli = await aiohttp_client(create_app)
    async with atoot.client("test", access_token="test", session=cli) as c:
        c.base_url = ""
        res = await c.verify_account_credentials()
        assert res == {}
