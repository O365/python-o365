from __future__ import annotations

import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Optional, Protocol, Union, TYPE_CHECKING

from msal.token_cache import TokenCache

if TYPE_CHECKING:
    from O365.connection import Connection

log = logging.getLogger(__name__)


RESERVED_SCOPES = {"profile", "openid", "offline_access"}


class CryptographyManagerType(Protocol):
    """Abstract cryptography manager"""

    def encrypt(self, data: str) -> bytes: ...

    def decrypt(self, data: bytes) -> str: ...


class BaseTokenBackend(TokenCache):
    """A base token storage class"""

    serializer = json  # The default serializer is json

    def __init__(self):
        super().__init__()
        self._has_state_changed: bool = False
        #: Optional cryptography manager.  |br| **Type:** CryptographyManagerType
        self.cryptography_manager: Optional[CryptographyManagerType] = None

    @property
    def has_data(self) -> bool:
        """Does the token backend contain data."""
        return bool(self._cache)

    def token_expiration_datetime(
        self, *, username: Optional[str] = None
    ) -> Optional[dt.datetime]:
        """
        Returns the current access token expiration datetime
        If the refresh token is present, then the expiration datetime is extended by 3 months
        :param str username: The username from which check the tokens
        :return dt.datetime or None: The expiration datetime
        """
        access_token = self.get_access_token(username=username)
        if access_token is None:
            return None

        expires_on = access_token.get("expires_on")
        if expires_on is None:
            # consider the token has expired
            return None
        else:
            expires_on = int(expires_on)
            return dt.datetime.fromtimestamp(expires_on)

    def token_is_expired(self, *, username: Optional[str] = None) -> bool:
        """
        Checks whether the current access token is expired
        :param str username: The username from which check the tokens
        :return bool: True if the token is expired, False otherwise
        """
        token_expiration_datetime = self.token_expiration_datetime(username=username)
        if token_expiration_datetime is None:
            return True
        else:
            return dt.datetime.now() > token_expiration_datetime

    def token_is_long_lived(self, *, username: Optional[str] = None) -> bool:
        """Returns if the token backend has a refresh token"""
        return self.get_refresh_token(username=username) is not None

    def _get_home_account_id(self, username: str) -> Optional[str]:
        """Gets the home_account_id string from the ACCOUNT cache for the specified username"""

        result = list(
            self.search(TokenCache.CredentialType.ACCOUNT, query={"username": username})
        )
        if result:
            return result[0].get("home_account_id")
        else:
            log.debug(f"No account found for username: {username}")
            return None

    def get_all_accounts(self) -> list[dict]:
        """Returns a list of all accounts present in the token cache"""
        return list(self.search(TokenCache.CredentialType.ACCOUNT))

    def get_account(
        self, *, username: Optional[str] = None, home_account_id: Optional[str] = None
    ) -> Optional[dict]:
        """Gets the account object for the specified username or home_account_id"""
        if username and home_account_id:
            raise ValueError(
                'Provide nothing or either username or home_account_id to "get_account", but not both'
            )

        query = None
        if username is not None:
            query = {"username": username}
        if home_account_id is not None:
            query = {"home_account_id": home_account_id}

        result = list(self.search(TokenCache.CredentialType.ACCOUNT, query=query))

        if result:
            return result[0]
        else:
            return None

    def get_access_token(self, *, username: Optional[str] = None) -> Optional[dict]:
        """
        Retrieve the stored access token
        If username is None, then the first access token will be retrieved
        :param str username: The username from which retrieve the access token
        """
        query = None
        if username is not None:
            home_account_id = self._get_home_account_id(username)
            if home_account_id:
                query = {"home_account_id": home_account_id}
            else:
                return None

        results = list(self.search(TokenCache.CredentialType.ACCESS_TOKEN, query=query))
        return results[0] if results else None

    def get_refresh_token(self, *, username: Optional[str] = None) -> Optional[dict]:
        """Retrieve the stored refresh token
        If username is None, then the first access token will be retrieved
        :param str username: The username from which retrieve the refresh token
        """
        query = None
        if username is not None:
            home_account_id = self._get_home_account_id(username)
            if home_account_id:
                query = {"home_account_id": home_account_id}
            else:
                return None

        results = list(
            self.search(TokenCache.CredentialType.REFRESH_TOKEN, query=query)
        )
        return results[0] if results else None

    def get_id_token(self, *, username: Optional[str] = None) -> Optional[dict]:
        """Retrieve the stored id token
        If username is None, then the first id token will be retrieved
        :param str username: The username from which retrieve the id token
        """
        query = None
        if username is not None:
            home_account_id = self._get_home_account_id(username)
            if home_account_id:
                query = {"home_account_id": home_account_id}
            else:
                return None

        results = list(self.search(TokenCache.CredentialType.ID_TOKEN, query=query))
        return results[0] if results else None

    def get_token_scopes(
        self, *, username: Optional[str] = None, remove_reserved: bool = False
    ) -> Optional[list]:
        """
        Retrieve the scopes the token (refresh first then access) has permissions on
        :param str username: The username from which retrieve the refresh token
        :param bool remove_reserved: if True RESERVED_SCOPES will be removed from the list
        """
        token = self.get_refresh_token(username=username) or self.get_access_token(
            username=username
        )
        if token:
            scopes_str = token.get("target")
            if scopes_str:
                scopes = scopes_str.split(" ")
                if remove_reserved:
                    scopes = [scope for scope in scopes if scope not in RESERVED_SCOPES]
                return scopes
        return None

    def remove_data(self, *, username: str) -> bool:
        """
        Removes all tokens and all related data from the token cache for the specified username.
        Returns success or failure.
        :param str username: The username from which remove the tokens and related data
        """
        home_account_id = self._get_home_account_id(username)
        if not home_account_id:
            return False

        query = {"home_account_id": home_account_id}

        # remove id token
        results = list(self.search(TokenCache.CredentialType.ID_TOKEN, query=query))
        for id_token in results:
            self.remove_idt(id_token)

        # remove access token
        results = list(self.search(TokenCache.CredentialType.ACCESS_TOKEN, query=query))
        for access_token in results:
            self.remove_at(access_token)

        # remove refresh tokens
        results = list(
            self.search(TokenCache.CredentialType.REFRESH_TOKEN, query=query)
        )
        for refresh_token in results:
            self.remove_rt(refresh_token)

        # remove accounts
        results = list(self.search(TokenCache.CredentialType.ACCOUNT, query=query))
        for account in results:
            self.remove_account(account)

        self._has_state_changed = True
        return True

    def add(self, event, **kwargs) -> None:
        """Add to the current cache."""
        super().add(event, **kwargs)
        self._has_state_changed = True

    def modify(self, credential_type, old_entry, new_key_value_pairs=None) -> None:
        """Modify content in the cache."""
        super().modify(credential_type, old_entry, new_key_value_pairs)
        self._has_state_changed = True

    def serialize(self) -> Union[bytes, str]:
        """Serialize the current cache state into a string."""
        with self._lock:
            self._has_state_changed = False
            token_str = self.serializer.dumps(self._cache, indent=4)
            if self.cryptography_manager is not None:
                token_str = self.cryptography_manager.encrypt(token_str)
            return token_str

    def deserialize(self, token_cache_state: Union[bytes, str]) -> dict:
        """Deserialize the cache from a state previously obtained by serialize()"""
        with self._lock:
            self._has_state_changed = False
            if self.cryptography_manager is not None:
                token_cache_state = self.cryptography_manager.decrypt(token_cache_state)
            return self.serializer.loads(token_cache_state) if token_cache_state else {}

    def load_token(self) -> bool:
        """
        Abstract method that will retrieve the token data from the backend
        This MUST be implemented in subclasses
        """
        raise NotImplementedError

    def save_token(self, force=False) -> bool:
        """
        Abstract method that will save the token data into the backend
        This MUST be implemented in subclasses
        """
        raise NotImplementedError

    def delete_token(self) -> bool:
        """Optional Abstract method to delete the token from the backend"""
        raise NotImplementedError

    def check_token(self) -> bool:
        """Optional Abstract method to check for the token existence in the backend"""
        raise NotImplementedError

    def should_refresh_token(self, con: Optional[Connection] = None, *,
                             username: Optional[str] = None) -> Optional[bool]:
        """
        This method is intended to be implemented for environments
        where multiple Connection instances are running on parallel.

        This method should check if it's time to refresh the token or not.
        The chosen backend can store a flag somewhere to answer this question.
        This can avoid race conditions between different instances trying to
        refresh the token at once, when only one should make the refresh.

        This is an example of how to achieve this:

            1. Along with the token store a Flag
            2. The first to see the Flag as True must transactional update it
               to False. This method then returns True and therefore the
               connection will refresh the token.
            3. The save_token method should be rewritten to also update the flag
               back to True always.
            4. Meanwhile between steps 2 and 3, any other token backend checking
               for this method should get the flag with a False value.

            | This method should then wait and check again the flag.
            | This can be implemented as a call with an incremental backoff
              factor to avoid too many calls to the database.
            | At a given point in time, the flag will return True.
            | Then this method should load the token and finally return False
              signaling there is no need to refresh the token.

            | If this returns True, then the Connection will refresh the token.
            | If this returns False, then the Connection will NOT refresh the token as it was refreshed by
             another instance or thread.
            | If this returns None, then this method has already executed the refresh and also updated the access
             token into the connection session and therefore the Connection does not have to.

            By default, this always returns True

        There is an example of this in the example's folder.



        :param con: the Connection instance passed by the caller. This is passed because maybe
         the locking mechanism needs to refresh the token within the lock applied in this method.
        :param username: The username from which retrieve the refresh token
        :return: | True if the Connection should refresh the token
                 | False if the Connection should not refresh the token as it was refreshed by another instance
                 | None if the token was refreshed by this method and therefore the Connection should do nothing.
        """
        return True


class FileSystemTokenBackend(BaseTokenBackend):
    """A token backend based on files on the filesystem"""

    def __init__(self, token_path=None, token_filename=None):
        """
        Init Backend
        :param str or Path token_path: the path where to store the token
        :param str token_filename: the name of the token file
        """
        super().__init__()
        if not isinstance(token_path, Path):
            token_path = Path(token_path) if token_path else Path()

        if token_path.is_file():
            #: Path to the token stored in the file system.  |br| **Type:** str
            self.token_path = token_path
        else:
            token_filename = token_filename or "o365_token.txt"
            self.token_path = token_path / token_filename

    def __repr__(self):
        return str(self.token_path)

    def load_token(self) -> bool:
        """
        Retrieves the token from the File System and stores it in the cache
        :return bool: Success / Failure
        """
        if self.token_path.exists():
            with self.token_path.open("r") as token_file:
                token_dict = self.deserialize(token_file.read())
                if "access_token" in token_dict:
                    raise ValueError(
                        "The token you are trying to load is not valid anymore. "
                        "Please delete the token and proceed to authenticate again."
                    )
                self._cache = token_dict
                log.debug(f"Token loaded from {self.token_path}")
            return True
        return False

    def save_token(self, force=False) -> bool:
        """
        Saves the token cache dict in the specified file
        Will create the folder if it doesn't exist
        :param bool force: Force save even when state has not changed
        :return bool: Success / Failure
        """
        if not self._cache:
            return False

        if force is False and self._has_state_changed is False:
            return True

        try:
            if not self.token_path.parent.exists():
                self.token_path.parent.mkdir(parents=True)
        except Exception as e:
            log.error(f"Token could not be saved: {e}")
            return False

        with self.token_path.open("w") as token_file:
            token_file.write(self.serialize())
        return True

    def delete_token(self) -> bool:
        """
        Deletes the token file
        :return bool: Success / Failure
        """
        if self.token_path.exists():
            self.token_path.unlink()
            return True
        return False

    def check_token(self) -> bool:
        """
        Checks if the token exists in the filesystem
        :return bool: True if exists, False otherwise
        """
        return self.token_path.exists()


class MemoryTokenBackend(BaseTokenBackend):
    """A token backend stored in memory."""

    def __repr__(self):
        return "MemoryTokenBackend"

    def load_token(self) -> bool:
        return True

    def save_token(self, force=False) -> bool:
        return True


class EnvTokenBackend(BaseTokenBackend):
    """A token backend based on environmental variable."""

    def __init__(self, token_env_name=None):
        """
        Init Backend
        :param str token_env_name: the name of the environmental variable that will hold the token
        """
        super().__init__()

        #: Name of the environment token (Default - `O365TOKEN`).  |br| **Type:** str
        self.token_env_name = token_env_name if token_env_name else "O365TOKEN"

    def __repr__(self):
        return str(self.token_env_name)

    def load_token(self) -> bool:
        """
        Retrieves the token from the environmental variable
        :return bool: Success / Failure
        """
        if self.token_env_name in os.environ:
            self._cache = self.deserialize(os.environ.get(self.token_env_name))
            return True
        return False

    def save_token(self, force=False) -> bool:
        """
        Saves the token dict in the specified environmental variable
        :param bool force: Force save even when state has not changed
        :return bool: Success / Failure
        """
        if not self._cache:
            return False

        if force is False and self._has_state_changed is False:
            return True

        os.environ[self.token_env_name] = self.serialize()

        return True

    def delete_token(self) -> bool:
        """
        Deletes the token environmental variable
        :return bool: Success / Failure
        """
        if self.token_env_name in os.environ:
            del os.environ[self.token_env_name]
            return True
        return False

    def check_token(self) -> bool:
        """
        Checks if the token exists in the environmental variables
        :return bool: True if exists, False otherwise
        """
        return self.token_env_name in os.environ


class FirestoreBackend(BaseTokenBackend):
    """A Google Firestore database backend to store tokens"""

    def __init__(self, client, collection, doc_id, field_name="token"):
        """
        Init Backend
        :param firestore.Client client: the firestore Client instance
        :param str collection: the firestore collection where to store tokens (can be a field_path)
        :param str doc_id: # the key of the token document. Must be unique per-case.
        :param str field_name: the name of the field that stores the token in the document
        """
        super().__init__()
        #: Fire store client.  |br| **Type:** firestore.Client
        self.client = client
        #: Fire store collection.  |br| **Type:** str
        self.collection = collection
        #: Fire store token document key.  |br| **Type:** str
        self.doc_id = doc_id
        #: Fire store document reference.  |br| **Type:** any
        self.doc_ref = client.collection(collection).document(doc_id)
        #: Fire store token field name (Default - `token`).  |br| **Type:** str
        self.field_name = field_name

    def __repr__(self):
        return f"Collection: {self.collection}. Doc Id: {self.doc_id}"

    def load_token(self) -> bool:
        """
        Retrieves the token from the store
        :return bool: Success / Failure
        """
        try:
            doc = self.doc_ref.get()
        except Exception as e:
            log.error(
                f"Token (collection: {self.collection}, doc_id: {self.doc_id}) "
                f"could not be retrieved from the backend: {e}"
            )
            doc = None
        if doc and doc.exists:
            token_str = doc.get(self.field_name)
            if token_str:
                self._cache = self.deserialize(token_str)
                return True
        return False

    def save_token(self, force=False) -> bool:
        """
        Saves the token dict in the store
        :param bool force: Force save even when state has not changed
        :return bool: Success / Failure
        """
        if not self._cache:
            return False

        if force is False and self._has_state_changed is False:
            return True

        try:
            # set token will overwrite previous data
            self.doc_ref.set({self.field_name: self.serialize()})
        except Exception as e:
            log.error(f"Token could not be saved: {e}")
            return False

        return True

    def delete_token(self) -> bool:
        """
        Deletes the token from the store
        :return bool: Success / Failure
        """
        try:
            self.doc_ref.delete()
        except Exception as e:
            log.error(
                f"Could not delete the token (key: {self.doc_id}): {e}"
            )
            return False
        return True

    def check_token(self) -> bool:
        """
        Checks if the token exists
        :return bool: True if it exists on the store
        """
        try:
            doc = self.doc_ref.get()
        except Exception as e:
            log.error(
                f"Token (collection: {self.collection}, doc_id:"
                f" {self.doc_id}) could not be retrieved from the backend: {e}"
                )
            doc = None
        return doc and doc.exists


class AWSS3Backend(BaseTokenBackend):
    """An AWS S3 backend to store tokens"""

    def __init__(self, bucket_name, filename):
        """
        Init Backend
        :param str bucket_name: Name of the S3 bucket
        :param str filename: Name of the S3 file
        """
        try:
            import boto3
        except ModuleNotFoundError as e:
            raise Exception(
                "Please install the boto3 package to use this token backend."
            ) from e
        super().__init__()
        #: S3 bucket name.  |br| **Type:** str
        self.bucket_name = bucket_name
        #: S3 file name.  |br| **Type:** str
        self.filename = filename
        self._client = boto3.client("s3")

    def __repr__(self):
        return f"AWSS3Backend('{self.bucket_name}', '{self.filename}')"

    def load_token(self) -> bool:
        """
        Retrieves the token from the store
         :return bool: Success / Failure
        """
        try:
            token_object = self._client.get_object(
                Bucket=self.bucket_name, Key=self.filename
            )
            self._cache = self.deserialize(token_object["Body"].read())
        except Exception as e:
            log.error(
                f"Token ({self.filename}) could not be retrieved from the backend: {e}"
            )
            return False
        return True

    def save_token(self, force=False) -> bool:
        """
        Saves the token dict in the store
        :param bool force: Force save even when state has not changed
        :return bool: Success / Failure
        """
        if not self._cache:
            return False

        if force is False and self._has_state_changed is False:
            return True

        token_str = str.encode(self.serialize())
        if self.check_token():  # file already exists
            try:
                _ = self._client.put_object(
                    Bucket=self.bucket_name, Key=self.filename, Body=token_str
                )
            except Exception as e:
                log.error(f"Token file could not be saved: {e}")
                return False
        else:  # create a new token file
            try:
                r = self._client.put_object(
                    ACL="private",
                    Bucket=self.bucket_name,
                    Key=self.filename,
                    Body=token_str,
                    ContentType="text/plain",
                )
            except Exception as e:
                log.error(f"Token file could not be created: {e}")
                return False

        return True

    def delete_token(self) -> bool:
        """
        Deletes the token from the store
        :return bool: Success / Failure
        """
        try:
            r = self._client.delete_object(Bucket=self.bucket_name, Key=self.filename)
        except Exception as e:
            log.error(f"Token file could not be deleted: {e}")
            return False
        else:
            log.warning(
                f"Deleted token file {self.filename} in bucket {self.bucket_name}."
            )
            return True

    def check_token(self) -> bool:
        """
        Checks if the token exists
        :return bool: True if it exists on the store
        """
        try:
            _ = self._client.head_object(Bucket=self.bucket_name, Key=self.filename)
        except:
            return False
        else:
            return True


class AWSSecretsBackend(BaseTokenBackend):
    """An AWS Secrets Manager backend to store tokens"""

    def __init__(self, secret_name, region_name):
        """
        Init Backend
        :param str secret_name: Name of the secret stored in Secrets Manager
        :param str region_name: AWS region hosting the secret (for example, 'us-east-2')
        """
        try:
            import boto3
        except ModuleNotFoundError as e:
            raise Exception(
                "Please install the boto3 package to use this token backend."
            ) from e
        super().__init__()
        #: AWS Secret secret name.  |br| **Type:** str
        self.secret_name = secret_name
        #: AWS Secret region name.  |br| **Type:** str
        self.region_name = region_name
        self._client = boto3.client("secretsmanager", region_name=region_name)

    def __repr__(self):
        return f"AWSSecretsBackend('{self.secret_name}', '{self.region_name}')"

    def load_token(self) -> bool:
        """
        Retrieves the token from the store
        :return bool: Success / Failure
        """
        try:
            get_secret_value_response = self._client.get_secret_value(
                SecretId=self.secret_name
            )
            token_str = get_secret_value_response["SecretString"]
            self._cache = self.deserialize(token_str)
        except Exception as e:
            log.error(
                f"Token (secret: {self.secret_name}) could not be retrieved from the backend: {e}"
            )
            return False

        return True

    def save_token(self, force=False) -> bool:
        """
        Saves the token dict in the store
        :param bool force: Force save even when state has not changed
        :return bool: Success / Failure
        """
        if not self._cache:
            return False

        if force is False and self._has_state_changed is False:
            return True

        if self.check_token():  # secret already exists
            try:
                _ = self._client.update_secret(
                    SecretId=self.secret_name, SecretString=self.serialize()
                )
            except Exception as e:
                log.error(f"Token secret could not be saved: {e}")
                return False
        else:  # create a new secret
            try:
                r = self._client.create_secret(
                    Name=self.secret_name,
                    Description="Token generated by the O365 python package (https://pypi.org/project/O365/).",
                    SecretString=self.serialize(),
                )
            except Exception as e:
                log.error(f"Token secret could not be created: {e}")
                return False
            else:
                log.warning(
                    f"\nCreated secret {r['Name']} ({r['ARN']}). Note: using AWS Secrets Manager incurs charges, "
                    f"please see https://aws.amazon.com/secrets-manager/pricing/ for pricing details.\n"
                )

        return True

    def delete_token(self) -> bool:
        """
        Deletes the token from the store
        :return bool: Success / Failure
        """
        try:
            r = self._client.delete_secret(
                SecretId=self.secret_name, ForceDeleteWithoutRecovery=True
            )
        except Exception as e:
            log.error(f"Token secret could not be deleted: {e}")
            return False
        else:
            log.warning(f"Deleted token secret {r['Name']} ({r['ARN']}).")
            return True

    def check_token(self) -> bool:
        """
        Checks if the token exists
        :return bool: True if it exists on the store
        """
        try:
            _ = self._client.describe_secret(SecretId=self.secret_name)
        except:
            return False
        else:
            return True


class BitwardenSecretsManagerBackend(BaseTokenBackend):
    """A Bitwarden Secrets Manager backend to store tokens"""

    def __init__(self, access_token: str, secret_id: str):
        """
        Init Backend
        :param str access_token: Access Token used to access the Bitwarden Secrets Manager API
        :param str secret_id: ID of Bitwarden Secret used to store the O365 token
        """
        try:
            from bitwarden_sdk import BitwardenClient
        except ModuleNotFoundError as e:
            raise Exception(
                "Please install the bitwarden-sdk package to use this token backend."
            ) from e
        super().__init__()
        #: Bitwarden client.  |br| **Type:** BitWardenClient
        self.client = BitwardenClient()
        #: Bitwarden login access token.  |br| **Type:** str
        self.client.auth().login_access_token(access_token)
        #: Bitwarden secret is.  |br| **Type:** str
        self.secret_id = secret_id
        #: Bitwarden secret.  |br| **Type:** str
        self.secret = None

    def __repr__(self):
        return f"BitwardenSecretsManagerBackend('{self.secret_id}')"

    def load_token(self) -> bool:
        """
        Retrieves the token from Bitwarden Secrets Manager
        :return bool: Success / Failure
        """
        resp = self.client.secrets().get(self.secret_id)
        if not resp.success:
            return False

        self.secret = resp.data

        try:
            self._cache = self.deserialize(self.secret.value)
            return True
        except:
            logging.warning("Existing token could not be decoded")
            return False

    def save_token(self, force=False) -> bool:
        """
        Saves the token dict in Bitwarden Secrets Manager
        :param bool force: Force save even when state has not changed
        :return bool: Success / Failure
        """
        if self.secret is None:
            raise ValueError('You have to set "self.secret" data first.')

        if not self._cache:
            return False

        if force is False and self._has_state_changed is False:
            return True

        self.client.secrets().update(
            self.secret.id,
            self.secret.key,
            self.secret.note,
            self.secret.organization_id,
            self.serialize(),
            [self.secret.project_id],
        )
        return True


class DjangoTokenBackend(BaseTokenBackend):
    """
    A Django database token backend to store tokens. To use this backend add the `TokenModel`
    model below into your Django application.

    .. code-block:: python

        class TokenModel(models.Model):
            token = models.JSONField()
            created_at = models.DateTimeField(auto_now_add=True)
            updated_at = models.DateTimeField(auto_now=True)

            def __str__(self):
                return f"Token for {self.token.get('client_id', 'unknown')}"

    Example usage:

    .. code-block:: python

        from O365.utils import DjangoTokenBackend
        from models import TokenModel

        token_backend = DjangoTokenBackend(token_model=TokenModel)
        account = Account(credentials, token_backend=token_backend)
    """

    def __init__(self, token_model=None):
        """
        Initializes the DjangoTokenBackend.

        :param token_model: The Django model class to use for storing and retrieving tokens (defaults to TokenModel).
        """
        super().__init__()
        # Use the provided token_model class
        #: Django token model  |br| **Type:** TokenModel
        self.token_model = token_model

    def __repr__(self):
        return "DjangoTokenBackend"

    def load_token(self) -> bool:
        """
        Retrieves the latest token from the Django database
        :return bool: Success / Failure
        """

        try:
            # Retrieve the latest token based on the most recently created record
            token_record = self.token_model.objects.latest("created_at")
            self._cache = self.deserialize(token_record.token)
        except Exception as e:
            log.warning(f"No token found in the database, creating a new one: {e}")
            return False

        return True

    def save_token(self, force=False) -> bool:
        """
        Saves the token dict in the Django database
        :param bool force: Force save even when state has not changed
        :return bool: Success / Failure
        """
        if not self._cache:
            return False

        if force is False and self._has_state_changed is False:
            return True

        try:
            # Create a new token record in the database
            self.token_model.objects.create(token=self.serialize())
        except Exception as e:
            log.error(f"Token could not be saved: {e}")
            return False

        return True

    def delete_token(self) -> bool:
        """
        Deletes the latest token from the Django database
        :return bool: Success / Failure
        """
        try:
            # Delete the latest token
            token_record = self.token_model.objects.latest("created_at")
            token_record.delete()
        except Exception as e:
            log.error(f"Could not delete token: {e}")
            return False
        return True

    def check_token(self) -> bool:
        """
        Checks if any token exists in the Django database
        :return bool: True if it exists, False otherwise
        """
        return self.token_model.objects.exists()
