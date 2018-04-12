import logging
from enum import Enum
from dateutil.parser import parse
from tzlocal import get_localzone
import pytz

from O365.utils import Pagination, NEXT_LINK_KEYWORD, ApiComponent, Attachments, Attachment, AttachableMixin
from O365.message import HandleRecipientsMixin

log = logging.getLogger(__name__)


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


class EventAttachment(Attachment):
    _endpoints = {}


class EventAttachments(Attachments):
    pass


class ResponseStatus(ApiComponent):

    def __init__(self, parent, response_status):
        super().__init__(protocol=parent.protocol, main_resource=parent.main_resource)
        self.status = response_status.get(self._cc('response'))
        self.response_time = response_status.get(self._cc('time'))
        if self.response_time:
            local_tz = get_localzone()  # calls to get_localzone() are cached so no problem here
            self.response_time = parse(self.response_time).astimezone(local_tz)

    def __str__(self):
        return self.status

    def __repr__(self):
        return self.__str__()


class Attendee:
    """ A Event attendee """

    def __init__(self, address, *, name=None, attendee_type=None, response_status=None):
        self.address = address
        self.name = name
        if isinstance(response_status, ResponseStatus):
            self.__response_status = response_status
        else:
            self.__response_status = None
        self.__attendee_type = AttendeeType.Required
        if attendee_type:
            self.attendee_type = attendee_type

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


class Attendees(ApiComponent):
    """ A Collection of Attendees """

    def __init__(self, event, attendees=None):
        super().__init__(protocol=event.protocol, main_resource=event.main_resource)
        self._event = event
        self.__attendees = []
        if attendees:
            self.add(attendees)

    def __iter__(self):
        return iter(self.__attendees)

    def __getitem__(self, key):
        return self.__attendees[key]

    def __contains__(self, item):
        return item in {attendee.email for attendee in self.__attendees}

    def __len__(self):
        return len(self.__attendees)

    def __str__(self):
        return 'Attendees Count: {}'.format(len(self.__attendees))

    def clear(self):
        self.__attendees = []

    def add(self, attendees):
        """ attendees must be a list of path strings or dictionary elements """

        if attendees:
            if isinstance(attendees, str):
                self.__attendees.append(Attendee(address=attendees))
            elif isinstance(attendees, Attendee):
                self.__attendees.append(attendees)
            elif isinstance(attendees, tuple):
                name, address = attendees
                if address:
                    self.__attendees.append(Attendee(address=address, name=name))
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
                            Attendee(address=address, name=name, attendee_type=attendee_type,
                                     response_status=ResponseStatus(parent=self,
                                                                    response_status=attendee.get(self._cc('status'), {}))))
            else:
                raise ValueError('Attendees must be an address string, an'
                                 ' Attendee instance, a (name, address) tuple or a list')

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
    }

    _importance_options = {'normal': 'normal', 'low': 'low', 'high': 'high'}

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        download_attachments = kwargs.get('download_attachments')
        cloud_data = kwargs.get(self._cloud_data_key, {})

        cc = self._cc  # alias
        self.object_id = cloud_data.get(cc('id'), None)
        self.subject = cloud_data.get(cc('subject'), kwargs.get('subject', '') or '')
        body = cloud_data.get(cc('body'), {})
        self.body = body.get(cc('content'), '')
        self.body_type = body.get(cc('contentType'), 'HTML')  # default to HTML for new messages

        self.__attendees = Attendees(event=self, attendees={self._cloud_data_key: cloud_data.get(cc('attendees'), [])})
        self.__categories = cloud_data.get(cc('categories'), [])

        self.created = cloud_data.get(cc('createdDateTime'), None)
        self.modified = cloud_data.get(cc('lastModifiedDateTime'), None)

        local_tz = get_localzone()
        self.created = parse(self.created).astimezone(local_tz) if self.created else None
        self.modified = parse(self.modified).astimezone(local_tz) if self.modified else None

        start = cloud_data.get(cc('start'), {})
        timezone = pytz.timezone(start.get(cc('timeZone'), local_tz))

        start = start.get(cc('dateTime'), None)
        start = parse(start).astimezone(timezone) if start else None
        if start and timezone != local_tz:
            start = start.astimezone(local_tz)
        self.start = start

        end = cloud_data.get(cc('end'), {})
        timezone = pytz.timezone(end.get(cc('timeZone'), local_tz))

        end = end.get(cc('dateTime'), None)
        end = parse(end).astimezone(timezone) if end else None
        if end and timezone != local_tz:
            end = start.astimezone(local_tz)
        self.end = end

        self.has_attachments = cloud_data.get(cc('hasAttachments'), False)
        self.__attachments = EventAttachments(parent=self, attachments=[])
        if self.has_attachments and download_attachments:
            self.attachments.download_attachments()
        self.categories = cloud_data.get(cc('categories'), [])
        self.ical_uid = cloud_data.get(cc('iCalUId'), None)
        self.importance = self._importance_options.get(cloud_data.get(cc('importance'), 'normal'), 'normal')  # only allow valid importance
        self.is_all_day = cloud_data.get(cc('isAllDay'), False)
        self.is_cancelled = cloud_data.get(cc('isCancelled'), False)
        self.is_organizer = cloud_data.get(cc('isOrganizer'), True)
        self.is_reminder_on = cloud_data.get(cc('isReminderOn'), None)
        self.location = cloud_data.get(cc('location'), {})  # TODO
        self.locations = cloud_data.get(cc('locations'), [])  # TODO
        self.online_meeting_url = cloud_data.get(cc('onlineMeetingUrl'), None)
        self.__organizer = self._recipient_from_cloud(cloud_data.get(cc('organizer'), None))
        self.recurrence = cloud_data.get(cc('recurrence'), None)  # TODO:
        self.remind_before_minutes = cloud_data.get(cc('reminderMinutesBeforeStart'), 15)
        self.response_requested = cloud_data.get(cc('responseRequested'), True)
        self.__response_status = ResponseStatus(parent=self, response_status=cloud_data.get(cc('responseStatus'), {}))
        self.__sensitivity = EventSensitivity(cloud_data.get(cc('sensitivity'), 'normal'))
        self.series_master_id = cloud_data.get(cc('seriesMasterId'), None)
        self.__show_as = EventShowAs(cloud_data.get(cc('showAs'), 'busy'))
        self.event_type = cloud_data.get(cc('type'), None)  # TODO: Enumerate type

    def __str__(self):
        return 'Subject: {}'.format(self.subject)

    def __repr__(self):
        return self.__str__()

    def to_api_data(self):
        pass

    @property
    def organizer(self):
        return self.__organizer

    @property
    def show_as(self):
        return self.__show_as

    @show_as.setter
    def show_as(self, value):
        self.__show_as = EventShowAs(value)

    @property
    def sensitivity(self):
        return self.__sensitivity

    @sensitivity.setter
    def sensitivity(self, value):
        self.__sensitivity = EventSensitivity(value)

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
        self.__owner = self._recipient_from_cloud(cloud_data.get(self._cc('owner'), {}))
        color = cloud_data.get(self._cc('color'), -1)
        if isinstance(color, str):
            color = -1 if color == 'auto' else color
            # TODO: other string colors?
        self.color = CalendarColors(color)
        self.can_edit = cloud_data.get(self._cc('canEdit'), False)
        self.can_share = cloud_data.get(self._cc('canShare'), False)
        self.can_view_private_items = cloud_data.get(self._cc('canViewPrivateItems'), False)

    def __str__(self):
        return 'Calendar: {} from {}'.format(self.name, self.owner)

    def __repr__(self):
        return self.__str__()

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

        try:
            response = self.con.patch(url, data=data)
        except Exception as e:
            log.error('Error updating calendar {}. Error: {}'.format(self.calendar_id, str(e)))
            return False

        if response.status_code != 201:
            log.debug('Updating calendar (id: {}) Request failed: {}'.format(self.calendar_id, response.reason))
            return False

        return True

    def delete(self):
        """ Deletes this calendar """

        if not self.calendar_id:
            return False

        url = self.build_url(self._endpoints.get('calendar').format(id=self.calendar_id))

        try:
            response = self.con.delete(url)
        except Exception as e:
            log.error('Error deleting calendar {}. Error: {}'.format(self.name, str(e)))
            return False

        if response.status_code != 204:
            log.debug('Deleting calendar Request failed: {}'.format(response.reason))
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

        url = self.build_url(self._endpoints.get('get_events'))

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

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error donwloading events. Error {}'.format(e))
            return []

        if response.status_code != 200:
            log.debug('Getting events Request failed: {}'.format(response.reason))
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        events = [self.event_constructor(parent=self, download_attachments=download_attachments,
                                         **{self._cloud_data_key: event})
                  for event in data.get('value', [])]
        if batch:
            return Pagination(parent=self, data=events, constructor=self.event_constructor,
                              next_link=data.get(NEXT_LINK_KEYWORD, None), limit=limit)
        else:
            return events

    def new_event(self, subject=None):
        """ Returns a new (unsaved) Event object """
        return self.event_constructor(parent=self, subject=subject)

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

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error getting event: {}. Error {}'.format(param, e))
            return None

        if response.status_code != 200:
            log.debug('Getting event Request failed: {}'.format(response.reason))
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
        'get_events': '/calendar/events'
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
        return 'Schedule resource: {}'.format(self.main_resource)

    def __repr__(self):
        return self.__str__()

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

        try:
            response = self.con.get(url, params=params or None)
        except Exception as e:
            log.error('Error getting calendars. Error {}'.format(str(e)))
            return []

        if response.status_code != 200:
            log.debug('Getting calendars Request failed: {}'.format(response.reason))
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

        try:
            response = self.con.post(url, data={self._cc('name'): calendar_name})
        except Exception as e:
            log.error('Error creating new calendar. Error: {}'.format(str(e)))
            return None

        if response.status_code != 201:
            log.debug('Creating new calendar Request failed: {}'.format(response.reason))
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

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error getting calendar {}. Error: {}'.format(calendar_id or calendar_name, str(e)))
            return None

        if response.status_code != 200:
            log.debug('Getting calendar Request failed: {}'.format(response.reason))
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

        try:
            response = self.con.get(url)
        except Exception as e:
            log.error('Error getting default calendar. Error: {}'.format(e))
            return None

        if response.status_code != 200:
            log.debug('Getting default calendar Request failed: {}'.format(response.reason))
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

        url = self.build_url(self._endpoints.get('get_events'))

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

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error donwloading events. Error {}'.format(e))
            return []

        if response.status_code != 200:
            log.debug('Getting events Request failed: {}'.format(response.reason))
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        events = [self.event_constructor(parent=self, download_attachments=download_attachments,
                                         **{self._cloud_data_key: event})
                  for event in data.get('value', [])]
        if batch:
            return Pagination(parent=self, data=events, constructor=self.event_constructor,
                              next_link=data.get(NEXT_LINK_KEYWORD, None), limit=limit)
        else:
            return events
