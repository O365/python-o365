import datetime as dt
import logging
from collections import OrderedDict
from enum import Enum

import pytz
from dateutil.parser import parse
from stringcase import snakecase

from .windows_tz import get_iana_tz, get_windows_tz
from .decorators import fluent

ME_RESOURCE = 'me'
USERS_RESOURCE = 'users'

NEXT_LINK_KEYWORD = '@odata.nextLink'

log = logging.getLogger(__name__)

MAX_RECIPIENTS_PER_MESSAGE = 500  # Actual limit on Office 365


class CaseEnum(Enum):
    """ A Enum that converts the value to a snake_case casing """

    def __new__(cls, value):
        obj = object.__new__(cls)
        obj._value_ = snakecase(value)  # value will be transformed to snake_case
        return obj

    @classmethod
    def from_value(cls, value):
        """ Gets a member by a snaked-case provided value"""
        try:
            return cls(snakecase(value))
        except ValueError:
            return None


class ImportanceLevel(CaseEnum):
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
    def __init__(self, *args, casing=None, **kwargs):
        """ A Custom Set that changes the casing of it's keys

        :param func casing: a function to convert into specified case
        """
        self.cc = casing
        super().__init__(*args, **kwargs)

    def add(self, value):
        value = self.cc(value)
        super().add(value)

    def remove(self, value):
        value = self.cc(value)
        super().remove(value)


class Recipient:
    """ A single Recipient """

    def __init__(self, address=None, name=None, parent=None, field=None):
        """ Create a recipient with provided information

        :param str address: email address of the recipient
        :param str name: name of the recipient
        :param HandleRecipientsMixin parent: parent recipients handler
        :param str field: name of the field to update back
        """
        self._address = address or ''
        self._name = name or ''
        self._parent = parent
        self._field = field

    def __bool__(self):
        return bool(self.address)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if self.name:
            return '{} ({})'.format(self.name, self.address)
        else:
            return self.address

    # noinspection PyProtectedMember
    def _track_changes(self):
        """ Update the track_changes on the parent to reflect a
        needed update on this field """
        if self._field and getattr(self._parent, '_track_changes',
                                   None) is not None:
            self._parent._track_changes.add(self._field)

    @property
    def address(self):
        """ Email address of the recipient

        :getter: Get the email address
        :setter: Set and update the email address
        :type: str
        """
        return self._address

    @address.setter
    def address(self, value):
        self._address = value
        self._track_changes()

    @property
    def name(self):
        """ Name of the recipient

        :getter: Get the name
        :setter: Set and update the name
        :type: str
        """
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._track_changes()


class Recipients:
    """ A Sequence of Recipients """

    def __init__(self, recipients=None, parent=None, field=None):
        """ Recipients must be a list of either address strings or
        tuples (name, address) or dictionary elements

        :param recipients: list of either address strings or
         tuples (name, address) or dictionary elements
        :type recipients: list[str] or list[tuple] or list[dict]
         or list[Recipient]
        :param HandleRecipientsMixin parent: parent recipients handler
        :param str field: name of the field to update back
        """
        self._parent = parent
        self._field = field
        self._recipients = []
        self.untrack = True
        if recipients:
            self.add(recipients)
        self.untrack = False

    def __iter__(self):
        return iter(self._recipients)

    def __getitem__(self, key):
        return self._recipients[key]

    def __contains__(self, item):
        return item in {recipient.address for recipient in self._recipients}

    def __bool__(self):
        return bool(len(self._recipients))

    def __len__(self):
        return len(self._recipients)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Recipients count: {}'.format(len(self._recipients))

    # noinspection PyProtectedMember
    def _track_changes(self):
        """ Update the track_changes on the parent to reflect a
        needed update on this field """
        if self._field and getattr(self._parent, '_track_changes',
                                   None) is not None and self.untrack is False:
            self._parent._track_changes.add(self._field)

    def clear(self):
        """ Clear the list of recipients """
        self._recipients = []
        self._track_changes()

    def add(self, recipients):
        """ Add the supplied recipients to the exiting list

        :param recipients: list of either address strings or
         tuples (name, address) or dictionary elements
        :type recipients: list[str] or list[tuple] or list[dict]
        """

        if recipients:
            if isinstance(recipients, str):
                self._recipients.append(
                    Recipient(address=recipients, parent=self._parent,
                              field=self._field))
            elif isinstance(recipients, Recipient):
                self._recipients.append(recipients)
            elif isinstance(recipients, tuple):
                name, address = recipients
                if address:
                    self._recipients.append(
                        Recipient(address=address, name=name,
                                  parent=self._parent, field=self._field))
            elif isinstance(recipients, list):
                for recipient in recipients:
                    self.add(recipient)
            else:
                raise ValueError('Recipients must be an address string, a '
                                 'Recipient instance, a (name, address) '
                                 'tuple or a list')
            self._track_changes()

    def remove(self, address):
        """ Remove an address or multiple addresses

        :param address: list of addresses to remove
        :type address: str or list[str]
        """
        recipients = []
        if isinstance(address, str):
            address = {address}  # set
        elif isinstance(address, (list, tuple)):
            address = set(address)

        for recipient in self._recipients:
            if recipient.address not in address:
                recipients.append(recipient)
        if len(recipients) != len(self._recipients):
            self._track_changes()
        self._recipients = recipients

    def get_first_recipient_with_address(self):
        """ Returns the first recipient found with a non blank address

        :return: First Recipient
        :rtype: Recipient
        """
        recipients_with_address = [recipient for recipient in self._recipients
                                   if recipient.address]
        if recipients_with_address:
            return recipients_with_address[0]
        else:
            return None


class HandleRecipientsMixin:

    def _recipients_from_cloud(self, recipients, field=None):
        """ Transform a recipient from cloud data to object data """
        recipients_data = []
        for recipient in recipients:
            recipients_data.append(
                self._recipient_from_cloud(recipient, field=field))
        return Recipients(recipients_data, parent=self, field=field)

    def _recipient_from_cloud(self, recipient, field=None):
        """ Transform a recipient from cloud data to object data """

        if recipient:
            recipient = recipient.get(self._cc('emailAddress'),
                                      recipient if isinstance(recipient,
                                                              dict) else {})
            address = recipient.get(self._cc('address'), '')
            name = recipient.get(self._cc('name'), '')
            return Recipient(address=address, name=name, parent=self,
                             field=field)
        else:
            return Recipient()

    def _recipient_to_cloud(self, recipient):
        """ Transforms a Recipient object to a cloud dict """
        data = None
        if recipient:
            data = {self._cc('emailAddress'): {
                self._cc('address'): recipient.address}}
            if recipient.name:
                data[self._cc('emailAddress')][
                    self._cc('name')] = recipient.name
        return data


class ApiComponent:
    """ Base class for all object interactions with the Cloud Service API

    Exposes common access methods to the api protocol within all Api objects
    """

    _cloud_data_key = '__cloud_data__'  # wraps cloud data with this dict key
    _endpoints = {}  # dict of all API service endpoints needed

    def __init__(self, *, protocol=None, main_resource=None, **kwargs):
        """ Object initialization

        :param Protocol protocol: A protocol class or instance to be used with
         this connection
        :param str main_resource: main_resource to be used in these API
         communications
        """
        self.protocol = protocol() if isinstance(protocol, type) else protocol
        if self.protocol is None:
            raise ValueError('Protocol not provided to Api Component')
        self.main_resource = (self._parse_resource(
            main_resource if main_resource is not None
            else protocol.default_resource))
        # noinspection PyUnresolvedReferences
        self._base_url = '{}{}'.format(self.protocol.service_url,
                                       self.main_resource)
        if self._base_url.endswith('/'):
            # when self.main_resource is empty then remove the last slash.
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
            # when for example accessing a shared mailbox the
            # resource is set to the email address. we have to prefix
            # the email with the resource 'users/' so --> 'users/email_address'
            return '{}/{}'.format(USERS_RESOURCE, resource)
        else:
            return resource

    def build_url(self, endpoint):
        """ Returns a url for a given endpoint using the protocol
        service url

        :param str endpoint: endpoint to build the url for
        :return: final url
        :rtype: str
        """
        return '{}{}'.format(self._base_url, endpoint)

    def _gk(self, keyword):
        """ Alias for protocol.get_service_keyword """
        return self.protocol.get_service_keyword(keyword)

    def _cc(self, dict_key):
        """ Alias for protocol.convert_case """
        return self.protocol.convert_case(dict_key)

    def _parse_date_time_time_zone(self, date_time_time_zone):
        """ Parses and convert to protocol timezone a dateTimeTimeZone resource
        This resource is a dict with a date time and a windows timezone
        This is a common structure on Microsoft apis so it's included here.
        """
        if date_time_time_zone is None:
            return None

        local_tz = self.protocol.timezone
        if isinstance(date_time_time_zone, dict):
            try:
                timezone = pytz.timezone(
                    get_iana_tz(date_time_time_zone.get(self._cc('timeZone'), 'UTC')))
            except pytz.UnknownTimeZoneError:
                timezone = local_tz
            date_time = date_time_time_zone.get(self._cc('dateTime'), None)
            try:
                date_time = timezone.localize(parse(date_time)) if date_time else None
            except OverflowError as e:
                log.debug('Could not parse dateTimeTimeZone: {}. Error: {}'.format(date_time_time_zone, str(e)))
                date_time = None

            if date_time and timezone != local_tz:
                date_time = date_time.astimezone(local_tz)
        else:
            # Outlook v1.0 api compatibility (fallback to datetime string)
            try:
                date_time = local_tz.localize(parse(date_time_time_zone)) if date_time_time_zone else None
            except Exception as e:
                log.debug('Could not parse dateTimeTimeZone: {}. Error: {}'.format(date_time_time_zone, str(e)))
                date_time = None

        return date_time

    def _build_date_time_time_zone(self, date_time):
        """ Converts a datetime to a dateTimeTimeZone resource """
        timezone = date_time.tzinfo.zone if date_time.tzinfo is not None else None
        return {
            self._cc('dateTime'): date_time.strftime('%Y-%m-%dT%H:%M:%S'),
            self._cc('timeZone'): get_windows_tz(timezone or self.protocol.timezone)
        }

    def new_query(self, attribute=None):
        """ Create a new query to filter results

        :param str attribute: attribute to apply the query for
        :return: new Query
        :rtype: Query
        """
        return Query(attribute=attribute, protocol=self.protocol)

    q = new_query  # alias for new query


class Pagination(ApiComponent):
    """ Utility class that allows batching requests to the server """

    def __init__(self, *, parent=None, data=None, constructor=None,
                 next_link=None, limit=None, **kwargs):
        """ Returns an iterator that returns data until it's exhausted.
        Then will request more data (same amount as the original request)
        to the server until this data is exhausted as well.
        Stops when no more data exists or limit is reached.

        :param parent: the parent class. Must implement attributes:
         con, api_version, main_resource
        :param data: the start data to be return
        :param constructor: the data constructor for the next batch.
         It can be a function.
        :param str next_link: the link to request more data to
        :param int limit: when to stop retrieving more data
        :param kwargs: any extra key-word arguments to pass to the
         construtctor.
        """
        if parent is None:
            raise ValueError('Parent must be another Api Component')

        super().__init__(protocol=parent.protocol,
                         main_resource=parent.main_resource)

        self.parent = parent
        self.con = parent.con
        self.constructor = constructor
        self.next_link = next_link
        self.limit = limit
        self.data = data = list(data) if data else []

        data_count = len(data)
        if limit and limit < data_count:
            self.data_count = limit
            self.total_count = limit
        else:
            self.data_count = data_count
            self.total_count = data_count
        self.state = 0
        self.extra_args = kwargs

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if callable(self.constructor) and not isinstance(
                self.constructor, type):
            return 'Pagination Iterator'
        else:
            return "'{}' Iterator".format(
                self.constructor.__name__ if self.constructor else 'Unknown')

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
            # Everything  from cloud must be passed as self._cloud_data_key
            self.data = []
            kwargs = {}
            kwargs.update(self.extra_args)
            if callable(self.constructor) and not isinstance(self.constructor, type):
                for value in data:
                    kwargs[self._cloud_data_key] = value
                    self.data.append(self.constructor(value)(parent=self.parent, **kwargs))
            else:
                for value in data:
                    kwargs[self._cloud_data_key] = value
                    self.data.append(self.constructor(parent=self.parent, **kwargs))
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
        'end': 'end/DateTime',
        'flag': 'flag/flagStatus'
    }

    def __init__(self, attribute=None, *, protocol):
        """ Build a query to apply OData filters
        https://docs.microsoft.com/en-us/graph/query-parameters

        :param str attribute: attribute to apply the query for
        :param Protocol protocol: protocol to use for connecting
        """
        self.protocol = protocol() if isinstance(protocol, type) else protocol
        self._attribute = None
        self._chain = None
        self.new(attribute)
        self._negation = False
        self._filters = []  # store all the filters
        self._order_by = OrderedDict()
        self._selects = set()
        self._expands = set()
        self._search = None

    def __str__(self):
        return 'Filter: {}\nOrder: {}\nSelect: {}\nExpand: {}\nSearch: {}'.format(self.get_filters(),
                                                                                  self.get_order(),
                                                                                  self.get_selects(),
                                                                                  self.get_expands(),
                                                                                  self._search)

    def __repr__(self):
        return self.__str__()

    @fluent
    def select(self, *attributes):
        """ Adds the attribute to the $select parameter

        :param str attributes: the attributes tuple to select.
         If empty, the on_attribute previously set is added.
        :rtype: Query
        """
        if attributes:
            for attribute in attributes:
                attribute = self.protocol.convert_case(
                    attribute) if attribute and isinstance(attribute,
                                                           str) else None
                if attribute:
                    if '/' in attribute:
                        # only parent attribute can be selected
                        attribute = attribute.split('/')[0]
                    self._selects.add(attribute)
        else:
            if self._attribute:
                self._selects.add(self._attribute)

        return self

    @fluent
    def expand(self, *relationships):
        """ Adds the relationships (e.g. "event" or "attachments")
        that should be expanded with the $expand parameter
        Important: The ApiComponent using this should know how to handle this relationships.
            eg: Message knows how to handle attachments, and event (if it's an EventMessage).
        Important: When using expand on multi-value relationships a max of 20 items will be returned.
        :param str relationships: the relationships tuple to expand.
        :rtype: Query
        """

        for relationship in relationships:
            if relationship == 'event':
                relationship = '{}/event'.format(self.protocol.get_service_keyword('event_message_type'))
            self._expands.add(relationship)

        return self

    @fluent
    def search(self, text):
        """
        Perform a search.
        Not from graph docs:
         You can currently search only message and person collections.
         A $search request returns up to 250 results.
         You cannot use $filter or $orderby in a search request.
        :param str text: the text to search
        :return: the Query instance
        """
        if text is None:
            self._search = None
        else:
            # filters an order are not allowed
            self.clear_filters()
            self.clear_order()
            self._search = '"{}"'.format(text)

        return self

    def as_params(self):
        """ Returns the filters, orders, select, expands and search as query parameters

        :rtype: dict
        """
        params = {}
        if self.has_filters:
            params['$filter'] = self.get_filters()
        if self.has_order:
            params['$orderby'] = self.get_order()
        if self.has_selects:
            params['$select'] = self.get_selects()
        if self.has_expands:
            params['$expand'] = self.get_expands()
        if self._search:
            params['$search'] = self._search
            params.pop('$filter', None)
            params.pop('$orderby', None)
        return params

    @property
    def has_filters(self):
        """ Whether the query has filters or not

        :rtype: bool
        """
        return bool(self._filters)

    @property
    def has_order(self):
        """ Whether the query has order_by or not

        :rtype: bool
        """
        return bool(self._order_by)

    @property
    def has_selects(self):
        """ Whether the query has select filters or not

        :rtype: bool
        """
        return bool(self._selects)

    @property
    def has_expands(self):
        """ Whether the query has relationships that should be expanded or not

         :rtype: bool
        """
        return bool(self._expands)

    def get_filters(self):
        """ Returns the result filters

        :rtype: str or None
        """
        if self._filters:
            filters_list = self._filters
            if isinstance(filters_list[-1], Enum):
                filters_list = filters_list[:-1]
            return ' '.join(
                [fs.value if isinstance(fs, Enum) else fs[1] for fs in
                 filters_list]).strip()
        else:
            return None

    def get_order(self):
        """ Returns the result order by clauses

        :rtype: str or None
        """
        # first get the filtered attributes in order as they must appear
        # in the order_by first
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

        filter_order_clauses.update(
            order_by_dict)  # append any remaining order_by clause

        if filter_order_clauses:
            return ','.join(['{} {}'.format(attribute,
                                            direction if direction else '')
                            .strip()
                             for attribute, direction in
                             filter_order_clauses.items()])
        else:
            return None

    def get_selects(self):
        """ Returns the result select clause

        :rtype: str or None
        """
        if self._selects:
            return ','.join(self._selects)
        else:
            return None

    def get_expands(self):
        """ Returns the result expand clause

         :rtype: str or None
        """
        if self._expands:
            return ','.join(self._expands)
        else:
            return None

    def _get_mapping(self, attribute):
        if attribute:
            mapping = self._mapping.get(attribute)
            if mapping:
                attribute = '/'.join(
                    [self.protocol.convert_case(step) for step in
                     mapping.split('/')])
            else:
                attribute = self.protocol.convert_case(attribute)
            return attribute
        return None

    @fluent
    def new(self, attribute, operation=ChainOperator.AND):
        """ Combine with a new query

        :param str attribute: attribute of new query
        :param ChainOperator operation: operation to combine to new query
        :rtype: Query
        """
        if isinstance(operation, str):
            operation = ChainOperator(operation)
        self._chain = operation
        self._attribute = self._get_mapping(attribute) if attribute else None
        self._negation = False
        return self

    def clear_filters(self):
        """ Clear filters """
        self._filters = []

    def clear_order(self):
        """ Clears any order commands """
        self._order_by = OrderedDict()

    @fluent
    def clear(self):
        """ Clear everything

        :rtype: Query
        """
        self._filters = []
        self._order_by = OrderedDict()
        self._selects = set()
        self._negation = False
        self._attribute = None
        self._chain = None
        self._search = None

        return self

    @fluent
    def negate(self):
        """ Apply a not operator

        :rtype: Query
        """
        self._negation = not self._negation
        return self

    @fluent
    def chain(self, operation=ChainOperator.AND):
        """ Start a chain operation

        :param ChainOperator, str operation: how to combine with a new one
        :rtype: Query
        """
        if isinstance(operation, str):
            operation = ChainOperator(operation)
        self._chain = operation
        return self

    @fluent
    def on_attribute(self, attribute):
        """ Apply query on attribute, to be used along with chain()

        :param str attribute: attribute name
        :rtype: Query
        """
        self._attribute = self._get_mapping(attribute)
        return self

    def remove_filter(self, filter_attr):
        """ Removes a filter given the attribute name """
        filter_attr = self._get_mapping(filter_attr)
        new_filters = []
        remove_chain = False

        for flt in self._filters:
            if isinstance(flt, tuple):
                if flt[0] == filter_attr:
                    remove_chain = True
                else:
                    new_filters.append(flt)
            else:
                # this is a ChainOperator
                if remove_chain is False:
                    new_filters.append(flt)
                else:
                    remove_chain = False

        self._filters = new_filters

    def _add_filter(self, *filter_data):
        if self._attribute:
            if self._filters and not isinstance(self._filters[-1],
                                                ChainOperator):
                self._filters.append(self._chain)
            self._filters.append((self._attribute, filter_data[0], filter_data[1]))
        else:
            raise ValueError(
                'Attribute property needed. call on_attribute(attribute) '
                'or new(attribute)')

    def _parse_filter_word(self, word):
        """ Converts the word parameter into the correct format """
        if isinstance(word, str):
            word = "'{}'".format(word)
        elif isinstance(word, dt.date):
            if isinstance(word, dt.datetime):
                if word.tzinfo is None:
                    # if it's a naive datetime, localize the datetime.
                    word = self.protocol.timezone.localize(
                        word)  # localize datetime into local tz
                if word.tzinfo != pytz.utc:
                    word = word.astimezone(
                        pytz.utc)  # transform local datetime to utc
            if '/' in self._attribute:
                # TODO: this is a fix for the case when the parameter
                #  filtered is a string instead a dateTimeOffset
                #  but checking the '/' is not correct, but it will
                #  differentiate for now the case on events:
                #  start/dateTime (date is a string here) from
                #  the case on other dates such as
                #  receivedDateTime (date is a dateTimeOffset)
                word = "'{}'".format(
                    word.isoformat())  # convert datetime to isoformat.
            else:
                word = "{}".format(
                    word.isoformat())  # convert datetime to isoformat
        elif isinstance(word, bool):
            word = str(word).lower()
        return word

    @staticmethod
    def _prepare_sentence(attribute, operation, word, negation=False):
        negation = 'not' if negation else ''
        attrs = (negation, attribute, operation, word)
        return '{} {} {} {}'.format(negation, attribute, operation, word).strip(), attrs

    @fluent
    def logical_operator(self, operation, word):
        """ Apply a logical operator

        :param str operation: how to combine with a new one
        :param word: other parameter for the operation
         (a = b) would be like a.logical_operator('eq', 'b')
        :rtype: Query
        """
        word = self._parse_filter_word(word)
        self._add_filter(
            *self._prepare_sentence(self._attribute, operation, word,
                                    self._negation))
        return self

    @fluent
    def equals(self, word):
        """ Add a equals check

        :param word: word to compare with
        :rtype: Query
        """
        return self.logical_operator('eq', word)

    @fluent
    def unequal(self, word):
        """ Add a unequals check

        :param word: word to compare with
        :rtype: Query
        """
        return self.logical_operator('ne', word)

    @fluent
    def greater(self, word):
        """ Add a greater than check

        :param word: word to compare with
        :rtype: Query
        """
        return self.logical_operator('gt', word)

    @fluent
    def greater_equal(self, word):
        """ Add a greater than or equal to check

        :param word: word to compare with
        :rtype: Query
        """
        return self.logical_operator('ge', word)

    @fluent
    def less(self, word):
        """ Add a less than check

        :param word: word to compare with
        :rtype: Query
        """
        return self.logical_operator('lt', word)

    @fluent
    def less_equal(self, word):
        """ Add a less than or equal to check

        :param word: word to compare with
        :rtype: Query
        """
        return self.logical_operator('le', word)

    @staticmethod
    def _prepare_function(function_name, attribute, word, negation=False):
        negation = 'not' if negation else ''
        attrs = (negation, attribute, function_name, word)
        return "{} {}({}, {})".format(negation, function_name, attribute, word).strip(), attrs

    @fluent
    def function(self, function_name, word):
        """ Apply a function on given word

        :param str function_name: function to apply
        :param str word: word to apply function on
        :rtype: Query
        """
        word = self._parse_filter_word(word)

        self._add_filter(
            *self._prepare_function(function_name, self._attribute, word,
                                    self._negation))
        return self

    @fluent
    def contains(self, word):
        """ Adds a contains word check

        :param str word: word to check
        :rtype: Query
        """
        return self.function('contains', word)

    @fluent
    def startswith(self, word):
        """ Adds a startswith word check

        :param str word: word to check
        :rtype: Query
        """
        return self.function('startswith', word)

    @fluent
    def endswith(self, word):
        """ Adds a endswith word check

        :param str word: word to check
        :rtype: Query
        """
        return self.function('endswith', word)

    @fluent
    def iterable(self, iterable_name, *, collection, attribute, word, func=None,
                 operation=None):
        """ Performs a filter with the OData 'iterable_name' keyword
        on the collection

        For example:
        q.iterable('any', collection='email_addresses', attribute='address',
        operation='eq', word='george@best.com')

        will transform to a filter such as:
        emailAddresses/any(a:a/address eq 'george@best.com')

        :param str iterable_name: the OData name of the iterable
        :param str collection: the collection to apply the any keyword on
        :param str attribute: the attribute of the collection to check
        :param str word: the word to check
        :param str func: the logical function to apply to the attribute inside
         the collection
        :param str operation: the logical operation to apply to the attribute
         inside the collection
        :rtype: Query
        """

        if func is None and operation is None:
            raise ValueError('Provide a function or an operation to apply')
        elif func is not None and operation is not None:
            raise ValueError(
                'Provide either a function or an operation but not both')

        current_att = self._attribute
        self._attribute = iterable_name

        word = self._parse_filter_word(word)
        collection = self._get_mapping(collection)
        attribute = self._get_mapping(attribute)

        if func is not None:
            sentence = self._prepare_function(func, attribute, word)
        else:
            sentence = self._prepare_sentence(attribute, operation, word)

        filter_str, attrs = sentence

        filter_data = '{}/{}(a:a/{})'.format(collection, iterable_name, filter_str), attrs
        self._add_filter(*filter_data)

        self._attribute = current_att

        return self

    @fluent
    def any(self, *, collection, attribute, word, func=None, operation=None):
        """ Performs a filter with the OData 'any' keyword on the collection

        For example:
        q.any(collection='email_addresses', attribute='address',
        operation='eq', word='george@best.com')

        will transform to a filter such as:

        emailAddresses/any(a:a/address eq 'george@best.com')

        :param str collection: the collection to apply the any keyword on
        :param str attribute: the attribute of the collection to check
        :param str word: the word to check
        :param str func: the logical function to apply to the attribute
         inside the collection
        :param str operation: the logical operation to apply to the
         attribute inside the collection
        :rtype: Query
        """

        return self.iterable('any', collection=collection, attribute=attribute,
                             word=word, func=func, operation=operation)

    @fluent
    def all(self, *, collection, attribute, word, func=None, operation=None):
        """ Performs a filter with the OData 'all' keyword on the collection

        For example:
        q.any(collection='email_addresses', attribute='address',
        operation='eq', word='george@best.com')

        will transform to a filter such as:

        emailAddresses/all(a:a/address eq 'george@best.com')

        :param str collection: the collection to apply the any keyword on
        :param str attribute: the attribute of the collection to check
        :param str word: the word to check
        :param str func: the logical function to apply to the attribute
         inside the collection
        :param str operation: the logical operation to apply to the
         attribute inside the collection
        :rtype: Query
        """

        return self.iterable('all', collection=collection, attribute=attribute,
                             word=word, func=func, operation=operation)

    @fluent
    def order_by(self, attribute=None, *, ascending=True):
        """ Applies a order_by clause

        :param str attribute: attribute to apply on
        :param bool ascending: should it apply ascending order or descending
        :rtype: Query
        """
        attribute = self._get_mapping(attribute) or self._attribute
        if attribute:
            self._order_by[attribute] = None if ascending else 'desc'
        else:
            raise ValueError(
                'Attribute property needed. call on_attribute(attribute) '
                'or new(attribute)')
        return self
