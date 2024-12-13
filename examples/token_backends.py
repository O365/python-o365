import time
import logging
import random
from portalocker import Lock
from portalocker.exceptions import LockException

from O365.utils import FirestoreBackend, FileSystemTokenBackend

log = logging.getLogger(__name__)


# This is an implementation of the 'should_refresh_token' method


class LockableFirestoreBackend(FirestoreBackend):
    """
    A firestore backend that can answer to
    'should_refresh_token'. Synchronous.
    """

    def __init__(self, *args, **kwargs):
        self.refresh_flag_field_name = kwargs.get('refresh_flag_field_name')
        if self.refresh_flag_field_name is None:
            raise ValueError('Must provide the db field name of the refresh token flag')
        self.max_tries = kwargs.pop('max_tries', 5)  # max db calls
        self.factor = kwargs.pop('factor', 1.5)  # incremental back off factor
        super().__init__(*args, **kwargs)

    def _take_refresh_action(self):
        # this should transactionally get the flag and set it to False if it's True
        # it should return True if it has set the flag to False.
        # if the flag was already False then return False
        resolution = True  # example...
        return resolution

    def _check_refresh_flag(self):
        """ Returns the token if the flag is True or None otherwise"""
        try:
            doc = self.doc_ref.get()
        except Exception as e:
            log.error('Flag (collection: {}, doc_id: {}) '
                      'could not be retrieved from the backend: {}'
                      .format(self.collection, self.doc_id, str(e)))
            doc = None
        if doc and doc.exists:
            if doc.get(self.refresh_flag_field_name):
                token_str = doc.get(self.field_name)
                if token_str:
                    token = self.token_constructor(self.serializer.loads(token_str))
                    return token
        return None

    def should_refresh_token(self, con=None):
        # 1) check if the token is already a new one:
        new_token = self.load_token()
        if new_token and new_token.get('access_token') != self.token.get('access_token'):
            # The token is different. Store it and return False
            self.token = new_token
            return False

        # 2) ask if you can take the action of refreshing the access token
        if self._take_refresh_action():
            # we have updated the flag and an now begin to refresh the token
            return True

        # 3) we must wait until the refresh is done by another instance
        tries = 0
        while True:
            tries += 1
            value = self.factor * 2 ** (tries - 1)
            seconds = random.uniform(0, value)
            time.sleep(seconds)  # we sleep first as _take_refresh_action already checked the flag

            # 4) Check for the flag. if returns a token then is the new token.
            token = self._check_refresh_flag()
            if token is not None:
                # store the token and leave
                self.token = token
                break
            if tries == self.max_tries:
                # we tried and didn't get a result.
                return True
        return False

    def save_token(self):
        """We must overwrite this method to update also the flag to True"""
        if self.token is None:
            raise ValueError('You have to set the "token" first.')

        try:
            # set token will overwrite previous data
            self.doc_ref.set({
                self.field_name: self.serializer.dumps(self.token),
                self.refresh_flag_field_name: True
            })
        except Exception as e:
            log.error('Token could not be saved: {}'.format(str(e)))
            return False

        return True


class LockableFileSystemTokenBackend(FileSystemTokenBackend):
    """
    GH #350
    A token backend that ensures atomic operations when working with tokens 
    stored on a file system. Avoids concurrent instances of O365 racing
    to refresh the same token file. It does this by wrapping the token refresh
    method in the Portalocker package's Lock class, which itself is a wrapper
    around Python's fcntl and win32con.
    """

    def __init__(self, *args, **kwargs):
        self.max_tries = kwargs.pop('max_tries')
        self.fs_wait = False
        super().__init__(*args, **kwargs)

    def should_refresh_token(self, con=None):
        """
        Method for refreshing the token when there are concurrently running 
        O365 instances. Determines if we need to call the MS server and refresh
        the token and its file, or if another Connection instance has already 
        updated it and we should just load that updated token from the file.

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
        more times. If we don't suceed after the loop has terminated, raise a 
        runtime exception
        """

        for _ in range(self.max_tries, 0, -1):
            if self.token.is_access_expired:
                try:
                    with Lock(self.token_path, 'r+',
                              fail_when_locked=True, timeout=0):
                        log.debug('Locked oauth token file')
                        if con.get_refresh_token() is False:
                            raise RuntimeError('Token Refresh Operation not '
                                               'working')
                        log.info('New oauth token fetched')
                    log.debug('Unlocked oauth token file')
                    return None
                except LockException:
                    self.fs_wait = True
                    log.warning('Oauth file locked. Sleeping for 2 seconds... retrying {} more times.'.format(_ - 1))
                    time.sleep(2)
                    log.debug('Waking up and rechecking token file for update'
                              ' from other instance...')
                    self.token = self.load_token()
            else:
                log.info('Token was refreshed by another instance...')
                self.fs_wait = False
                return False

        # if we exit the loop, that means we were locked out of the file after
        # multiple retries give up and throw an error - something isn't right
        raise RuntimeError('Could not access locked token file after {}'.format(self.max_tries))
