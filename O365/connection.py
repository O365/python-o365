import logging
import json
import os
from pathlib import Path
from enum import Enum

from stringcase import pascalcase, camelcase
import requests
from oauthlib.oauth2 import TokenExpiredError
from requests_oauthlib import OAuth2Session

from O365.utils import ME_RESOURCE

log = logging.getLogger(__name__)

O365_API_VERSION = 'v1.0'  # v2.0 does not allow basic auth
GRAPH_API_VERSION = 'v1.0'
OAUTH_REDIRECT_URL = 'https://outlook.office365.com/owa/'

SCOPES_FOR = {
    'basic': ['offline_access', 'https://graph.microsoft.com/User.Read'],
    'mailbox': ['https://graph.microsoft.com/Mail.Read'],
    'mailbox_shared': ['https://graph.microsoft.com/Mail.Read.Shared'],
    'message_send': ['https://graph.microsoft.com/Mail.Send'],
    'message_send_shared': ['https://graph.microsoft.com/Mail.Send.Shared'],
    'message_all': ['https://graph.microsoft.com/Mail.ReadWrite', 'https://graph.microsoft.com/Mail.Send'],
    'message_all_shared': ['https://graph.microsoft.com/Mail.ReadWrite.Shared',
                           'https://graph.microsoft.com/Mail.Send.Shared'],
    'address_book': ['https://graph.microsoft.com/Contacts.Read'],
    'address_book_shared': ['https://graph.microsoft.com/Contacts.Read.Shared'],
    'address_book_all': ['https://graph.microsoft.com/Contacts.ReadWrite'],
    'address_book_all_shared': ['https://graph.microsoft.com/Contacts.ReadWrite.Shared'],
    'calendar': ['https://graph.microsoft.com/Calendars.ReadWrite'],
    'users': ['https://graph.microsoft.com/User.ReadBasic.All']
}


class AUTH_METHOD(Enum):
    BASIC = 'basic'
    OAUTH = 'oauth'


def get_scopes_for(app_parts=None):
    """ Returns a list of scopes needed for all the app_parts
    :param app_parts: a list of
    """
    if app_parts is None:
        app_parts = [app_part for app_part in SCOPES_FOR]
    elif isinstance(app_parts, str):
        app_parts = [app_parts]

    if not isinstance(app_parts, (list, tuple)):
        raise ValueError('app_parts must be a list or a tuple of strings')

    return list({scope for ap in (list(app_parts) + ['basic']) for scope in SCOPES_FOR.get(ap, [ap])})


class Protocol:
    """ Base class for all protocols """

    _cloud_data_key = '__cloud_data__'  # wrapps cloud data with this dict key

    def __init__(self, *, protocol_url=None, api_version=None, default_resource=ME_RESOURCE, casing_function=None):
        """
        :param protocol_url: the base url used to comunicate with the server
        :param api_version: the api version
        :param default_resource: the default resource to use when there's no other option
        :param casing_function: the casing transform function to be used on api keywords
        """
        if protocol_url is None or api_version is None:
            raise ValueError('Must provide valid protocol_url and api_version values')
        self.protocol_url = protocol_url
        self.api_version = api_version
        self.service_url = '{}{}/'.format(protocol_url, api_version)
        self.default_resource = default_resource
        self.use_default_casing = True if casing_function is None else False  # if true just returns the key without transform
        self.casing_function = casing_function or camelcase
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


class MSGraphProtocol(Protocol):
    """ A Microsoft Graph Protocol Implementation """

    _protocol_url = 'https://graph.microsoft.com/'

    def __init__(self, api_version='v1.0', default_resource=ME_RESOURCE):
        super().__init__(protocol_url=self._protocol_url, default_resource=default_resource,
                         api_version=api_version, casing_function=camelcase)

        self.keyword_data_store['message_type'] = 'microsoft.graph.message'
        self.keyword_data_store['file_attachment_type'] = '#microsoft.graph.fileAttachment'
        self.keyword_data_store['item_attachment_type'] = '#microsoft.graph.itemAttachment'
        self.max_top_value = 999  # Max $top parameter value


class MSOffice365Protocol(Protocol):
    """ A Microsoft Office 365 Protocol Implementation """

    # _protocol_url = 'https://outlook.office365.com/api/'
    _protocol_url = 'https://outlook.office.com/api/'

    def __init__(self, api_version='v1.0', default_resource=ME_RESOURCE):
        super().__init__(protocol_url=self._protocol_url, default_resource=default_resource,
                         api_version=api_version, casing_function=pascalcase)

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

    def __init__(self, credentials, *, auth_method=AUTH_METHOD.OAUTH, scopes=None,
                 proxy_server=None, proxy_port=8080, proxy_username=None, proxy_password=None):
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
            self.scopes = get_scopes_for(scopes)  # defaults to full scopes spectrum
            self.oauth = None
            self.store_token = True
            self.token_path = self._default_token_path
            self.token = None
        else:
            raise ValueError("Auth Method must be 'basic' or 'oauth'")

        self.proxy = None
        self.set_proxy(proxy_server, proxy_port, proxy_username, proxy_password)

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

    def get_authorization_url(self, requested_scopes=None):
        """
        Inicialices the oauth authorization flow, getting the authorization url that the user must approve.
        This is a two step process, first call this function. Then get the url result from the user and then
        call 'request_token' to get and store the access token.
        """
        if self.auth_method is AUTH_METHOD.BASIC:
            raise RuntimeError('Method not allowed using basic authentication')

        client_id, client_secret = self.auth

        if requested_scopes:
            scopes = get_scopes_for(requested_scopes)
        elif self.scopes is not None:
            scopes = self.scopes
        else:
            scopes = get_scopes_for()

        self.oauth = oauth = OAuth2Session(client_id=client_id, redirect_uri=OAUTH_REDIRECT_URL, scope=scopes)

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

        if self.oauth is None:
            raise RuntimeError("Fist call 'get_authorization_url' to generate a valid oauth object")

        _, client_secret = self.auth

        # Allow token scope to not match requested scope. (Other auth libraries allow
        # this, but Requests-OAuthlib raises exception on scope mismatch by default.)
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'

        try:
            self.token = self.oauth.fetch_token(token_url=self._oauth2_token_url,
                                                authorization_response=authorizated_url,
                                                client_secret=client_secret, proxies=self.proxy)
        except Exception as e:
            log.error('Unable to fetch auth token. Error: {}'.format(str(e)))
            return None

        if token_path:
            self.token_path = token_path
        self.store_token = store_token
        if self.store_token:
            self._save_token(self.token, self.token_path)

        return True

    def oauth2(self, token_path=None):
        """ Create a valid oauth session with the stored token

        :param token_path: full path to where the token should be load from
        """
        if self.auth_method is AUTH_METHOD.BASIC:
            raise RuntimeError('Method not allowed using basic authentication')

        if self.token is None:
            self.token = self._load_token(token_path)

        if self.token:
            client_id, _ = self.auth
            self.oauth = OAuth2Session(client_id=client_id, token=self.token)
        else:
            raise RuntimeError('No auth token found. Authentication Flow needed')

    def refresh_token(self):
        """ Gets another token """

        if self.auth_method is AUTH_METHOD.BASIC:
            raise RuntimeError('Method not allowed using basic authentication')

        client_id, client_secret = self.auth
        self.token = token = self.oauth.refresh_token(self._oauth2_token_url, client_id=client_id,
                                                      client_secret=client_secret, proxies=self.proxy)
        if self.store_token:
            self._save_token(token)

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

        if self.proxy:
            kwargs['proxies'] = self.proxy

        log.info('Requesting URL: {}'.format(url))

        if self.auth_method is AUTH_METHOD.BASIC:
            # basic authentication
            kwargs['auth'] = self.auth
            response = requests.request(method, url, **kwargs)
        else:
            # oauth2 authentication
            if not self.oauth:
                self.oauth2()
            try:
                response = self.oauth.request(method, url, **kwargs)
            except TokenExpiredError:
                log.info('Token is expired, fetching a new token')
                self.refresh_token()
                log.info('New token fetched')
                response = self.oauth.request(method, url, **kwargs)

        log.info('Received response from URL {}'.format(response.url))

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
