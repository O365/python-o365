import time
import logging
import random

from O365.utils import FirestoreBackend

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
