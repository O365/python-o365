import json
import logging
import time
from typing import Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse

from msal import ConfidentialClientApplication, PublicClientApplication
from requests import Response, Session
from requests.adapters import HTTPAdapter
from requests.exceptions import (
    ConnectionError,
    HTTPError,
    ProxyError,
    RequestException,
    SSLError,
    Timeout,
)

# Dynamic loading of module Retry by requests.packages
# noinspection PyUnresolvedReferences
from requests.packages.urllib3.util.retry import Retry
from tzlocal import get_localzone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .utils import (
    ME_RESOURCE,
    BaseTokenBackend,
    FileSystemTokenBackend,
    get_windows_tz,
    to_camel_case,
    to_pascal_case,
    to_snake_case,
)

log = logging.getLogger(__name__)

O365_API_VERSION = 'v2.0'
GRAPH_API_VERSION = 'v1.0'
OAUTH_REDIRECT_URL = 'https://login.microsoftonline.com/common/oauth2/nativeclient'

RETRIES_STATUS_LIST = (
    429,  # Status code for TooManyRequests
    500, 502, 503, 504  # Server errors
)
RETRIES_BACKOFF_FACTOR = 0.5

DEFAULT_SCOPES = {
    # wrap any scope in a 1 element tuple to avoid prefixing
    'basic': ['User.Read'],
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

MsalClientApplication = Union[PublicClientApplication, ConfidentialClientApplication]


class TokenExpiredError(HTTPError):
    pass


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
        self.service_url: str = f'{protocol_url}{api_version}/'
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
    def timezone(self) -> ZoneInfo:
        return self._timezone

    @timezone.setter
    def timezone(self, timezone: Union[str, ZoneInfo]) -> None:
        self._update_timezone(timezone)

    def _update_timezone(self, timezone: Union[str, ZoneInfo]) -> None:
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

    def get_service_keyword(self, keyword: str) -> Optional[str]:
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
            for scope in self._oauth_scopes.get(app_part, [app_part]):
                scopes.add(self.prefix_scope(scope))

        return list(scopes)

    def prefix_scope(self, scope: str) -> str:
        """ Inserts the protocol scope prefix if required"""
        if self.protocol_scope_prefix:
            if not scope.startswith(self.protocol_scope_prefix):
                return f'{self.protocol_scope_prefix}{scope}'
        return scope


class MSGraphProtocol(Protocol):
    """ A Microsoft Graph Protocol Implementation
    https://docs.microsoft.com/en-us/outlook/rest/compare-graph-outlook
    """

    _protocol_url = 'https://graph.microsoft.com/'
    _oauth_scope_prefix = 'https://graph.microsoft.com/'
    _oauth_scopes = DEFAULT_SCOPES

    def __init__(self, api_version='v1.0', default_resource=None, **kwargs):
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
    def timezone(self, timezone: Union[str, ZoneInfo]) -> None:
        super()._update_timezone(timezone)
        self.keyword_data_store['prefer_timezone_header'] = f'outlook.timezone="{get_windows_tz(self._timezone)}"'


class MSOffice365Protocol(Protocol):
    """ A Microsoft Office 365 Protocol Implementation
    https://docs.microsoft.com/en-us/outlook/rest/compare-graph-outlook
    """

    _protocol_url = 'https://outlook.office.com/api/'
    _oauth_scope_prefix = 'https://outlook.office.com/'
    _oauth_scopes = DEFAULT_SCOPES

    def __init__(self, api_version='v2.0', default_resource=None, **kwargs):
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
    def timezone(self, timezone: Union[str, ZoneInfo]) -> None:
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

    def __init__(self, api_version='v1.0', default_resource=None, environment=None, **kwargs):
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

        self._protocol_url = f"{self._protocol_url}v{_version}{_environment}/api/"

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
    def timezone(self, timezone: Union[str, ZoneInfo]) -> None:
        super()._update_timezone(timezone)
        self.keyword_data_store['prefer_timezone_header'] = f'outlook.timezone="{get_windows_tz(self._timezone)}"'


class Connection:
    """ Handles all communication (requests) between the app and the server """

    _allowed_methods = ['get', 'post', 'put', 'patch', 'delete']

    def __init__(self, credentials: Tuple, *,
                 proxy_server: Optional[str] = None, proxy_port: Optional[int] = 8080,
                 proxy_username: Optional[str] = None, proxy_password: Optional[str] = None,
                 proxy_http_only: bool = False, requests_delay: int = 200, raise_http_errors: bool = True,
                 request_retries: int = 3, token_backend: Optional[BaseTokenBackend] = None,
                 tenant_id: str = 'common', auth_flow_type: str = 'authorization',
                 username: Optional[str] = None, password: Optional[str] = None,
                 timeout: Optional[int] = None, json_encoder: Optional[json.JSONEncoder] = None,
                 verify_ssl: bool = True,
                 default_headers: dict = None,
                 store_token_after_refresh: bool = True,
                 **kwargs):
        """Creates an API connection object

        :param tuple credentials: a tuple of (client_id, client_secret)
         Generate client_id and client_secret in https://entra.microsoft.com/
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

            - 'authorization': 2-step web style grant flow using an authentication url
            - 'public': 2-step web style grant flow using an authentication url for public apps where
                client secret cannot be secured
            - 'credentials': also called client credentials grant flow using only the client id and secret.
                The secret can be certificate based authentication
            - 'password': using the username and password. Not recommended

        :param str username: The username the credentials will be taken from in the token backend.
            If None, the username will be the first one found in the token backend.
            The user's email address to provide in case of auth_flow_type == 'password'
        :param str password: The user's password to provide in case of auth_flow_type == 'password'
        :param float or tuple timeout: How long to wait for the server to send
            data before giving up, as a float, or a tuple (connect timeout, read timeout)
        :param JSONEncoder json_encoder: The JSONEncoder to use during the JSON serialization on the request.
        :param bool verify_ssl: set the verify flag on the requests library
        :param bool store_token_after_refresh: if after a token refresh the token backend should call save_token
        :param dict kwargs: any extra params passed to Connection
        :raises ValueError: if credentials is not tuple of (client_id, client_secret)

        """

        if auth_flow_type in (
            "public",
            "password",
        ):  # allow client id only for public or password flow
            if isinstance(credentials, str):
                credentials = (credentials,)
            if (
                not isinstance(credentials, tuple)
                or len(credentials) != 1
                or (not credentials[0])
            ):
                raise ValueError(
                    "Provide client id only for public or password flow credentials"
                )
        else:
            if (
                not isinstance(credentials, tuple)
                or len(credentials) != 2
                or (not credentials[0] and not credentials[1])
            ):
                raise ValueError("Provide valid auth credentials")

        self._auth_flow_type = (
            auth_flow_type  # 'authorization', 'credentials', 'password', or 'public'
        )
        if auth_flow_type in ("credentials", "password") and tenant_id == "common":
            raise ValueError(
                'When using the "credentials" or "password" auth_flow, the "tenant_id" must be set'
            )

        self.auth: Tuple = credentials
        self.tenant_id: str = tenant_id

        self.default_headers: Dict = default_headers or dict()
        self.store_token_after_refresh: bool = store_token_after_refresh

        token_backend = token_backend or FileSystemTokenBackend(**kwargs)
        if not isinstance(token_backend, BaseTokenBackend):
            raise ValueError(
                '"token_backend" must be an instance of a subclass of BaseTokenBackend'
            )
        self.token_backend: BaseTokenBackend = token_backend
        self.session: Optional[Session] = None

        self.password: Optional[str] = password

        self._username: Optional[str] = None
        self.username: Optional[str] = username  # validate input

        self.proxy: Dict = {}
        self.set_proxy(
            proxy_server, proxy_port, proxy_username, proxy_password, proxy_http_only
        )

        self.requests_delay: int = requests_delay or 0
        self._previous_request_at: Optional[float] = None  # store previous request time
        self.raise_http_errors: bool = raise_http_errors
        self.request_retries: int = request_retries
        self.timeout: int = timeout
        self.verify_ssl: bool = verify_ssl
        self.json_encoder: Optional[json.JSONEncoder] = json_encoder

        self.naive_session: Optional[Session] = (
            None  # lazy loaded: holds a requests Session object
        )

        self._msal_client: Optional[MsalClientApplication] = (
            None  # store the msal client
        )
        self._msal_authority: str = f"https://login.microsoftonline.com/{tenant_id}"
        self.oauth_redirect_url: str = (
            "https://login.microsoftonline.com/common/oauth2/nativeclient"
        )

        # In the event of a response that returned 401 unauthorised this will flag between requests
        # that this 401 can be a token expired error. MsGraph is returning 401 when the access token
        # has expired. We can not distinguish between a real 401 or token expired 401. So in the event
        # of a 401 http error we will first try to refresh the token, set this flag to True and then
        # re-run the request. If the 401 goes away we will then set this flag to false. If it keeps the
        # 401 then we will raise the error.
        self._token_expired_flag: bool = False

    @property
    def auth_flow_type(self) -> str:
        return self._auth_flow_type

    def _set_username_from_token_backend(
        self, *, home_account_id: Optional[str] = None
    ) -> None:
        """
        If token data is present, this will try to set the username. If home_account_id is not provided this will try
        to set the username from the first account found on the token_backend.
        """
        account_info = self.token_backend.get_account(home_account_id=home_account_id)
        if account_info:
            self.username = account_info.get("username")

    @property
    def username(self) -> Optional[str]:
        """
        Returns the username in use
        If username is not set this will try to set the username to the first account found
        from the token_backend.
        """
        if not self._username:
            self._set_username_from_token_backend()
        return self._username

    @username.setter
    def username(self, username: Optional[str]) -> None:
        if self._username == username:
            return
        log.debug(f"Current username changed from {self._username} to {username}")
        self._username = username

        # if the user is changed and a valid session is set we must change the auth token in the session
        if self.session is not None:
            access_token = self.token_backend.get_access_token(username=username)
            if access_token is not None:
                self.session.headers.update({"Authorization": f"Bearer {access_token}"})
            else:
                # if we can't find an access token for the current user, then remove the auth header from the session
                if "Authorization" in self.session.headers:
                    del self.session.headers["Authorization"]

    def set_proxy(
        self,
        proxy_server: str,
        proxy_port: int,
        proxy_username: str,
        proxy_password: str,
        proxy_http_only: bool,
    ) -> None:
        """Sets a proxy on the Session

        :param str proxy_server: the proxy server
        :param int proxy_port: the proxy port, defaults to 8080
        :param str proxy_username: the proxy username
        :param str proxy_password: the proxy password
        :param bool proxy_http_only: if the proxy should only be used for http
        """
        if proxy_server and proxy_port:
            if proxy_username and proxy_password:
                proxy_uri = (
                    f"{proxy_username}:{proxy_password}@{proxy_server}:{proxy_port}"
                )
            else:
                proxy_uri = f"{proxy_server}:{proxy_port}"

            if proxy_http_only is False:
                self.proxy = {
                    "http": f"http://{proxy_uri}",
                    "https": f"https://{proxy_uri}",
                }
            else:
                self.proxy = {
                    "http": f"http://{proxy_uri}",
                    "https": f"http://{proxy_uri}",
                }

    @property
    def msal_client(self) -> MsalClientApplication:
        """Returns the msal client or creates it if it's not already done"""
        if self._msal_client is None:
            if self.auth_flow_type in ("public", "password"):
                client = PublicClientApplication(
                    client_id=self.auth[0],
                    authority=self._msal_authority,
                    token_cache=self.token_backend,
                )
            elif self.auth_flow_type in ("authorization", "credentials"):
                client = ConfidentialClientApplication(
                    client_id=self.auth[0],
                    client_credential=self.auth[1],
                    authority=self._msal_authority,
                    token_cache=self.token_backend,
                )
            else:
                raise ValueError(
                    '"auth_flow_type" must be "authorization", "public" or "credentials"'
                )
            self._msal_client = client
        return self._msal_client

    def get_authorization_url(
        self, requested_scopes: List[str], redirect_uri: Optional[str] = None, **kwargs
    ) -> Tuple[str, dict]:
        """Initializes the oauth authorization flow, getting the
        authorization url that the user must approve.

        :param list[str] requested_scopes: list of scopes to request access for
        :param str redirect_uri: redirect url configured in registered app
        :param kwargs: allow to pass unused params in conjunction with Connection
        :return: authorization url and the flow dict
        """

        redirect_uri = redirect_uri or self.oauth_redirect_url

        if self.auth_flow_type not in ("authorization", "public"):
            raise RuntimeError(
                'This method is only valid for auth flow type "authorization" and "public"'
            )

        if not requested_scopes:
            raise ValueError("Must provide at least one scope")

        flow = self.msal_client.initiate_auth_code_flow(
            scopes=requested_scopes, redirect_uri=redirect_uri
        )

        return flow.get("auth_uri"), flow

    def request_token(
        self,
        authorization_url: Optional[str],
        *,
        flow: Optional[dict] = None,
        requested_scopes: Optional[List[str]] = None,
        store_token: bool = True,
        **kwargs,
    ) -> bool:
        """Authenticates for the specified url and gets the oauth token data. Saves the
        token in the backend if store_token is True. This will replace any other tokens stored
        for the same username and scopes requested.
        If the token data is successfully requested, then this method will try to set the username if
        not previously set.

        :param str or None authorization_url: url given by the authorization flow or None if it's client credentials
        :param dict flow: dict object holding the data used in get_authorization_url
        :param list[str] requested_scopes: list of scopes to request access for
        :param bool store_token: True to store the token in the token backend,
         so you don't have to keep opening the auth link and
         authenticating every time
        :param kwargs: allow to pass unused params in conjunction with Connection
        :return: Success/Failure
        :rtype: bool
        """

        if self.auth_flow_type in ("authorization", "public"):
            if not authorization_url:
                raise ValueError(
                    f"Authorization url not provided for oauth flow {self.auth_flow_type}"
                )
            # parse the authorization url to obtain the query string params
            parsed = urlparse(authorization_url)
            query_params_dict = {k: v[0] for k, v in parse_qs(parsed.query).items()}

            result = self.msal_client.acquire_token_by_auth_code_flow(
                flow, auth_response=query_params_dict
            )

        elif self.auth_flow_type == "credentials":
            if requested_scopes is None:
                raise ValueError(
                    f'Auth flow type "credentials" needs the default scope for a resource.'
                    f" For example: https://graph.microsoft.com/.default"
                )

            result = self.msal_client.acquire_token_for_client(scopes=requested_scopes)

        elif self.auth_flow_type == "password":
            if not requested_scopes:
                raise ValueError(
                    'Auth flow type "password" requires scopes and none where given'
                )
            result = self.msal_client.acquire_token_by_username_password(
                username=self.username, password=self.password, scopes=requested_scopes
            )
        else:
            raise ValueError(
                '"auth_flow_type" must be "authorization", "password", "public" or "credentials"'
            )

        if "access_token" not in result:
            log.error(
                f'Unable to fetch auth token. Error: {result.get("error")} | Description: {result.get("error_description")}'
            )
            return False
        else:
            # extract from the result the home_account_id used in the authentication to retrieve its username
            id_token_claims = result.get("id_token_claims")
            if id_token_claims:
                oid = id_token_claims.get("oid")
                tid = id_token_claims.get("tid")
                if oid and tid:
                    home_account_id = f"{oid}.{tid}"
                    # the next call will change the current username, updating the session headers if session exists
                    self._set_username_from_token_backend(
                        home_account_id=home_account_id
                    )

            # Update the session headers if the session exists
            if self.session is not None:
                access_token = result["access_token"]
                self.session.headers.update({"Authorization": f"Bearer {access_token}"})

        if store_token:
            self.token_backend.save_token()
        return True

    def load_token_from_backend(self) -> bool:
        """Loads the token from the backend and tries to set the self.username if it's not set"""
        if self.token_backend.load_token():
            if self._username is None:
                account_info = self.token_backend.get_account()
                if account_info:
                    self.username = account_info.get("username")
            return True
        return False

    def get_session(self, load_token: bool = False) -> Session:
        """Create a requests Session object with the oauth token attached to it

        :param bool load_token: load the token from the token backend and load the access token into the session auth
        :return: A ready to use requests session with authentication header attached
        :rtype: requests.Session
        """

        if load_token and not self.token_backend.has_data:
            # try to load the token from the token backend
            self.load_token_from_backend()

        token = self.token_backend.get_access_token(username=self.username)
        if token is None:
            raise RuntimeError("No auth token found. Authentication Flow needed")

        session = Session()
        session.headers.update({"Authorization": f'Bearer {token["secret"]}'})
        session.verify = self.verify_ssl
        session.proxies = self.proxy

        if self.request_retries:
            retry = Retry(
                total=self.request_retries,
                read=self.request_retries,
                connect=self.request_retries,
                backoff_factor=RETRIES_BACKOFF_FACTOR,
                status_forcelist=RETRIES_STATUS_LIST,
                respect_retry_after_header=True,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("http://", adapter)
            session.mount("https://", adapter)

        return session

    def get_naive_session(self) -> Session:
        """Creates and returns a naive session"""
        naive_session = Session()  # requests Session object
        naive_session.proxies = self.proxy
        naive_session.verify = self.verify_ssl

        if self.request_retries:
            retry = Retry(
                total=self.request_retries,
                read=self.request_retries,
                connect=self.request_retries,
                backoff_factor=RETRIES_BACKOFF_FACTOR,
                status_forcelist=RETRIES_STATUS_LIST,
            )
            adapter = HTTPAdapter(max_retries=retry)
            naive_session.mount("http://", adapter)
            naive_session.mount("https://", adapter)

        return naive_session

    def refresh_token(self) -> bool:
        """
        Refresh the OAuth authorization token.
        This will be called automatically when the access token
        expires, however, you can manually call this method to
        request a new refresh token.

        :return bool: Success / Failure
        """
        if self.session is None:
            self.session = self.get_session(load_token=True)

        if self.token_backend.get_access_token(username=self.username) is None:
            raise RuntimeError('Access Token not found. You will need to re-authenticate.')

        token_refreshed = False

        if (self.token_backend.token_is_long_lived(username=self.username) or
                self.auth_flow_type == 'credentials'):

            should_rt = self.token_backend.should_refresh_token(self)
            if should_rt is True:
                # The backend has checked that we can refresh the token
                log.debug('Refreshing access token')

                # This will set the connection scopes from the scopes set in the stored token
                scopes = self.token_backend.get_token_scopes(
                    username=self.username,
                    remove_reserved=True
                )

                result = self.msal_client.acquire_token_silent_with_error(
                    scopes=scopes,
                    account=self.msal_client.get_accounts(username=self.username)[0]
                )
                if result is None:
                    raise RuntimeError('There is no access token to refresh')
                elif 'error' in result:
                    raise RuntimeError(f'Refresh token operation failed: {result["error"]}')
                elif 'access_token' in result:
                    # refresh done, update authorization header
                    token_refreshed = True
                    self.session.headers.update({'Authorization': f'Bearer {result["access_token"]}'})
                    log.debug(f'New oauth token fetched by refresh method for username: {self.username}')
            elif should_rt is False:
                # the token was refreshed by another instance and updated into this instance,
                # so: update the session token and retry the request again
                access_token = self.token_backend.get_access_token(username=self.username)
                if access_token:
                    self.session.headers.update({'Authorization': f'Bearer {access_token["secret"]}'})
                else:
                    raise RuntimeError("Can't get access token refreshed by another instance.")
            else:
                # the refresh was performed by the token backend.
                pass
        else:
            log.error('You can not refresh an access token that has no "refresh_token" available.'
                      'Include "offline_access" scope when authenticating to get a "refresh_token"')
            return False

        if token_refreshed and self.store_token_after_refresh:
            self.token_backend.save_token()
        return True

    def _check_delay(self) -> None:
        """ Checks if a delay is needed between requests and sleeps if True """
        if self._previous_request_at:
            dif = round(time.time() - self._previous_request_at,
                        2) * 1000  # difference in milliseconds
            if dif < self.requests_delay:
                sleep_for = (self.requests_delay - dif)
                log.debug(f'Sleeping for {sleep_for} milliseconds')
                time.sleep(sleep_for / 1000)  # sleep needs seconds
        self._previous_request_at = time.time()

    def _internal_request(self, session_obj: Session,
                          url: str, method: str, **kwargs) -> Response:
        """ Internal handling of requests. Handles Exceptions.

        :param session_obj: a requests Session instance.
        :param str url: url to send request to
        :param str method: type of request (get/put/post/patch/delete)
        :param kwargs: extra params to send to the request api
        :return: Response of the request
        :rtype: requests.Response
        """
        method = method.lower()
        if method not in self._allowed_methods:
            raise ValueError(f'Method must be one of: {self._allowed_methods}')

        if 'headers' not in kwargs:
            kwargs['headers'] = {**self.default_headers}
        else:
            for key, value in self.default_headers.items():
                if key not in kwargs['headers']:
                    kwargs['headers'][key] = value
                elif key == 'Prefer' and key in kwargs['headers']:
                    kwargs['headers'][key] = f"{kwargs['headers'][key]}, {value}"

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

        self._check_delay()  # sleeps if needed
        try:
            log.debug(f'Requesting ({method.upper()}) URL: {url}')
            log.debug(f'Request parameters: {kwargs}')
            # auto_retry will occur inside this function call if enabled
            response = session_obj.request(method, url, **kwargs)

            response.raise_for_status()  # raise 4XX and 5XX error codes.
            log.debug(f'Received response ({response.status_code}) from URL {response.url}')
            return response
        except (ConnectionError, ProxyError, SSLError, Timeout) as e:
            # We couldn't connect to the target url, raise error
            log.debug(f'Connection Error calling: {url}.{f"Using proxy {self.proxy}" if self.proxy else ""}')
            raise e  # re-raise exception
        except HTTPError as e:
            # Server response with 4XX or 5XX error status codes
            if e.response.status_code == 401 and self._token_expired_flag is False:
                # This could be a token expired error.
                if self.token_backend.token_is_expired(username=self.username):
                    # Token has expired, try to refresh the token and try again on the next loop
                    # By raising custom exception TokenExpiredError we signal oauth_request to fire a
                    # refresh token operation.
                    log.debug(f'Oauth Token is expired for username: {self.username}')
                    self._token_expired_flag = True
                    raise TokenExpiredError('Oauth Token is expired')

            # try to extract the error message:
            try:
                error = e.response.json()
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
                log.error(f'Client Error: {e} | Error Message: {error_message} | Error Code: {error_code}')
            else:
                # Server Error
                log.debug(f'Server Error: {e}')
            if self.raise_http_errors:
                if error_message:
                    raise HTTPError(f'{e.args[0]} | Error Message: {error_message}', response=e.response) from None
                else:
                    raise e
            else:
                return e.response
        except RequestException as e:
            # catch any other exception raised by requests
            log.debug(f'Request Exception: {e}')
            raise e

    def naive_request(self, url: str, method: str, **kwargs) -> Response:
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

    def oauth_request(self, url: str, method: str, **kwargs) -> Response:
        """ Makes a request to url using an oauth session.
        Raises RuntimeError if the session does not have an Authorization header

        :param str url: url to send request to
        :param str method: type of request (get/put/post/patch/delete)
        :param kwargs: extra params to send to the request api
        :return: Response of the request
        :rtype: requests.Response
        """
        # oauth authentication
        if self.session is None:
            self.session = self.get_session(load_token=True)
        else:
            if self.session.headers.get('Authorization') is None:
                raise RuntimeError(f'No auth token found. Authentication Flow needed for user {self.username}')

        try:
            return self._internal_request(self.session, url, method, **kwargs)
        except TokenExpiredError as e:
            # refresh and try again the request!
            try:
                if self.refresh_token():
                    return self._internal_request(self.session, url, method, **kwargs)
                else:
                    raise e
            finally:
                self._token_expired_flag = False

    def get(self, url: str, params: Optional[dict] = None, **kwargs) -> Response:
        """ Shorthand for self.oauth_request(url, 'get')

        :param str url: url to send get oauth request to
        :param dict params: request parameter to get the service data
        :param kwargs: extra params to send to request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(url, 'get', params=params, **kwargs)

    def post(self, url: str, data: Optional[dict] = None, **kwargs) -> Response:
        """ Shorthand for self.oauth_request(url, 'post')

        :param str url: url to send post oauth request to
        :param dict data: post data to update the service
        :param kwargs: extra params to send to request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(url, 'post', data=data, **kwargs)

    def put(self, url: str, data: Optional[dict] = None, **kwargs) -> Response:
        """ Shorthand for self.oauth_request(url, 'put')

        :param str url: url to send put oauth request to
        :param dict data: put data to update the service
        :param kwargs: extra params to send to request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(url, 'put', data=data, **kwargs)

    def patch(self, url: str, data: Optional[dict] = None, **kwargs) -> Response:
        """ Shorthand for self.oauth_request(url, 'patch')

        :param str url: url to send patch oauth request to
        :param dict data: patch data to update the service
        :param kwargs: extra params to send to request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(url, 'patch', data=data, **kwargs)

    def delete(self, url: str, **kwargs) -> Response:
        """ Shorthand for self.request(url, 'delete')

        :param str url: url to send delete oauth request to
        :param kwargs: extra params to send to request api
        :return: Response of the request
        :rtype: requests.Response
        """
        return self.oauth_request(url, 'delete', **kwargs)

    def __del__(self) -> None:
        """
        Clear the session by closing it
        This should be called manually by the user "del account.con"
        There is no guarantee that this method will be called by the garbage collection
        But this is not an issue because this connections will be automatically closed.
        """
        if hasattr(self, 'session') and self.session is not None:
            self.session.close()
        if hasattr(self, 'naive_session') and self.naive_session is not None:
            self.naive_session.close()


def oauth_authentication_flow(client_id: str, client_secret: str, scopes: List[str] = None,
                              protocol: Optional[Protocol] = None, **kwargs) -> bool:
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

    con = Connection(credentials, **kwargs)

    consent_url, flow = con.get_authorization_url(requested_scopes=protocol.get_scopes_for(scopes), **kwargs)

    print('Visit the following url to give consent:')
    print(consent_url)

    token_url = input('Paste the authenticated url here:\n')

    if token_url:
        result = con.request_token(token_url, flow=flow, **kwargs)
        if result:
            print('Authentication Flow Completed. Oauth Access Token Stored. '
                  'You can now use the API.')
        else:
            print('Something go wrong. Please try again.')

        return result
    else:
        print('Authentication Flow aborted.')
        return False
