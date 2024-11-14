import json
import logging
import os
import time
from typing import Optional, Callable, Union

from oauthlib.oauth2 import TokenExpiredError, WebApplicationClient, BackendApplicationClient, LegacyApplicationClient
from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError, RequestException, ProxyError
from requests.exceptions import SSLError, Timeout, ConnectionError
# Dynamic loading of module Retry by requests.packages
# noinspection PyUnresolvedReferences
from requests.packages.urllib3.util.retry import Retry
from requests_oauthlib import OAuth2Session
from tzlocal import get_localzone
from zoneinfo import ZoneInfoNotFoundError, ZoneInfo
from .utils import (ME_RESOURCE, BaseTokenBackend, FileSystemTokenBackend, Token, get_windows_tz, to_camel_case,
                    to_snake_case, to_pascal_case)
import datetime as dt

log = logging.getLogger(__name__)

O365_API_VERSION = 'v2.0'
GRAPH_API_VERSION = 'v1.0'
OAUTH_REDIRECT_URL = 'https://login.microsoftonline.com/common/oauth2/nativeclient'  # version <= 1.1.3.  : 'https://outlook.office365.com/owa/'

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
    "mailbox_settings": ["MailboxSettings.ReadWrite"],
    'message_send': ['Mail.Send'],
    'message_send_shared': ['Mail.Send.Shared'],
    'message_all': ['Mail.ReadWrite', 'Mail.Send'],
    'message_all_shared': ['Mail.ReadWrite.Shared', 'Mail.Send.Shared'],
    'address_book': ['Contacts.Read'],
    'address_book_shared': ['Contacts.Read.Shared'],
    'address_book_all': ['Contacts.ReadWrite'],
    'address_book_all_shared': ['Contacts.ReadWrite.Shared'],
    'calendar': ['Calendars.Read'],
    'calendar_shared': ['Calendars.Read.Shared'],
    'calendar_all': ['Calendars.ReadWrite'],
    'calendar_shared_all': ['Calendars.ReadWrite.Shared'],
    'users': ['User.ReadBasic.All'],
    'onedrive': ['Files.Read.All'],
    'onedrive_all': ['Files.ReadWrite.All'],
    'sharepoint': ['Sites.Read.All'],
    'sharepoint_all': ['Sites.ReadWrite.All'],
    'settings_all': ['MailboxSettings.ReadWrite'],
    'tasks': ['Tasks.Read'],
    'tasks_all': ['Tasks.ReadWrite'],
    'presence': ['Presence.Read']
}


class Protocol:
    """ Base class for all protocols """

    # Override these in subclass
    _protocol_url = 'not_defined'  # Main url to request.
    _oauth_scope_prefix = ''  # Prefix for scopes
    _oauth_scopes = {}  # Dictionary of {scopes_name: [scope1, scope2]}

    def __init__(self, *, protocol_url: Optional[str] = None,
                 api_version: Optional[str] = None,
                 default_resource: Optional[str] = None,
                 casing_function: Optional[Callable] = None,
                 protocol_scope_prefix: Optional[str] = None,
                 timezone: Union[Optional[str], Optional[ZoneInfo]] = None, **kwargs):
        """ Create a new protocol object

        :param protocol_url: the base url used to communicate with the
         server
        :param api_version: the api version
        :param default_resource: the default resource to use when there is
         nothing explicitly specified during the requests
        :param casing_function: the casing transform function to be
         used on api keywords (camelcase / pascalcase)
        :param protocol_scope_prefix: prefix url for scopes
        :param timezone: preferred timezone, if not provided will default
         to the system timezone or fallback to UTC
        :raises ValueError: if protocol_url or api_version are not supplied
        """
        if protocol_url is None or api_version is None:
            raise ValueError(
                'Must provide valid protocol_url and api_version values')
        self.protocol_url: str = protocol_url or self._protocol_url
        self.protocol_scope_prefix: str = protocol_scope_prefix or ''
        self.api_version: str = api_version
        self.service_url: str = '{}{}/'.format(protocol_url, api_version)
        self.default_resource: str = default_resource or ME_RESOURCE
        self.use_default_casing: bool = True if casing_function is None else False
        self.casing_function: Callable = casing_function or to_camel_case

        # get_localzone() from tzlocal will try to get the system local timezone and if not will return UTC
        self._timezone: ZoneInfo = get_localzone()

        # define any keyword that can be different in this protocol
        # for example, attachments OData type differs between Outlook
        #  rest api and graph: (graph = #microsoft.graph.fileAttachment and
        #  outlook = #Microsoft.OutlookServices.FileAttachment')
        self.keyword_data_store: dict = {}

        self.max_top_value: int = 500  # Max $top parameter value

        if timezone:
            self.timezone = timezone  # property setter will convert this timezone to ZoneInfo if a string is provided

    @property
    def timezone(self):
        return self._timezone

    @timezone.setter
    def timezone(self, timezone: Union[str, ZoneInfo]):
        self._update_timezone(timezone)

    def _update_timezone(self, timezone: Union[str, ZoneInfo]):
        """Sets the timezone. This is not done in the setter as you can't call super from a overriden setter """
        if isinstance(timezone, str):
            # convert string to ZoneInfo
            try:
                timezone = ZoneInfo(timezone)
            except ZoneInfoNotFoundError as e:
                log.error(f'Timezone {timezone} could not be found.')
                raise e
        else:
            if not isinstance(timezone, ZoneInfo):
                raise ValueError('The timezone parameter must be either a string or a valid ZoneInfo instance.')
        self._timezone = timezone

    def get_service_keyword(self, keyword: str) -> str:
        """ Returns the data set to the key in the internal data-key dict

        :param keyword: key to get value for
        :return: value of the keyword
        """
        return self.keyword_data_store.get(keyword, None)

    def convert_case(self, key: str) -> str:
        """ Returns a key converted with this protocol casing method

        Converts case to send/read from the cloud

        When using Microsoft Graph API, the keywords of the API use
        lowerCamelCase Casing

        When using Office 365 API, the keywords of the API use PascalCase Casing

        Default case in this API is lowerCamelCase

        :param  key: a dictionary key to convert
        :return: key after case conversion
        """
        return key if self.use_default_casing else self.casing_function(key)

    @staticmethod
    def to_api_case(key: str) -> str:
        """ Converts key to snake_case

        :param key: key to convert into snake_case
        :return: key after case conversion
        """
        return to_snake_case(key)

    def get_scopes_for(self, user_provided_scopes: Optional[Union[list, str, tuple]]) -> list:
        """ Returns a list of scopes needed for each of the
        scope_helpers provided, by adding the prefix to them if required

        :param user_provided_scopes: a list of scopes or scope helpers
        :return: scopes with url prefix added
        :raises ValueError: if unexpected datatype of scopes are passed
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
            for scope in self._oauth_scopes.get(app_part, [(app_part,)]):
                scopes.add(self.prefix_scope(scope))

        return list(scopes)

    def prefix_scope(self, scope: Union[tuple, str]) -> str:
        """ Inserts the protocol scope prefix if required"""
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


class MSGraphProtocol(Protocol):
    """ A Microsoft Graph Protocol Implementation
    https://docs.microsoft.com/en-us/outlook/rest/compare-graph-outlook
    """

    _protocol_url = 'https://graph.microsoft.com/'
    _oauth_scope_prefix = 'https://graph.microsoft.com/'
    _oauth_scopes = DEFAULT_SCOPES

    def __init__(self, api_version='v1.0', default_resource=None,
                 **kwargs):
        """ Create a new Microsoft Graph protocol object

        _protocol_url = 'https://graph.microsoft.com/'

        _oauth_scope_prefix = 'https://graph.microsoft.com/'

        :param str api_version: api version to use
        :param str default_resource: the default resource to use when there is
         nothing explicitly specified during the requests
        """
        super().__init__(protocol_url=self._protocol_url,
                         api_version=api_version,
                         default_resource=default_resource,
                         casing_function=to_camel_case,
                         protocol_scope_prefix=self._oauth_scope_prefix,
                         **kwargs)

        self.keyword_data_store['message_type'] = 'microsoft.graph.message'
        self.keyword_data_store['event_message_type'] = 'microsoft.graph.eventMessage'
        self.keyword_data_store['file_attachment_type'] = '#microsoft.graph.fileAttachment'
        self.keyword_data_store['item_attachment_type'] = '#microsoft.graph.itemAttachment'
        self.keyword_data_store['prefer_timezone_header'] = f'outlook.timezone="{get_windows_tz(self._timezone)}"'
        self.max_top_value = 999  # Max $top parameter value

    @Protocol.timezone.setter
    def timezone(self, timezone: Union[str, ZoneInfo]):
        super()._update_timezone(timezone)
        self.keyword_data_store['prefer_timezone_header'] = f'outlook.timezone="{get_windows_tz(self._timezone)}"'


class MSOffice365Protocol(Protocol):
    """ A Microsoft Office 365 Protocol Implementation
    https://docs.microsoft.com/en-us/outlook/rest/compare-graph-outlook
    """

    _protocol_url = 'https://outlook.office.com/api/'
    _oauth_scope_prefix = 'https://outlook.office.com/'
    _oauth_scopes = DEFAULT_SCOPES

    def __init__(self, api_version='v2.0', default_resource=None,
                 **kwargs):
        """ Create a new Office 365 protocol object

        _protocol_url = 'https://outlook.office.com/api/'

        _oauth_scope_prefix = 'https://outlook.office.com/'

        :param str api_version: api version to use
        :param str default_resource: the default resource to use when there is
         nothing explicitly specified during the requests
        """
        super().__init__(protocol_url=self._protocol_url,
                         api_version=api_version,
                         default_resource=default_resource,
                         casing_function=to_pascal_case,
                         protocol_scope_prefix=self._oauth_scope_prefix,
                         **kwargs)

        self.keyword_data_store['message_type'] = 'Microsoft.OutlookServices.Message'
        self.keyword_data_store['event_message_type'] = 'Microsoft.OutlookServices.EventMessage'
        self.keyword_data_store['file_attachment_type'] = '#Microsoft.OutlookServices.FileAttachment'
        self.keyword_data_store['item_attachment_type'] = '#Microsoft.OutlookServices.ItemAttachment'
        self.keyword_data_store['prefer_timezone_header'] = f'outlook.timezone="{get_windows_tz(self.timezone)}"'
        self.max_top_value = 999  # Max $top parameter value

    @Protocol.timezone.setter
    def timezone(self, timezone: Union[str, ZoneInfo]):
        super()._update_timezone(timezone)
        self.keyword_data_store['prefer_timezone_header'] = f'outlook.timezone="{get_windows_tz(self._timezone)}"'


class MSBusinessCentral365Protocol(Protocol):
    """ A Microsoft Business Central Protocol Implementation
    https://docs.microsoft.com/en-us/dynamics-nav/api-reference/v1.0/endpoints-apis-for-dynamics
    """

    _protocol_url = 'https://api.businesscentral.dynamics.com/'
    _oauth_scope_prefix = 'https://api.businesscentral.dynamics.com/'
    _oauth_scopes = DEFAULT_SCOPES
    _protocol_scope_prefix = 'https://api.businesscentral.dynamics.com/'

    def __init__(self, api_version='v1.0', default_resource=None, environment=None,
                 **kwargs):
        """ Create a new Microsoft Graph protocol object

        _protocol_url = 'https://api.businesscentral.dynamics.com/'

        _oauth_scope_prefix = 'https://api.businesscentral.dynamics.com/'

        :param str api_version: api version to use
        :param str default_resource: the default resource to use when there is
         nothing explicitly specified during the requests
        """
        if environment:
            _version = "2.0"
            _environment = "/" + environment
        else:
            _version = "1.0"
            _environment = ''

        self._protocol_url = "{}v{}{}/api/".format(self._protocol_url, _version, _environment)

        super().__init__(protocol_url=self._protocol_url,
                         api_version=api_version,
                         default_resource=default_resource,
                         casing_function=to_camel_case,
                         protocol_scope_prefix=self._protocol_scope_prefix,
                         **kwargs)

        self.keyword_data_store['message_type'] = 'microsoft.graph.message'
        self.keyword_data_store['event_message_type'] = 'microsoft.graph.eventMessage'
        self.keyword_data_store['file_attachment_type'] = '#microsoft.graph.fileAttachment'
        self.keyword_data_store['item_attachment_type'] = '#microsoft.graph.itemAttachment'
        self.keyword_data_store['prefer_timezone_header'] = f'outlook.timezone="{get_windows_tz(self.timezone)}"'
        self.max_top_value = 999  # Max $top parameter value

    @Protocol.timezone.setter
    def timezone(self, timezone: Union[str, ZoneInfo]):
        super()._update_timezone(timezone)
        self.keyword_data_store['prefer_timezone_header'] = f'outlook.timezone="{get_windows_tz(self._timezone)}"'


class Connection:
    """ Handles all communication (requests) between the app and the server """

    _allowed_methods = ['get', 'post', 'put', 'patch', 'delete']

    def __init__(self, credentials, *, scopes=None,
                 proxy_server=None, proxy_port=8080, proxy_username=None,
                 proxy_password=None, proxy_http_only=False, requests_delay=200, raise_http_errors=True,
                 request_retries=3, token_backend=None,
                 tenant_id='common',
                 auth_flow_type='authorization',
                 username=None, password=None,
                 timeout=None, json_encoder=None,
                 verify_ssl=True,
                 default_headers: dict = None,
                 **kwargs):
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
        :param BaseTokenBackend token_backend: the token backend used to get
         and store tokens
        :param str tenant_id: use this specific tenant id, defaults to common
        :param dict default_headers: allow to force headers in api call
        (ex: default_headers={"Prefer": 'IdType="ImmutableId"'}) to get constant id for objects.
        :param str auth_flow_type: the auth method flow style used: Options:
            - 'authorization': 2 step web style grant flow using an authentication url
            - 'public': 2 step web style grant flow using an authentication url for public apps where
            client secret cannot be secured
            - 'credentials': also called client credentials grant flow using only the client id and secret
            - 'certificate': like credentials, but using the client id and a JWT assertion (obtained from a certificate)
        :param str username: The user's email address to provide in case of auth_flow_type == 'password'
        :param str password: The user's password to provide in case of auth_flow_type == 'password'
        :param float or tuple timeout: How long to wait for the server to send
            data before giving up, as a float, or a tuple (connect timeout, read timeout)
        :param JSONEncoder json_encoder: The JSONEncoder to use during the JSON serialization on the request.
        :param bool verify_ssl: set the verify flag on the requests library
        :param dict kwargs: any extra params passed to Connection
        :raises ValueError: if credentials is not tuple of
         (client_id, client_secret)
        """
        if auth_flow_type in ('public', 'password'):  # allow client id only for public or password flow
            if isinstance(credentials, str):
                credentials = (credentials,)
            if not isinstance(credentials, tuple) or len(credentials) != 1 or (not credentials[0]):
                raise ValueError('Provide client id only for public or password flow credentials')
        else:
            if not isinstance(credentials, tuple) or len(credentials) != 2 or (
                    not credentials[0] and not credentials[1]):
                raise ValueError('Provide valid auth credentials')

        self._auth_flow_type = auth_flow_type  # 'authorization', 'credentials', 'certificate', 'password', or 'public'
        if auth_flow_type in ('credentials', 'certificate', 'password') and tenant_id == 'common':
            raise ValueError('When using the "credentials", "certificate", or "password" auth_flow the "tenant_id" '
                             'must be set')

        self.tenant_id = tenant_id
        self.auth = credentials
        self.username = username
        self.password = password
        self.scopes = scopes
        self.default_headers = default_headers or dict()
        self.store_token = True
        token_backend = token_backend or FileSystemTokenBackend(**kwargs)
        if not isinstance(token_backend, BaseTokenBackend):
            raise ValueError('"token_backend" must be an instance of a subclass of BaseTokenBackend')
        self.token_backend = token_backend
        self.session = None  # requests Oauth2Session object

        self.proxy = {}
        self.set_proxy(proxy_server, proxy_port, proxy_username, proxy_password, proxy_http_only)
        self.requests_delay = requests_delay or 0
        self._previous_request_at = None  # store previous request time
        self.raise_http_errors = raise_http_errors
        self.request_retries = request_retries
        self.timeout = timeout
        self.json_encoder = json_encoder
        self.verify_ssl = verify_ssl

        self.naive_session = None  # lazy loaded: holds a requests Session object

        self._oauth2_authorize_url = 'https://login.microsoftonline.com/' \
                                     '{}/oauth2/v2.0/authorize'.format(tenant_id)
        self._oauth2_token_url = 'https://login.microsoftonline.com/' \
                                 '{}/oauth2/v2.0/token'.format(tenant_id)
        self.oauth_redirect_url = 'https://login.microsoftonline.com/common/oauth2/nativeclient'

    @property
    def auth_flow_type(self):
        return self._auth_flow_type

    def set_proxy(self, proxy_server, proxy_port, proxy_username,
                  proxy_password, proxy_http_only):
        """ Sets a proxy on the Session

        :param str proxy_server: the proxy server
        :param int proxy_port: the proxy port, defaults to 8080
        :param str proxy_username: the proxy username
        :param str proxy_password: the proxy password
        """
        if proxy_server and proxy_port:
            if proxy_username and proxy_password:
                proxy_uri = "{}:{}@{}:{}".format(proxy_username,
                                                 proxy_password,
                                                 proxy_server,
                                                 proxy_port)
            else:
                proxy_uri = "{}:{}".format(proxy_server,
                                           proxy_port)

            if proxy_http_only is False:
                self.proxy = {
                    "http": "http://{}".format(proxy_uri),
                    "https": "https://{}".format(proxy_uri)
                }
            else:
                self.proxy = {
                    "http": "http://{}".format(proxy_uri),
                    "https": "http://{}".format(proxy_uri)
                }

    def get_authorization_url(self, requested_scopes=None,
                              redirect_uri=None, **kwargs):
        """ Initializes the oauth authorization flow, getting the
        authorization url that the user must approve.

        :param list[str] requested_scopes: list of scopes to request access for
        :param str redirect_uri: redirect url configured in registered app
        :param kwargs: allow to pass unused params in conjunction with Connection
        :return: authorization url
        :rtype: str
        """

        redirect_uri = redirect_uri or self.oauth_redirect_url

        scopes = requested_scopes or self.scopes
        if not scopes:
            raise ValueError('Must provide at least one scope')

        self.session = oauth = self.get_session(redirect_uri=redirect_uri,
                                                scopes=scopes)

        # TODO: access_type='offline' has no effect according to documentation
        #  This is done through scope 'offline_access'.
        auth_url, state = oauth.authorization_url(
            url=self._oauth2_authorize_url, access_type='offline', **kwargs)

        return auth_url, state

    def request_token(self, authorization_url, *,
                      state=None,
                      redirect_uri=None,
                      requested_scopes=None,
                      store_token=True,
                      **kwargs):
        """ Authenticates for the specified url and gets the token, save the
        token for future based if requested

        :param str or None authorization_url: url given by the authorization flow
        :param str state: session-state identifier for web-flows
        :param str redirect_uri: callback url for web-flows
        :param lst requested_scopes: a list of scopes to be requested.
         Only used when auth_flow_type is 'credentials'
        :param bool store_token: whether or not to store the token,
         so you don't have to keep opening the auth link and
         authenticating every time
        :param kwargs: allow to pass unused params in conjunction with Connection
        :return: Success/Failure
        :rtype: bool
        """

        redirect_uri = redirect_uri or self.oauth_redirect_url

        # Allow token scope to not match requested scope.
        # (Other auth libraries allow this, but Requests-OAuthlib
        # raises exception on scope mismatch by default.)
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'

        scopes = requested_scopes or self.scopes

        if self.session is None:
            if self.auth_flow_type in ('authorization', 'public'):
                self.session = self.get_session(state=state,
                                                redirect_uri=redirect_uri)
            elif self.auth_flow_type in ('credentials', 'certificate', 'password'):
                self.session = self.get_session(scopes=scopes)
            else:
                raise ValueError('"auth_flow_type" must be "authorization", "public", "credentials", "password",'
                                 ' or "certificate"')

        try:
            if self.auth_flow_type == 'authorization':
                self.token_backend.token = Token(self.session.fetch_token(
                    token_url=self._oauth2_token_url,
                    authorization_response=authorization_url,
                    include_client_id=True,
                    client_secret=self.auth[1],
                    verify=self.verify_ssl))
            elif self.auth_flow_type == 'public':
                self.token_backend.token = Token(self.session.fetch_token(
                    token_url=self._oauth2_token_url,
                    authorization_response=authorization_url,
                    include_client_id=True,
                    verify=self.verify_ssl))
            elif self.auth_flow_type == 'credentials':
                self.token_backend.token = Token(self.session.fetch_token(
                    token_url=self._oauth2_token_url,
                    include_client_id=True,
                    client_secret=self.auth[1],
                    scope=scopes,
                    verify=self.verify_ssl))
            elif self.auth_flow_type == 'password':
                self.token_backend.token = Token(self.session.fetch_token(
                    token_url=self._oauth2_token_url,
                    include_client_id=True,
                    username=self.username,
                    password=self.password,
                    scope=scopes,
                    verify=self.verify_ssl))
            elif self.auth_flow_type == 'certificate':
                self.token_backend.token = Token(self.session.fetch_token(
                    token_url=self._oauth2_token_url,
                    include_client_id=True,
                    client_assertion=self.auth[1],
                    client_assertion_type="urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    scope=scopes,
                    verify=self.verify_ssl))
        except Exception as e:
            log.error('Unable to fetch auth token. Error: {}'.format(str(e)))
            return False

        if store_token:
            self.token_backend.save_token()
        return True

    def get_session(self, *, state=None,
                    redirect_uri=None,
                    load_token=False,
                    scopes=None):
        """ Create a requests Session object

        :param str state: session-state identifier to rebuild OAuth session (CSRF protection)
        :param str redirect_uri: callback URL specified in previous requests
        :param list(str) scopes: list of scopes we require access to
        :param bool load_token: load and ensure token is present
        :return: A ready to use requests session, or a rebuilt in-flow session
        :rtype: OAuth2Session
        """

        redirect_uri = redirect_uri or self.oauth_redirect_url

        client_id = self.auth[0]

        if self.auth_flow_type in ('authorization', 'public'):
            oauth_client = WebApplicationClient(client_id=client_id)
        elif self.auth_flow_type in ('credentials', 'certificate'):
            oauth_client = BackendApplicationClient(client_id=client_id)
        elif self.auth_flow_type == 'password':
            oauth_client = LegacyApplicationClient(client_id=client_id)
        else:
            raise ValueError('"auth_flow_type" must be "authorization", "credentials" or "public"')

        requested_scopes = scopes or self.scopes

        if load_token:
            # gets a fresh token from the store
            token = self.token_backend.get_token()
            if token is None:
                raise RuntimeError('No auth token found. Authentication Flow needed')

            oauth_client.token = token
            if self.auth_flow_type in ('authorization', 'public', 'password'):
                requested_scopes = None  # the scopes are already in the token (Not if type is backend)
            session = OAuth2Session(client_id=client_id,
                                    client=oauth_client,
                                    token=token,
                                    scope=requested_scopes)
        else:
            session = OAuth2Session(client_id=client_id,
                                    client=oauth_client,
                                    state=state,
                                    redirect_uri=redirect_uri,
                                    scope=requested_scopes)

        session.verify = self.verify_ssl
        session.proxies = self.proxy

        if self.request_retries:
            retry = Retry(total=self.request_retries, read=self.request_retries,
                          connect=self.request_retries,
                          backoff_factor=RETRIES_BACKOFF_FACTOR,
                          status_forcelist=RETRIES_STATUS_LIST,
                          respect_retry_after_header=True)
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)

        return session

    def get_naive_session(self):
        """ Creates and returns a naive session """
        naive_session = Session()  # requests Session object
        naive_session.proxies = self.proxy
        naive_session.verify = self.verify_ssl

        if self.request_retries:
            retry = Retry(total=self.request_retries, read=self.request_retries,
                          connect=self.request_retries,
                          backoff_factor=RETRIES_BACKOFF_FACTOR,
                          status_forcelist=RETRIES_STATUS_LIST)
            adapter = HTTPAdapter(max_retries=retry)
            naive_session.mount('http://', adapter)
            naive_session.mount('https://', adapter)

        return naive_session

    def refresh_token(self):
        """
        Refresh the OAuth authorization token.
        This will be called automatically when the access token
         expires, however, you can manually call this method to
         request a new refresh token.
        :return bool: Success / Failure
        """
        if self.session is None:
            self.session = self.get_session(load_token=True)

        token = self.token_backend.token
        if not token:
            raise RuntimeError('Token not found.')

        if token.is_long_lived or self.auth_flow_type == 'credentials':
            log.debug('Refreshing token')
            if self.auth_flow_type == 'authorization':
                client_id, client_secret = self.auth
                self.token_backend.token = Token(
                    self.session.refresh_token(
                        self._oauth2_token_url,
                        client_id=client_id,
                        client_secret=client_secret,
                        verify=self.verify_ssl)
                )
            elif self.auth_flow_type in ('public', 'password'):
                client_id = self.auth[0]
                self.token_backend.token = Token(
                    self.session.refresh_token(
                        self._oauth2_token_url,
                        client_id=client_id,
                        verify=self.verify_ssl)
                )
            elif self.auth_flow_type in ('credentials', 'certificate'):
                if self.request_token(None, store_token=False) is False:
                    log.error('Refresh for Client Credentials Grant Flow failed.')
                    return False
            log.debug('New oauth token fetched by refresh method')
        else:
            log.error('You can not refresh an access token that has no "refresh_token" available.'
                      'Include "offline_access" scope when authenticating to get a "refresh_token"')
            return False

        if self.store_token:
            self.token_backend.save_token()
        return True

    def _check_delay(self):
        """ Checks if a delay is needed between requests and sleeps if True """
        if self._previous_request_at:
            dif = round(time.time() - self._previous_request_at,
                        2) * 1000  # difference in milliseconds
            if dif < self.requests_delay:
                sleep_for = (self.requests_delay - dif)
                log.debug('Sleeping for {} milliseconds'.format(sleep_for))
                time.sleep(sleep_for / 1000)  # sleep needs seconds
        self._previous_request_at = time.time()

    def _internal_request(self, request_obj, url, method, **kwargs):
        """ Internal handling of requests. Handles Exceptions.

        :param request_obj: a requests session.
        :param str url: url to send request to
        :param str method: type of request (get/put/post/patch/delete)
        :param kwargs: extra params to send to the request api
        :return: Response of the request
        :rtype: requests.Response
        """
        method = method.lower()
        if method not in self._allowed_methods:
            raise ValueError('Method must be one of: {}'.format(self._allowed_methods))

        if 'headers' not in kwargs:
            kwargs['headers'] = {**self.default_headers}
        else:
            for key, value in self.default_headers.items():
                if key not in kwargs['headers']:
                    kwargs['headers'][key] = value
                elif key == 'Prefer' and key in kwargs['headers']:
                    kwargs['headers'][key] = "{}, {}".format(kwargs['headers'][key], value)

        if method == 'get':
            kwargs.setdefault('allow_redirects', True)
        elif method in ['post', 'put', 'patch']:
            if kwargs.get('headers') is not None and kwargs['headers'].get(
                    'Content-type') is None:
                kwargs['headers']['Content-type'] = 'application/json'
            if 'data' in kwargs and kwargs['data'] is not None and kwargs['headers'].get(
                    'Content-type') == 'application/json':
                kwargs['data'] = json.dumps(kwargs['data'], cls=self.json_encoder)  # convert to json

        if self.timeout is not None:
            kwargs['timeout'] = self.timeout

        kwargs.setdefault("verify", self.verify_ssl)

        request_done = False
        token_refreshed = False

        while not request_done:
            self._check_delay()  # sleeps if needed
            try:
                log.debug('Requesting ({}) URL: {}'.format(method.upper(), url))
                log.debug('Request parameters: {}'.format(kwargs))
                # auto_retry will occur inside this function call if enabled
                response = request_obj.request(method, url, **kwargs)
                response.raise_for_status()  # raise 4XX and 5XX error codes.
                log.debug('Received response ({}) from URL {}'.format(
                    response.status_code, response.url))
                request_done = True
                return response
            except TokenExpiredError as e:
                # Token has expired, try to refresh the token and try again on the next loop
                log.debug('Oauth Token is expired')
                if self.token_backend.token.is_long_lived is False and self.auth_flow_type == 'authorization':
                    raise e
                if token_refreshed:
                    # Refresh token done but still TokenExpiredError raise
                    raise RuntimeError('Token Refresh Operation not working')
                should_rt = self.token_backend.should_refresh_token(self)
                if should_rt is True:
                    # The backend has checked that we can refresh the token
                    if self.refresh_token() is False:
                        raise RuntimeError('Token Refresh Operation not working')
                    token_refreshed = True
                elif should_rt is False:
                    # the token was refreshed by another instance and updated into
                    # this instance, so: update the session token and
                    # go back to the loop and try the request again.
                    request_obj.token = self.token_backend.token
                else:
                    # the refresh was performed by the tokend backend.
                    token_refreshed = True

            except (ConnectionError, ProxyError, SSLError, Timeout) as e:
                # We couldn't connect to the target url, raise error
                log.debug('Connection Error calling: {}.{}'
                          ''.format(url, ('Using proxy: {}'.format(self.proxy)
                                          if self.proxy else '')))
                raise e  # re-raise exception
            except HTTPError as e:
                # Server response with 4XX or 5XX error status codes

                # try to extract the error message:
                try:
                    error = response.json()
                    error_message = error.get('error', {}).get('message', '')
                    error_code = (
                        error.get("error", {}).get("innerError", {}).get("code", "")
                    )
                except ValueError:
                    error_message = ''
                    error_code = ''

                status_code = int(e.response.status_code / 100)
                if status_code == 4:
                    # Client Error
                    # Logged as error. Could be a library error or Api changes
                    log.error(
                        "Client Error: {} | Error Message: {} | Error Code: {}".format(
                            str(e), error_message, error_code
                        )
                    )
                else:
                    # Server Error
                    log.debug('Server Error: {}'.format(str(e)))
                if self.raise_http_errors:
                    if error_message:
                        raise HTTPError('{} | Error Message: {}'.format(e.args[0], error_message),
                                        response=response) from None
                    else:
                        raise e
                else:
                    return e.response
            except RequestException as e:
                # catch any other exception raised by requests
                log.debug('Request Exception: {}'.format(str(e)))
                raise e

    def naive_request(self, url, method, **kwargs):
        """ Makes a request to url using an without oauth authorization
        session, but through a normal session

        :param str url: url to send request to
        :param str method: type of request (get/put/post/patch/delete)
        :param kwargs: extra params to send to the request api
        :return: Response of the request
        :rtype: requests.Response
        """
        if self.naive_session is None:
            # lazy creation of a naive session
            self.naive_session = self.get_naive_session()
        return self._internal_request(self.naive_session, url, method, **kwargs)

    def oauth_request(self, url, method, **kwargs):
        """ Makes a request to url using an oauth session

        :param str url: url to send request to
        :param str method: type of request (get/put/post/patch/delete)
        :param kwargs: extra params to send to the request api
        :return: Response of the request
        :rtype: requests.Response
        """
        # oauth authentication
        if self.session is None:
            self.session = self.get_session(load_token=True)

        return self._internal_request(self.session, url, method, **kwargs)

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

    def __del__(self):
        """
        Clear the session by closing it
        This should be called manually by the user "del account.con"
        There is no guarantee that this method will be called by the garbage collection
        But this is not an issue because this connections will be automatically closed.
        """
        if hasattr(self, 'session') and self.session is not None:
            self.session.close()


def oauth_authentication_flow(client_id, client_secret, scopes=None,
                              protocol=None, **kwargs):
    """ A helper method to perform the OAuth2 authentication flow.
    Authenticate and get the oauth token

    :param str client_id: the client_id
    :param str client_secret: the client_secret
    :param list[str] scopes: a list of protocol user scopes to be converted
     by the protocol or raw scopes
    :param Protocol protocol: the protocol to be used.
     Defaults to MSGraphProtocol
    :param kwargs: other configuration to be passed to the Connection instance,
     connection.get_authorization_url or connection.request_token
    :return: Success or Failure
    :rtype: bool
    """

    credentials = (client_id, client_secret)

    protocol = protocol or MSGraphProtocol()

    con = Connection(credentials, scopes=protocol.get_scopes_for(scopes),
                     **kwargs)

    consent_url, _ = con.get_authorization_url(**kwargs)

    print('Visit the following url to give consent:')
    print(consent_url)

    token_url = input('Paste the authenticated url here:\n')

    if token_url:
        result = con.request_token(token_url, **kwargs)  # no need to pass state as the session is the same
        if result:
            print('Authentication Flow Completed. Oauth Access Token Stored. '
                  'You can now use the API.')
        else:
            print('Something go wrong. Please try again.')

        return bool(result)
    else:
        print('Authentication Flow aborted.')
        return False
