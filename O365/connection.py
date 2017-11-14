import requests
import logging

log = logging.getLogger(__name__)


class Connection(object):
    instance = None

    def __new__(cls, *args, **kwargs):
        if not Connection.instance:
            Connection.instance = object.__new__(cls)

        return Connection.instance

    def __init__(self, api_version='1.0'):
        """ Creates a O365 connection object for specified version

        :param api_version: which version of Office 365 rest api to use, only 1.0 supported as of now
        """
        self.api_version = api_version
        self.auth = None
        self.proxy_dict = None

    @staticmethod
    def login(username, password):
        """ Connect to office 365 using specified username and password

        :param username: username to login with
        :param password: password for authentication
        """
        if not Connection.instance:
            Connection()

        Connection.instance.auth = (username, password)
        return Connection.instance

    @staticmethod
    def proxy(url, port, username, password):
        """ Connect to Office 365 though the specified proxy

        :param url: url of the proxy server
        :param port: port to connect to proxy server
        :param username: username for authentication in the proxy server
        :param password: password for the specified username
        """
        if not Connection.instance:
            Connection()

        Connection.instance.proxy_dict = {
            "http": "http://{}:{}@{}:{}".format(username, password, url, port),
            "https": "https://{}:{}@{}:{}".format(username, password, url,
                                                  port),
        }
        return Connection.instance

    @staticmethod
    def get_response(request_url, **kwargs):
        """ Fetches the response for specified url and arguments, adding the auth and proxy information to the url

        :param request_url: url to request
        :param kwargs: any keyword arguments to pass to the requests api
        :return: response object
        """
        if not Connection.instance:
            Connection()

        if not Connection.instance.auth:
            raise RuntimeError('Connection is not configured, please use '
                               '"O365.Connection" to set username and password')
        con_params = {'auth': Connection.instance.auth}
        if Connection.instance.proxy_dict:
            con_params['proxies'] = Connection.instance.proxy_dict
        con_params.update(kwargs)

        log.info('Requesting URL: {}'.format(request_url))
        response = requests.get(request_url, **con_params)
        log.info('Received response from URL {}'.format(response.url))
        return response
