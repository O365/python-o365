import logging
import json
import os
import time
from pathlib import Path
from tzlocal import get_localzone
from datetime import tzinfo
import pytz

from stringcase import pascalcase, camelcase, snakecase
from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry  # dynamic loading of module Retry by requests.packages
from requests.exceptions import HTTPError, RequestException, ProxyError, SSLError, Timeout, ConnectionError
from oauthlib.oauth2 import TokenExpiredError
from requests_oauthlib import OAuth2Session

from O365.utils import ME_RESOURCE, IANA_TO_WIN, WIN_TO_IANA

log = logging.getLogger(__name__)

O365_API_VERSION = 'v2.0'  # v2.0 does not allow basic auth
GRAPH_API_VERSION = 'v1.0'
OAUTH_REDIRECT_URL = 'https://outlook.office365.com/owa/'

RETRIES_STATUS_LIST = (429, 500, 502, 503, 504)  # 429 is the TooManyRequests status code.
RETRIES_BACKOFF_FACTOR = 0.5


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
    'users': ['User.ReadBasic.All'],
    'onedrive': ['Files.ReadWrite.All'],
    'sharepoint_dl': ['Sites.ReadWrite.All'],
}


class Protocol:
    """ Base class for all protocols """

    _protocol_url = 'not_defined'  # Main url to request. Override in subclass
    _oauth_scope_prefix = ''  # prefix for scopes (in MS GRAPH is 'https://graph.microsoft.com/' + SCOPE)
    _oauth_scopes = {}  # dictionary of {scopes_name: [scope1, scope2]}

    def __init__(self, *, protocol_url=None, api_version=None, default_resource=ME_RESOURCE,
                 casing_function=None, protocol_scope_prefix=None, timezone=None, **kwargs):
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
        self.max_top_value = 500  # Max $top parameter value

        # define any keyword that can be different in this protocol
        self.keyword_data_store = {}

    def get_service_keyword(self, keyword):
        """ Returns the data set to the key in the internal data-key dict """
        return self.keyword_data_store.get(keyword, None)

    def convert_case(self, dict_key):
        """ Returns a key converted with this protocol casing method

        Converts case to send/read from the cloud
        When using Microsoft Graph API, the keywords of the API use lowerCamelCase Casing.
        When using Office 365 API, the keywords of the API use PascalCase Casing.

        Default case in this API is lowerCamelCase.

        :param dict_key: a dictionary key to convert
        """
        return dict_key if self.use_default_casing else self.casing_function(dict_key)

    @staticmethod
    def to_api_case(dict_key):
        """ Converts keys to snake case """
        return snakecase(dict_key)

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


class Connection:
    """ Handles all comunication (requests) between the app and the server """

    _oauth2_authorize_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    _oauth2_token_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
    _default_token_file = 'o365_token.txt'
    _default_token_path = Path() / _default_token_file
    _allowed_methods = ['get', 'post', 'put', 'patch', 'delete']

    def __init__(self, credentials, *, scopes=None,
                 proxy_server=None, proxy_port=8080, proxy_username=None, proxy_password=None,
                 requests_delay=200, raise_http_errors=True, request_retries=3, token_file_name=None):
        """ Creates an API connection object

        :param credentials: a tuple containing the credentials for this connection.
            This could be either (username, password) using basic authentication or (client_id, client_secret) using oauth.
            Generate client_id and client_secret in https://apps.dev.microsoft.com.
        :param scopes: oauth2: a list of scopes permissions to request access to
        :param proxy_server: the proxy server
        :param proxy_port: the proxy port, defaults to 8080
        :param proxy_username: the proxy username
        :param proxy_password: the proxy password
        :param requests_delay: number of miliseconds to wait between api calls
            The Api will respond with 429 Too many requests if more than 17 requests are made per second.
            Defaults to 200 miliseconds just in case more than 1 connection is making requests across multiple processes.
        :param raise_http_errors: If True Http 4xx and 5xx status codes will raise as exceptions
        :param request_retries: number of retries done when the server responds with 5xx error codes.
        :param token_file_name: custom token file name to be used when storing the token credentials.
        """
        if not isinstance(credentials, tuple) or len(credentials) != 2 or (not credentials[0] and not credentials[1]):
            raise ValueError('Provide valid auth credentials')

        self.auth = credentials
        self.scopes = scopes
        self.store_token = True
        self.token_path = (Path() / token_file_name) if token_file_name else self._default_token_path
        self.token = None

        self.session = None  # requests Oauth2Session object

        self.proxy = {}
        self.set_proxy(proxy_server, proxy_port, proxy_username, proxy_password)
        self.requests_delay = requests_delay or 0
        self.previous_request_at = None  # store the time of the previous request
        self.raise_http_errors = raise_http_errors
        self.request_retries = request_retries

        self.naive_session = Session()  # requests Session object
        self.naive_session.proxies = self.proxy

        if self.request_retries:
            retry = Retry(total=self.request_retries, read=self.request_retries, connect=self.request_retries,
                          backoff_factor=RETRIES_BACKOFF_FACTOR, status_forcelist=RETRIES_STATUS_LIST)
            adapter = HTTPAdapter(max_retries=retry)
            self.naive_session.mount('http://', adapter)
            self.naive_session.mount('https://', adapter)

    def set_proxy(self, proxy_server, proxy_port, proxy_username, proxy_password):
        """ Sets a proxy on the Session """
        if proxy_server and proxy_port:
            if proxy_username and proxy_password:
                self.proxy = {
                    "http": "http://{}:{}@{}:{}".format(proxy_username, proxy_password, proxy_server, proxy_port),
                    "https": "https://{}:{}@{}:{}".format(proxy_username, proxy_password, proxy_server, proxy_port),
                }
            else:
                self.proxy = {
                    "http": "http://{}:{}".format(proxy_server, proxy_port),
                    "https": "https://{}:{}".format(proxy_server, proxy_port),
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

        if self.session is None:
            raise RuntimeError("Fist call 'get_authorization_url' to generate a valid oauth object")

        client_id, client_secret = self.auth

        # Allow token scope to not match requested scope. (Other auth libraries allow
        # this, but Requests-OAuthlib raises exception on scope mismatch by default.)
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'

        try:
            self.token = self.session.fetch_token(token_url=self._oauth2_token_url,
                                                  authorization_response=authorizated_url,
                                                  client_id=client_id,
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
        self.token = self.token or self._load_token(token_path or self.token_path)

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

    def _internal_request(self, request_obj, url, method, **kwargs):
        """
        Internal handling of requests. Handles Exceptions.

        :param request_obj: a requests session.
        :param url: the url to be requested
        :param method: the method used on the request
        :param kwargs: any other payload to be passed to requests
        """

        method = method.lower()
        assert method in self._allowed_methods, 'Method must be one of the allowed ones'

        if method == 'get':
            kwargs.setdefault('allow_redirects', True)
        elif method in ['post', 'put', 'patch']:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            if kwargs.get('headers') is not None and kwargs['headers'].get('Content-type') is None:
                kwargs['headers']['Content-type'] = 'application/json'
            if 'data' in kwargs and kwargs['headers'].get('Content-type') == 'application/json':
                kwargs['data'] = json.dumps(kwargs['data'])  # autoconvert to json

        request_done = False
        token_refreshed = False

        while not request_done:
            self._check_delay()  # sleeps if needed
            try:
                log.info('Requesting ({}) URL: {}'.format(method.upper(), url))
                log.info('Request parameters: {}'.format(kwargs))
                response = request_obj.request(method, url, **kwargs)  # auto_retry will occur inside this funcion call if enabled
                response.raise_for_status()  # raise 4XX and 5XX error codes.
                log.info('Received response ({}) from URL {}'.format(response.status_code, response.url))
                request_done = True
                return response
            except TokenExpiredError:
                # Token has expired refresh token and try again on the next loop
                if token_refreshed:
                    # Refresh token done but still TolenExpiredError raise
                    raise RuntimeError('Token Refresh Operation not working')
                log.info('Oauth Token is expired, fetching a new token')
                self.refresh_token()
                log.info('New oauth token fetched')
                token_refreshed = True
            except (ConnectionError, ProxyError, SSLError, Timeout) as e:
                # We couldn't connect to the target url, raise error
                log.debug('Connection Error calling: {}.{}'.format(url, 'Using proxy: {}'.format(self.proxy) if self.proxy else ''))
                raise e  # re-raise exception
            except HTTPError as e:
                # Server response with 4XX or 5XX error status codes
                status_code = int(e.response.status_code / 100)
                if status_code == 4:
                    # Client Error
                    log.error('Client Error: {}'.format(str(e)))  # logged as error. Could be a library error or Api changes
                else:
                    # Server Error
                    log.debug('Server Error: {}'.format(str(e)))
                if self.raise_http_errors:
                    raise e
                else:
                    return e.response
            except RequestException as e:
                # catch any other exception raised by requests
                log.debug('Request Exception: {}'.format(str(e)))
                raise e

    def naive_request(self, url, method, **kwargs):
        """ A naive request without any Authorization headers """
        return self._internal_request(self.naive_session, url, method, **kwargs)

    def oauth_request(self, url, method, **kwargs):
        """ Makes a request to url using an oauth session """

        # oauth authentication
        if not self.session:
            self.get_session()

        return self._internal_request(self.session, url, method, **kwargs)

    def get(self, url, params=None, **kwargs):
        """ Shorthand for self.request(url, 'get') """
        return self.oauth_request(url, 'get', params=params, **kwargs)

    def post(self, url, data=None, **kwargs):
        """ Shorthand for self.request(url, 'post') """
        return self.oauth_request(url, 'post', data=data, **kwargs)

    def put(self, url, data=None, **kwargs):
        """ Shorthand for self.request(url, 'put') """
        return self.oauth_request(url, 'put', data=data, **kwargs)

    def patch(self, url, data=None, **kwargs):
        """ Shorthand for self.request(url, 'patch') """
        return self.oauth_request(url, 'patch', data=data, **kwargs)

    def delete(self, url, **kwargs):
        """ Shorthand for self.request(url, 'delete') """
        return self.oauth_request(url, 'delete', **kwargs)

    def _save_token(self, token, token_path=None):
        """ Save the specified token dictionary to a specified file path

        :param token: token dictionary returned by the oauth token request
        :param token_path: Path object to where the file is to be saved
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

        :param token_path: Path object to the file with token information saved
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

        :param token_path: Path object to where the token is saved
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


def oauth_authentication_flow(client_id, client_secret, scopes=None, protocol=None, **kwargs):
    """
    A helper method to authenticate and get the oauth token
    :param client_id: the client_id
    :param client_secret: the client_secret
    :param scopes: a list of protocol user scopes to be converted by the protocol
    :param protocol: the protocol to be used. Defaults to MSGraphProtocol
    :param kwargs: other configuration to be passed to the Connection instance
    """

    credentials = (client_id, client_secret)

    protocol = protocol or MSGraphProtocol()

    con = Connection(credentials, scopes=protocol.get_scopes_for(scopes), **kwargs)

    consent_url = con.get_authorization_url()
    print('Visit the following url to give consent:')
    print(consent_url)

    token_url = input('Paste the authenticated url here: ')

    if token_url:
        result = con.request_token(token_url)
        if result:
            print('Authentication Flow Completed. Oauth Access Token Stored. You can now use the API.')
        else:
            print('Something go wrong. Please try again.')

        return bool(result)
    else:
        print('Authentication Flow aborted.')
        return False
