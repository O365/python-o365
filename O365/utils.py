import logging
from enum import Enum

from O365.connection import ApiComponent

NEXT_LINK_KEYWORD = '@odata.nextLink'

log = logging.getLogger(__name__)


class WellKnowFolderNames(Enum):
    INBOX = 'Inbox'
    JUNK = 'JunkEmail'
    DELETED = 'DeletedItems'
    DRAFTS = 'Drafts'
    SENT = 'SentItems'
    OUTBOX = 'Outbox'


class Pagination(ApiComponent):
    """ Utility class that allows batching requests to the server """

    def __init__(self, *, parent=None, data=None, constructor=None, next_link=None, limit=None):
        """
        Returns an iterator that returns data until it's exhausted. Then will request more data
        (same amount as the original request) to the server until this data is exhausted as well.
        Stops when no more data exists or limit is reached.

        :param parent: the parent class. Must implement attributes:
            con, api_version, main_resource, auth_method
        :param data: the start data to be return
        :param constructor: the data constructor for the next batch
        :param next_link: the link to request more data to
        :param limit: when to stop retrieving more data
        """
        if parent is None:
            raise ValueError('Parent must be another Api Component')

        super().__init__(protocol=parent.protocol, main_resource=parent.main_resource)

        self.con = parent.con
        self.constructor = constructor
        self.next_link = next_link
        self.limit = limit
        self.data = data if data else []

        data_count = len(data)
        if limit and limit < data_count:
            self.data_count = limit
            self.total_count = limit
        else:
            self.data_count = data_count
            self.total_count = data_count
        self.state = 0

    def __str__(self):
        return "Iterating over '{}'".format(self.constructor.__name__ if self.constructor else 'Unknown')

    def __repr__(self):
        return self.__str__()

    def __iter__(self):
        return self

    def __next__(self):
        if self.state < self.data_count:
            value = self.data[self.state]
            self.state += 1
            return value
        else:
            if self.limit and self.total_count >= self.limit:
                raise StopIteration()

        if self.next_link is None:
            raise StopIteration()
        try:
            response = self.con.get(self.next_link)
        except Exception as e:
            log.error('Error while Paginating. Error: {}'.format(str(e)))
            raise e

        if response.status_code != 200:
            log.debug('Failed Request while Paginating. Reason: {}'.format(response.reason))
            raise StopIteration()

        data = response.json()
        self.next_link = data.get(NEXT_LINK_KEYWORD, None) or None
        data = data.get('value', [])
        if self.constructor:
            # Everything received from the cloud must be passed with self._cloud_data_key
            self.data = [self.constructor(parent=self, **{self._cloud_data_key: value})
                         for value in data]
        else:
            self.data = data

        items_count = len(data)
        if self.limit:
            dif = self.limit - (self.total_count + items_count)
            if dif < 0:
                self.data = self.data[:dif]
                self.next_link = None  # stop batching
                items_count = items_count + dif
        if items_count:
            self.data_count = items_count
            self.total_count += items_count
            self.state = 0
            value = self.data[self.state]
            self.state += 1
            return value
        else:
            raise StopIteration()


class Query:
    """ Helper to conform OData filters """
    _mapping = {
        'from': {'expands_to': 'from/emailAddress/address'},
        'received': {}

    }

    def __init__(self, protocol):
        self.protocol = protocol

    def filter(self, and_filter):
        pass

