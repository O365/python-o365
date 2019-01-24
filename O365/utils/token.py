import logging
import json
import datetime as dt
from pathlib import Path

log = logging.getLogger(__name__)


EXPIRES_ON_THRESHOLD = 2 * 60  # 2 minutes


class Token(dict):
    """ A dict subclass with extra methods to resemble a token """

    @property
    def is_long_lived(self):
        """
        Checks whether this token has a refresh token
        :return bool: True if has a refresh_token
        """
        return 'refresh_token' in self

    @property
    def is_expired(self):
        """
        Checks whether this token is expired
        :return bool: True if the token is expired, False otherwise
        """
        return dt.datetime.now() > self.expiration_datetime

    @property
    def expiration_datetime(self):
        """
        Returns the expiration datetime
        :return datetime: The datetime this token expires
        """
        expires_at = self.get('expires_at')
        if expires_at is None:
            # consider it is expired
            return dt.datetime.now() - dt.timedelta(seconds=10)
        expires_on = dt.datetime.fromtimestamp(expires_at) - dt.timedelta(seconds=EXPIRES_ON_THRESHOLD)
        if self.is_long_lived:
            expires_on = expires_on + dt.timedelta(days=90)
        return expires_on


class BaseTokenBackend:
    """ A base token storage class """

    serializer = json  # The default serializer is json
    token_constructor = Token  # the default token constructor

    def __init__(self):
        self._token = None

    @property
    def token(self):
        """ The stored Token dict """
        return self._token

    @token.setter
    def token(self, value):
        """ Setter to convert any token dict into Token instance """
        if value and not isinstance(value, Token):
            value = Token(value)
        self._token = value

    def get_token(self):
        """ Abstract method that will retrieve the oauth token """
        raise NotImplementedError()

    def save_token(self):
        """ Abstract method that will save the oauth token """
        raise NotImplementedError()


class FileSystemTokenBackend(BaseTokenBackend):
    """ A token backend based on files on the filesystem """

    def __init__(self, token_path=None, token_filename=None):
        super().__init__()
        if not isinstance(token_path, Path):
            token_path = Path(token_path) if token_path else Path()
        token_filename = token_filename or 'o365_token.txt'
        self.token_path = token_path / token_filename

    def get_token(self):
        """
        Retrieves the token from the File System
        :return dict or None: The token if exists, None otherwise
        """
        token = None
        if self.token_path.exists():
            with self.token_path.open('r') as token_file:
                token = self.token_constructor(self.serializer.load(token_file))
        self.token = token
        return token

    def save_token(self):
        """
        Saves the token dict in the specified file
        :param token: a Token Dictionary
        :type token: dict
        :return bool: Success / Failure
        """
        if self.token is None:
            raise ValueError('You have to set the "token" first.')

        try:
            if not self.token_path.parent.exists():
                self.token_path.parent.mkdir(parents=True)
        except Exception as e:
            log.error('Token could not be saved: {}'.format(str(e)))
            return False

        with self.token_path.open('w') as token_file:
            # 'indent = True' will make the file human readable
            self.serializer.dump(self.token, token_file, indent=True)

        return True

    def delete_token(self):
        """
        Deletes the token file
        :return bool: Success / Failure
        """
        if self.token_path.exists():
            self.token_path.unlink()
            return True
        return False

    def check_token(self):
        """
        Cheks if the token exists in the filesystem
        :return bool: True if exists, False otherwise
        """
        return self.token_path.exists()
