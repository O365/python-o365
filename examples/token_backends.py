from __future__ import  annotations

import time
import logging
import random
from typing import Optional, TYPE_CHECKING

from portalocker import Lock
from portalocker.exceptions import LockException

from O365.utils import FirestoreBackend, FileSystemTokenBackend

if TYPE_CHECKING:
    from O365.connection import Connection


log = logging.getLogger(__name__)


# This is an implementation of the 'should_refresh_token' method


class LockableFirestoreBackend(FirestoreBackend):
    """
    A firestore backend that can answer to
    'should_refresh_token'. Synchronous.
    """

    def __init__(self, *args, **kwargs):
        self.refresh_flag_field_name = kwargs.get("refresh_flag_field_name")
        if self.refresh_flag_field_name is None:
            raise ValueError("Must provide the db field name of the refresh token flag")
        self.max_tries = kwargs.pop("max_tries", 5)  # max db calls
        self.factor = kwargs.pop("factor", 1.5)  # incremental back off factor
        super().__init__(*args, **kwargs)

    def _take_refresh_action(self) -> bool:
        # this should transactional get the flag and set it to False only if it's True
        # it should return True if it has set the flag to false (to say "hey you can safely refresh the token")
        # if the flag was already False then return False (to say "hey somebody else is refreshing the token atm")
        resolution = True  # example...
        return resolution

    def _check_refresh_flag(self) -> bool:
        """ Returns the token if the flag is True or None otherwise"""
        try:
            doc = self.doc_ref.get()
        except Exception as e:
            log.error(f"Flag (collection: {self.collection}, doc_id: {self.doc_id}) "
                      f"could not be retrieved from the backend: {e}")
            doc = None
        if doc and doc.exists:
            if doc.get(self.refresh_flag_field_name):  # if the flag is True get the token
                token_str = doc.get(self.field_name)
                if token_str:
                    # store the token
                    self._cache = self.deserialize(token_str)
                    return True
        return False

    def should_refresh_token(self, con: Optional[Connection] = None, username: Optional[str] = None):
        # 1) check if the token is already a new one:
        old_access_token = self.get_access_token(username=username)
        if old_access_token:
            self.load_token()  # retrieve again the token from the backend
            new_access_token = self.get_access_token(username=username)
            if old_access_token["secret"] != new_access_token["secret"]:
                # The token is different so the refresh took part somewhere else.
                # Return False so the connection can update the token access from the backend into the session
                return False

        # 2) Here the token stored in the token backend and in the token cache of this instance is the same
        # Therefore ask if we can take the action of refreshing the access token
        if self._take_refresh_action():
            # we have successfully updated the flag, and we can now tell the
            # connection that it can begin to refresh the token
            return True

        # 3) We should refresh the token, but can't as the flag was set to False by somebody else.
        # Therefore, we must wait until the refresh is saved by another instance or thread.
        tries = 0
        while True:
            tries += 1
            value = self.factor * 2 ** (tries - 1)
            seconds = random.uniform(0, value)
            time.sleep(seconds)  # we sleep first as _take_refresh_action already checked the flag

            # 4) Check again for the flag. If returns True then we now have a new token stored
            token_stored = self._check_refresh_flag()
            if token_stored:
                break
            if tries == self.max_tries:
                # We tried and didn't get a result. We return True so the Connection can try a new refresh
                # at the expense of possibly having other instances or threads with a stale refresh token
                return True
        # Return False so the connection can update the token access from the backend into the session
        return False

    def save_token(self, force=False):
        """We must overwrite this method to update also the 'refresh_flag_field_name' to True"""
        if not self._cache:
            return False

        if force is False and self._has_state_changed is False:
            return True

        try:
            # set token will overwrite previous data
            self.doc_ref.set({
                self.field_name: self.serialize(),
                # everytime we store a token we overwrite the flag to True so other instances or threads know
                # then token was updated while waiting for it.
                self.refresh_flag_field_name: True
            })
        except Exception as e:
            log.error(f"Token could not be saved: {str(e)}")
            return False

        return True


class LockableFileSystemTokenBackend(FileSystemTokenBackend):
    """
    See GitHub issue #350
    A token backend that ensures atomic operations when working with tokens 
    stored on a file system. Avoids concurrent instances of O365 racing
    to refresh the same token file. It does this by wrapping the token refresh
    method in the Portalocker package's Lock class, which itself is a wrapper
    around Python's fcntl and win32con.
    """

    def __init__(self, *args, **kwargs):
        self.max_tries: int = kwargs.pop("max_tries", 3)
        self.fs_wait: bool = False
        super().__init__(*args, **kwargs)

    def should_refresh_token(self, con: Optional[Connection] = None, username: Optional[str] = None):
        """
        Method for refreshing the token when there are concurrently running 
        O365 instances. Determines if we need to call the MS server and refresh
        the token and its file, or if another Connection instance has already 
        updated it, and we should just load that updated token from the file.

        It will always return False, None, OR raise an error if a token file
        couldn't be accessed after X tries. That is because this method 
        completely handles token refreshing via the passed Connection object 
        argument. If it determines that the token should be refreshed, it locks
        the token file, calls the Connection's 'refresh_token' method (which 
        loads the fresh token from the server into memory and the file), then 
        unlocks the file. Since refreshing has been taken care of, the calling 
        method does not need to refresh and we return None.
        
        If we are blocked because the file is locked, that means another
        instance is using it. We'll change the backend's state to waiting,
        sleep for 2 seconds, reload a token into memory from the file (since
        another process is using it, we can assume it's being updated), and
        loop again.
        
        If this newly loaded token is not expired, the other instance loaded
        a new token to file, and we can happily move on and return False.
        (since we don't need to refresh the token anymore). If the same token 
        was loaded into memory again and is still expired, that means it wasn't
        updated by the other instance yet. Try accessing the file again for X 
        more times. If we don't succeed after the loop has terminated, raise a
        runtime exception
        """

        # 1) check if the token is already a new one:
        old_access_token = self.get_access_token(username=username)
        if old_access_token:
            self.load_token()  # retrieve again the token from the backend
            new_access_token = self.get_access_token(username=username)
            if old_access_token["secret"] != new_access_token["secret"]:
                # The token is different so the refresh took part somewhere else.
                # Return False so the connection can update the token access from the backend into the session
                return False

        # 2) Here the token stored in the token backend and in the token cache of this instance is the same
        for i in range(self.max_tries, 0, -1):
            try:
                with Lock(self.token_path, "r+", fail_when_locked=True, timeout=0) as token_file:
                    # we were able to lock the file ourselves so proceed to refresh the token
                    # we have to do the refresh here as we must do it with the lock applied
                    log.debug("Locked oauth token file. Refreshing the token now...")
                    token_refreshed = con.refresh_token()
                    if token_refreshed is False:
                        raise RuntimeError("Token Refresh Operation not working")

                    # we have refreshed the auth token ourselves to we must take care of
                    # updating the header and save the token file
                    con.update_session_auth_header()
                    log.debug("New oauth token fetched. Saving the token data into the file")
                    token_file.write(self.serialize())
                log.debug("Unlocked oauth token file")
                return None
            except LockException:
                # somebody else has adquired a lock so will be in the process of updating the token
                self.fs_wait = True
                log.debug(f"Oauth file locked. Sleeping for 2 seconds... retrying {i - 1} more times.")
                time.sleep(2)
                log.debug("Waking up and rechecking token file for update from other instance...")
                # Assume the token has been already updated
                self.load_token()
                # Return False so the connection can update the token access from the backend into the session
                return False

        # if we exit the loop, that means we were locked out of the file after
        # multiple retries give up and throw an error - something isn't right
        raise RuntimeError(f"Could not access locked token file after {self.max_tries}")
