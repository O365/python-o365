"""
2019-04-15
Note: Support for workbooks stored in OneDrive Consumer platform is still not available.
At this time, only the files stored in business platform is supported by Excel REST APIs.
"""

import logging
import datetime as dt
from urllib.parse import quote

from .utils import ApiComponent
from .drive import File

log = logging.getLogger(__name__)

PERSISTENT_SESSION_INACTIVITY_MAX_AGE = 60 * 7  # 7 minutes
NON_PERSISTENT_SESSION_INACTIVITY_MAX_AGE = 60 * 5  # 5 minutes
EXCEL_XLSX_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class FunctionException(Exception):
    pass


class WorkbookSession(ApiComponent):
    """
    See https://docs.microsoft.com/en-us/graph/api/resources/excel?view=graph-rest-1.0#sessions-and-persistence
    """

    _endpoints = {
        'create_session': '/createSession',
        'refresh_session': '/refreshSession',
        'close_session': '/closeSession',
    }

    def __init__(self, *, parent=None, con=None, persist=True, **kwargs):
        """ Create a workbook session object.

        :param parent: parent for this operation
        :param Connection con: connection to use if no parent specified
        :param Bool persist: Whether or not to persist the session changes
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

        self.persist = persist

        self.inactivity_limit = dt.timedelta(seconds=PERSISTENT_SESSION_INACTIVITY_MAX_AGE) \
            if persist else dt.timedelta(seconds=NON_PERSISTENT_SESSION_INACTIVITY_MAX_AGE)
        self.session_id = None
        self.last_activity = dt.datetime.now()

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Workbook Session: {}'.format(self.session_id or 'Not set')

    def __bool__(self):
        return self.session_id is not None

    def create_session(self):
        """ Request a new session id """

        url = self.build_url(self._endpoints.get('create_session'))
        response = self.con.post(url, data={'persistChanges': self.persist})
        if not response:
            raise RuntimeError('Could not create session as requested by the user.')
        data = response.json()
        self.session_id = data.get('id')

        return True

    def refresh_session(self):
        """ Refresh the current session id """

        if self.session_id:
            url = self.build_url(self._endpoints.get('refresh_session'))
            response = self.con.post(url, headers={'workbook-session-id': self.session_id})
            return bool(response)
        return False

    def close_session(self):
        """ Close the current session """

        if self.session_id:
            url = self.build_url(self._endpoints.get('close_session'))
            response = self.con.post(url, headers={'workbook-session-id': self.session_id})
            return bool(response)
        return False

    def prepare_request(self, kwargs):
        """ If session is in use, prepares the request headers and
         checks if the session is expired.
        """
        if self.session_id is not None:
            actual = dt.datetime.now()

            if (self.last_activity + self.inactivity_limit) < actual:
                # session expired
                if self.persist:
                    # request new session
                    self.create_session()
                    actual = dt.datetime.now()
                else:
                    # raise error and recommend to manualy refresh session
                    raise RuntimeError('A non Persistent Session is expired. '
                                       'For consistency reasons this exception is raised. '
                                       'Please try again with manual refresh of the session ')
            self.last_activity = actual

            headers = kwargs.get('headers')
            if headers is None:
                kwargs['headers'] = headers = {}
            headers['workbook-session-id'] = self.session_id

    def get(self, *args, **kwargs):
        self.prepare_request(kwargs)
        return self.con.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.prepare_request(kwargs)
        return self.con.post(*args, **kwargs)

    def put(self, *args, **kwargs):
        self.prepare_request(kwargs)
        return self.con.put(*args, **kwargs)

    def patch(self, *args, **kwargs):
        self.prepare_request(kwargs)
        return self.con.patch(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.prepare_request(kwargs)
        return self.con.delete(*args, **kwargs)


class WorkSheet(ApiComponent):
    """ An Excel WorkSheet """

    _endpoints = {}

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError('Need a parent or a session but not both')

        self.workbook = parent
        self.session = parent.session if parent else session
        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id', None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        # append the encoded worksheet path
        main_resource = "{}/worksheets('{}')".format(main_resource, quote(self.object_id))

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.name = cloud_data.get('name', None)
        self.position = cloud_data.get('position', None)
        self.visibility = cloud_data.get('visibility', None)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Worksheet: {}'.format(self.name)

    def delete(self):
        """ Deletes this worksheet """
        return bool(self.session.delete(self.build_url('')))

    def update(self, *, name=None, position=None, visibility=None):
        """ Changes the name, position or visibility of this worksheet """

        if name is None and position is None and visibility is None:
            raise ValueError('Provide at least one parameter to update')
        data = {}
        if name:
            data['name'] = name
        if position:
            data['position'] = position
        if visibility:
            data['visibility'] = visibility

        response = self.session.patch(self.build_url(''), data=data)
        if not response:
            return False

        data = response.json()
        self.name = data.get('name', self.name)
        self.position = data.get('position', self.position)
        self.visibility = data.get('visibility', self.visibility)

        return True


class WorkBook(ApiComponent):
    _endpoints = {
        'get_worksheets': '/worksheets',
        'get_worksheet': '/worksheets/{id}',
        'function': '/functions/{name}',
    }
    worksheet_constructor = WorkSheet

    def __init__(self, file_item, *, use_session=True, persist=True):
        """ Create a workbook representation

        :param File file_item: the Drive File you want to interact with
        :param Bool use_session: Whether or not to use a session to be more efficient
        :param Bool persist: Whether or not to persist this info
        """
        if file_item is None or not isinstance(file_item, File) or file_item.mime_type != EXCEL_XLSX_MIME_TYPE:
            raise ValueError('This file is not a valid Excel xlsx file.')

        # append the workbook path
        main_resource = '{}{}/workbook'.format(file_item.main_resource,
                                               file_item._endpoints.get('item').format(id=file_item.object_id))

        super().__init__(protocol=file_item.protocol, main_resource=main_resource)

        persist = persist if use_session is True else True
        self.session = WorkbookSession(parent=file_item, persist=persist, main_resource=main_resource)

        if use_session:
            self.session.create_session()

        self.name = file_item.name

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Workbook: {}'.format(self.name)

    def get_worksheets(self):
        """ Returns a collection of this workbook worksheets"""

        url = self.build_url(self._endpoints.get('get_worksheets'))
        response = self.session.get(url)

        if not response:
            return []

        data = response.json()

        return [self.worksheet_constructor(parent=self, **{self._cloud_data_key: ws})
                for ws in data.get('value', [])]

    def get_worksheet(self, id_or_name):
        """ Gets a specific worksheet by id or name """
        url = self.build_url(self._endpoints.get('get_worksheet').format(id=quote(id_or_name)))
        response = self.session.get(url)
        if not response:
            return None
        data = response.json()
        return self.worksheet_constructor(parent=self, **{self._cloud_data_key: data})

    def add_worksheet(self, name=None):
        """ Adds a new worksheet """
        url = self.build_url(self._endpoints.get('get_worksheets'))
        response = self.session.post(url, data={'name': name} if name else None)
        if not response:
            return None
        data = response.json()
        return self.worksheet_constructor(parent=self, **{self._cloud_data_key: data})

    def delete_worksheet(self, worksheet_id):
        """ Deletes a worksheet by it's id """
        url = self.build_url(self._endpoints.get('get_worksheet').format(id=quote(worksheet_id)))
        return bool(self.session.delete(url))

    def invoke_function(self, function_name, **function_params):
        """ Invokes an Excel Function """
        url = self.build_url(self._endpoints.get('function').format(function_name))
        response = self.session.post(url, data=function_params)
        if not response:
            return None
        data = response.json()

        error = data.get('error')
        if error is None:
            return data.get('value')
        else:
            raise FunctionException(error)
