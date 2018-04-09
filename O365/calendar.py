import logging
from enum import Enum

from O365.message import Recipient, MixinHandleRecipients
from O365.utils import Pagination, NEXT_LINK_KEYWORD, ApiComponent, RecipientType

log = logging.getLogger(__name__)


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

    def __init__(self, address, name=None, status=None, attendee_type=None):
        self.address = address
        self.name = name
        self.response_status = status[0] if status else None
        self.response_datetime = status[1] if status else None
        self.attendee_type = attendee_type

    def _to_api_data(self):
        pass


class Attendees:
    """ A Collection of Attendees """

    def __init__(self, event, attendees=None):
        self.event = event  # check if reference to event is needed
        self.attendees = []
        if attendees:
            self.add(attendees)

    def __iter__(self):
        return iter(self.attendees)

    def __getitem__(self, key):
        return self.attendees[key]

    def __contains__(self, item):
        return item in {attendee.email for attendee in self.attendees}

    def __len__(self):
        return len(self.attendees)

    def __str__(self):
        return 'Attendees Count: {}'.format(len(self.attendees))

    def clear(self):
        self.attendees = []

    def add(self, attendees):
        """ attendees must be a list of path strings or dictionary elements """

        if attendees:
            if isinstance(attendees, str):
                self.attendees.append(Attendee(address=attendees))
            elif isinstance(attendees, Attendee):
                self.attendees.append(attendees)
            elif isinstance(attendees, tuple):
                name, address = attendees
                if address:
                    self.attendees.append(Attendee(address=address, name=name))
            elif isinstance(attendees, list):
                for recipient in attendees:
                    self.add(recipient)
            else:
                raise ValueError('Recipients must be an address string, an'
                                 ' Attendee instance, a (name, address) tuple or a list')


class Event(ApiComponent):
    """ A Calendar event """

    _endpoints = {
        'calendar': '/calendars/{id}',
        # 'child_contact': '/contactFolders/{id}/contacts'
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        cc = self._cc  # alias
        self.event_id = cloud_data.get(cc('id'), None)
        self.subject = cloud_data.get(cc('subject'), '')
        body = cloud_data.get(cc('body'), {})
        self.body = body.get(cc('content'), '')
        self.body_type = body.get(cc('contentType'), 'HTML')  # default to HTML for new messages


        self.owner_name = owner.get(self._cc('name'), '')
        self.owner_email = owner.get(self._cc('address'), '')
        self.color = cloud_data.get(self._cc('color'), -1)
        self.color = CalendarColors(self.color)
        self.can_edit = cloud_data.get(self._cc('canEdit'), False)
        self.can_share = cloud_data.get(self._cc('canShare'), False)
        self.can_view_private_items = cloud_data.get(self._cc('canViewPrivateItems'), False)


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
        self.color = cloud_data.get(self._cc('color'), -1)
        self.color = CalendarColors(self.color)
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
