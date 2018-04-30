import logging
import json
import os
import time
from pathlib import Path
from enum import Enum
from tzlocal import get_localzone
from datetime import tzinfo
import pytz

from stringcase import pascalcase, camelcase
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry  # dynamic loading of module Retry by requests.packages
from requests.exceptions import HTTPError
from oauthlib.oauth2 import TokenExpiredError
from requests_oauthlib import OAuth2Session

from O365.utils import ME_RESOURCE, IANA_TO_WIN, WIN_TO_IANA

log = logging.getLogger(__name__)

O365_API_VERSION = 'v1.0'  # v2.0 does not allow basic auth
GRAPH_API_VERSION = 'v1.0'
OAUTH_REDIRECT_URL = 'https://outlook.office365.com/owa/'

RETRIES_STATUS_LIST = [500, 502, 503, 504]
RETRIES_BACKOFF_FACTOR = 0.5


# Custom Exceptions
class BaseApiException(HTTPError):

    def __init__(self, response):
        try:
            error = response.json()
        except ValueError:
            error = {}
        error = error.get('error', {})
        super().__init__('{}: {} - {}'.format(response.status_code,
                                              error.get('code', response.reason),
                                              error.get('message', '')),
                         response=response)


class ApiBadRequestError(BaseApiException):
    """ Generic Error for 400 Bad Request error code """
    pass


class ApiInternalServerError(BaseApiException):
    """ Generic Error for 500 Internal Server Error error code """
    pass


class ApiOtherException(BaseApiException):
    """ Group of all other posible exceptions """
    pass


DEFAULT_SCOPES = {
    'basic': [('offline_access',), 'User.Read'],  # wrap any scope in a 1 element tuple to avoid prefixing
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
    'users': ['User.ReadBasic.All']
}


class AUTH_METHOD(Enum):
    BASIC = 'basic'
    OAUTH = 'oauth'


class Protocol:
    """ Base class for all protocols """

    _protocol_url = 'not_defined'  # Main url to request. Override in subclass
    _oauth_scope_prefix = ''  # prefix for scopes (in MS GRAPH is 'https://graph.microsoft.com/' + SCOPE)
    _oauth_scopes = {}  # dictionary of {scopes_name: [scope1, scope2]}
    _protocol_endpoint_transform = {}  # a dictionary of endpoints transformations

    def __init__(self, *, protocol_url=None, api_version=None, default_resource=ME_RESOURCE,
                 casing_function=None, protocol_scope_prefix=None, timezone=None):
        """
        :param protocol_url: the base url used to comunicate with the server
        :param api_version: the api version
        :param default_resource: the default resource to use when there's no other option
        :param casing_function: the casing transform function to be used on api keywords
        :param protocol_scope_prefix: prefix for scopes (in MS GRAPH is 'https://graph.microsoft.com/' + SCOPE)
        :param timezone: prefered timezone, defaults to the system timezone
        """
        if protocol_url is None or api_version is None:
            raise ValueError('Must provide valid protocol_url and api_version values')
        self.protocol_url = protocol_url or self._protocol_url
        self.protocol_scope_prefix = protocol_scope_prefix or ''
        self.api_version = api_version
        self.service_url = '{}{}/'.format(protocol_url, api_version)
        self.default_resource = default_resource
        self.use_default_casing = True if casing_function is None else False  # if true just returns the key without transform
        self.casing_function = casing_function or camelcase
        self.timezone = timezone or get_localzone()  # pytz timezone

        # define any keyword that can be different in this protocol
        self.keyword_data_store = {}

    def get_service_keyword(self, keyword):
        """ Returns the data set to the key in the internal data-key dict """
        return self.keyword_data_store.get(keyword, None)

    def convert_case(self, dict_key):
        """ Returns a key converted with this protocol casing method

        Converts case to send/read from the cloud
        When using Microsoft Graph API, the keywords of the API use lowerCamelCase Casing.
        When using ffice 365 API, the keywords of the API use PascalCase Casing.

        Default case in this API is lowerCamelCase.

        :param dict_key: a dictionary key to convert
        """
        return dict_key if self.use_default_casing else self.casing_function(dict_key)

    def get_scopes_for(self, user_provided_scopes):
        """ Returns a list of scopes needed for each of the scope_helpers provided
        :param user_provided_scopes: a list of scopes or scope helpers
        """
        if user_provided_scopes is None:
            # return all available scopes
            user_provided_scopes = [app_part for app_part in self._oauth_scopes]
        elif isinstance(user_provided_scopes, str):
            user_provided_scopes = [user_provided_scopes]

        if not isinstance(user_provided_scopes, (list, tuple)):
            raise ValueError("'user_provided_scopes' must be a list or a tuple of strings")

        scopes = set()
        for app_part in user_provided_scopes:
            for scope in self._oauth_scopes.get(app_part, [app_part]):
                scopes.add(self._prefix_scope(scope))

        return list(scopes)

    def _prefix_scope(self, scope):
        """ Inserts the protocol scope prefix """
        if self.protocol_scope_prefix:
            if isinstance(scope, tuple):
                return scope[0]
            elif scope.startswith(self.protocol_scope_prefix):
                return scope
            else:
                return '{}{}'.format(self.protocol_scope_prefix, scope)
        else:
            if isinstance(scope, tuple):
                return scope[0]
            else:
                return scope

    def transform_endpoint(self, endpoint):
        """ Converts and endpoint by replacing keywords """
        for key_word, replacement in self._protocol_endpoint_transform.items():
            if key_word in endpoint:
                endpoint = endpoint.replace(key_word, replacement)
        return endpoint

    @staticmethod
    def get_iana_tz(windows_tz):
        """ Returns a valid pytz TimeZone (Iana/Olson Timezones) from a given windows TimeZone
        Note: Windows Timezones are SHIT!
        """
        timezone = WIN_TO_IANA.get(windows_tz)
        if timezone is None:
            # Nope, that didn't work. Try adding "Standard Time",
            # it seems to work a lot of times:
            timezone = WIN_TO_IANA.get(windows_tz + ' Standard Time')

        # Return what we have.
        if timezone is None:
            raise pytz.UnknownTimeZoneError("Can't find Windows TimeZone " + windows_tz)

        return timezone

    def get_windows_tz(self, iana_tz=None):
        """ Returns a valid windows TimeZone from a given pytz TimeZone (Iana/Olson Timezones)
        Note: Windows Timezones are SHIT!... no ... really THEY ARE HOLY FUCKING SHIT!.
        """
        iana_tz = iana_tz or self.timezone
        timezone = IANA_TO_WIN.get(iana_tz.zone if isinstance(iana_tz, tzinfo) else iana_tz)
        if timezone is None:
            raise pytz.UnknownTimeZoneError("Can't find Iana TimeZone " + iana_tz.zone)

        return timezone


class MSGraphProtocol(Protocol):
    """ A Microsoft Graph Protocol Implementation
    https://docs.microsoft.com/en-us/outlook/rest/compare-graph-outlook
    """

    _protocol_url = 'https://graph.microsoft.com/'
    _oauth_scope_prefix = 'https://graph.microsoft.com/'
    _oauth_scopes = DEFAULT_SCOPES

    def __init__(self, api_version='v1.0', default_resource=ME_RESOURCE, **kwargs):
        super().__init__(protocol_url=self._protocol_url, api_version=api_version,
                         default_resource=default_resource, casing_function=camelcase,
                         protocol_scope_prefix=self._oauth_scope_prefix, **kwargs)

        self.keyword_data_store['message_type'] = 'microsoft.graph.message'
        self.keyword_data_store['file_attachment_type'] = '#microsoft.graph.fileAttachment'
        self.keyword_data_store['item_attachment_type'] = '#microsoft.graph.itemAttachment'
        self.max_top_value = 999  # Max $top parameter value


class MSOffice365Protocol(Protocol):
    """ A Microsoft Office 365 Protocol Implementation
    https://docs.microsoft.com/en-us/outlook/rest/compare-graph-outlook
    """

    _protocol_url = 'https://outlook.office.com/api/'
    _oauth_scope_prefix = 'https://outlook.office.com/'
    _oauth_scopes = DEFAULT_SCOPES

    def __init__(self, api_version='v2.0', default_resource=ME_RESOURCE, **kwargs):
        super().__init__(protocol_url=self._protocol_url, api_version=api_version,
                         default_resource=default_resource, casing_function=pascalcase,
                         protocol_scope_prefix=self._oauth_scope_prefix, **kwargs)

        self.keyword_data_store['message_type'] = 'Microsoft.OutlookServices.Message'
        self.keyword_data_store['file_attachment_type'] = '#Microsoft.OutlookServices.FileAttachment'
        self.keyword_data_store['item_attachment_type'] = '#Microsoft.OutlookServices.ItemAttachment'
        self.max_top_value = 999  # Max $top parameter value


class BasicAuthProtocol(MSOffice365Protocol):
    """
    A Microsoft Office 365 Protocol Implementation that works with basic auth
    Basic auth only works on 'https://outlook.office365.com/api/ protocol url
        with api version v1.0 and until November 1 2018.
    """

    _protocol_url = 'https://outlook.office365.com/api/'
    _protocol_endpoint_transform = {
        'mailFolders': 'Folders'
    }

    def __init__(self, api_version='v1.0', default_resource=ME_RESOURCE, **kwargs):
        super().__init__(api_version=api_version, default_resource=default_resource, **kwargs)


class Connection:
    """ Handles all comunication (requests) between the app and the server """

    _oauth2_authorize_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    _oauth2_token_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
    _default_token_file = 'o365_token.txt'
    _default_token_path = Path() / _default_token_file
    _allowed_methods = ['get', 'post', 'put', 'patch', 'delete']

    def __init__(self, credentials, *, auth_method=AUTH_METHOD.OAUTH, scopes=None,
                 proxy_server=None, proxy_port=8080, proxy_username=None, proxy_password=None,
                 requests_delay=200, raise_http_errors=True, request_retries=3):
        """ Creates an API connection object

        :param credentials: a tuple containing the credentials for this connection.
            This could be either (username, password) using basic authentication or (client_id, client_secret) using oauth.
            Generate client_id and client_secret in https://apps.dev.microsoft.com.
        :param auth_method: the method used when connecting to the service API.
        :param scopes: oauth2: a list of scopes permissions to request access to
        :param proxy_server: the proxy server
        :param proxy_port: the proxy port, defaults to 8080
        :param proxy_username: the proxy username
        :param proxy_password: the proxy password
        :param requests_delay: number of miliseconds to wait between api calls
            The Api will respond with 429 Too many requests if more than 17 requests are made per second.
            Defaults to 200 miliseconds just in case more than 1 connection is making requests across multiple processes.
        :param raise_http_errors: If True Http 4xx and 5xx status codes will raise a custom exception
        :param request_retries: number of retries done when the server responds with 5xx error codes.
        """
        if not isinstance(credentials, tuple) or len(credentials) != 2 or (not credentials[0] and not credentials[1]):
            raise ValueError('Provide valid auth credentials')

        if isinstance(auth_method, str):
            auth_method = AUTH_METHOD(auth_method)

        if auth_method is AUTH_METHOD.BASIC:
            self.auth_method = AUTH_METHOD.BASIC
            self.auth = credentials
        elif auth_method is AUTH_METHOD.OAUTH:
            self.auth_method = AUTH_METHOD.OAUTH
            self.auth = credentials
            self.scopes = scopes
            self.store_token = True
            self.token_path = self._default_token_path
            self.token = None
        else:
            raise ValueError("Auth Method must be 'basic' or 'oauth'")

        self.session = None  # requests Session object
        self.proxy = {}
        self.set_proxy(proxy_server, proxy_port, proxy_username, proxy_password)
        self.requests_delay = requests_delay or 0
        self.previous_request_at = None  # store the time of the previous request
        self.raise_http_errors = raise_http_errors
        self.request_retries = request_retries

    def set_proxy(self, proxy_server, proxy_port, proxy_username, proxy_password):
        """ Sets a proxy on the Session """
        if proxy_server and proxy_port and proxy_username and proxy_password:
            self.proxy = {
                "http": "http://{}:{}@{}:{}".format(proxy_username, proxy_password, proxy_server, proxy_port),
                "https": "https://{}:{}@{}:{}".format(proxy_username, proxy_password, proxy_server, proxy_port),
            }

    def check_token_file(self):
        """ Checks if the token file exists at the given position"""
        if self.token_path:
            path = Path(self.token_path)
        else:
            path = self._default_token_path

        return path.exists()

    def get_authorization_url(self, requested_scopes=None, redirect_uri=OAUTH_REDIRECT_URL):
        """
        Inicialices the oauth authorization flow, getting the authorization url that the user must approve.
        This is a two step process, first call this function. Then get the url result from the user and then
        call 'request_token' to get and store the access token.
        """
        if self.auth_method is AUTH_METHOD.BASIC:
            raise RuntimeError('Method not allowed using basic authentication')

        client_id, client_secret = self.auth

        if requested_scopes:
            scopes = requested_scopes
        elif self.scopes is not None:
            scopes = self.scopes
        else:
            raise ValueError('Must provide at least one scope')

        self.session = oauth = OAuth2Session(client_id=client_id, redirect_uri=redirect_uri, scope=scopes)
        self.session.proxies = self.proxy
        if self.request_retries:
            retry = Retry(total=self.request_retries, read=self.request_retries, connect=self.request_retries,
                          backoff_factor=RETRIES_BACKOFF_FACTOR, status_forcelist=RETRIES_STATUS_LIST)
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)

        # TODO: access_type='offline' has no effect acording to documentation. This is done through scope 'offline_access'.
        auth_url, state = oauth.authorization_url(url=self._oauth2_authorize_url, access_type='offline')

        return auth_url

    def request_token(self, authorizated_url, store_token=True, token_path=None):
        """
        Returns and saves the token with the authorizated_url provided by the user

        :param authorizated_url: url given by the authorization flow
        :param store_token: whether or not to store the token in file system,
                            so u don't have to keep opening the auth link and authenticating every time
        :param token_path: full path to where the token should be saved to
        """
        if self.auth_method is AUTH_METHOD.BASIC:
            raise RuntimeError('Method not allowed using basic authentication')

        if self.session is None:
            raise RuntimeError("Fist call 'get_authorization_url' to generate a valid oauth object")

        _, client_secret = self.auth

        # Allow token scope to not match requested scope. (Other auth libraries allow
        # this, but Requests-OAuthlib raises exception on scope mismatch by default.)
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'

        try:
            self.token = self.session.fetch_token(token_url=self._oauth2_token_url,
                                                  authorization_response=authorizated_url,
                                                  client_secret=client_secret)
        except Exception as e:
            log.error('Unable to fetch auth token. Error: {}'.format(str(e)))
            return None

        if token_path:
            self.token_path = token_path
        self.store_token = store_token
        if self.store_token:
            self._save_token(self.token, self.token_path)

        return True

    def get_session(self, token_path=None):
        """ Create a requests Session object

        :param token_path: Only oauth: full path to where the token should be load from
        """
        if self.auth_method is AUTH_METHOD.BASIC:
            self.session = requests.Session()
            self.session.auth = self.auth
        else:
            self.token = self.token or self._load_token(token_path)

            if self.token:
                client_id, _ = self.auth
                self.session = OAuth2Session(client_id=client_id, token=self.token)
            else:
                raise RuntimeError('No auth token found. Authentication Flow needed')

        self.session.proxies = self.proxy

        if self.request_retries:
            retry = Retry(total=self.request_retries, read=self.request_retries, connect=self.request_retries,
                          backoff_factor=RETRIES_BACKOFF_FACTOR, status_forcelist=RETRIES_STATUS_LIST)
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)

        return self.session

    def refresh_token(self):
        """ Gets another token """

        if self.auth_method is AUTH_METHOD.BASIC:
            raise RuntimeError('Method not allowed using basic authentication')

        client_id, client_secret = self.auth
        self.token = token = self.session.refresh_token(self._oauth2_token_url, client_id=client_id,
                                                        client_secret=client_secret)
        if self.store_token:
            self._save_token(token)

    def _check_delay(self):
        """ Checks if a delay is needed between requests and sleeps if True """
        if self.previous_request_at:
            dif = round(time.time() - self.previous_request_at, 2) * 1000  # difference in miliseconds
            if dif < self.requests_delay:
                time.sleep((self.requests_delay - dif) / 1000)  # sleep needs seconds
        self.previous_request_at = time.time()

    def request(self, url, method, **kwargs):
        """ Makes a request to url

        :param url: the requested url
        :param method: method to use
        """

        method = method.lower()
        assert method in self._allowed_methods, 'Method must be one of the allowed ones'

        if method == 'get':
            kwargs.setdefault('allow_redirects', True)
        elif method in ['post', 'put', 'patch']:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            if kwargs['headers'].get('Content-type') is None:
                kwargs['headers']['Content-type'] = 'application/json'
            if 'data' in kwargs and kwargs['headers']['Content-type'] == 'application/json':
                kwargs['data'] = json.dumps(kwargs['data'])  # autoconvert to json

        log.info('Requesting ({}) URL: {}'.format(method.upper(), url))
        log.info('Request parameters: {}'.format(kwargs))

        if self.auth_method is AUTH_METHOD.BASIC:
            # # basic authentication
            # kwargs['auth'] = self.auth  # set in get_session
            if not self.session:
                self.get_session()
            self._check_delay()  # sleeps if needed
            response = self.session.request(method, url, **kwargs)
        else:
            # oauth2 authentication
            if not self.session:
                self.get_session()
            self._check_delay()  # sleeps if needed
            try:
                response = self.session.request(method, url, **kwargs)
            except TokenExpiredError:
                log.info('Token is expired, fetching a new token')
                self.refresh_token()
                log.info('New token fetched')
                response = self.session.request(method, url, **kwargs)

        log.info('Received response ({}) from URL {}'.format(response.status_code, response.url))

        if response.status_code == 429:  # too many requests
            # Status Code 429 is not automatically retried by default.
            retry_after = response.headers.get('retry-after')
            reason = response.headers.get('rate-limit-reason')
            log.info('The Server respond with 429: Too Many Requests. Reason {}. Retry After {} seconds.'.format(reason, retry_after))
            # retry after seconds:
            if retry_after < 6:
                time.sleep(retry_after)
            log.info('Retrying request now after waiting for {} seconds'.format(retry_after))
            response = self.session.request(method, url, **kwargs)  # retrying request
            log.info('Received response ({}) from URL {}'.format(response.status_code, response.url))

        if not response.ok and self.raise_http_errors:
            raise self.raise_api_exception(response)
        return response

    def get(self, url, params=None, **kwargs):
        """ Shorthand for self.request(url, 'get') """
        return self.request(url, 'get', params=params, **kwargs)

    def post(self, url, data=None, **kwargs):
        """ Shorthand for self.request(url, 'post') """
        return self.request(url, 'post', data=data, **kwargs)

    def put(self, url, data=None, **kwargs):
        """ Shorthand for self.request(url, 'put') """
        return self.request(url, 'put', data=data, **kwargs)

    def patch(self, url, data=None, **kwargs):
        """ Shorthand for self.request(url, 'patch') """
        return self.request(url, 'patch', data=data, **kwargs)

    def delete(self, url, **kwargs):
        """ Shorthand for self.request(url, 'delete') """
        return self.request(url, 'delete', **kwargs)

    def _save_token(self, token, token_path=None):
        """ Save the specified token dictionary to a specified file path

        :param token: token dictionary returned by the oauth token request
        :param token_path: Path object to where the file is to be saved
        """
        if self.auth_method is AUTH_METHOD.BASIC:
            raise RuntimeError('Method not allowed using basic authentication')

        if not token_path:
            token_path = self._default_token_path
        else:
            if not isinstance(token_path, Path):
                raise ValueError('token_path must be a valid Path from pathlib')

        with token_path.open('w') as token_file:
            json.dump(token, token_file, indent=True)

        return True

    def _load_token(self, token_path=None):
        """ Load the specified token dictionary from specified file path

        :param token_path: Path object to the file with token information saved
        """
        if self.auth_method is AUTH_METHOD.BASIC:
            raise RuntimeError('Method not allowed using basic authentication')

        if not token_path:
            token_path = self._default_token_path
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

        :param token_path: Path object to where the token is saved
        """
        if self.auth_method is AUTH_METHOD.BASIC:
            raise RuntimeError('Method not allowed using basic authentication')

        if not token_path:
            token_path = self._default_token_path
        else:
            if not isinstance(token_path, Path):
                raise ValueError('token_path must be a valid Path from pathlib')

        if token_path.exists():
            token_path.unlink()
            return True
        return False

    @staticmethod
    def raise_api_exception(response):
        """ Raises a custom exception """
        code = int(response.status_code / 100)
        if code == 4:
            return ApiBadRequestError(response)
        elif code == 5:
            return ApiInternalServerError(response)
        else:
            return ApiOtherException(response)
