"""Async connection class."""
import json
import logging
import os

from aiohttp.client import _RequestContextManager

from O365.aio.connection_base import (
    ConnectionBase, HTTP_ALLOWED, HTTP_GET, HTTP_POST, HTTP_PUT, HTTP_PATCH,
    DEFAULT_SCOPES)
from O365.aio.oauth2_session import OAuth2Session as aio_OAuth2Session

_LOGGER = logging.getLogger(__name__)


class aio_Connection(ConnectionBase):  # pylint: disable=invalid-name
    """Async version."""

    async def request_token(self, *, authorization_url):
        """ Authenticates for the specified url and gets the token, save the
        token for future based if requested

        :param str authorization_url: url given by the authorization flow
        :return: Success/Failure
        :rtype: bool
        """
        if self.session is None:
            raise RuntimeError("Fist call 'get_authorization_url' to "
                               "generate a valid oauth object")

        client_id, client_secret = self.auth

        # Allow token scope to not match requested scope.
        # (Other auth libraries allow this, but Requests-OAuthlib
        #  raises exception on scope mismatch by default.)
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'

        try:
            self.token = await self.session.fetch_token(
                token_url=self._oauth2_token_url,
                authorization_response=authorization_url,
                client_id=client_id,
                client_secret=client_secret,
                include_client_id=True,
            )
        except Exception as err:  # pylint: disable=broad-except
            raise RuntimeError(f"Unable to fetch auth token. Error: {err}")

        # Store the new token, this can implement any async file operations
        if self.token_updater:
            await self.token_updater(self.token)

    def _session_init(self, *args, **kwargs):
        """Init oauth2_session for aiohttp.

        Token update is handled by OAuth2Session."""

        async def _update_token(token):
            if self.token_updater:
                await self.token_updater(token)

        self.session = aio_OAuth2Session(
            *args,
            auto_refresh_url=self._oauth2_token_url,
            auto_refresh_kwargs={
                # client_id and client_secret expected in refresh request body
                'client_id': self.auth[0],
                'client_secret': self.auth[1],
            },
            token_updater=_update_token,
            trust_env=True,  # Use http_proxy environment
            **kwargs
        )

    async def request(self, method, url, custom_session=None, **kwargs):
        """Make a request to url using an oauth session

        :param str url: url to send request to
        :param str method: type of request (get/put/post/patch/delete)
        :param custom_session: a requests session if not default session.
        :param kwargs: extra params to send to the request api
        :return: Response of the request
        :rtype: requests.Response
        """
        session = custom_session or self.session or self.get_session()

        assert method in HTTP_ALLOWED, \
            'Method must be one of the allowed ones'

        if method == HTTP_GET:
            kwargs.setdefault('allow_redirects', True)
        elif method in [HTTP_POST, HTTP_PUT, HTTP_PATCH]:
            kwargs.setdefault('headers', {})
            kwargs['headers'].setdefault('Content-type', 'application/json')
            if 'data' in kwargs and \
                    kwargs['headers']['Content-type'] == 'application/json':
                kwargs['data'] = json.dumps(
                    kwargs['data'])  # auto convert to json

        response = await session.request(method, url, **kwargs)

        return response

    def get(self, url, **kwargs):
        """GET Request."""
        return _RequestContextManager(self.request(HTTP_GET, url, **kwargs))

    def post(self, url, **kwargs):
        """POST request."""
        return _RequestContextManager(self.request(HTTP_POST, url, **kwargs))
