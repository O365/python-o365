import logging
from enum import Enum

ME_RESOURCE = 'me'
USERS_RESOURCE = 'users'

NEXT_LINK_KEYWORD = '@odata.nextLink'

log = logging.getLogger(__name__)


MAX_RECIPIENTS_PER_MESSAGE = 500  # Actual limit on Office 365


class RecipientType(Enum):
    TO = 'to'
    CC = 'cc'
    BCC = 'bcc'


class WellKnowFolderNames(Enum):
    INBOX = 'Inbox'
    JUNK = 'JunkEmail'
    DELETED = 'DeletedItems'
    DRAFTS = 'Drafts'
    SENT = 'SentItems'
    OUTBOX = 'Outbox'


class ChainOperator(Enum):
    AND = 'and'
    OR = 'or'


class ApiComponent:
    """ Base class for all object interactions with the Cloud Service API

    Exposes common access methods to the api protocol within all Api objects
    """

    _cloud_data_key = '__cloud_data__'  # wrapps cloud data with this dict key
    _endpoints = {}  # dict of all API service endpoints needed

    def __init__(self, *, protocol=None, main_resource=None, **kwargs):
        """ Object initialization
        :param protocol: A protocol class or instance to be used with this connection
        :param main_resource: main_resource to be used in these API comunications
        :param kwargs: Extra arguments
        """
        self.protocol = protocol() if isinstance(protocol, type) else protocol
        if self.protocol is None:
            raise ValueError('Protocol not provided to Api Component')
        self.main_resource = self._parse_resource(main_resource or protocol.default_resource)
        self._base_url = '{}{}'.format(self.protocol.service_url, self.main_resource)

    @staticmethod
    def _parse_resource(resource):
        """ Parses and completes resource information """
        if resource == ME_RESOURCE:
            return resource
        elif USERS_RESOURCE == resource:
            return resource
        else:
            if USERS_RESOURCE not in resource:
                resource = resource.replace('/', '')
                return '{}/{}'.format(USERS_RESOURCE, resource)
            else:
                return resource

    def build_url(self, endpoint):
        """ Returns a url for a given endpoint using the protocol service url """
        return '{}{}'.format(self._base_url, endpoint)

    def _gk(self, keyword):
        """ Alias for protocol.get_service_keyword """
        return self.protocol.get_service_keyword(keyword)

    def _cc(self, dict_key):
        """ Alias for protocol.convert_case """
        return self.protocol.convert_case(dict_key)

    def new_query(self, attribute=None):
        return Query(attribute=attribute, protocol=self.protocol)


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
        return "'{}' Iterator".format(self.constructor.__name__ if self.constructor else 'Unknown')

    def __repr__(self):
        return self.__str__()

    def __bool__(self):
        return bool(self.data) or bool(self.next_link)

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
        'from': 'from/emailAddress/address',
        'received': ''
    }

    def __init__(self, attribute=None, *, protocol):
        self.protocol = protocol
        self._attribute = None
        self._chain = None
        self.new(attribute)
        self._negation = False
        self._filters = []

    def __str__(self):
        if self._filters:
            filters_list = self._filters
            if isinstance(filters_list[-1], Enum):
                filters_list = filters_list[:-1]
            return ' '.join([fs.value if isinstance(fs, Enum) else fs for fs in filters_list]).strip()
        else:
            return ''

    def __repr__(self):
        return self.__str__()

    def filter(self, and_filter):
        pass

    def _get_mapping(self, attribute):
        mapping = self._mapping.get(attribute)
        if mapping:
            attribute = '/'.join([self.protocol.convert_case(step) for step in mapping.split('/')])
        else:
            attribute = self.protocol.convert_case(attribute)
        return attribute

    def new(self, attribute, operation=ChainOperator.AND):
        if isinstance(operation, str):
            operation = ChainOperator(operation)
        self._chain = operation
        self._attribute = self._get_mapping(attribute) if attribute else None
        self._negation = False
        return self

    def negate(self):
        self._negation = not self._negation
        return self

    def chain(self, operation=ChainOperator.AND):
        if isinstance(operation, str):
            operation = ChainOperator(operation)
        self._chain = operation
        return self

    def on_attribute(self, attribute):
        self._attribute = self._get_mapping(attribute)
        return self

    def _add_filter(self, filter_str):
        if self._attribute:
            self._filters.append(filter_str)
            self._filters.append(self._chain)
        else:
            raise ValueError('Attribute property needed. call on_attribute(attribute) or new(attribute)')

    def logical_operator(self, operation, word):
        if isinstance(word, str):
            sentence = "{} {} {} '{}'".format('not' if self._negation else '', self._attribute, operation, word).strip()
        else:
            sentence = '{} {} {} {}'.format('not' if self._negation else '', self._attribute, operation, word).strip()

        self._add_filter(sentence)
        return self

    def equals(self, word):
        self.logical_operator('eq', word)
        return self

    def unequal(self, word):
        self.logical_operator('ne', word)
        return self

    def greater(self, word):
        self.logical_operator('gt', word)
        return self

    def greater_equal(self, word):
        self.logical_operator('ge', word)
        return self

    def less(self, word):
        self.logical_operator('lt', word)
        return self

    def less_equal(self, word):
        self.logical_operator('le', word)
        return self

    def contains(self, word):
        self._add_filter("{} contains({}, '{}')".format('not' if self._negation else '', self._attribute, word).strip())
        return self

    def startswith(self, word):
        self._add_filter("{} startswith({}, '{}')".format('not' if self._negation else '', self._attribute, word).strip())
        return self

    def endswith(self, word):
        self._add_filter("{} endswith({}, '{}')".format('not' if self._negation else '', self._attribute, word).strip())
        return self
