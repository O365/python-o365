import calendar
import datetime as dt
import logging

# noinspection PyPep8Naming
from bs4 import BeautifulSoup as bs
from dateutil.parser import parse
from zoneinfo import ZoneInfo

from .category import Category
from .utils import (
    NEXT_LINK_KEYWORD,
    ApiComponent,
    AttachableMixin,
    BaseAttachment,
    BaseAttachments,
    CaseEnum,
    HandleRecipientsMixin,
    ImportanceLevel,
    Pagination,
    TrackerSet,
)
from .utils.windows_tz import get_windows_tz

log = logging.getLogger(__name__)

MONTH_NAMES = [calendar.month_name[x] for x in range(1, 13)]


class EventResponse(CaseEnum):
    Organizer = 'organizer'
    TentativelyAccepted = 'tentativelyAccepted'
    Accepted = 'accepted'
    Declined = 'declined'
    NotResponded = 'notResponded'


class AttendeeType(CaseEnum):
    Required = 'required'
    Optional = 'optional'
    Resource = 'resource'


class EventSensitivity(CaseEnum):
    Normal = 'normal'
    Personal = 'personal'
    Private = 'private'
    Confidential = 'confidential'


class EventShowAs(CaseEnum):
    Free = 'free'
    Tentative = 'tentative'
    Busy = 'busy'
    Oof = 'oof'
    WorkingElsewhere = 'workingElsewhere'
    Unknown = 'unknown'


class CalendarColor(CaseEnum):
    LightBlue = 'lightBlue'
    LightGreen = 'lightGreen'
    LightOrange = 'lightOrange'
    LightGray = 'lightGray'
    LightYellow = 'lightYellow'
    LightTeal = 'lightTeal'
    LightPink = 'lightPink'
    LightBrown = 'lightBrown'
    LightRed = 'lightRed'
    MaxColor = 'maxColor'
    Auto = 'auto'


class EventType(CaseEnum):
    SingleInstance = 'singleInstance'  # a normal (non-recurring) event
    Occurrence = 'occurrence'  # all the other recurring events that is not the first one (seriesMaster)
    Exception = 'exception'  # ?
    SeriesMaster = 'seriesMaster'  # the first recurring event of the series


class OnlineMeetingProviderType(CaseEnum):
    Unknown = 'unknown'
    TeamsForBusiness = 'teamsForBusiness'
    SkypeForBusiness = 'skypeForBusiness'
    SkypeForConsumer = 'skypeForConsumer'


class EventAttachment(BaseAttachment):
    _endpoints = {'attach': '/events/{id}/attachments'}


class EventAttachments(BaseAttachments):
    _endpoints = {
        'attachments': '/events/{id}/attachments',
        'attachment': '/events/{id}/attachments/{ida}',
        'create_upload_session': '/events/{id}/attachments/createUploadSession'
    }

    _attachment_constructor = EventAttachment


class DailyEventFrequency:
    def __init__(self, recurrence_type, interval):
        self.recurrence_type = recurrence_type
        self.interval = interval


# noinspection PyAttributeOutsideInit
class EventRecurrence(ApiComponent):
    def __init__(self, event, recurrence=None):
        """ A representation of an event recurrence properties

        :param Event event: event object
        :param dict recurrence: recurrence information
        """
        super().__init__(protocol=event.protocol,
                         main_resource=event.main_resource)

        self._event = event
        recurrence = recurrence or {}
        # recurrence pattern
        recurrence_pattern = recurrence.get(self._cc('pattern'), {})

        self.__interval = recurrence_pattern.get(self._cc('interval'), None)
        self.__days_of_week = recurrence_pattern.get(self._cc('daysOfWeek'),
                                                     set())
        self.__first_day_of_week = recurrence_pattern.get(
            self._cc('firstDayOfWeek'), None)
        if 'type' in recurrence_pattern.keys():
            if 'weekly' not in recurrence_pattern['type'].lower():
                self.__first_day_of_week = None

        self.__day_of_month = recurrence_pattern.get(self._cc('dayOfMonth'),
                                                     None)
        self.__month = recurrence_pattern.get(self._cc('month'), None)
        self.__index = recurrence_pattern.get(self._cc('index'), 'first')

        # recurrence range
        recurrence_range = recurrence.get(self._cc('range'), {})

        self.__occurrences = recurrence_range.get(
            self._cc('numberOfOccurrences'), None)
        self.__start_date = recurrence_range.get(self._cc('startDate'), None)
        self.__end_date = recurrence_range.get(self._cc('endDate'), None)
        self.__recurrence_time_zone = recurrence_range.get(
            self._cc('recurrenceTimeZone'),
            get_windows_tz(self.protocol.timezone))
        # time and time zones are not considered in recurrence ranges...
        # I don't know why 'recurrenceTimeZone' is present here
        # Sending a startDate datetime to the server results in an Error:
        # Cannot convert the literal 'datetime' to the expected type 'Edm.Date'
        if recurrence_range:
            self.__start_date = parse(
                self.__start_date).date() if self.__start_date else None
            self.__end_date = parse(
                self.__end_date).date() if self.__end_date else None

    def __repr__(self):
        if not self.__interval:
            return 'No recurrence enabled'

        pattern = 'Daily: every {} day{}'.format(
            self.__interval,
            's' if self.__interval != 1 else '')
        if self.__days_of_week:
            days = ' or '.join(list(self.__days_of_week))
            pattern = 'Relative Monthly: {} {} every {} month{}'.format(
                self.__index,
                days,
                self.__interval,
                's' if self.__interval != 1 else '')
            if self.__first_day_of_week:
                pattern = 'Weekly: every {} week{} on {}'.format(
                    self.__interval,
                    's' if self.__interval != 1 else '',
                    days)
            elif self.__month:
                pattern = ('Relative Yearly: {} {} every {} year{} on {}'
                           ''.format(
                    self.__index,
                    days,
                    self.__interval,
                    's' if self.__interval != 1 else '',
                    MONTH_NAMES[self.__month - 1]))
        elif self.__day_of_month:
            pattern = ('Absolute Monthly: on day {} every {} month{}'
                       ''.format(
                self.__day_of_month,
                self.__interval,
                's' if self.__interval != 1 else ''))
            if self.__month:
                pattern = ('Absolute Yearly: on {} {} every {} year/s'
                           ''.format(MONTH_NAMES[self.__month - 1],
                                     self.__day_of_month,
                                     self.__interval))

        r_range = ''
        if self.__start_date:
            r_range = 'Starting on {}'.format(self.__start_date)
            ends_on = 'with no end'
            if self.__end_date:
                ends_on = 'ending on {}'.format(self.__end_date)
            elif self.__occurrences:
                ends_on = 'up to {} occurrence{}'.format(
                    self.__occurrences,
                    's' if self.__occurrences != 1 else '')
            r_range = '{} {}'.format(r_range, ends_on)
        return '{}. {}'.format(pattern, r_range)

    def __str__(self):
        return self.__repr__()

    def __bool__(self):
        return bool(self.__interval)

    def _track_changes(self):
        """ Update the track_changes on the event to reflect a needed
        update on this field """
        self._event._track_changes.add('recurrence')

    @property
    def interval(self):
        """ Repeat interval for the event

        :getter: Get the current interval
        :setter: Update to a new interval
        :type: int
        """
        return self.__interval

    @interval.setter
    def interval(self, value):
        self.__interval = value
        self._track_changes()

    @property
    def days_of_week(self):
        """ Days in week to repeat

        :getter: Get the current list of days
        :setter: Set the list of days to repeat
        :type: set(str)
        """
        return self.__days_of_week

    @days_of_week.setter
    def days_of_week(self, value):
        self.__days_of_week = value
        self._track_changes()

    @property
    def first_day_of_week(self):
        """ Which day to consider start of the week

        :getter: Get the current start of week
        :setter: Set the start day of week
        :type: str
        """
        return self.__first_day_of_week

    @first_day_of_week.setter
    def first_day_of_week(self, value):
        self.__first_day_of_week = value
        self._track_changes()

    @property
    def day_of_month(self):
        """ Repeat on this day of month

        :getter: Get the repeat day of month
        :setter: Set the repeat day of month
        :type: int
        """
        return self.__day_of_month

    @day_of_month.setter
    def day_of_month(self, value):
        self.__day_of_month = value
        self._track_changes()

    @property
    def month(self):
        """ Month of the event

        :getter: Get month
        :setter: Update month
        :type: int
        """
        return self.__month

    @month.setter
    def month(self, value):
        self.__month = value
        self._track_changes()

    @property
    def index(self):
        """ Index

        :getter: Get index
        :setter: Set index
        :type: str
        """
        return self.__index

    @index.setter
    def index(self, value):
        self.__index = value
        self._track_changes()

    @property
    def occurrences(self):
        """ No. of occurrences

        :getter: Get the no. of occurrences
        :setter: Set the no. of occurrences
        :type: int
        """
        return self.__occurrences

    @occurrences.setter
    def occurrences(self, value):
        self.__occurrences = value
        self._track_changes()

    @property
    def recurrence_time_zone(self):
        """ Timezone to consider for repeating

        :getter: Get the timezone
        :setter: Set the timezone
        :type: str
        """
        return self.__recurrence_time_zone

    @recurrence_time_zone.setter
    def recurrence_time_zone(self, value):
        self.__recurrence_time_zone = value
        self._track_changes()

    @property
    def start_date(self):
        """ Start date of repetition

        :getter: get the start date
        :setter: set the start date
        :type: date
        """
        return self.__start_date

    @start_date.setter
    def start_date(self, value):
        if not isinstance(value, dt.date):
            raise ValueError('start_date value must be a valid date object')
        if isinstance(value, dt.datetime):
            value = value.date()
        self.__start_date = value
        self._track_changes()

    @property
    def end_date(self):
        """ End date of repetition

        :getter: get the end date
        :setter: set the end date
        :type: date
        """
        return self.__end_date

    @end_date.setter
    def end_date(self, value):
        if not isinstance(value, dt.date):
            raise ValueError('end_date value must be a valid date object')
        if isinstance(value, dt.datetime):
            value = value.date()
        self.__end_date = value
        self._track_changes()

    def to_api_data(self):
        """ Returns a dict to communicate with the server

        :rtype: dict
        """
        data = {}
        # recurrence pattern
        if self.__interval and isinstance(self.__interval, int):
            recurrence_pattern = data[self._cc('pattern')] = {}
            recurrence_pattern[self._cc('type')] = 'daily'
            recurrence_pattern[self._cc('interval')] = self.__interval
            if self.__days_of_week and isinstance(self.__days_of_week,
                                                  (list, tuple, set)):
                recurrence_pattern[self._cc('type')] = 'relativeMonthly'
                recurrence_pattern[self._cc('daysOfWeek')] = list(
                    self.__days_of_week)
                if self.__first_day_of_week:
                    recurrence_pattern[self._cc('type')] = 'weekly'
                    recurrence_pattern[
                        self._cc('firstDayOfWeek')] = self.__first_day_of_week
                elif self.__month and isinstance(self.__month, int):
                    recurrence_pattern[self._cc('type')] = 'relativeYearly'
                    recurrence_pattern[self._cc('month')] = self.__month
                    if self.__index:
                        recurrence_pattern[self._cc('index')] = self.__index
                else:
                    if self.__index:
                        recurrence_pattern[self._cc('index')] = self.__index

            elif self.__day_of_month and isinstance(self.__day_of_month, int):
                recurrence_pattern[self._cc('type')] = 'absoluteMonthly'
                recurrence_pattern[self._cc('dayOfMonth')] = self.__day_of_month
                if self.__month and isinstance(self.__month, int):
                    recurrence_pattern[self._cc('type')] = 'absoluteYearly'
                    recurrence_pattern[self._cc('month')] = self.__month

        # recurrence range
        if self.__start_date:
            recurrence_range = data[self._cc('range')] = {}
            recurrence_range[self._cc('type')] = 'noEnd'
            recurrence_range[
                self._cc('startDate')] = self.__start_date.isoformat()
            recurrence_range[
                self._cc('recurrenceTimeZone')] = self.__recurrence_time_zone

            if self.__end_date:
                recurrence_range[self._cc('type')] = 'endDate'
                recurrence_range[
                    self._cc('endDate')] = self.__end_date.isoformat()
            elif self.__occurrences is not None and isinstance(
                    self.__occurrences,
                    int):
                recurrence_range[self._cc('type')] = 'numbered'
                recurrence_range[
                    self._cc('numberOfOccurrences')] = self.__occurrences

        return data

    def _clear_pattern(self):
        """ Clears this event recurrence """
        # pattern group
        self.__interval = None
        self.__days_of_week = set()
        self.__first_day_of_week = None
        self.__day_of_month = None
        self.__month = None
        self.__index = 'first'
        # range group
        self.__start_date = None
        self.__end_date = None
        self.__occurrences = None

    def set_range(self, start=None, end=None, occurrences=None):
        """ Set the range of recurrence

        :param date start: Start date of repetition
        :param date end: End date of repetition
        :param int occurrences: no of occurrences
        """
        if start is None:
            if self.__start_date is None:
                self.__start_date = dt.date.today()
        else:
            self.start_date = start

        if end:
            self.end_date = end
        elif occurrences:
            self.__occurrences = occurrences
        self._track_changes()

    def set_daily(self, interval, **kwargs):
        """ Set to repeat every x no. of days

        :param int interval: no. of days to repeat at
        :keyword date start: Start date of repetition (kwargs)
        :keyword date end: End date of repetition (kwargs)
        :keyword int occurrences: no of occurrences (kwargs)
        """
        self._clear_pattern()
        self.__interval = interval
        self.set_range(**kwargs)

    def set_weekly(self, interval, *, days_of_week, first_day_of_week,
                   **kwargs):
        """ Set to repeat every week on specified days for every x no. of days

        :param int interval: no. of days to repeat at
        :param str first_day_of_week: starting day for a week
        :param list[str] days_of_week: list of days of the week to repeat
        :keyword date start: Start date of repetition (kwargs)
        :keyword date end: End date of repetition (kwargs)
        :keyword int occurrences: no of occurrences (kwargs)
        """
        self.set_daily(interval, **kwargs)
        self.__days_of_week = set(days_of_week)
        self.__first_day_of_week = first_day_of_week

    def set_monthly(self, interval, *, day_of_month=None, days_of_week=None,
                    index=None, **kwargs):
        """ Set to repeat every month on specified days for every x no. of days

        :param int interval: no. of days to repeat at
        :param int day_of_month: repeat day of a month
        :param list[str] days_of_week: list of days of the week to repeat
        :param index: index
        :keyword date start: Start date of repetition (kwargs)
        :keyword date end: End date of repetition (kwargs)
        :keyword int occurrences: no of occurrences (kwargs)
        """
        if not day_of_month and not days_of_week:
            raise ValueError('Must provide day_of_month or days_of_week values')
        if day_of_month and days_of_week:
            raise ValueError('Must provide only one of the two options')
        self.set_daily(interval, **kwargs)
        if day_of_month:
            self.__day_of_month = day_of_month
        elif days_of_week:
            self.__days_of_week = set(days_of_week)
            if index:
                self.__index = index

    def set_yearly(self, interval, month, *, day_of_month=None,
                   days_of_week=None, index=None, **kwargs):
        """ Set to repeat every month on specified days for every x no. of days

        :param int interval: no. of days to repeat at
        :param int month: month to repeat
        :param int day_of_month: repeat day of a month
        :param list[str] days_of_week: list of days of the week to repeat
        :param index: index
        :keyword date start: Start date of repetition (kwargs)
        :keyword date end: End date of repetition (kwargs)
        :keyword int occurrences: no of occurrences (kwargs)
        """
        self.set_monthly(interval, day_of_month=day_of_month,
                         days_of_week=days_of_week, index=index, **kwargs)
        self.__month = month


class ResponseStatus(ApiComponent):
    """ An event response status (status, time) """

    def __init__(self, parent, response_status):
        """ An event response status (status, time)

        :param parent: parent of this
        :type parent: Attendees or Event
        :param dict response_status: status info frm cloud
        """
        super().__init__(protocol=parent.protocol,
                         main_resource=parent.main_resource)
        self.status = response_status.get(self._cc('response'), 'none')
        self.status = None if self.status == 'none' else EventResponse.from_value(self.status)
        if self.status:
            self.response_time = response_status.get(self._cc('time'), None)
            if self.response_time == '0001-01-01T00:00:00Z':
                # consider there's no response time
                # this way we don't try to convert this Iso 8601 datetime to the
                #  local timezone which generated parse errors
                self.response_time = None
            if self.response_time:
                try:
                    self.response_time = parse(self.response_time).astimezone(self.protocol.timezone)
                except OverflowError:
                    log.debug(f"Couldn't parse event response time: {self.response_time}")
                    self.response_time = None
        else:
            self.response_time = None

    def __repr__(self):
        return self.status or 'None'

    def __str__(self):
        return self.__repr__()


class Attendee:
    """ A Event attendee """

    def __init__(self, address, *, name=None, attendee_type=None,
                 response_status=None, event=None):
        """ Create a event attendee

        :param str address: email address of the attendee
        :param str name: name of the attendee
        :param AttendeeType attendee_type: requirement of attendee
        :param Response response_status: response status requirement
        :param Event event: event for which to assign the attendee
        """
        self._untrack = True
        self._address = address
        self._name = name
        self._event = event
        if isinstance(response_status, ResponseStatus):
            self.__response_status = response_status
        else:
            self.__response_status = None
        self.__attendee_type = AttendeeType.Required
        if attendee_type:
            self.attendee_type = attendee_type
        self._untrack = False

    def __repr__(self):
        if self.name:
            return '{}: {} ({})'.format(self.attendee_type.name, self.name,
                                        self.address)
        else:
            return '{}: {}'.format(self.attendee_type.name, self.address)

    def __str__(self):
        return self.__repr__()

    @property
    def address(self):
        """ Email address

        :getter: Get the email address of attendee
        :setter: Set the email address of attendee
        :type: str
        """
        return self._address

    @address.setter
    def address(self, value):
        self._address = value
        self._name = ''
        self._track_changes()

    @property
    def name(self):
        """ Name

        :getter: Get the name of attendee
        :setter: Set the name of attendee
        :type: str
        """
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._track_changes()

    def _track_changes(self):
        """ Update the track_changes on the event to reflect a
        needed update on this field """
        if self._untrack is False:
            self._event._track_changes.add('attendees')

    @property
    def response_status(self):
        """ Response status of the attendee

        :type: ResponseStatus
        """
        return self.__response_status

    @property
    def attendee_type(self):
        """ Requirement of the attendee

        :getter: Get the requirement of attendee
        :setter: Set the requirement of attendee
        :type: AttendeeType
        """
        return self.__attendee_type

    @attendee_type.setter
    def attendee_type(self, value):
        if isinstance(value, AttendeeType):
            self.__attendee_type = value
        else:
            self.__attendee_type = AttendeeType.from_value(value)
        self._track_changes()


class Attendees(ApiComponent):
    """ A Collection of Attendees """

    def __init__(self, event, attendees=None):
        """ Create a collection of attendees

        :param Event event: event for which to assign the attendees
        :param attendees: list of attendees to add
        :type attendees: str or tuple(str, str) or Attendee or list[str] or
         list[tuple(str,str)] or list[Attendee]
        """
        super().__init__(protocol=event.protocol,
                         main_resource=event.main_resource)
        self._event = event
        self.__attendees = []
        self.untrack = True
        if attendees:
            self.add(attendees)
        self.untrack = False

    def __iter__(self):
        return iter(self.__attendees)

    def __getitem__(self, key):
        return self.__attendees[key]

    def __contains__(self, item):
        return item in {attendee.address for attendee in self.__attendees}

    def __len__(self):
        return len(self.__attendees)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Attendees Count: {}'.format(len(self.__attendees))

    def clear(self):
        """ Clear the attendees list """
        self.__attendees = []
        self._track_changes()

    def _track_changes(self):
        """ Update the track_changes on the event to reflect a needed
        update on this field """
        if self.untrack is False:
            self._event._track_changes.add('attendees')

    def add(self, attendees):
        """ Add attendees to the parent event

        :param attendees: list of attendees to add
        :type attendees: str or tuple(str, str) or Attendee or list[str] or
         list[tuple(str,str)] or list[Attendee]
        """
        if attendees:
            if isinstance(attendees, str):
                self.__attendees.append(
                    Attendee(address=attendees, event=self._event))
                self._track_changes()
            elif isinstance(attendees, Attendee):
                self.__attendees.append(attendees)
                self._track_changes()
            elif isinstance(attendees, tuple):
                name, address = attendees
                if address:
                    self.__attendees.append(
                        Attendee(address=address, name=name, event=self._event))
                    self._track_changes()
            elif isinstance(attendees, list):
                for attendee in attendees:
                    self.add(attendee)
            elif isinstance(attendees,
                            dict) and self._cloud_data_key in attendees:
                attendees = attendees.get(self._cloud_data_key)
                for attendee in attendees:
                    email = attendee.get(self._cc('emailAddress'), {})
                    address = email.get(self._cc('address'), None)
                    if address:
                        name = email.get(self._cc('name'), None)
                        # default value
                        attendee_type = attendee.get(self._cc('type'),
                                                     'required')
                        self.__attendees.append(
                            Attendee(address=address, name=name,
                                     attendee_type=attendee_type,
                                     event=self._event,
                                     response_status=
                                     ResponseStatus(parent=self,
                                                    response_status=
                                                    attendee.get(
                                                        self._cc('status'),
                                                        {}))))
            else:
                raise ValueError('Attendees must be an address string, an '
                                 'Attendee instance, a (name, address) '
                                 'tuple or a list')

    def remove(self, attendees):
        """ Remove the provided attendees from the event

        :param attendees: list of attendees to add
        :type attendees: str or tuple(str, str) or Attendee or list[str] or
         list[tuple(str,str)] or list[Attendee]
        """
        if isinstance(attendees, (list, tuple)):
            attendees = {
                attendee.address if isinstance(attendee, Attendee) else attendee
                for
                attendee in attendees}
        elif isinstance(attendees, str):
            attendees = {attendees}
        elif isinstance(attendees, Attendee):
            attendees = {attendees.address}
        else:
            raise ValueError('Incorrect parameter type for attendees')

        new_attendees = []
        for attendee in self.__attendees:
            if attendee.address not in attendees:
                new_attendees.append(attendee)
        self.__attendees = new_attendees
        self._track_changes()

    def to_api_data(self):
        """ Returns a dict to communicate with the server

        :rtype: dict
        """
        data = []
        for attendee in self.__attendees:
            if attendee.address:
                att_data = {
                    self._cc('emailAddress'): {
                        self._cc('address'): attendee.address,
                        self._cc('name'): attendee.name
                    },
                    self._cc('type'): self._cc(attendee.attendee_type.value)
                }
                data.append(att_data)
        return data


# noinspection PyAttributeOutsideInit
class Event(ApiComponent, AttachableMixin, HandleRecipientsMixin):
    """ A Calendar event """

    _endpoints = {
        'calendar': '/calendars/{id}',
        'event': '/events/{id}',
        'event_default': '/calendar/events',
        'event_calendar': '/calendars/{id}/events',
        'occurrences': '/events/{id}/instances',
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Create a calendar event representation

        :param parent: parent for this operation
        :type parent: Calendar or Schedule or ApiComponent
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        :param str calendar_id: id of the calender to add this event in
         (kwargs)
        :param bool download_attachments: whether or not to download attachments
         (kwargs)
        :param str subject: subject of the event (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        cc = self._cc  # alias
        # internal to know which properties need to be updated on the server
        self._track_changes = TrackerSet(casing=cc)
        self.calendar_id = kwargs.get('calendar_id', None)
        download_attachments = kwargs.get('download_attachments')
        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get(cc('id'), None)
        self.__subject = cloud_data.get(cc('subject'),
                                        kwargs.get('subject', '') or '')
        body = cloud_data.get(cc('body'), {})
        self.__body = body.get(cc('content'), '')
        self.body_type = body.get(cc('contentType'),
                                  'HTML')  # default to HTML for new messages

        self.__attendees = Attendees(event=self, attendees={
            self._cloud_data_key: cloud_data.get(cc('attendees'), [])})
        self.__categories = cloud_data.get(cc('categories'), [])

        self.__created = cloud_data.get(cc('createdDateTime'), None)
        self.__modified = cloud_data.get(cc('lastModifiedDateTime'), None)

        local_tz = self.protocol.timezone
        self.__created = parse(self.__created).astimezone(
            local_tz) if self.__created else None
        self.__modified = parse(self.__modified).astimezone(
            local_tz) if self.__modified else None

        self.__is_all_day = cloud_data.get(cc('isAllDay'), False)

        start_obj = cloud_data.get(cc('start'), {})
        self.__start = self._parse_date_time_time_zone(start_obj, self.__is_all_day)

        end_obj = cloud_data.get(cc('end'), {})
        self.__end = self._parse_date_time_time_zone(end_obj, self.__is_all_day)

        self.has_attachments = cloud_data.get(cc('hasAttachments'), False)
        self.__attachments = EventAttachments(parent=self, attachments=[])
        if self.has_attachments and download_attachments:
            self.attachments.download_attachments()
        self.__categories = cloud_data.get(cc('categories'), [])
        self.ical_uid = cloud_data.get(cc('iCalUId'), None)
        self.__importance = ImportanceLevel.from_value(
            cloud_data.get(cc('importance'), 'normal') or 'normal')
        self.is_cancelled = cloud_data.get(cc('isCancelled'), False)
        self.is_organizer = cloud_data.get(cc('isOrganizer'), True)
        self.__location = cloud_data.get(cc('location'), {})
        self.locations = cloud_data.get(cc('locations'), [])  # TODO

        self.online_meeting_url = cloud_data.get(cc('onlineMeetingUrl'), None)
        self.__is_online_meeting = cloud_data.get(cc('isOnlineMeeting'), False)
        self.__online_meeting_provider = OnlineMeetingProviderType.from_value(
            cloud_data.get(cc('onlineMeetingProvider'), 'teamsForBusiness'))
        self.online_meeting = cloud_data.get(cc('onlineMeeting'), None)
        if not self.online_meeting_url and self.is_online_meeting:
            self.online_meeting_url = self.online_meeting.get(cc('joinUrl'), None) \
                if self.online_meeting else None

        self.__organizer = self._recipient_from_cloud(
            cloud_data.get(cc('organizer'), None), field=cc('organizer'))
        self.__recurrence = EventRecurrence(event=self,
                                            recurrence=cloud_data.get(
                                                cc('recurrence'), None))
        self.__is_reminder_on = cloud_data.get(cc('isReminderOn'), True)
        self.__remind_before_minutes = cloud_data.get(
            cc('reminderMinutesBeforeStart'), 15)
        self.__response_requested = cloud_data.get(cc('responseRequested'),
                                                   True)
        self.__response_status = ResponseStatus(parent=self,
                                                response_status=cloud_data.get(
                                                    cc('responseStatus'), {}))
        self.__sensitivity = EventSensitivity.from_value(
            cloud_data.get(cc('sensitivity'), 'normal'))
        self.series_master_id = cloud_data.get(cc('seriesMasterId'), None)
        self.__show_as = EventShowAs.from_value(cloud_data.get(cc('showAs'), 'busy'))
        self.__event_type = EventType.from_value(cloud_data.get(cc('type'), 'singleInstance'))
        self.__no_forwarding = False
        self.web_link = cloud_data.get(cc('webLink'), None)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if self.start.date() == self.end.date():
            return 'Subject: {} (on: {} from: {} to: {})'.format(self.subject, self.start.date(), self.start.time(),
                                                                 self.end.time())
        else:
            return 'Subject: {} (starts: {} {} and ends: {} {})'.format(self.subject, self.start.date(),
                                                                        self.start.time(), self.end.date(),
                                                                        self.end.time())

    def __eq__(self, other):
        return self.object_id == other.object_id

    def to_api_data(self, restrict_keys=None):
        """ Returns a dict to communicate with the server

        :param restrict_keys: a set of keys to restrict the returned data to
        :rtype: dict
        """
        cc = self._cc  # alias
        if self.__location:
            if isinstance(self.__location, dict):
                location = self.__location
            else:
                location = {cc('displayName'): self.__location}
        else:
            location = {cc('displayName'): ''}

        data = {
            cc('subject'): self.__subject,
            cc('body'): {
                cc('contentType'): self.body_type,
                cc('content'): self.__body},
            cc('start'): self._build_date_time_time_zone(self.__start),
            cc('end'): self._build_date_time_time_zone(self.__end),
            cc('attendees'): self.__attendees.to_api_data(),
            cc('location'): location,
            cc('categories'): self.__categories,
            cc('isAllDay'): self.__is_all_day,
            cc('importance'): cc(self.__importance.value),
            cc('isReminderOn'): self.__is_reminder_on,
            cc('reminderMinutesBeforeStart'): self.__remind_before_minutes,
            cc('responseRequested'): self.__response_requested,
            cc('sensitivity'): cc(self.__sensitivity.value),
            cc('showAs'): cc(self.__show_as.value),
            cc('isOnlineMeeting'): cc(self.__is_online_meeting),
            cc('onlineMeetingProvider'): cc(self.__online_meeting_provider.value),
            cc("SingleValueExtendedProperties"): [
                {
                    "id": "Boolean {00020329-0000-0000-C000-000000000046} Name DoNotForward",
                    "value": cc(self.__no_forwarding),
                }
            ],
        }

        if self.__recurrence:
            data[cc('recurrence')] = self.__recurrence.to_api_data()

        if self.has_attachments:
            data[cc('attachments')] = self.__attachments.to_api_data()

        if restrict_keys:
            if 'attachments' in restrict_keys:
                self.attachments._update_attachments_to_cloud()

            for key in list(data.keys()):
                if key not in restrict_keys:
                    del data[key]
        return data

    @property
    def created(self):
        """ Created time of the event

        :rtype: datetime
        """
        return self.__created

    @property
    def modified(self):
        """ Last modified time of the event

        :rtype: datetime
        """
        return self.__modified

    @property
    def body(self):
        """ Body of the event

        :getter: Get body text
        :setter: Set body of event
        :type: str
        """
        return self.__body

    @body.setter
    def body(self, value):
        self.__body = value
        self._track_changes.add(self._cc('body'))

    @property
    def subject(self):
        """ Subject of the event

        :getter: Get subject
        :setter: Set subject of event
        :type: str
        """
        return self.__subject

    @subject.setter
    def subject(self, value):
        self.__subject = value
        self._track_changes.add(self._cc('subject'))

    @property
    def start(self):
        """ Start Time of event

        :getter: get the start time
        :setter: set the start time
        :type: datetime
        """
        return self.__start

    @start.setter
    def start(self, value):
        if not isinstance(value, dt.date):
            raise ValueError("'start' must be a valid datetime object")
        if not isinstance(value, dt.datetime):
            # force datetime
            value = dt.datetime(value.year, value.month, value.day)
        if value.tzinfo is None:
            # localize datetime
            value = value.replace(tzinfo=self.protocol.timezone)
        else:
            if not isinstance(value.tzinfo, ZoneInfo):
                raise ValueError('TimeZone data must be set using ZoneInfo objects')
        self.__start = value
        if not self.end:
            self.end = self.__start + dt.timedelta(minutes=30)
        self._track_changes.add(self._cc('start'))

    @property
    def end(self):
        """ End Time of event

        :getter: get the end time
        :setter: set the end time
        :type: datetime
        """
        return self.__end

    @end.setter
    def end(self, value):
        if not isinstance(value, dt.date):
            raise ValueError("'end' must be a valid datetime object")
        if not isinstance(value, dt.datetime):
            # force datetime
            value = dt.datetime(value.year, value.month, value.day)
        if value.tzinfo is None:
            # localize datetime
            value = value.replace(tzinfo=self.protocol.timezone)
        else:
            if not isinstance(value.tzinfo, ZoneInfo):
                raise ValueError('TimeZone data must be set using ZoneInfo objects')
        self.__end = value
        self._track_changes.add(self._cc('end'))

    @property
    def importance(self):
        """ Event Priority

        :getter: get importance of event
        :setter: set the importance of event
        :type: ImportanceLevel
        """
        return self.__importance

    @importance.setter
    def importance(self, value):
        self.__importance = (value if isinstance(value, ImportanceLevel)
                             else ImportanceLevel.from_value(value))
        self._track_changes.add(self._cc('importance'))

    @property
    def is_all_day(self):
        """ Is the event for whole day

        :getter: get the current status of is_all_day property
        :setter: set if the event is all day or not
        :type: bool
        """
        return self.__is_all_day

    @is_all_day.setter
    def is_all_day(self, value):
        self.__is_all_day = value
        if value:
            # Api requirement: start and end must be set to midnight
            # is_all_day needs event.start included in the request on updates
            # is_all_day needs event.end included in the request on updates
            start = self.__start or dt.date.today()
            end = self.__end or dt.date.today()

            if (start + dt.timedelta(hours=24)) > end:
                # Api requires that under is_all_day=True start and
                # end must be at least 24 hours away
                end = start + dt.timedelta(hours=24)

            # set to midnight
            start = dt.datetime(start.year, start.month, start.day)
            end = dt.datetime(end.year, end.month, end.day)

            self.start = start
            self.end = end
        self._track_changes.add(self._cc('isAllDay'))

    @property
    def location(self):
        """ Location of event

        :getter: get current location configured for the event
        :setter: set a location for the event
        :type: str
        """
        return self.__location

    @location.setter
    def location(self, value):
        self.__location = value
        self._track_changes.add(self._cc('location'))

    @property
    def is_reminder_on(self):
        """ Status of the Reminder

        :getter: check is reminder enabled or not
        :setter: enable or disable reminder option
        :type: bool
        """
        return self.__is_reminder_on

    @is_reminder_on.setter
    def is_reminder_on(self, value):
        self.__is_reminder_on = value
        self._track_changes.add(self._cc('isReminderOn'))
        self._track_changes.add(self._cc('reminderMinutesBeforeStart'))

    @property
    def remind_before_minutes(self):
        """ No. of minutes to remind before the meeting

        :getter: get current minutes
        :setter: set to remind before new x minutes
        :type: int
        """
        return self.__remind_before_minutes

    @remind_before_minutes.setter
    def remind_before_minutes(self, value):
        self.__is_reminder_on = True
        self.__remind_before_minutes = int(value)
        self._track_changes.add(self._cc('isReminderOn'))
        self._track_changes.add(self._cc('reminderMinutesBeforeStart'))

    @property
    def response_requested(self):
        """ Is response requested or not

        :getter: Is response requested or not
        :setter: set the event to request response or not
        :type: bool
        """
        return self.__response_requested

    @response_requested.setter
    def response_requested(self, value):
        self.__response_requested = value
        self._track_changes.add(self._cc('responseRequested'))

    @property
    def recurrence(self):
        """ Recurrence information of the event

        :rtype: EventRecurrence
        """
        return self.__recurrence

    @property
    def organizer(self):
        """ Organizer of the meeting event

        :rtype: Recipient
        """
        return self.__organizer

    @property
    def show_as(self):
        """ Show as "busy" or any other status during the event

        :getter: Current status during the event
        :setter: update show as status
        :type: EventShowAs
        """
        return self.__show_as

    @show_as.setter
    def show_as(self, value):
        self.__show_as = (value if isinstance(value, EventShowAs)
                          else EventShowAs.from_value(value))
        self._track_changes.add(self._cc('showAs'))

    @property
    def sensitivity(self):
        """ Sensitivity of the Event

        :getter: Get the current sensitivity
        :setter: Set a new sensitivity
        :type: EventSensitivity
        """
        return self.__sensitivity

    @sensitivity.setter
    def sensitivity(self, value):
        self.__sensitivity = (value if isinstance(value, EventSensitivity)
                              else EventSensitivity.from_value(value))
        self._track_changes.add(self._cc('sensitivity'))

    @property
    def response_status(self):
        """ Your response

        :rtype: ResponseStatus
        """
        return self.__response_status

    @property
    def attachments(self):
        """ List of attachments

        :rtype: EventAttachments
        """
        return self.__attachments

    @property
    def attendees(self):
        """ List of meeting attendees

        :rtype: Attendees
        """
        return self.__attendees

    @property
    def categories(self):
        """ Categories of the event

        :getter: get the list of categories
        :setter: set the list of categories
        :type: list[str]
        """
        return self.__categories

    @categories.setter
    def categories(self, value):
        if isinstance(value, list):
            self.__categories = []
            for val in value:
                if isinstance(val, Category):
                    self.__categories.append(val.name)
                else:
                    self.__categories.append(val)
        elif isinstance(value, str):
            self.__categories = [value]
        elif isinstance(value, Category):
            self.__categories = [value.name]
        else:
            raise ValueError('categories must be a list')
        self._track_changes.add(self._cc('categories'))

    @property
    def event_type(self):
        return self.__event_type

    @property
    def is_online_meeting(self):
        """ Status of the online_meeting

        :getter: check is online_meeting enabled or not
        :setter: enable or disable online_meeting option
        :type: bool
        """
        return self.__is_online_meeting

    @is_online_meeting.setter
    def is_online_meeting(self, value):
        self.__is_online_meeting = value
        self._track_changes.add(self._cc('isOnlineMeeting'))

    @property
    def online_meeting_provider(self):
        """ online_meeting_provider of event

        :getter: get current online_meeting_provider configured for the event
        :setter: set a online_meeting_provider for the event
        :type: OnlineMeetingProviderType
        """
        return self.__online_meeting_provider

    @online_meeting_provider.setter
    def online_meeting_provider(self, value):
        self.__online_meeting_provider = (value if isinstance(value, OnlineMeetingProviderType)
                                          else OnlineMeetingProviderType.from_value(value))
        self._track_changes.add(self._cc('onlineMeetingProvider'))

    @property
    def no_forwarding(self):
        return self.__no_forwarding

    @no_forwarding.setter
    def no_forwarding(self, value):
        self.__no_forwarding = value
        self._track_changes.add('SingleValueExtendedProperties')

    def get_occurrences(self, start, end, *, limit=None, query=None, order_by=None, batch=None):
        """
        Returns all the occurrences of a seriesMaster event for a specified time range.

        :type start: datetime
        :param start: the start of the time range
        :type end: datetime
        :param end: the end of the time range
        :param int limit: ax no. of events to get. Over 999 uses batch.
        :type query: Query or str
        :param query: optional. extra filters or ordes to apply to this query
        :type order_by: str
        :param order_by: orders the result set based on this condition
        :param int batch: batch size, retrieves items in
             batches allowing to retrieve more items than the limit.
        :return: a list of events
        :rtype: list[Event] or Pagination
        """
        if self.event_type != EventType.SeriesMaster:
            # you can only get occurrences if it's a seriesMaster
            return []

        url = self.build_url(
            self._endpoints.get('occurrences').format(id=self.object_id))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params = {'$top': batch if batch else limit}

        if order_by:
            params['$orderby'] = order_by

        if query:
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

        if isinstance(start, dt.date):
            # Convert an all-day date which only contains year/month/day into a datetime object
            start = dt.datetime(start.year, start.month, start.day)
        if start.tzinfo is None:
            # if it's a naive datetime, localize the datetime.
            start = start.replace(tzinfo=self.protocol.timezone)  # localize datetime into local tz

        if isinstance(end, dt.date):
            # Convert an all-day date which only contains year/month/day into a datetime object
            end = dt.datetime(end.year, end.month, end.day)
        if end.tzinfo is None:
            # if it's a naive datetime, localize the datetime.
            end = end.replace(tzinfo=self.protocol.timezone)  # localize datetime into local tz

        params[self._cc('startDateTime')] = start.isoformat()
        params[self._cc('endDateTime')] = end.isoformat()

        response = self.con.get(url, params=params)

        if not response:
            return iter(())

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        events = (self.__class__(parent=self, **{self._cloud_data_key: event})
                  for event in data.get('value', []))
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=events,
                              constructor=self.__class__,
                              next_link=next_link, limit=limit)
        else:
            return events

    def delete(self):
        """ Deletes a stored event

        :return: Success / Failure
        :rtype: bool
        """
        if self.object_id is None:
            raise RuntimeError('Attempting to delete an unsaved event')

        url = self.build_url(self._endpoints.get('event').format(id=self.object_id))

        response = self.con.delete(url)

        return bool(response)

    def save(self):
        """ Create a new event or update an existing one by checking what
        values have changed and update them on the server

        :return: Success / Failure
        :rtype: bool
        """

        if self.object_id:
            # update event
            if not self._track_changes:
                return True  # there's nothing to update
            url = self.build_url(self._endpoints.get('event').format(id=self.object_id))
            method = self.con.patch
            data = self.to_api_data(restrict_keys=self._track_changes)
        else:
            # new event
            if self.calendar_id:
                url = self.build_url(self._endpoints.get('event_calendar').format(id=self.calendar_id))
            else:
                url = self.build_url(self._endpoints.get('event_default'))
            method = self.con.post
            data = self.to_api_data()

        response = method(url, data=data)
        if not response:
            return False

        self._track_changes.clear()  # clear the tracked changes

        if not self.object_id:
            # new event
            event = response.json()

            self.object_id = event.get(self._cc('id'), None)

            self.__created = event.get(self._cc('createdDateTime'), None)
            self.__modified = event.get(self._cc('lastModifiedDateTime'), None)

            self.__created = parse(self.__created).astimezone(
                self.protocol.timezone) if self.__created else None
            self.__modified = parse(self.__modified).astimezone(
                self.protocol.timezone) if self.__modified else None

            self.ical_uid = event.get(self._cc('iCalUId'), None)
        else:
            self.__modified = dt.datetime.now().replace(tzinfo=self.protocol.timezone)

        return True

    def accept_event(self, comment=None, *, send_response=True,
                     tentatively=False):
        """ Accept the event

        :param comment: comment to add
        :param send_response: whether or not to send response back
        :param tentatively: whether acceptance is tentative
        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            raise RuntimeError("Can't accept event that doesn't exist")

        url = self.build_url(
            self._endpoints.get('event').format(id=self.object_id))
        url = url + '/tentativelyAccept' if tentatively else url + '/accept'

        data = {}
        if comment and isinstance(comment, str):
            data[self._cc('comment')] = comment
        if send_response is False:
            data[self._cc('sendResponse')] = send_response

        response = self.con.post(url, data=data or None)

        return bool(response)

    def decline_event(self, comment=None, *, send_response=True):
        """ Decline the event

        :param str comment: comment to add
        :param bool send_response: whether or not to send response back
        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            raise RuntimeError("Can't accept event that doesn't exist")

        url = self.build_url(
            self._endpoints.get('event').format(id=self.object_id))
        url = url + '/decline'

        data = {}
        if comment and isinstance(comment, str):
            data[self._cc('comment')] = comment
        if send_response is False:
            data[self._cc('sendResponse')] = send_response

        response = self.con.post(url, data=data or None)

        return bool(response)

    def cancel_event(self, comment=None, *, send_response=True):
        """ Cancel the event

        :param str comment: comment to add
        :param bool send_response: whether or not to send response back
        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            raise RuntimeError("Can't accept event that doesn't exist")

        url = self.build_url(
            self._endpoints.get('event').format(id=self.object_id))
        url = url + '/cancel'

        data = {}
        if comment and isinstance(comment, str):
            data[self._cc('comment')] = comment
        if send_response is False:
            data[self._cc('sendResponse')] = send_response

        response = self.con.post(url, data=data or None)

        return bool(response)

    def get_body_text(self):
        """ Parse the body html and returns the body text using bs4

        :return: body text
        :rtype: str
        """
        if self.body_type != 'HTML':
            return self.body

        try:
            soup = bs(self.body, 'html.parser')
        except RuntimeError:
            return self.body
        else:
            return soup.body.text

    def get_body_soup(self):
        """ Returns the beautifulsoup4 of the html body

        :return: Html body
        :rtype: BeautifulSoup
        """
        if self.body_type.upper() != 'HTML':
            return None
        else:
            return bs(self.body, 'html.parser')


class Calendar(ApiComponent, HandleRecipientsMixin):
    _endpoints = {
        'calendar': '/calendars/{id}',
        'get_events': '/calendars/{id}/events',
        'default_events': '/calendar/events',
        'events_view': '/calendars/{id}/calendarView',
        'default_events_view': '/calendar/calendarView',
        'get_event': '/calendars/{id}/events/{ide}',
    }
    event_constructor = Event

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Create a Calendar Representation

        :param parent: parent for this operation
        :type parent: Schedule
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.name = cloud_data.get(self._cc('name'), '')
        self.calendar_id = cloud_data.get(self._cc('id'), None)
        self.__owner = self._recipient_from_cloud(
            cloud_data.get(self._cc('owner'), {}), field='owner')
        color = cloud_data.get(self._cc('color'), 'auto')
        try:
            self.color = CalendarColor.from_value(color)
        except:
            self.color = CalendarColor.from_value('auto')
        self.can_edit = cloud_data.get(self._cc('canEdit'), False)
        self.can_share = cloud_data.get(self._cc('canShare'), False)
        self.can_view_private_items = cloud_data.get(
            self._cc('canViewPrivateItems'), False)

        # Hex color only returns a value when a custom calandar is set
        # Hex color is read-only, cannot be used to set calendar's color
        self.hex_color = cloud_data.get(self._cc('hexColor'), None)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Calendar: {} from {}'.format(self.name, self.owner)

    def __eq__(self, other):
        return self.calendar_id == other.calendar_id

    @property
    def owner(self):
        """ Owner of the calendar

        :rtype: str
        """
        return self.__owner

    def update(self):
        """ Updates this calendar. Only name and color can be changed.

        :return: Success / Failure
        :rtype: bool
        """

        if not self.calendar_id:
            return False

        url = self.build_url(self._endpoints.get('calendar').format(id=self.calendar_id))

        data = {
            self._cc('name'): self.name,
            self._cc('color'): self._cc(self.color.value
                                        if isinstance(self.color, CalendarColor)
                                        else self.color)
        }

        response = self.con.patch(url, data=data)

        return bool(response)

    def delete(self):
        """ Deletes this calendar

        :return: Success / Failure
        :rtype: bool
        """

        if not self.calendar_id:
            return False

        url = self.build_url(
            self._endpoints.get('calendar').format(id=self.calendar_id))

        response = self.con.delete(url)
        if not response:
            return False

        self.calendar_id = None

        return True

    def get_events(self, limit=25, *, query=None, order_by=None, batch=None,
                   download_attachments=False, include_recurring=True):
        """ Get events from this Calendar

        :param int limit: max no. of events to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :param download_attachments: downloads event attachments
        :param bool include_recurring: whether to include recurring events or not
        :return: list of events in this calendar
        :rtype: list[Event] or Pagination
        """

        if self.calendar_id is None:
            # I'm the default calendar
            if include_recurring:
                url = self.build_url(self._endpoints.get('default_events_view'))
            else:
                url = self.build_url(self._endpoints.get('default_events'))
        else:
            if include_recurring:
                url = self.build_url(
                    self._endpoints.get('events_view').format(id=self.calendar_id))
            else:
                url = self.build_url(
                    self._endpoints.get('get_events').format(id=self.calendar_id))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        if batch:
            download_attachments = False

        params = {'$top': batch if batch else limit}

        if include_recurring:
            start = None
            end = None
            if query and not isinstance(query, str):
                # extract start and end from query because
                # those are required by a calendarView
                for query_data in query._filters:
                    if not isinstance(query_data, list):
                        continue
                    attribute = query_data[0]
                    # the 2nd position contains the filter data
                    # and the 3rd position in filter_data contains the value
                    word = query_data[2][3]

                    if attribute.lower().startswith('start/'):
                        start = word.replace("'", '')  # remove the quotes
                        query.remove_filter('start')
                    if attribute.lower().startswith('end/'):
                        end = word.replace("'", '')  # remove the quotes
                        query.remove_filter('end')

            if start is None or end is None:
                raise ValueError(
                    "When 'include_recurring' is True you must provide a 'start' and 'end' datetimes inside a Query instance.")

            if end < start:
                raise ValueError('When using "include_recurring=True", the date asigned to the "end" datetime'
                                 ' should be greater or equal than the date asigned to the "start" datetime.')

            params[self._cc('startDateTime')] = start
            params[self._cc('endDateTime')] = end

        if order_by:
            params['$orderby'] = order_by

        if query:
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

        response = self.con.get(url, params=params)

        if not response:
            return iter(())

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        events = (self.event_constructor(parent=self,
                                         download_attachments=
                                         download_attachments,
                                         **{self._cloud_data_key: event})
                  for event in data.get('value', []))
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=events,
                              constructor=self.event_constructor,
                              next_link=next_link, limit=limit)
        else:
            return events

    def new_event(self, subject=None):
        """ Returns a new (unsaved) Event object

        :rtype: Event
        """
        return self.event_constructor(parent=self, subject=subject,
                                      calendar_id=self.calendar_id)

    def get_event(self, param):
        """ Returns an Event instance by it's id

        :param param: an event_id or a Query instance
        :return: event for the specified info
        :rtype: Event
        """

        if param is None:
            return None
        if isinstance(param, str):
            url = self.build_url(
                self._endpoints.get('get_event').format(id=self.calendar_id,
                                                        ide=param))
            params = None
            by_id = True
        else:
            url = self.build_url(
                self._endpoints.get('get_events').format(id=self.calendar_id))
            params = {'$top': 1}
            params.update(param.as_params())
            by_id = False

        response = self.con.get(url, params=params)

        if not response:
            return None

        if by_id:
            event = response.json()
        else:
            event = response.json().get('value', [])
            if event:
                event = event[0]
            else:
                return None
        return self.event_constructor(parent=self,
                                      **{self._cloud_data_key: event})


class Schedule(ApiComponent):
    _endpoints = {
        'root_calendars': '/calendars',
        'get_calendar': '/calendars/{id}',
        'default_calendar': '/calendar',
        'get_availability': '/calendar/getSchedule',
    }

    calendar_constructor = Calendar
    event_constructor = Event

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Create a wrapper around calendars and events

        :param parent: parent for this operation
        :type parent: Account
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Schedule resource: {}'.format(self.main_resource)

    def list_calendars(self, limit=None, *, query=None, order_by=None):
        """ Gets a list of calendars

        To use query an order_by check the OData specification here:
        http://docs.oasis-open.org/odata/odata/v4.0/errata03/os/complete/
        part2-url-conventions/odata-v4.0-errata03-os-part2-url-conventions
        -complete.html

        :param int limit: max no. of calendars to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :return: list of calendars
        :rtype: list[Calendar]

        """
        url = self.build_url(self._endpoints.get('root_calendars'))

        params = {}
        if limit:
            params['$top'] = limit
        if query:
            params['$filter'] = str(query)
        if order_by:
            params['$orderby'] = order_by

        response = self.con.get(url, params=params or None)
        if not response:
            return []

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        contacts = [self.calendar_constructor(parent=self, **{
            self._cloud_data_key: x}) for x in data.get('value', [])]

        return contacts

    def new_calendar(self, calendar_name):
        """ Creates a new calendar

        :param str calendar_name: name of the new calendar
        :return: a new Calendar instance
        :rtype: Calendar
        """
        if not calendar_name:
            return None

        url = self.build_url(self._endpoints.get('root_calendars'))

        response = self.con.post(url, data={self._cc('name'): calendar_name})
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.calendar_constructor(parent=self,
                                         **{self._cloud_data_key: data})

    def get_calendar(self, calendar_id=None, calendar_name=None):
        """ Returns a calendar by it's id or name

        :param str calendar_id: the calendar id to be retrieved.
        :param str calendar_name: the calendar name to be retrieved.
        :return: calendar for the given info
        :rtype: Calendar
        """
        if calendar_id and calendar_name:
            raise RuntimeError('Provide only one of the options')

        if not calendar_id and not calendar_name:
            raise RuntimeError('Provide one of the options')

        if calendar_id:
            # get calendar by it's id
            url = self.build_url(
                self._endpoints.get('get_calendar').format(id=calendar_id))
            params = None
        else:
            # get calendar by name
            url = self.build_url(self._endpoints.get('root_calendars'))
            params = {
                '$filter': "{} eq '{}'".format(self._cc('name'), calendar_name),
                '$top': 1}

        response = self.con.get(url, params=params)
        if not response:
            return None

        if calendar_id:
            data = response.json()
        else:
            data = response.json().get('value')
            data = data[0] if data else None
            if data is None:
                return None

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.calendar_constructor(parent=self,
                                         **{self._cloud_data_key: data})

    def get_default_calendar(self):
        """ Returns the default calendar for the current user

        :rtype: Calendar
        """

        url = self.build_url(self._endpoints.get('default_calendar'))

        response = self.con.get(url)
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.calendar_constructor(parent=self,
                                         **{self._cloud_data_key: data})

    def get_events(self, limit=25, *, query=None, order_by=None, batch=None,
                   download_attachments=False, include_recurring=True):
        """ Get events from the default Calendar

        :param int limit: max no. of events to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :param bool download_attachments: downloads event attachments
        :param bool include_recurring: whether to include recurring events or not
        :return: list of items in this folder
        :rtype: list[Event] or Pagination
        """

        default_calendar = self.calendar_constructor(parent=self)

        return default_calendar.get_events(limit=limit, query=query,
                                           order_by=order_by, batch=batch,
                                           download_attachments=download_attachments,
                                           include_recurring=include_recurring)

    def new_event(self, subject=None):
        """ Returns a new (unsaved) Event object in the default calendar

        :param str subject: subject text for the new event
        :return: new event
        :rtype: Event
        """
        return self.event_constructor(parent=self, subject=subject)

    def get_availability(self, schedules, start, end, interval=60):
        """
        Returns the free/busy availability for a set of users in a given time frame
        :param list schedules: a list of strings (email addresses)
        :param datetime start: the start time frame to look for available space
        :param datetime end: the end time frame to look for available space
        :param int interval: the number of minutes to look for space
        """
        url = self.build_url(self._endpoints.get('get_availability'))

        data = {
            'startTime': self._build_date_time_time_zone(start),
            'endTime': self._build_date_time_time_zone(end),
            'availabilityViewInterval': interval,
            'schedules': schedules
        }

        response = self.con.post(url, data=data)
        if not response:
            return []

        data = response.json().get('value', [])

        # transform dates and availabilityView
        availability_view_codes = {
            '0': 'free',
            '1': 'tentative',
            '2': 'busy',
            '3': 'out of office',
            '4': 'working elsewhere',
        }
        for schedule in data:
            a_view = schedule.get('availabilityView', '')
            schedule['availabilityView'] = [availability_view_codes.get(code, 'unkknown') for code in a_view]
            for item in schedule.get('scheduleItems', []):
                item['start'] = self._parse_date_time_time_zone(item.get('start'))
                item['end'] = self._parse_date_time_time_zone(item.get('end'))

        return data
