"""O365.aiohttp OAuth2Session sample for Microsoft Graph

Follows the examples from Microsoft, with a aio_http async session

The static files were copied form the Microsoft repository
https://github.com/microsoftgraph/python-sample-auth
"""
import os
from pathlib import Path

import aiohttp
import aiohttp_jinja2
import jinja2

try:
    import config
except ImportError:
    assert False, (
        "You need a local config.py file with your app credentials,",
        "https://github.com/microsoftgraph/python-sample-auth/blob/master/config.py"
    )

from O365.aio.connection import aio_Connection
from O365.info import Info
from O365.connection import MSGraphProtocol


DEFAULT_SCOPES = ['offline_access', 'User.read', 'Sites.Read.All']
MSGRAPH = aio_Connection(
    (config.CLIENT_ID, config.CLIENT_SECRET),
    scopes=(config.SCOPES or DEFAULT_SCOPES))

ROUTES = aiohttp.web.RouteTableDef()

# Enable non-HTTPS redirect URI for development/testing.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


@ROUTES.get('/')
@aiohttp_jinja2.template('homepage.html')
async def homepage(_request):
    """Render the home page."""
    return {'sample': 'Async Connection'}


@ROUTES.get('/login')
async def login(_request):
    """Prompt user to authenticate."""
    authorization_url = MSGRAPH.get_authorization_url(
        redirect_uri=config.REDIRECT_URI)
    print('a_url', authorization_url)
    raise aiohttp.web.HTTPFound(authorization_url)  # redirect


@ROUTES.get('/login/authorized')
async def authorized(request):
    """Handler for the application's Redirect Uri."""
    await MSGRAPH.request_token(request.url, store_token=False)
    raise aiohttp.web.HTTPFound('/graphcall')


@ROUTES.get('/graphcall')
@aiohttp_jinja2.template('graphcall.html')
async def graphcall(_request):
    """Confirm user authentication by calling Graph and displaying data."""
    # endpoint = config.RESOURCE + config.API_VERSION + '/me'
    # resp = await MSGRAPH.get(endpoint)
    #graphdata = await resp.json()

    info = Info(con=MSGRAPH, protocol=MSGraphProtocol)
    res = await info.aio_get_my_info()

    return {'graphdata': res, 'sample': 'aiohttp'}


def run():
    """Run the application."""
    import signal
    signal.signal(signal.SIGINT,  signal.SIG_DFL)
    app = aiohttp.web.Application()
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader(str(
            Path(__file__).parent / 'static/templates')))
    app.router.add_static('/static', str(Path(__file__).parent / 'static'))
    app.router.add_routes(ROUTES)
    aiohttp.web.run_app(app, port=5000, host='localhost')


if __name__ == '__main__':
    run()
