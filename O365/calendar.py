import logging
from enum import Enum
from dateutil.parser import parse
import datetime as dt
import pytz
import calendar
from bs4 import BeautifulSoup as bs

from O365.utils import Pagination, NEXT_LINK_KEYWORD, ApiComponent, BaseAttachments, BaseAttachment, \
    AttachableMixin, ImportanceLevel, TrackerSet
from O365.message import HandleRecipientsMixin
from O365.utils.windows_tz import get_iana_tz, get_windows_tz

log = logging.getLogger(__name__)

MONTH_NAMES = [calendar.month_name[x] for x in range(1, 13)]


class EventResponse(Enum):
    Organizer = 'organizer'
    TentativelyAccepted = 'tentativelyAccepted'
    Accepted = 'accepted'
    Declined = 'declined'
    NotResponded = 'notResponded'


class AttendeeType(Enum):
    Required = 'required'
    Optional = 'optional'
    Resource = 'resource'


class EventSensitivity(Enum):
    Normal = 'normal'
    Personal = 'personal'
    Private = 'private'
    Confidential = 'confidential'


class EventShowAs(Enum):
    Free = 'free'
    Tentative = 'tentative'
    Busy = 'busy'
    Oof = 'oof'
    WorkingElsewhere = 'workingElsewhere'
    Unknown = 'unknown'


class CalendarColors(Enum):
    LightBlue = 0
    LightGreen = 1
    LightOrange = 2
    LightGray = 3
    LightYellow = 4
    LightTeal = 5
    LightPink = 6
    LightBrown = 7
    LightRed = 8
    MaxColor = 9
    Auto = -1


class EventAttachment(BaseAttachment):
    _endpoints = {'attach': '/events/{id}/attachments'}


class EventAttachments(BaseAttachments):
    _endpoints = {'attachments': '/events/{id}/attachments'}

    _attachment_constructor = EventAttachment


class DailyEventFrequency:

    def __init__(self, recurrence_type, interval):
        self.recurrence_type = recurrence_type
        self.interval = interval


class EventRecurrence(ApiComponent):
    """ A representation of an event recurrence properties """

    def __init__(self, event, recurrence=None):
        super().__init__(protocol=event.protocol, main_resource=event.main_resource)

        self._event = event
        recurrence = recurrence or {}
        # recurrence pattern
        recurrence_pattern = recurrence.get(self._cc('pattern'), {})

        self.__interval = recurrence_pattern.get(self._cc('interval'), None)
        self.__days_of_week = recurrence_pattern.get(self._cc('daysOfWeek'), set())
        self.__first_day_of_week = recurrence_pattern.get(self._cc('firstDayOfWeek'), None)
        self.__day_of_month = recurrence_pattern.get(self._cc('dayOfMonth'), None)
        self.__month = recurrence_pattern.get(self._cc('month'), None)
        self.__index = recurrence_pattern.get(self._cc('index'), 'first')

        # recurrence range
        recurrence_range = recurrence.get(self._cc('range'), {})

        self.__ocurrences = recurrence_range.get(self._cc('numberOfOccurrences'), None)
        self.__start_date = recurrence_range.get(self._cc('startDate'), None)
        self.__end_date = recurrence_range.get(self._cc('endDate'), None)
        self.__recurrence_time_zone = recurrence_range.get(self._cc('recurrenceTimeZone'), get_windows_tz(self.protocol.timezone))
        # time and time zones are not considered in recurrence ranges...
        # I don't know why 'recurrenceTimeZone' is present here
        # Sending a startDate datetime to the server results in an Error:
        # "Cannot convert the literal 'datetime' to the expected type 'Edm.Date'"
        if recurrence_range:
            self.__start_date = parse(self.__start_date).date() if self.__start_date else None
            self.__end_date = parse(self.__end_date).date() if self.__end_date else None

    def __repr__(self):
        if self.__interval:
            pattern = 'Daily: every {} day/s'.format(self.__interval)
            if self.__days_of_week:
                days = ' or '.join(list(self.__days_of_week))
                pattern = 'Relative Monthly: {} {} every {} month/s'.format(self.__index, days, self.__interval)
                if self.__first_day_of_week:
                    pattern = 'Weekly: every {} week/s on {}'.format(self.__interval, days)
                elif self.__month:
                    pattern = 'Relative Yearly: {} {} every {} year/s on {}'.format(self.__index, days,
                                                                                    self.__interval,
                                                                                    MONTH_NAMES[self.__month - 1])
            elif self.__day_of_month:
                pattern = 'Absolute Monthly: on day {} every {} month/s'.format(self.__day_of_month, self.__interval)
                if self.__month:
                    pattern = 'Absolute Yearly: on {} {} every {} year/s'.format(MONTH_NAMES[self.__month - 1],
                                                                                 self.__day_of_month,
                                                                                 self.__interval)

            r_range = ''
            if self.__start_date:
                r_range = 'Starting on {}'.format(self.__start_date)
                ends_on = 'with no end'
                if self.__end_date:
                    ends_on = 'ending on {}'.format(self.__end_date)
                elif self.__ocurrences:
                    ends_on = 'up to {} ocurrences'.format(self.__ocurrences)
                r_range = '{} {}'.format(r_range, ends_on)
            return '{}. {}'.format(pattern, r_range)
        else:
            return 'No recurrence enabled'

    def __str__(self):
        return self.__repr__()

    def __bool__(self):
        return bool(self.__interval)

    def _track_changes(self):
        """ Update the track_changes on the event to reflect a needed update on this field """
        self._event._track_changes.add('recurrence')

    @property
    def interval(self):
        return self.__interval

    @interval.setter
    def interval(self, value):
        self.__interval = value
        self._track_changes()

    @property
    def days_of_week(self):
        return self.__days_of_week

    @days_of_week.setter
    def days_of_week(self, value):
        self.__days_of_week = value
        self._track_changes()

    @property
    def first_day_of_week(self):
        return self.__first_day_of_week

    @first_day_of_week.setter
    def first_day_of_week(self, value):
        self.__first_day_of_week = value
        self._track_changes()

    @property
    def day_of_month(self):
        return self.__day_of_month

    @day_of_month.setter
    def day_of_month(self, value):
        self.__day_of_month = value
        self._track_changes()

    @property
    def month(self):
        return self.__month

    @month.setter
    def month(self, value):
        self.__month = value
        self._track_changes()

    @property
    def index(self):
        return self.__index

    @index.setter
    def index(self, value):
        self.__index = value
        self._track_changes()

    @property
    def ocurrences(self):
        return self.__ocurrences

    @ocurrences.setter
    def ocurrences(self, value):
        self.__ocurrences = value
        self._track_changes()

    @property
    def recurrence_time_zone(self):
        return self.__recurrence_time_zone

    @recurrence_time_zone.setter
    def recurrence_time_zone(self, value):
        self.__recurrence_time_zone = value
        self._track_changes()

    @property
    def start_date(self):
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
        return self.__start_date

    @end_date.setter
    def end_date(self, value):
        if not isinstance(value, dt.date):
            raise ValueError('end_date value must be a valid date object')
        if isinstance(value, dt.datetime):
            value = value.date()
        self.__end_date = value
        self._track_changes()

    def to_api_data(self):
        data = {}
        # recurrence pattern
        if self.__interval and isinstance(self.__interval, int):
            recurrence_pattern = data[self._cc('pattern')] = {}
            recurrence_pattern[self._cc('type')] = 'daily'
            recurrence_pattern[self._cc('interval')] = self.__interval
            if self.__days_of_week and isinstance(self.__days_of_week, (list, tuple, set)):
                recurrence_pattern[self._cc('type')] = 'relativeMonthly'
                recurrence_pattern[self._cc('daysOfWeek')] = list(self.__days_of_week)
                if self.__first_day_of_week:
                    recurrence_pattern[self._cc('type')] = 'weekly'
                    recurrence_pattern[self._cc('firstDayOfWeek')] = self.__first_day_of_week
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
            recurrence_range[self._cc('startDate')] = self.__start_date.isoformat()
            recurrence_range[self._cc('recurrenceTimeZone')] = self.__recurrence_time_zone

            if self.__end_date:
                recurrence_range[self._cc('type')] = 'endDate'
                recurrence_range[self._cc('endDate')] = self.__end_date.isoformat()
            elif self.__ocurrences is not None and isinstance(self.__ocurrences, int):
                recurrence_range[self._cc('type')] = 'numbered'
                recurrence_range[self._cc('numberOfOccurrences')] = self.__ocurrences

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
        self.__ocurrences = None

    def set_range(self, start=None, end=None, ocurrences=None):
        if start is None:
            if self.__start_date is None:
                self.__start_date = dt.date.today()
        else:
            self.start_date = start

        if end:
            self.end_date = end
        elif ocurrences:
            self.__ocurrences = ocurrences
        self._track_changes()

    def set_daily(self, interval, **kwargs):
        self._clear_pattern()
        self.__interval = interval
        self.set_range(**kwargs)

    def set_weekly(self, interval, *, days_of_week, first_day_of_week, **kwargs):
        self.set_daily(interval, **kwargs)
        self.__days_of_week = set(days_of_week)
        self.__first_day_of_week = first_day_of_week

    def set_monthly(self, interval, *, day_of_month=None, days_of_week=None, index=None, **kwargs):
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

    def set_yearly(self, interval, month, *, day_of_month=None, days_of_week=None, index=None, **kwargs):
        self.set_monthly(interval, day_of_month=day_of_month, days_of_week=days_of_week, index=index, **kwargs)
        self.__month = month


class ResponseStatus(ApiComponent):
    """ An event response status (status, time) """

    def __init__(self, parent, response_status):
        super().__init__(protocol=parent.protocol, main_resource=parent.main_resource)
        self.status = response_status.get(self._cc('response'), None)
        self.status = None if self.status == 'none' else self.status
        if self.status:
            self.response_time = response_status.get(self._cc('time'), None)
            if self.response_time:
                self.response_time = parse(self.response_time).astimezone(self.protocol.timezone)
        else:
            self.response_time = None

    def __repr__(self):
        return self.status

    def __str__(self):
        return self.__repr__()


class Attendee:
    """ A Event attendee """

    def __init__(self, address, *, name=None, attendee_type=None, response_status=None, event=None):
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

    def __repr__(self):
        if self.name:
            return '{}: {} ({})'.format(self.attendee_type.name, self.name, self.address)
        else:
            return '{}: {}'.format(self.attendee_type.name, self.address)

    def __str__(self):
        return self.__repr__()

    @property
    def address(self):
        return self._address

    @address.setter
    def address(self, value):
        self._address = value
        self._name = ''
        self._track_changes()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._track_changes()

    def _track_changes(self):
        """ Update the track_changes on the event to reflect a needed update on this field """
        self._event._track_changes.add('attendees')

    @property
    def response_status(self):
        return self.__response_status

    @property
    def attendee_type(self):
        return self.__attendee_type

    @attendee_type.setter
    def attendee_type(self, value):
        if isinstance(value, AttendeeType):
            self.__attendee_type = value
        else:
            self.__attendee_type = AttendeeType(value)
        self._track_changes()


class Attendees(ApiComponent):
    """ A Collection of Attendees """

    def __init__(self, event, attendees=None):
        super().__init__(protocol=event.protocol, main_resource=event.main_resource)
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
        return item in {attendee.email for attendee in self.__attendees}

    def __len__(self):
        return len(self.__attendees)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Attendees Count: {}'.format(len(self.__attendees))

    def clear(self):
        self.__attendees = []
        self._track_changes()

    def _track_changes(self):
        """ Update the track_changes on the event to reflect a needed update on this field """
        if self.untrack is False:
            self._event._track_changes.add('attendees')

    def add(self, attendees):
        """ Add attendees to the parent event """

        if attendees:
            if isinstance(attendees, str):
                self.__attendees.append(Attendee(address=attendees, event=self._event))
                self._track_changes()
            elif isinstance(attendees, Attendee):
                self.__attendees.append(attendees)
                self._track_changes()
            elif isinstance(attendees, tuple):
                name, address = attendees
                if address:
                    self.__attendees.append(Attendee(address=address, name=name, event=self._event))
                    self._track_changes()
            elif isinstance(attendees, list):
                for attendee in attendees:
                    self.add(attendee)
            elif isinstance(attendees, dict) and self._cloud_data_key in attendees:
                attendees = attendees.get(self._cloud_data_key)
                for attendee in attendees:
                    email = attendee.get(self._cc('emailAddress'), {})
                    address = email.get(self._cc('address'), None)
                    if address:
                        name = email.get(self._cc('name'), None)
                        attendee_type = attendee.get(self._cc('type'), 'required')  # default value
                        self.__attendees.append(
                            Attendee(address=address, name=name, attendee_type=attendee_type, event=self._event,
                                     response_status=ResponseStatus(parent=self,
                                                                    response_status=attendee.get(self._cc('status'), {}))))
            else:
                raise ValueError('Attendees must be an address string, an'
                                 ' Attendee instance, a (name, address) tuple or a list')

    def remove(self, attendees):
        """ Remove the provided attendees from the event """
        if isinstance(attendees, (list, tuple)):
            attendees = {attendee.address if isinstance(attendee, Attendee) else attendee for attendee in attendees}
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
        data = []
        for attendee in self.__attendees:
            if attendee.address:
                att_data = {
                    self._cc('emailAddress'): {
                        self._cc('address'): attendee.address,
                        self._cc('name'): attendee.name
                    },
                    self._cc('type'): attendee.attendee_type.value
                }
                data.append(att_data)
        return data


class Event(ApiComponent, AttachableMixin, HandleRecipientsMixin):
    """ A Calendar event """

    _endpoints = {
        'calendar': '/calendars/{id}',
        'event': '/events/{id}',
        'event_default': '/calendar/events',
        'event_calendar': '/calendars/{id}/events'
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        cc = self._cc  # alias
        self._track_changes = TrackerSet(casing=cc)  # internal to know which properties need to be updated on the server
        self.calendar_id = kwargs.get('calendar_id', None)
        download_attachments = kwargs.get('download_attachments')
        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get(cc('id'), None)
        self.__subject = cloud_data.get(cc('subject'), kwargs.get('subject', '') or '')
        body = cloud_data.get(cc('body'), {})
        self.__body = body.get(cc('content'), '')
        self.body_type = body.get(cc('contentType'), 'HTML')  # default to HTML for new messages

        self.__attendees = Attendees(event=self, attendees={self._cloud_data_key: cloud_data.get(cc('attendees'), [])})
        self.__categories = cloud_data.get(cc('categories'), [])

        self.__created = cloud_data.get(cc('createdDateTime'), None)
        self.__modified = cloud_data.get(cc('lastModifiedDateTime'), None)

        local_tz = self.protocol.timezone
        self.__created = parse(self.__created).astimezone(local_tz) if self.__created else None
        self.__modified = parse(self.__modified).astimezone(local_tz) if self.__modified else None

        start_obj = cloud_data.get(cc('start'), {})
        if isinstance(start_obj, dict):
            try:
                timezone = pytz.timezone(get_iana_tz(start_obj.get(self._cc('timeZone'), 'UTC')))
            except pytz.UnknownTimeZoneError:
                timezone = local_tz
            start = start_obj.get(cc('dateTime'), None)
            start = timezone.localize(parse(start)) if start else None
            if start and timezone != local_tz:
                start = start.astimezone(local_tz)
        else:
            # Outlook v1.0 api compatibility
            start = local_tz.localize(parse(start_obj)) if start_obj else None
        self.__start = start

        end_obj = cloud_data.get(cc('end'), {})
        if isinstance(end_obj, dict):
            try:
                timezone = pytz.timezone(get_iana_tz(end_obj.get(self._cc('timeZone'), 'UTC')))
            except pytz.UnknownTimeZoneError:
                timezone = local_tz
            end = end_obj.get(cc('dateTime'), None)
            end = timezone.localize(parse(end)) if end else None
            if end and timezone != local_tz:
                end = end.astimezone(local_tz)
        else:
            # Outlook v1.0 api compatibility
            end = local_tz.localize(parse(end_obj)) if end_obj else None
        self.__end = end

        self.has_attachments = cloud_data.get(cc('hasAttachments'), False)
        self.__attachments = EventAttachments(parent=self, attachments=[])
        if self.has_attachments and download_attachments:
            self.attachments.download_attachments()
        self.__categories = cloud_data.get(cc('categories'), [])
        self.ical_uid = cloud_data.get(cc('iCalUId'), None)
        self.__importance = ImportanceLevel(cloud_data.get(cc('importance'), 'normal') or 'normal')
        self.__is_all_day = cloud_data.get(cc('isAllDay'), False)
        self.is_cancelled = cloud_data.get(cc('isCancelled'), False)
        self.is_organizer = cloud_data.get(cc('isOrganizer'), True)
        self.__location = cloud_data.get(cc('location'), {}).get(cc('displayName'), '')
        self.locations = cloud_data.get(cc('locations'), [])  # TODO
        self.online_meeting_url = cloud_data.get(cc('onlineMeetingUrl'), None)
        self.__organizer = self._recipient_from_cloud(cloud_data.get(cc('organizer'), None), field='organizer')
        self.__recurrence = EventRecurrence(event=self, recurrence=cloud_data.get(cc('recurrence'), None))
        self.__is_reminder_on = cloud_data.get(cc('isReminderOn'), True)
        self.__remind_before_minutes = cloud_data.get(cc('reminderMinutesBeforeStart'), 15)
        self.__response_requested = cloud_data.get(cc('responseRequested'), True)
        self.__response_status = ResponseStatus(parent=self, response_status=cloud_data.get(cc('responseStatus'), {}))
        self.__sensitivity = EventSensitivity(cloud_data.get(cc('sensitivity'), 'normal'))
        self.series_master_id = cloud_data.get(cc('seriesMasterId'), None)
        self.__show_as = EventShowAs(cloud_data.get(cc('showAs'), 'busy'))
        self.event_type = cloud_data.get(cc('type'), None)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Subject: {}'.format(self.subject)

    def to_api_data(self, restrict_keys=None):
        """ Returns a dict to comunicate with the server

        :param restrict_keys: a set of keys to restrict the returned data to.
        """
        cc = self._cc  # alias
        data = {
            cc('subject'): self.__subject,
            cc('body'): {
                cc('contentType'): self.body_type,
                cc('content'): self.__body},
            cc('start'): {
                cc('dateTime'): self.__start.strftime('%Y-%m-%dT%H:%M:%S'),
                cc('timeZone'): get_windows_tz(self.__start.tzinfo.zone or self.protocol.timezone)
            },
            cc('end'): {
                cc('dateTime'): self.__end.strftime('%Y-%m-%dT%H:%M:%S'),
                cc('timeZone'): get_windows_tz(self.__end.tzinfo.zone or self.protocol.timezone)
            },
            cc('attendees'): self.__attendees.to_api_data(),
            cc('location'): {cc('displayName'): self.__location},
            cc('categories'): self.__categories,
            cc('isAllDay'): self.__is_all_day,
            cc('importance'): self.__importance.value,
            cc('isReminderOn'): self.__is_reminder_on,
            cc('reminderMinutesBeforeStart'): self.__remind_before_minutes,
            cc('responseRequested'): self.__response_requested,
            cc('sensitivity'): self.__sensitivity.value,
            cc('showAs'): self.__show_as.value,
        }

        if self.__recurrence:
            data[cc('recurrence')] = self.__recurrence.to_api_data()

        if self.has_attachments:
            data[cc('attachments')] = self.__attachments.to_api_data()

        if restrict_keys:
            for key in list(data.keys()):
                if key not in restrict_keys:
                    del data[key]
        return data

    @property
    def created(self):
        return self.__created

    @property
    def modified(self):
        return self.__modified

    @property
    def body(self):
        return self.__body

    @body.setter
    def body(self, value):
        self.__body = value
        self._track_changes.add('body')

    @property
    def subject(self):
        return self.__subject

    @subject.setter
    def subject(self, value):
        self.__subject = value
        self._track_changes.add('subject')

    @property
    def start(self):
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
            value = self.protocol.timezone.localize(value)
        elif value.tzinfo != self.protocol.timezone:
            value = value.astimezone(self.protocol.timezone)
        self.__start = value
        if not self.end:
            self.end = self.__start + dt.timedelta(minutes=30)
        self._track_changes.add('start')

    @property
    def end(self):
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
            value = self.protocol.timezone.localize(value)
        elif value.tzinfo != self.protocol.timezone:
            value = value.astimezone(self.protocol.timezone)
        self.__end = value
        self._track_changes.add('end')

    @property
    def importance(self):
        return self.__importance

    @importance.setter
    def importance(self, value):
        self.__importance = value if isinstance(value, ImportanceLevel) else ImportanceLevel(value)
        self._track_changes.add('importance')

    @property
    def is_all_day(self):
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
                # Api requires that under is_all_day=True start and end must be at least 24 hours away
                end = start + dt.timedelta(hours=24)

            # set to midnight
            start = dt.datetime(start.year, start.month, start.day)
            end = dt.datetime(end.year, end.month, end.day)

            self.start = start
            self.end = end
        self._track_changes.add('isAllDay')

    @property
    def location(self):
        return self.__location

    @location.setter
    def location(self, value):
        self.__location = value
        self._track_changes.add('location')

    @property
    def is_reminder_on(self):
        return self.__is_reminder_on

    @is_reminder_on.setter
    def is_reminder_on(self, value):
        self.__is_reminder_on = value
        self._track_changes.add('isReminderOn')
        self._track_changes.add('reminderMinutesBeforeStart')

    @property
    def remind_before_minutes(self):
        return self.__remind_before_minutes

    @remind_before_minutes.setter
    def remind_before_minutes(self, value):
        self.__is_reminder_on = True
        self.__remind_before_minutes = int(value)
        self._track_changes.add('isReminderOn')
        self._track_changes.add('reminderMinutesBeforeStart')

    @property
    def response_requested(self):
        return self.__response_requested

    @response_requested.setter
    def response_requested(self, value):
        self.__response_requested = value
        self._track_changes.add('responseRequested')

    @property
    def recurrence(self):
        return self.__recurrence

    @property
    def organizer(self):
        return self.__organizer

    @property
    def show_as(self):
        return self.__show_as

    @show_as.setter
    def show_as(self, value):
        self.__show_as = value if isinstance(value, EventShowAs) else EventShowAs(value)
        self._track_changes.add('showAs')

    @property
    def sensitivity(self):
        return self.__sensitivity

    @sensitivity.setter
    def sensitivity(self, value):
        self.__sensitivity = value if isinstance(value, EventSensitivity) else EventSensitivity(value)
        self._track_changes.add('sensitivity')

    @property
    def response_status(self):
        return self.__response_status

    @property
    def attachments(self):
        return self.__attachments

    @property
    def attendees(self):
        return self.__attendees

    @property
    def categories(self):
        return self.__categories

    @categories.setter
    def categories(self, value):
        if isinstance(value, list):
            self.__categories = value
        elif isinstance(value, str):
            self.__categories = [value]
        elif isinstance(value, tuple):
            self.__categories = list(value)
        else:
            raise ValueError('categories must be a list')
        self._track_changes.add('categories')

    def delete(self):
        """ Deletes a stored event """
        if self.object_id is None:
            raise RuntimeError('Attempting to delete an unsaved event')

        url = self.build_url(self._endpoints.get('event').format(id=self.object_id))

        response = self.con.delete(url)

        return bool(response)

    def save(self):
        """ Create a new event or update an existing one by checking what
        values have changed and update them on the server
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

        if not self.object_id:
            # new event
            event = response.json()

            self.object_id = event.get(self._cc('id'), None)

            self.__created = event.get(self._cc('createdDateTime'), None)
            self.__modified = event.get(self._cc('lastModifiedDateTime'), None)

            self.__created = parse(self.__created).astimezone(self.protocol.timezone) if self.__created else None
            self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None
        else:
            self.__modified = self.protocol.timezone.localize(dt.datetime.now())

        return True

    def accept_event(self, comment=None, *, send_response=True, tentatively=False):

        if not self.object_id:
            raise RuntimeError("Can't accept event that doesn't exist")

        url = self.build_url(self._endpoints.get('event').format(id=self.object_id))
        url = url + '/tentativelyAccept' if tentatively else '/accept'

        data = {}
        if comment and isinstance(comment, str):
            data[self._cc('comment')] = comment
        if send_response is False:
            data[self._cc('sendResponse')] = send_response

        response = self.con.post(url, data=data or None)

        return bool(response)

    def decline_event(self, comment=None, *, send_response=True):

        if not self.object_id:
            raise RuntimeError("Can't accept event that doesn't exist")

        url = self.build_url(self._endpoints.get('event').format(id=self.object_id))
        url = url + '/decline'

        data = {}
        if comment and isinstance(comment, str):
            data[self._cc('comment')] = comment
        if send_response is False:
            data[self._cc('sendResponse')] = send_response

        response = self.con.post(url, data=data or None)

        return bool(response)

    def get_body_text(self):
        """ Parse the body html and returns the body text using bs4 """
        if self.body_type != 'HTML':
            return self.body

        try:
            soup = bs(self.body, 'html.parser')
        except Exception as e:
            return self.body
        else:
            return soup.body.text

    def get_body_soup(self):
        """ Returns the beautifulsoup4 of the html body"""
        if self.body_type != 'HTML':
            return None
        else:
            return bs(self.body, 'html.parser')


class Calendar(ApiComponent, HandleRecipientsMixin):
    """ A Calendar Representation """

    _endpoints = {
        'calendar': '/calendars/{id}',
        'get_events': '/calendars/{id}/events',
        'get_event': '/calendars/{id}/events/{ide}'
    }
    event_constructor = Event

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.name = cloud_data.get(self._cc('name'), '')
        self.calendar_id = cloud_data.get(self._cc('id'), None)
        self.__owner = self._recipient_from_cloud(cloud_data.get(self._cc('owner'), {}), field='owner')
        color = cloud_data.get(self._cc('color'), -1)
        if isinstance(color, str):
            color = -1 if color == 'auto' else color
            # TODO: other string colors?
        self.color = CalendarColors(color)
        self.can_edit = cloud_data.get(self._cc('canEdit'), False)
        self.can_share = cloud_data.get(self._cc('canShare'), False)
        self.can_view_private_items = cloud_data.get(self._cc('canViewPrivateItems'), False)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Calendar: {} from {}'.format(self.name, self.owner)

    @property
    def owner(self):
        return self.__owner

    def update(self):
        """ Updates this calendar. Only name and color can be changed. """

        if not self.calendar_id:
            return False

        url = self.build_url(self._endpoints.get('calendar'))

        data = {
            self._cc('name'): self.name,
            self._cc('color'): self.color.value if isinstance(self.color, CalendarColors) else self.color
        }

        response = self.con.patch(url, data=data)

        return bool(response)

    def delete(self):
        """ Deletes this calendar """

        if not self.calendar_id:
            return False

        url = self.build_url(self._endpoints.get('calendar').format(id=self.calendar_id))

        response = self.con.delete(url)
        if not response:
            return False

        self.calendar_id = None

        return True

    def get_events(self, limit=25, *, query=None, order_by=None, batch=None, download_attachments=False):
        """
        Get events from the default Calendar

        :param limit: limits the result set. Over 999 uses batch.
        :param query: applies a filter to the request such as 'displayName:HelloFolder'
        :param order_by: orders the result set based on this condition
        :param batch: Returns a custom iterator that retrieves items in batches allowing
            to retrieve more items than the limit. Download_attachments is ignored.
        :param download_attachments: downloads event attachments
        """

        url = self.build_url(self._endpoints.get('get_events').format(id=self.calendar_id))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        if batch:
            download_attachments = False

        params = {'$top': batch if batch else limit}

        if order_by:
            params['$orderby'] = order_by

        if query:
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

        response = self.con.get(url, params=params, headers={'Prefer': 'outlook.timezone="UTC"'})
        if not response:
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        events = [self.event_constructor(parent=self, download_attachments=download_attachments,
                                         **{self._cloud_data_key: event})
                  for event in data.get('value', [])]
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=events, constructor=self.event_constructor,
                              next_link=next_link, limit=limit)
        else:
            return events

    def new_event(self, subject=None):
        """ Returns a new (unsaved) Event object """
        return self.event_constructor(parent=self, subject=subject, calendar_id=self.calendar_id)

    def get_event(self, param):
        """Returns an Event instance by it's id
        :param param: an event_id or a Query instance
        """

        if param is None:
            return None
        if isinstance(param, str):
            url = self.build_url(self._endpoints.get('get_event').format(id=self.calendar_id, ide=param))
            params = None
        else:
            url = self.build_url(self._endpoints.get('get_events').format(id=self.calendar_id))
            params = {'$top': 1}
            params.update(param.as_params())

        response = self.con.get(url, params=params, headers={'Prefer': 'outlook.timezone="UTC"'})
        if not response:
            return None

        if isinstance(param, str):
            event = response.json()
        else:
            event = response.json().get('value', [])
            if event:
                event = event[0]
            else:
                return None
        return self.event_constructor(parent=self, **{self._cloud_data_key: event})


class Schedule(ApiComponent):
    """ A Wrapper around calendars and events"""

    _endpoints = {
        'root_calendars': '/calendars',
        'get_calendar': '/calendars/{id}',
        'default_calendar': '/calendar',
        'events': '/calendar/events'
    }

    calendar_constructor = Calendar
    event_constructor = Event

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Schedule resource: {}'.format(self.main_resource)

    def list_calendars(self, limit=None, *, query=None, order_by=None):
        """
        Gets a list of calendars

        To use query an order_by check the OData specification here:
        http://docs.oasis-open.org/odata/odata/v4.0/errata03/os/complete/part2-url-conventions/odata-v4.0-errata03-os-part2-url-conventions-complete.html

        :param limit: Number of elements to return.
        :param query: a OData valid filter clause
        :param order_by: OData valid order by clause
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

        # Everything received from the cloud must be passed with self._cloud_data_key
        contacts = [self.calendar_constructor(parent=self, **{self._cloud_data_key: calendar})
                    for calendar in data.get('value', [])]

        return contacts

    def new_calendar(self, calendar_name):
        """
        Creates a new calendar
        :return a new Calendar instance
        """

        if not calendar_name:
            return None

        url = self.build_url(self._endpoints.get('root_calendars'))

        response = self.con.post(url, data={self._cc('name'): calendar_name})
        if not response:
            return None

        calendar = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self.calendar_constructor(parent=self, **{self._cloud_data_key: calendar})

    def get_calendar(self, calendar_id=None, calendar_name=None):
        """
        Returns a calendar by it's id or name
        :param calendar_id: the calendar id to be retrieved.
        :param calendar_name: the calendar name to be retrieved.
        """
        if calendar_id and calendar_name:
            raise RuntimeError('Provide only one of the options')

        if not calendar_id and not calendar_name:
            raise RuntimeError('Provide one of the options')

        if calendar_id:
            # get calendar by it's id
            url = self.build_url(self._endpoints.get('get_calendar').format(id=calendar_id))
            params = None
        else:
            # get calendar by name
            url = self.build_url(self._endpoints.get('root_calendars'))
            params = {'$filter': "{} eq '{}'".format(self._cc('name'), calendar_name), '$top': 1}

        response = self.con.get(url, params=params)
        if not response:
            return None

        if calendar_id:
            calendar = response.json()
        else:
            calendar = response.json().get('value')
            calendar = calendar[0] if calendar else None
            if calendar is None:
                return None

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self.calendar_constructor(parent=self, **{self._cloud_data_key: calendar})

    def get_default_calendar(self):
        """ Returns the default calendar for the current user """

        url = self.build_url(self._endpoints.get('default_calendar'))

        response = self.con.get(url)
        if not response:
            return None

        calendar = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self.calendar_constructor(parent=self, **{self._cloud_data_key: calendar})

    def get_events(self, limit=25, *, query=None, order_by=None, batch=None, download_attachments=False):
        """
        Get events from the default Calendar

        :param limit: limits the result set. Over 999 uses batch.
        :param query: applies a filter to the request such as 'displayName:HelloFolder'
        :param order_by: orders the result set based on this condition
        :param batch: Returns a custom iterator that retrieves items in batches allowing
            to retrieve more items than the limit. Download_attachments is ignored.
        :param download_attachments: downloads event attachments
        """

        url = self.build_url(self._endpoints.get('events'))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        if batch:
            download_attachments = False

        params = {'$top': batch if batch else limit}

        if order_by:
            params['$orderby'] = order_by

        if query:
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

        response = self.con.get(url, params=params, headers={'Prefer': 'outlook.timezone="UTC"'})
        if not response:
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        events = [self.event_constructor(parent=self, download_attachments=download_attachments,
                                         **{self._cloud_data_key: event})
                  for event in data.get('value', [])]
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=events, constructor=self.event_constructor,
                              next_link=next_link, limit=limit)
        else:
            return events

    def new_event(self, subject=None):
        """ Returns a new (unsaved) Event object in the default calendar """
        return self.event_constructor(parent=self, subject=subject)
