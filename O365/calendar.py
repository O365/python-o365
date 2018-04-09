import logging
from enum import Enum
from dateutil.parser import parse
from tzlocal import get_localzone
import pytz

from O365.utils.utils import Pagination, NEXT_LINK_KEYWORD, ApiComponent

log = logging.getLogger(__name__)


class AttendeeType(Enum):
    Required = 'required'
    Optional = 'optional'
    Resource = 'resource'


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


class Attendee:
    """ A Event attendee """

    def __init__(self, address, *, name=None, attendee_type=None, status=None):
        self.address = address
        self.name = name
        self.response_status = status[0] if status else None
        self.response_datetime = status[1] if status else None
        self.__attendee_type = AttendeeType.Required
        self.attendee_type = attendee_type

    @property
    def attendee_type(self):
        return self.__attendee_type

    @attendee_type.setter
    def attendee_type(self, value):
        self.__attendee_type = AttendeeType(value)

    def _to_api_data(self):
        pass


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
                email = attendees.get(self._cc('emailAddress'), {})
                address = email.get(self._cc('address'), None)
                if address:
                    name = email.get(self._cc('name'), None)
                    status = attendees.get(self._cc('status'), {})
                    response_time = status.get(self._cc('time'), None)
                    response_status = status.get(self._cc('response'), None)
                    if response_time:
                        local_tz = get_localzone()  # calls to get_localzone() are cached so no problem here
                        response_time = parse(response_time).astimezone(local_tz)

                    attendee_type = attendees.get(self._cc('type'), 'required')  # default value
                    self.__attendees.append(Attendee(address=address, name=name, attendee_type=attendee_type,
                                                     status=(response_status, response_time)))
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


class Event(ApiComponent):
    """ A Calendar event """

    _endpoints = {
        'calendar': '/calendars/{id}',
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        cc = self._cc  # alias
        self.object_id = cloud_data.get(cc('id'), None)
        self.subject = cloud_data.get(cc('subject'), '')
        body = cloud_data.get(cc('body'), {})
        self.body = body.get(cc('content'), '')
        self.body_type = body.get(cc('contentType'), 'HTML')  # default to HTML for new messages

        self.__attendees = Attendees(event=self, attendees=cloud_data.get(cc('attendees'), []))
        self.__categories = cloud_data.get(cc('categories'), [])

        self.created = cloud_data.get(cc('createdDateTime'), None)
        self.modified = cloud_data.get(cc('lastModifiedDateTime'), None)

        local_tz = get_localzone()
        self.created = parse(self.created).astimezone(local_tz) if self.created else None
        self.modified = parse(self.modified).astimezone(local_tz) if self.modified else None

        start = cloud_data.get(cc('start'), {})
        timezone = pytz.timezone(start.get(cc('timeZone'), get_localzone()))
        start = start.get(cc('dateTime'), None)
        self.start = parse(start).astimezone(timezone) if start else None

        end = cloud_data.get(cc('end'), {})
        timezone = pytz.timezone(end.get(cc('timeZone'), get_localzone()))
        end = end.get(cc('dateTime'), None)
        self.end = parse(end).astimezone(timezone) if end else None

        self.has_attachments = cloud_data.get(cc('hasAttachments'), False)

    @property
    def attendees(self):
        """ Just to avoid api misuse by assigning to 'attendees' """
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


class Calendar(ApiComponent):
    """ A Calendar Representation """

    _endpoints = {
        'calendar': '/calendars/{id}',
        # 'child_contact': '/contactFolders/{id}/contacts'
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
        owner = cloud_data.get(self._cc('owner'), {})
        self.owner_name = owner.get(self._cc('name'), '')
        self.owner_email = owner.get(self._cc('address'), '')
        self.color = CalendarColors(cloud_data.get(self._cc('color'), -1))
        self.can_edit = cloud_data.get(self._cc('canEdit'), False)
        self.can_share = cloud_data.get(self._cc('canShare'), False)
        self.can_view_private_items = cloud_data.get(self._cc('canViewPrivateItems'), False)

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


class Schedule(ApiComponent):
    """ A Wrapper around calendars and events"""

    _endpoints = {
        'root_calendars': '/calendars',
        'get_calendar': '/calendars/{id}',
    }
    calendar_constructor = Calendar

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
