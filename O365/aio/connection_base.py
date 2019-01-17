"""Connection class."""
import json
import logging
import os
import time
from pathlib import Path

from oauthlib.oauth2 import TokenExpiredError
from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError as rConnectionError
from requests.exceptions import (HTTPError, ProxyError, RequestException,
                                 SSLError, Timeout)
# Dynamic loading of module Retry by requests.packages
# noinspection PyUnresolvedReferences
from requests.packages.urllib3.util.retry import Retry
from requests_oauthlib import OAuth2Session

_LOGGER = logging.getLogger(__name__)

O365_API_VERSION = 'v2.0'
GRAPH_API_VERSION = 'v1.0'
OAUTH_REDIRECT_URL = 'https://outlook.office365.com/owa/'

RETRIES_STATUS_LIST = (
    429,  # Status code for TooManyRequests
    500, 502, 503, 504  # Server errors
)
RETRIES_BACKOFF_FACTOR = 0.5

DEFAULT_SCOPES = {
    # wrap any scope in a 1 element tuple to avoid prefixing
    'basic': [('offline_access',), 'User.Read'],
    'mailbox': ['Mail.Read'],
    'mailbox_shared': ['Mail.Read.Shared'],
    'message_send': ['Mail.Send'],
    'message_send_shared': ['Mail.Send.Shared'],
    'message_all': ['Mail.ReadWrite', 'Mail.Send'],
    'message_all_shared': ['Mail.ReadWrite.Shared', 'Mail.Send.Shared'],
    'address_book': ['Contacts.Read'],
    'address_book_shared': ['Contacts.Read.Shared'],
    'address_book_all': ['Contacts.ReadWrite'],
    'address_book_all_shared': ['Contacts.ReadWrite.Shared'],
    'calendar': ['Calendars.ReadWrite'],
    'users': ['User.ReadBasic.All'],
    'onedrive': ['Files.ReadWrite.All'],
    'sharepoint_dl': ['Sites.ReadWrite.All'],
}


class ConnectionBase:
    """ Handles all communication (requests) between the app and the server """

    _oauth2_authorize_url = 'https://login.microsoftonline.com/common/' \
                            'oauth2/v2.0/authorize'
    _oauth2_token_url = 'https://login.microsoftonline.com/common/' \
                        'oauth2/v2.0/token'
    _default_token_file = 'o365_token.txt'
    _default_token_path = Path() / _default_token_file
    _allowed_methods = ['get', 'post', 'put', 'patch', 'delete']

    def __init__(self, credentials, *, scopes=None,
                 proxy_server=None, proxy_port=8080, proxy_username=None,
                 proxy_password=None,
                 requests_delay=200, raise_http_errors=True, request_retries=3,
                 token_file_name=None, **kwargs):
        """ Creates an API connection object

        :param tuple credentials: a tuple of (client_id, client_secret)

         Generate client_id and client_secret in https://apps.dev.microsoft.com
        :param list[str] scopes: list of scopes to request access to
        :param str proxy_server: the proxy server
        :param int proxy_port: the proxy port, defaults to 8080
        :param str proxy_username: the proxy username
        :param str proxy_password: the proxy password
        :param int requests_delay: number of milliseconds to wait between api
         calls.

         The Api will respond with 429 Too many requests if more than
         17 requests are made per second. Defaults to 200 milliseconds
         just in case more than 1 connection is making requests
         across multiple processes.
        :param bool raise_http_errors: If True Http 4xx and 5xx status codes
         will raise as exceptions
        :param int request_retries: number of retries done when the server
         responds with 5xx error codes.
        :param str token_file_name: custom token file name to be used when
         storing the OAuth token credentials.
        :raises ValueError: if credentials is not tuple of
         (client_id, client_secret)
        """
        if not isinstance(credentials, tuple) or len(credentials) != 2 or (
                not credentials[0] and not credentials[1]):
            raise ValueError('Provide valid auth credentials')

        self.auth = credentials
        self.scopes = scopes
        self.store_token = True
        self.token_path = ((Path() / token_file_name) if token_file_name
                           else self._default_token_path)
        self.token = kwargs.get('token')
        self.state = kwargs.get('state')

        self.session = None  # requests Oauth2Session object

        self.proxy = {}
        self.set_proxy(proxy_server, proxy_port, proxy_username, proxy_password)
        self.requests_delay = requests_delay or 0
        self.previous_request_at = None  # store previous request time
        self.raise_http_errors = raise_http_errors
        self.request_retries = request_retries

    def set_proxy(self, proxy_server, proxy_port, proxy_username,
                  proxy_password):
        """ Sets a proxy on the Session

        :param str proxy_server: the proxy server
        :param int proxy_port: the proxy port, defaults to 8080
        :param str proxy_username: the proxy username
        :param str proxy_password: the proxy password
        """
        if proxy_server and proxy_port:
            if proxy_username and proxy_password:
                self.proxy = {
                    "http": "http://{}:{}@{}:{}".format(proxy_username,
                                                        proxy_password,
                                                        proxy_server,
                                                        proxy_port),
                    "https": "https://{}:{}@{}:{}".format(proxy_username,
                                                          proxy_password,
                                                          proxy_server,
                                                          proxy_port),
                }
            else:
                self.proxy = {
                    "http": "http://{}:{}".format(proxy_server, proxy_port),
                    "https": "https://{}:{}".format(proxy_server, proxy_port),
                }

    def check_token_file(self):
        """ Checks if the token file exists at the given position

        :return: if file exists or not
        :rtype: bool
        """
        if self.token_path:
            path = Path(self.token_path)
        else:
            path = self._default_token_path

        return path.exists()

    def get_authorization_url(self, requested_scopes=None,
                              redirect_uri=OAUTH_REDIRECT_URL):
        """ Initializes the oauth authorization flow, getting the
        authorization url that the user must approve.

        :param list[str] requested_scopes: list of scopes to request access for
        :param str redirect_uri: redirect url configured in registered app
        :return: authorization url
        :rtype: str
        """

        client_id, _client_secret = self.auth

        if requested_scopes:
            scopes = requested_scopes
        elif self.scopes is not None:
            scopes = self.scopes
        else:
            raise ValueError('Must provide at least one scope')

        self._session_init(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scopes,
            token=self.token,
            state=self.state
        )

        # TODO: access_type='offline' has no effect according to documentation
        # TODO: This is done through scope 'offline_access'.
        auth_url, state = self.session.authorization_url(
            url=self._oauth2_authorize_url, access_type='offline')
        self.state = state

        return auth_url

    def get_session(self, token_path=None):
        """ Create a requests Session object

        :param Path token_path: (Only oauth) full path to where the token
         should be load from
        :return: A ready to use requests session
        :rtype: OAuth2Session
        """
        self.token = self.token or self._load_token(
            token_path or self.token_path)

        if self.token:
            client_id, _ = self.auth
            self._session_init(client_id=client_id, token=self.token)
        else:
            raise RuntimeError(
                'No auth token found. Authentication Flow needed')

        return self.session

    def _session_init(self, *args, **kwargs):
        """Init session specific per transport provider request/aiohttp"""
        raise NotImplementedError

    def _check_delay(self):
        """ Checks if a delay is needed between requests and sleeps if True """
        if self.previous_request_at:
            dif = round(time.time() - self.previous_request_at,
                        2) * 1000  # difference in miliseconds
            if dif < self.requests_delay:
                time.sleep(
                    (self.requests_delay - dif) / 1000)  # sleep needs seconds
        self.previous_request_at = time.time()

    def _save_token(self, token, token_path=None):
        """ Save the specified token dictionary to a specified file path

        :param dict token: token dictionary returned by the oauth token request,
         to be saved
        :param Path token_path: Path to the file with token information saved
        :return: Success/Failure
        :rtype: bool
        """
        if not token_path:
            token_path = self.token_path or self._default_token_path
        else:
            if not isinstance(token_path, Path):
                raise ValueError('token_path must be a valid Path from pathlib')

        with token_path.open('w') as token_file:
            json.dump(token, token_file, indent=True)

        return True

    def _load_token(self, token_path=None):
        """ Load the specified token dictionary from specified file path

        :param Path token_path: Path to the file with token information saved
        :return: token data
        :rtype: dict
        """
        if not token_path:
            token_path = self.token_path or self._default_token_path
        else:
            if not isinstance(token_path, Path):
                raise ValueError('token_path must be a valid Path from pathlib')

        token = None
        if token_path.exists():
            with token_path.open('r') as token_file:
                token = json.load(token_file)
        return token

    def _delete_token(self, token_path=None):
        """ Delete the specified token dictionary from specified file path

        :param Path token_path: Path to the file with token information saved
        :return: Success/Failure
        :rtype: bool
        """
        if not token_path:
            token_path = self.token_path or self._default_token_path
        else:
            if not isinstance(token_path, Path):
                raise ValueError('token_path must be a valid Path from pathlib')

        if token_path.exists():
            token_path.unlink()
            return True
        return False


class Connection(ConnectionBase):
    """Connection class."""

    def __init__(self, *args, **kwargs):
        """Custom initialization."""

        super(Connection, self).__init__(*args, **kwargs)

        self.naive_session = Session()  # requests Session object
        self.naive_session.proxies = self.proxy

        if self.request_retries:
            retry = Retry(total=self.request_retries, read=self.request_retries,
                          connect=self.request_retries,
                          backoff_factor=RETRIES_BACKOFF_FACTOR,
                          status_forcelist=RETRIES_STATUS_LIST)
            adapter = HTTPAdapter(max_retries=retry)
            self.naive_session.mount('http://', adapter)
            self.naive_session.mount('https://', adapter)

    def request_token(self, authorization_url, store_token=True,
                      token_path=None):
        """ Authenticates for the specified url and gets the token, save the
        token for future based if requested

        :param str authorization_url: url given by the authorization flow
        :param bool store_token: whether or not to store the token in file
         system, so u don't have to keep opening the auth link and
         authenticating every time
        :param Path token_path: full path to where the token should be saved to
        :return: Success/Failure
        :rtype: bool
        """

        if self.session is None:
            raise RuntimeError("Fist call 'get_authorization_url' to "
                               "generate a valid oauth object")

        client_id, client_secret = self.auth

        # Allow token scope to not match requested scope.
        # (Other auth libraries allow this, but Requests-OAuthlib
        # raises exception on scope mismatch by default.)
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'

        try:
            self.token = self.session.fetch_token(
                token_url=self._oauth2_token_url,
                authorization_response=authorization_url,
                client_id=client_id,
                client_secret=client_secret)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Unable to fetch auth token. Error: %s", err)
            return False

        if token_path:
            self.token_path = token_path
        self.store_token = store_token
        if self.store_token:
            self._save_token(self.token, self.token_path)

        return True

    def refresh_token(self):
        """ Refresh the OAuth authorization token """
        try:
            self.token = self.session.refresh_token(
                self._oauth2_token_url,
                refresh_token=self.token['refresh_token'])
            if self.store_token:
                self._save_token(self.token)
        except KeyError:
            raise Exception(
                "Refresh_Token not available, did you reqeest offline_access?")

    def naive_request(self, url, method, **kwargs):
        """ Makes a request to url using an without oauth authorization
        session, but through a normal session

        :param str url: url to send request to
        :param str method: type of request (get/put/post/patch/delete)
        :param kwargs: extra params to send to the request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(
            url, method, custom_session=self.naive_session, **kwargs)

    def oauth_request(self, url, method, custom_session=None, **kwargs):
        """ Makes a request to url using an oauth session

        :param str url: url to send request to
        :param str method: type of request (get/put/post/patch/delete)
        :param custom_session: a requests session if not default session.
        :param kwargs: extra params to send to the request api
        :return: Response of the request
        :rtype: requests.Response
        """
        session = custom_session or self.session or self.get_session()

        method = method.lower()
        assert method in self._allowed_methods, \
            'Method must be one of the allowed ones'

        if method == 'get':
            kwargs.setdefault('allow_redirects', True)
        elif method in ['post', 'put', 'patch']:
            kwargs.setdefault('headers', {})
            kwargs['headers'].setdefault('Content-type', 'application/json')
            if 'data' in kwargs and \
                    kwargs['headers']['Content-type'] == 'application/json':
                kwargs['data'] = json.dumps(
                    kwargs['data'])  # auto convert to json

        request_done = False
        token_refreshed = False

        while not request_done:
            self._check_delay()  # sleeps if needed
            try:
                _LOGGER.info("Requesting (%s) URL: %s", method.upper(), url)
                _LOGGER.info("Request parameters: %s", kwargs)
                # auto_retry will occur inside this function call if enabled
                response = session.request(method, url, **kwargs)
                response.raise_for_status()  # raise 4XX and 5XX error codes.
                _LOGGER.info("Received response (%s) from URL %s",
                             response.status_code, response.url)
                request_done = True
                return response
            except TokenExpiredError:
                # Token has expired refresh token and try again on the next loop
                if token_refreshed:
                    # Refresh token done but still TokenExpiredError raise
                    raise RuntimeError('Token Refresh Operation not working')
                _LOGGER.info("Oauth Token is expired, fetching a new token")
                self.refresh_token()
                _LOGGER.info("New oauth token fetched")
                token_refreshed = True
            except (rConnectionError, ProxyError, SSLError, Timeout) as err:
                # We couldn't connect to the target url, raise error
                _LOGGER.debug("Connection Error calling: %s.%s", url,
                              ("Using proxy: {}".format(self.proxy)
                               if self.proxy else ''))
                raise err  # re-raise exception
            except HTTPError as err:
                # Server response with 4XX or 5XX error status codes

                # try to extract the error message:
                try:
                    error = response.json()
                    error_message = error.get('error', {}).get('message', '')
                except ValueError:
                    error_message = ''

                status_code = int(err.response.status_code / 100)
                if status_code == 4:
                    # Client Error
                    # Logged as error. Could be a library error or Api changes
                    _LOGGER.error("Client Error: %s | Error Message: %s",
                                  err, error_message)
                else:
                    # Server Error
                    _LOGGER.debug("Server Error: %s", err)
                if self.raise_http_errors:
                    if error_message:
                        raise HTTPError('{} | Error Message: {}'.format(
                            err.args[0], error_message), response=response)
                    else:
                        raise err
                else:
                    return err.response
            except RequestException as err:
                # catch any other exception raised by requests
                _LOGGER.debug("Request Exception: %s", err)
                raise err

    def get(self, url, params=None, **kwargs):
        """ Shorthand for self.oauth_request(url, 'get')

        :param str url: url to send get oauth request to
        :param dict params: request parameter to get the service data
        :param kwargs: extra params to send to request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(url, 'get', params=params, **kwargs)

    def post(self, url, data=None, **kwargs):
        """ Shorthand for self.oauth_request(url, 'post')

        :param str url: url to send post oauth request to
        :param dict data: post data to update the service
        :param kwargs: extra params to send to request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(url, 'post', data=data, **kwargs)

    def put(self, url, data=None, **kwargs):
        """ Shorthand for self.oauth_request(url, 'put')

        :param str url: url to send put oauth request to
        :param dict data: put data to update the service
        :param kwargs: extra params to send to request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(url, 'put', data=data, **kwargs)

    def patch(self, url, data=None, **kwargs):
        """ Shorthand for self.oauth_request(url, 'patch')

        :param str url: url to send patch oauth request to
        :param dict data: patch data to update the service
        :param kwargs: extra params to send to request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(url, 'patch', data=data, **kwargs)

    def delete(self, url, **kwargs):
        """ Shorthand for self.request(url, 'delete')

        :param str url: url to send delete oauth request to
        :param kwargs: extra params to send to request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(url, 'delete', **kwargs)

    def _session_init(self, *args, **kwargs):
        """Init session specific per transport provider request/aiohttp"""

        self.session = OAuth2Session(*args, **kwargs)
        self.session.proxies = self.proxy

        if self.request_retries:
            retry = Retry(total=self.request_retries,
                          read=self.request_retries,
                          connect=self.request_retries,
                          backoff_factor=RETRIES_BACKOFF_FACTOR,
                          status_forcelist=RETRIES_STATUS_LIST)
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)
