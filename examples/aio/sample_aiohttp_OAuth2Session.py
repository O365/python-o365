"""aiohttp OAuth2Session sample for Microsoft Graph

Follows the examples from Microsoft, with a aio_http async session

The static files were copied form the Microsoft repository
https://github.com/microsoftgraph/python-sample-auth
"""
import os
import uuid
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

from O365.aio.oauth2_session import OAuth2Session


MSGRAPH = OAuth2Session(
    config.CLIENT_ID, scope=config.SCOPES, redirect_uri=config.REDIRECT_URI)
ROUTES = aiohttp.web.RouteTableDef()

# Enable non-HTTPS redirect URI for development/testing.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
# Allow token scope to not match requested scope. (Other auth libraries allow
# this, but OAuthlib raises exception on scope mismatch by default.)
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'


@ROUTES.get('/')
@aiohttp_jinja2.template('homepage.html')
async def homepage(_request):
    """Render the home page."""
    return {'sample': 'aio_http OAuthlib'}


@ROUTES.get('/login')
async def login(_request):
    """Prompt user to authenticate."""
    auth_base = config.AUTHORITY_URL + config.AUTH_ENDPOINT
    authorization_url, state = MSGRAPH.authorization_url(auth_base)
    MSGRAPH.auth_state = state
    print('a_url', authorization_url, 'state=', state)
    raise aiohttp.web.HTTPFound(authorization_url)


@ROUTES.get('/login/authorized')
async def authorized(request):
    """Handler for the application's Redirect Uri."""
    if request.query['state'] != MSGRAPH.auth_state:
        raise Exception('state returned to redirect URL does not match!')
    await MSGRAPH.fetch_token(
        config.AUTHORITY_URL + config.TOKEN_ENDPOINT,
        client_secret=config.CLIENT_SECRET,
        authorization_response=request.url)
    raise aiohttp.web.HTTPFound('/graphcall')


@ROUTES.get('/graphcall')
@aiohttp_jinja2.template('graphcall.html')
async def graphcall(_request):
    """Confirm user authentication by calling Graph and displaying data."""
    endpoint = config.RESOURCE + config.API_VERSION + '/me'
    headers = {'SdkVersion': 'sample-python-requests-0.1.0',
               'x-client-SKU': 'sample-python-requests',
               'client-request-id': str(uuid.uuid4()),
               'return-client-request-id': 'true'}
    async with MSGRAPH.get(endpoint, headers=headers) as resp:
        graphdata = await resp.json()
    return {'graphdata': graphdata, 'endpoint': endpoint,
            'sample': 'Requests-OAuthlib'}


def run():
    """Run the application."""
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = aiohttp.web.Application()
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader(str(
            Path(__file__).parent / 'static/templates')))
    app.router.add_static('/static', str(Path(__file__).parent / 'static'))
    app.router.add_routes(ROUTES)
    aiohttp.web.run_app(app, port=5000, host='localhost')


if __name__ == '__main__':
    run()
