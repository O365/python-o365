import logging
from enum import Enum
import datetime as dt
import pytz
from collections import OrderedDict

ME_RESOURCE = 'me'
USERS_RESOURCE = 'users'

NEXT_LINK_KEYWORD = '@odata.nextLink'

log = logging.getLogger(__name__)

MAX_RECIPIENTS_PER_MESSAGE = 500  # Actual limit on Office 365


class ImportanceLevel(Enum):
    Normal = 'normal'
    Low = 'low'
    High = 'high'


class OutlookWellKnowFolderNames(Enum):
    INBOX = 'Inbox'
    JUNK = 'JunkEmail'
    DELETED = 'DeletedItems'
    DRAFTS = 'Drafts'
    SENT = 'SentItems'
    OUTBOX = 'Outbox'


class OneDriveWellKnowFolderNames(Enum):
    DOCUMENTS = 'documents'
    PHOTOS = 'photos'
    CAMERA_ROLL = 'cameraroll'
    APP_ROOT = 'approot'
    MUSIC = 'music'
    ATTACHMENTS = 'attachments'


class ChainOperator(Enum):
    AND = 'and'
    OR = 'or'


class TrackerSet(set):
    """ A Custom Set that changes the casing of it's keys """

    def __init__(self, *args, casing=None, **kwargs):
        self.cc = casing
        super().__init__(*args, **kwargs)

    def add(self, value):
        value = self.cc(value)
        super().add(value)


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
        self.main_resource = self._parse_resource(main_resource if main_resource is not None else protocol.default_resource)
        self._base_url = '{}{}'.format(self.protocol.service_url, self.main_resource)
        if self._base_url.endswith('/'):
            # when self.main_resource is an empty string then remove the last slash.
            self._base_url = self._base_url[:-1]
        super().__init__()

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Api Component on resource: {}'.format(self.main_resource)

    @staticmethod
    def _parse_resource(resource):
        """ Parses and completes resource information """
        resource = resource.strip() if resource else resource
        if resource in {ME_RESOURCE, USERS_RESOURCE}:
            return resource
        elif '@' in resource and not resource.startswith(USERS_RESOURCE):
            # when for example accesing a shared mailbox the resource is set to the email address.
            # we have to prefix the email with the resource 'users/' so --> 'users/email_address'
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

    q = new_query  # alias for new query


class Pagination(ApiComponent):
    """ Utility class that allows batching requests to the server """

    def __init__(self, *, parent=None, data=None, constructor=None, next_link=None, limit=None):
        """
        Returns an iterator that returns data until it's exhausted. Then will request more data
        (same amount as the original request) to the server until this data is exhausted as well.
        Stops when no more data exists or limit is reached.

        :param parent: the parent class. Must implement attributes:
            con, api_version, main_resource
        :param data: the start data to be return
        :param constructor: the data constructor for the next batch. It can be a function.
        :param next_link: the link to request more data to
        :param limit: when to stop retrieving more data
        """
        if parent is None:
            raise ValueError('Parent must be another Api Component')

        super().__init__(protocol=parent.protocol, main_resource=parent.main_resource)

        self.parent = parent
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
        return self.__repr__()

    def __repr__(self):
        if callable(self.constructor):
            return 'Pagination Iterator'
        else:
            return "'{}' Iterator".format(self.constructor.__name__ if self.constructor else 'Unknown')

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

        response = self.con.get(self.next_link)
        if not response:
            raise StopIteration()

        data = response.json()

        self.next_link = data.get(NEXT_LINK_KEYWORD, None) or None
        data = data.get('value', [])
        if self.constructor:
            # Everything received from the cloud must be passed with self._cloud_data_key
            if callable(self.constructor) and not isinstance(self.constructor, type):  # it's callable but its not a Class
                self.data = [self.constructor(value)(parent=self.parent, **{self._cloud_data_key: value}) for value in data]
            else:
                self.data = [self.constructor(parent=self.parent, **{self._cloud_data_key: value}) for value in data]
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
        'to': 'toRecipients/emailAddress/address',
        'start': 'start/DateTime',
        'end': 'end/DateTime'
    }

    def __init__(self, attribute=None, *, protocol):
        self.protocol = protocol() if isinstance(protocol, type) else protocol
        self._attribute = None
        self._chain = None
        self.new(attribute)
        self._negation = False
        self._filters = []
        self._order_by = OrderedDict()
        self._selects = set()

    def __str__(self):
        return 'Filter: {}\nOrder: {}\nSelect: {}'.format(self.get_filters(), self.get_order(), self.get_selects())

    def __repr__(self):
        return self.__str__()

    def select(self, *attributes):
        """
        Adds the attribute to the $select parameter
        :param attributes: the attributes tuple to select. If empty, the on_attribute previously set is added.
        """
        if attributes:
            for attribute in attributes:
                attribute = self.protocol.convert_case(attribute) if attribute and isinstance(attribute, str) else None
                if attribute:
                    if '/' in attribute:
                        # only parent attribute can be selected
                        attribute = attribute.split('/')[0]
                    self._selects.add(attribute)
        else:
            if self._attribute:
                self._selects.add(self._attribute)

        return self

    def as_params(self):
        """ Returns the filters and orders as query parameters"""
        params = {}
        if self.has_filters:
            params['$filter'] = self.get_filters()
        if self.has_order:
            params['$orderby'] = self.get_order()
        if self.has_selects:
            params['$select'] = self.get_selects()
        return params

    @property
    def has_filters(self):
        return bool(self._filters)

    @property
    def has_order(self):
        return bool(self._order_by)

    @property
    def has_selects(self):
        return bool(self._selects)

    def get_filters(self):
        """ Returns the result filters """
        if self._filters:
            filters_list = self._filters
            if isinstance(filters_list[-1], Enum):
                filters_list = filters_list[:-1]
            return ' '.join([fs.value if isinstance(fs, Enum) else fs[1] for fs in filters_list]).strip()
        else:
            return None

    def get_order(self):
        """ Returns the result order by clauses """
        # first get the filtered attributes in order as they must appear in the order_by first
        if not self.has_order:
            return None
        filter_order_clauses = OrderedDict([(filter_attr[0], None)
                                            for filter_attr in self._filters
                                            if isinstance(filter_attr, tuple)])

        # any order_by attribute that appears in the filters is ignored
        order_by_dict = self._order_by.copy()
        for filter_oc in filter_order_clauses.keys():
            direction = order_by_dict.pop(filter_oc, None)
            filter_order_clauses[filter_oc] = direction

        filter_order_clauses.update(order_by_dict)  # append any remaining order_by clause

        if filter_order_clauses:
            return ','.join(['{} {}'.format(attribute, direction if direction else '').strip()
                             for attribute, direction in filter_order_clauses.items()])
        else:
            return None

    def get_selects(self):
        """ Returns the result select clause """
        if self._selects:
            return ','.join(self._selects)
        else:
            return None

    def _get_mapping(self, attribute):
        if attribute:
            mapping = self._mapping.get(attribute)
            if mapping:
                attribute = '/'.join([self.protocol.convert_case(step) for step in mapping.split('/')])
            else:
                attribute = self.protocol.convert_case(attribute)
            return attribute
        return None

    def new(self, attribute, operation=ChainOperator.AND):
        if isinstance(operation, str):
            operation = ChainOperator(operation)
        self._chain = operation
        self._attribute = self._get_mapping(attribute) if attribute else None
        self._negation = False
        return self

    def clear_filters(self):
        self._filters = []

    def clear(self):
        self._filters = []
        self._order_by = OrderedDict()
        self._selects = set()
        self.new(None)
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
            if self._filters and not isinstance(self._filters[-1], ChainOperator):
                self._filters.append(self._chain)
            self._filters.append((self._attribute, filter_str))
        else:
            raise ValueError('Attribute property needed. call on_attribute(attribute) or new(attribute)')

    def _parse_filter_word(self, word):
        """ Converts the word parameter into the correct format """
        if isinstance(word, str):
            word = "'{}'".format(word)
        elif isinstance(word, dt.date):
            if isinstance(word, dt.datetime):
                if word.tzinfo is None:
                    # if it's a naive datetime, localize the datetime.
                    word = self.protocol.timezone.localize(word)  # localize datetime into local tz
                if word.tzinfo != pytz.utc:
                    word = word.astimezone(pytz.utc)  # transform local datetime to utc
            word = '{}'.format(word.isoformat())  # convert datetime to isoformat
        elif isinstance(word, bool):
            word = str(word).lower()
        return word

    def logical_operator(self, operation, word):
        word = self._parse_filter_word(word)
        sentence = '{} {} {} {}'.format('not' if self._negation else '', self._attribute, operation, word).strip()
        self._add_filter(sentence)
        return self

    def equals(self, word):
        return self.logical_operator('eq', word)

    def unequal(self, word):
        return self.logical_operator('ne', word)

    def greater(self, word):
        return self.logical_operator('gt', word)

    def greater_equal(self, word):
        return self.logical_operator('ge', word)

    def less(self, word):
        return self.logical_operator('lt', word)

    def less_equal(self, word):
        return self.logical_operator('le', word)

    def function(self, function_name, word):
        word = self._parse_filter_word(word)

        self._add_filter(
            "{} {}({}, {})".format('not' if self._negation else '', function_name, self._attribute, word).strip())
        return self

    def contains(self, word):
        return self.function('contains', word)

    def startswith(self, word):
        return self.function('startswith', word)

    def endswith(self, word):
        return self.function('endswith', word)

    def order_by(self, attribute=None, *, ascending=True):
        """ applies a order_by clause"""
        attribute = self._get_mapping(attribute) or self._attribute
        if attribute:
            self._order_by[attribute] = None if ascending else 'desc'
        else:
            raise ValueError('Attribute property needed. call on_attribute(attribute) or new(attribute)')
        return self
