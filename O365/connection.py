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

    def proxy(self, url, port, username, password):
        pass
