import logging
import json
import datetime as dt
from pathlib import Path
from abc import ABC, abstractmethod

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


class BaseTokenBackend(ABC):
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

    @abstractmethod
    def get_token(self):
        """ Abstract method that will retrieve the oauth token """
        raise NotImplementedError

    @abstractmethod
    def save_token(self):
        """ Abstract method that will save the oauth token """
        raise NotImplementedError

    def delete_token(self):
        """ Optional Abstract method to delete the token """
        raise NotImplementedError

    def check_token(self):
        """ Optional Abstract method to check for the token existence """
        raise NotImplementedError


class FileSystemTokenBackend(BaseTokenBackend):
    """ A token backend based on files on the filesystem """

    def __init__(self, token_path=None, token_filename=None):
        """
        Init Backend
        :param token_path str or Path: the path where to store the token
        :param token_filename str: the name of the token file
        """
        super().__init__()
        if not isinstance(token_path, Path):
            token_path = Path(token_path) if token_path else Path()

        if token_path.is_file():
            self.token_path = token_path
        else:
            token_filename = token_filename or 'o365_token.txt'
            self.token_path = token_path / token_filename

    def __repr__(self):
        return str(self.token_path)

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


class FirestoreBackend(BaseTokenBackend):
    """ A Google Firestore database backend to store tokens """

    def __init__(self, client, collection, doc_id, field_name='token'):
        """
        Init Backend
        :param client firestore.Client: the firestore Client instance
        :param collection str: the firestore collection where to store tokens (can be a field_path)
        :param doc_id str: # the key of the token document. Must be unique per-case.
        :param field_name: the name of the field that stores the token in the document
        """
        super().__init__()
        self.client = client
        self.collection = collection
        self.doc_id = doc_id
        self.doc_ref = client.collections(collection).document(doc_id)
        self.field_name = field_name

    def __repr__(self):
        return 'Collection: {}. Doc Id: {}'.format(self.collection, self.doc_id)
    
    def get_token(self):
        """
        Retrieves the token from the store
        :return dict or None: The token if exists, None otherwise
        """
        token = None
        try:
            doc = self.doc_ref.get()
        except Exception as e:
            log.error('Token (collection: {}, doc_id: {}) '
                      'could not be retrieved from the backend: {}'
                      .format(self.collection, self.doc_id, str(e)))
            doc = None
        if doc and doc.exists:
            token_str = doc.get(self.field_name)
            if token_str:
                token = self.token_constructor(self.serializer.loads(token_str))
        self.token = token
        return token

    def save_token(self):
        """
        Saves the token dict in the store
        :return bool: Success / Failure
        """
        if self.token is None:
            raise ValueError('You have to set the "token" first.')

        try:
            # set token will overwrite previous data
            self.doc_ref.set({
                self.field_name: self.serializer.dumps(self.token)
            })
        except Exception as e:
            log.error('Token could not be saved: {}'.format(str(e)))
            return False

        return True

    def delete_token(self):
        """
        Deletes the token from the store
        :return bool: Success / Failure
        """
        try:
            self.doc_ref.delete()
        except Exception as e:
            log.error('Could not delete the token (key: {}): {}'.format(self.doc_id, str(e)))
            return False
        return True

    def check_token(self):
        """
        Checks if the token exists
        :return bool: True if it exists on the store
        """
        try:
            doc = self.doc_ref.get()
        except Exception as e:
            log.error('Token (collection: {}, doc_id: {}) '
                      'could not be retrieved from the backend: {}'
                      .format(self.collection, self.doc_id, str(e)))
            doc = None
        return doc and doc.exists
