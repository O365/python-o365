import json
import logging
import os
import os.path as path

import requests
from future.utils import with_metaclass
from oauthlib.oauth2 import TokenExpiredError
from requests_oauthlib import OAuth2Session
from builtins import input

from .utils import fluent

log = logging.getLogger(__name__)


class MicroDict(dict):
    """ Dictionary to handle camelCase and PascalCase differences between
    api v1.0 and 2.0
    """

    def __getitem__(self, key):
        result = super(MicroDict, self).get(key[:1].lower() + key[1:], None)
        if result is None:
            result = super(MicroDict, self).get(key[:1].upper() + key[1:])
        if type(result) is dict:
            result = MicroDict(result)
        return result

    def __setitem__(self, key, value):
        if Connection().api_version == "1.0":
            key = key[:1].upper() + key[1:]
        super(MicroDict, self).__setitem__(key, value)

    def __contains__(self, key):
        result = super(MicroDict, self).__contains__(key[:1].lower() + key[1:])
        if not result:
            result = super(MicroDict, self).__contains__(
                key[:1].upper() + key[1:])
        return result


class Singleton(type):
    """ Superclass to help create the singleton pattern """
    _instance = None

    def __call__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instance


# def __new__(cls, *args, **kwargs):
# 	 if not cls._instance:
# 		 cls._instance = object.__new__(cls)
# 	 return cls._instance


_default_token_file = '.o365_token'
_home_path = path.expanduser("~")
default_token_path = path.join(_home_path, _default_token_file)


def _save_token(token, token_path=None):
    """ Save the specified token dictionary to a specified file path

    :param token: token dictionary returned by the oauth token request
    :param token_path: path to where the files is to be saved
    """
    if not token_path:
        token_path = default_token_path

    with open(token_path, 'w') as token_file:
        json.dump(token, token_file, indent=True)


def _load_token(token_path=None):
    """ Save the specified token dictionary to a specified file path

    :param token_path: path to the file with token information saved
    """
    if not token_path:
        token_path = default_token_path

    token = None
    if path.exists(token_path):
        with open(token_path, 'r') as token_file:
            token = json.load(token_file)
    return token


def _delete_token(token_path=None):
    """ Save the specified token dictionary to a specified file path

    :param token_path: path to where the token is saved
    """
    if not token_path:
        token_path = default_token_path

    if path.exists(token_path):
        os.unlink(token_path)


class Connection(with_metaclass(Singleton)):
    """ Create a singleton O365 connection object """
    _oauth2_authorize_url = 'https://login.microsoftonline.com' \
                            '/common/oauth2/v2.0/authorize'
    _oauth2_token_url = 'https://login.microsoftonline.com' \
                        '/common/oauth2/v2.0/token'
    default_headers = {'Content-Type': 'application/json',
                       'Accept': 'text/plain'}

    url_dict = {
        '1.0': 'https://outlook.office365.com/api/v1.0',
        '2.0': 'https://graph.microsoft.com/v1.0'
    }

    scopes = [
        'https://graph.microsoft.com/Mail.ReadWrite',
        'https://graph.microsoft.com/Mail.Send',
        'offline_access'
    ]

    def __init__(self):
        """ Creates a O365 connection object """
        self.api_version = None
        self.auth = None

        self.root_url = None
        self.oauth = None
        self.client_id = None
        self.client_secret = None
        self.token = None
        self.token_path = None
        self.proxy_dict = None

    def is_valid(self):
        """ Check if the connection singleton is initialized or not

        :return: Valid or Not
        :rtype: bool
        """
        valid = False

        if self.api_version == '1.0':
            valid = True if self.auth else False
        elif self.api_version == '2.0':
            valid = True if self.oauth else False

        return valid

    @staticmethod
    @fluent
    def login(username, password):
        """
        .. deprecated:: 0.10.0
            Use :func:`oauth2` instead

        .. note::  Microsoft drops support to basic authentication
         on Nov 1, 2018

        Connect to office 365 using specified username and password

        :param username: username to login with
        :param password: password for authentication
        """
        connection = Connection()

        connection.api_version = '1.0'
        connection.root_url = Connection.url_dict[connection.api_version]
        connection.auth = (username, password)
        return connection

    @staticmethod
    @fluent
    def oauth2(client_id, client_secret, store_token=True, token_path=None):
        """ Connect to office 365 using specified Open Authentication protocol

        :param client_id: application_id generated by
         https://apps.dev.microsoft.com when you register your app
        :param client_secret: secret password key generated for your application
        :param store_token: whether or not to store the token in file system,
         so u don't have to keep opening the auth link and
         authenticating every time
        :param token_path: full path to where the token file should be saved to
        """
        connection = Connection()

        connection.api_version = '2.0'
        connection.root_url = Connection.url_dict[connection.api_version]
        connection.client_id = client_id
        connection.client_secret = client_secret
        connection.token_path = token_path

        if not store_token:
            _delete_token(token_path)

        token = _load_token(token_path)

        if not token:
            connection.oauth = OAuth2Session(
                client_id=client_id,
                redirect_uri='https://outlook.office365.com/owa/',
                scope=Connection.scopes, )
            oauth = connection.oauth
            auth_url, state = oauth.authorization_url(
                url=Connection._oauth2_authorize_url,
                access_type='offline')
            print(
                'Please open {} and authorize the application'.format(auth_url))
            auth_resp = input('Enter the full result url: ')
            os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = 'Y'
            token = oauth.fetch_token(token_url=Connection._oauth2_token_url,
                                      authorization_response=auth_resp,
                                      client_secret=client_secret)
            _save_token(token, token_path)
        else:
            connection.oauth = OAuth2Session(client_id=client_id,
                                             token=token)
        return connection

    @staticmethod
    @fluent
    def proxy(url, port, username, password):
        """ Connect to Office 365 though the specified proxy

        :param url: url of the proxy server
        :param port: port to connect to proxy server
        :param username: username for authentication in the proxy server
        :param password: password for the specified username
        """
        connection = Connection()

        connection.proxy_dict = {
            "http": "http://{}:{}@{}:{}".format(username, password, url, port),
            "https": "https://{}:{}@{}:{}".format(username, password, url,
                                                  port),
        }
        return connection

    @staticmethod
    def get_response(request_url, method='GET', **kwargs):
        """ Fetches the response for specified url and arguments,
        adding the auth and proxy information to the url

        :param request_url: url to request
        :param method: GET or POST or PATCH the request
        :param kwargs: any keyword arguments to pass to the requests api
        :return: json data (for GET), response object (for POST, PATCH)
        :rtype: dict (for GET), Response (for POST, PATCH)
        """
        connection = Connection()

        if method == 'GET':
            if connection.api_version == '1.0':
                process_request = requests.get
            else:
                process_request = connection.oauth.get
        elif method == 'POST':
            if connection.api_version == '1.0':
                process_request = requests.post
            else:
                process_request = connection.oauth.post
        elif method == 'PATCH':
            if connection.api_version == '1.0':
                process_request = requests.patch
            else:
                process_request = connection.oauth.patch
        else:
            raise RuntimeError('Unknown method {}'.format(method))

        if not connection.is_valid():
            raise RuntimeError(
                'Connection is not configured, please use "O365.Connection" '
                'to set username and password or OAuth2 authentication')

        con_params = {}
        if connection.proxy_dict:
            con_params['proxies'] = connection.proxy_dict
        if connection.default_headers:
            con_params['headers'] = connection.default_headers
        con_params.update(kwargs)

        log.debug('Requesting URL: {}'.format(request_url))

        if connection.api_version == '1.0':
            con_params['auth'] = connection.auth
            response = process_request(request_url, **con_params)
        else:
            try:
                response = process_request(request_url, **con_params)
            except TokenExpiredError:
                log.debug('Token is expired, fetching a new token')
                token = connection.oauth.refresh_token(
                    Connection._oauth2_token_url,
                    client_id=connection.client_id,
                    client_secret=connection.client_secret)
                log.debug('New token fetched')
                _save_token(token, connection.token_path)
                response = process_request(request_url, **con_params)

        log.debug('Received response from URL {}'.format(response.url))

        if response.status_code == 401:
            raise RuntimeError('API returned status code 401 Unauthorized, '
                               'check the connection credentials')

        if method == 'GET':
            response_json = response.json(object_pairs_hook=MicroDict)
            if 'value' not in response_json:
                raise RuntimeError('Something went wrong, '
                                   'received an unexpected result \n'
                                   '{}'.format(response_json))

            response_values = response_json['value']
            return response_values
        elif method in ('POST', 'PATCH'):
            return response
