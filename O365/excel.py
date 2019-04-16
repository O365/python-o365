"""
2019-04-15
Note: Support for workbooks stored in OneDrive Consumer platform is still not available.
At this time, only the files stored in business platform is supported by Excel REST APIs.
"""

import logging
import datetime as dt
from urllib.parse import quote

from .drive import File
from .connection import MSOffice365Protocol
from .utils import ApiComponent


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


class Range(ApiComponent):
    """ An Excel Range """

    _endpoints = {
        'get_cell': '/cell(row={row},column={column})',
        'get_column': '/column(column={column})'
    }

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError('Need a parent or a session but not both')

        self.parent = parent
        self.session = parent.session if parent else session

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('address', None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        # append the encoded range path
        if isinstance(parent, Range):
            # strip the main resource
            main_resource = main_resource.split('/range')[0]
        main_resource = "{}/range(address='{}')".format(main_resource, quote(self.object_id))

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.address = cloud_data.get('address', '')
        self.address_local = cloud_data.get('addressLocal', '')
        self.column_count = cloud_data.get('columnCount', 0)
        self.row_count = cloud_data.get('rowCount', 0)
        self.cell_count = cloud_data.get('cellCount', 0)
        self.column_hidden = cloud_data.get('columnHidden', False)
        self.column_index = cloud_data.get('columnIndex', 0)  # zero indexed
        self.row_hidden = cloud_data.get('rowHidden', False)
        self.row_index = cloud_data.get('rowIndex', 0)  # zero indexed
        self.formulas = cloud_data.get('formulas', '')
        self.formulas_local = cloud_data.get('formulasLocal', '')
        self.formulas_r1c1 = cloud_data.get('formulasR1C1', '')
        self.hidden = cloud_data.get('hidden', False)
        self.number_format = cloud_data.get('numberFormat', '')
        self.text = cloud_data.get('text', '')
        self.value_types = cloud_data.get('valueTypes', '')
        self.values = cloud_data.get('values', '')

    def get_cell(self, row, column):
        """
        Gets the range object containing the single cell based on row and column numbers.
        :param int row: the row number
        :param int column: the column number
        :return: a Range instance
        """
        url = self.build_url(self._endpoints.get('get_cell').format(row=row, column=column))
        response = self.session.get(url)
        if not response:
            return None
        return self.__class__(parent=self, **{self._cloud_data_key: response.json()})

    def get_column(self, index):
        """
        Returns a column whitin the range
        :param int index: the index of the column. zero indexed
        :return: a Range
        """
        url = self.build_url(self._endpoints.get('get_column').format(column=index))
        response = self.session.get(url)
        if not response:
            return None
        return self.__class__(parent=self, **{self._cloud_data_key: response.json()})


class TableRow(ApiComponent):
    """ An Excel Table Row """

    _endpoints = {
        'get_range': '/range',
        'delete': '/delete',
    }
    range_constructor = Range

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError('Need a parent or a session but not both')

        self.table = parent
        self.session = parent.session if parent else session

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('index', None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        # append the encoded column path
        main_resource = '{}/rows/{}'.format(main_resource, quote(self.object_id))

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.index = cloud_data.get('index', 0)  # zero indexed
        self.values = cloud_data.get('values', '')  # json string

    def get_range(self):
        """ Gets the range object associated with the entire row """
        url = self.build_url(self._endpoints.get('get_range'))
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(parent=self, **{self._cloud_data_key: response.json()})

    def update(self, values):
        """ Updates this row """
        response = self.session.patch(self.build_url(''), data={'values': values})
        if not response:
            return False
        data = response.json()
        self.values = data.get('values', self.values)
        return True

    def delete(self):
        """ Deletes this row """
        url = self.build_url(self._endpoints.get('delete'))
        return bool(self.session.post(url))


class TableColumn(ApiComponent):
    """ An Excel Table Column """

    _endpoints = {
        'delete': '/delete',
        'data_body_range': '/dataBodyRange',
        'header_row_range': '/headerRowRange',
        'total_row_range': '/totalRowRange',
        'entire_range': '/range',
        'clear_filter': '/filter/clear',
        'apply_filter': '/filter/apply',
    }
    range_constructor = Range

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError('Need a parent or a session but not both')

        self.table = parent
        self.session = parent.session if parent else session

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id', None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        # append the encoded column path
        main_resource = "{}/columns('{}')".format(main_resource, quote(self.object_id))

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.name = cloud_data.get('name', '')
        self.index = cloud_data.get('index', 0)  # zero indexed
        self.values = cloud_data.get('values', '')  # json string

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Table Column: {}'.format(self.name)

    def delete(self):
        """ Deletes this table Column """
        url = self.build_url(self._endpoints.get('delete'))
        return bool(self.session.post(url))

    def update(self, values):
        """
        Updates this column
        :param values: values to update
        """
        response = self.session.patch(self.build_url(''), data={'values': values})
        if not response:
            return False
        data = response.json()

        self.values = data.get('values', '')
        return True

    def _get_range(self, endpoint_name):
        """ Returns a Range based on the endpoint name """

        url = self.build_url(self._endpoints.get(endpoint_name))
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(parent=self, **{self._cloud_data_key: response.json()})

    def get_data_body_range(self):
        """ Gets the range object associated with the data body of the column """
        return self._get_range('data_body_range')

    def get_header_row_range(self):
        """ Gets the range object associated with the header row of the column """
        return self._get_range('header_row_range')

    def get_total_row_range(self):
        """ Gets the range object associated with the totals row of the column """
        return self._get_range('total_row_range')

    def get_range(self):
        """ Gets the range object associated with the entire column """
        return self._get_range('entire_range')

    def clear_filter(self):
        """ Clears the filter applied to this column """
        url = self.build_url(self._endpoints.get('clear_filter'))
        return bool(self.session.post(url))

    def apply_filter(self, criteria):
        """
        Apply the given filter criteria on the given column.
        :param str criteria: the criteria to apply
        criteria example:
        {
          "color": "string",
          "criterion1": "string",
          "criterion2": "string",
          "dynamicCriteria": "string",
          "filterOn": "string",
          "icon": {"@odata.type": "microsoft.graph.workbookIcon"},
          "values": {"@odata.type": "microsoft.graph.Json"}
        }
        """
        url = self.build_url(self._endpoints.get('apply_filter'))
        return bool(self.session.post(url, data={'criteria': criteria}))

    def get_filter(self):
        """ Returns the filter applie to this column """
        q = self.q().select('name').expand('filter')
        response = self.session.get(self.build_url(''), params=q.as_params())
        if not response:
            return None
        data = response.json()
        return data.get('criteria', None)


class Table(ApiComponent):
    """ An Excel Table """

    _endpoints = {
        'get_columns': '/columns',
        'get_column': '/columns/{id}',
        'delete_column': '/columns/{id}/delete',
        'get_column_index': '/columns/itemAt',
        'add_column': '/columns/add',
        'get_rows': '/rows',
        'get_row': '/rows/{id}',
        'delete_row': '/rows/{id}/delete',
        'get_row_index': '/rows/itemAt',
        'add_rows': '/rows/add',
        'delete': '/delete',
        'data_body_range': '/dataBodyRange',
        'header_row_range': '/headerRowRange',
        'total_row_range': '/totalRowRange',
        'entire_range': '/range',
        'convert_to_range': '/convertToRange',
        'clear_filters': '/clearFilters',
        'reapply_filters': '/reapplyFilters',
    }
    column_constructor = TableColumn
    row_constructor = TableRow
    range_constructor = Range

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError('Need a parent or a session but not both')

        self.parent = parent
        self.session = parent.session if parent else session

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id', None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        # append the encoded table path
        main_resource = "{}/tables('{}')".format(main_resource, quote(self.object_id))

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.name = cloud_data.get('name', None)
        self.show_headers = cloud_data.get('showHeaders', True)
        self.show_totals = cloud_data.get('showTotals', True)
        self.style = cloud_data.get('style', None)
        self.highlight_first_column = cloud_data.get('highlightFirstColumn', False)
        self.highlight_last_column = cloud_data.get('highlightLastColumn', False)
        self.show_banded_columns = cloud_data.get('showBandedColumns', False)
        self.show_banded_rows = cloud_data.get('showBandedRows', False)
        self.show_filter_button = cloud_data.get('showFilterButton', False)
        self.legacy_id = cloud_data.get('legacyId', False)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Table: {}'.format(self.name)

    def get_columns(self, *, top=None, skip=None):
        """
        Return the columns of this table
        :param int top: specify n columns to retrieve
        :param int skip: specify n columns to skip
        """
        url = self.build_url(self._endpoints.get('get_columns'))

        params = {}
        if top is not None:
            params['$top'] = top
        if skip is not None:
            params['$skip'] = skip
        params = None if not params else params
        response = self.session.get(url, params=params)

        if not response:
            return iter(())

        data = response.json()

        return (self.column_constructor(parent=self, **{self._cloud_data_key: column})
                for column in data.get('value', []))

    def get_column(self, id_or_name):
        """
        Gets a column from this table by id or name
        :param id_or_name: the id or name of the column
        :return: WorkBookTableColumn
        """
        url = self.build_url(self._endpoints.get('get_column').format(quote(id_or_name)))
        response = self.session.get(url)

        if not response:
            return None

        data = response.json()

        return self.column_constructor(parent=self, **{self._cloud_data_key: data})

    def get_column_at_index(self, index):
        """
        Returns a table column by it's index
        :param int index: the zero-indexed position of the column in the table
        """
        if index is None:
            return None

        url = self.build_url(self._endpoints.get('get_column_index'))
        response = self.session.post(url, data={'index': index})

        if not response:
            return None

        return self.column_constructor(parent=self, **{self._cloud_data_key: response.json()})

    def delete_column(self, id_or_name):
        """
        Deletes a Column by its id or name
        :param id_or_name: the id or name of the column
        :return bool: Success or Failure
        """
        url = self.build_url(self._endpoints.get('delete_column').format(id=quote(id_or_name)))
        return bool(self.session.post(url))

    def add_column(self, name, *, index=0, values=None):
        """
        Adds a column to the table
        :param str name: the name of the column
        :param int index: the index at which the column should be added. Defaults to 0.
        :param list values: a two dimension array of values to add to the column
        """
        if name is None:
            return None

        params = {
            'name': name,
            'index': index
        }
        if values is not None:
            params['values'] = values

        url = self.build_url(self._endpoints.get('add_column'))
        response = self.session.post(url, data=params)
        if not response:
            return None

        data = response.json()

        return self.column_constructor(parent=self, **{self._cloud_data_key: data})

    def get_rows(self, *, top=None, skip=None):
        """
        Return the rows of this table
        :param int top: specify n rows to retrieve
        :param int skip: specify n rows to skip
        """
        url = self.build_url(self._endpoints.get('get_rows'))

        params = {}
        if top is not None:
            params['$top'] = top
        if skip is not None:
            params['$skip'] = skip
        params = None if not params else params
        response = self.session.get(url, params=params)

        if not response:
            return iter(())

        data = response.json()

        return (self.row_constructor(parent=self, **{self._cloud_data_key: row})
                for row in data.get('value', []))

    def get_row(self, index):
        """ Returns a Row instance at an index """
        url = self.build_url(self._endpoints.get('get_row').format(id=index))
        response = self.session.get(url)
        if not response:
            return None
        return self.row_constructor(parent=self, **{self._cloud_data_key: response.json()})

    def get_row_at_index(self, index):
        """
        Returns a table row by it's index
        :param int index: the zero-indexed position of the row in the table
        """
        if index is None:
            return None

        url = self.build_url(self._endpoints.get('get_row_index'))
        response = self.session.post(url, data={'index': index})

        if not response:
            return None

        return self.row_constructor(parent=self, **{self._cloud_data_key: response.json()})

    def delete_row(self, index):
        """
        Deletes a Row by it's index
        :param int index: the index of the row. zero indexed
        :return bool: Success or Failure
        """
        url = self.build_url(self._endpoints.get('delete_row').format(id=index))
        return bool(self.session.post(url))

    def add_rows(self, values=None, index=None):
        """
        Add rows to this table.
        Multiple rows can be added at once.

        This request might occasionally receive a 504 HTTP error.
         The appropriate response to this error is to repeat the request.
        :param list values: Optional. a 1 or 2 dimensional array of values to add
        :param int index: Optional. Specifies the relative position of the new row.
         If null, the addition happens at the end.
        :return:
        """
        params = {}
        if values is not None:
            if values and not isinstance(values[0], list):
                # this is a single row
                values = [values]
            params['values'] = values
        if index is not None:
            params['index'] = index

        params = params if params else None

        url = self.build_url(self._endpoints.get('add_rows'))
        response = self.session.post(url, data=params)
        if not response:
            return None
        return self.row_constructor(parent=self, **{self._cloud_data_key: response.json()})

    def update(self, *, name=None, show_headers=None, show_totals=None, style=None):
        """
        Updates this table
        :param str name: the name of the table
        :param bool show_headers: whether or not to show the headers
        :param bool show_totals: whether or not to show the totals
        :param str style: the style of the table
        :return: Success or Failure
        """
        if name is None and show_headers is None and show_totals is None and style is None:
            raise ValueError('Provide at least one parameter to update')
        data = {}
        if name:
            data['name'] = name
        if show_headers:
            data['showHeaders'] = show_headers
        if show_totals:
            data['showTotals'] = show_totals
        if style:
            data['style'] = style

        response = self.session.patch(self.build_url(''), data=data)
        if not response:
            return False

        data = response.json()
        self.name = data.get('name', self.name)
        self.show_headers = data.get('showHeaders', self.show_headers)
        self.show_totals = data.get('showTotals', self.show_totals)
        self.style = data.get('style', self.style)

        return True

    def delete(self):
        """ Deletes this table """
        url = self.build_url(self._endpoints.get('delete'))
        return bool(self.session.post(url))

    def _get_range(self, endpoint_name):
        """ Returns a Range based on the endpoint name """

        url = self.build_url(self._endpoints.get(endpoint_name))
        response = self.session.get(url)
        if not response:
            return None
        data = response.json()
        return self.range_constructor(parent=self, **{self._cloud_data_key: data})

    def get_data_body_range(self):
        """ Gets the range object associated with the data body of the table """
        return self._get_range('data_body_range')

    def get_header_row_range(self):
        """ Gets the range object associated with the header row of the table """
        return self._get_range('header_row_range')

    def get_total_row_range(self):
        """ Gets the range object associated with the totals row of the table """
        return self._get_range('total_row_range')

    def get_range(self):
        """ Gets the range object associated with the entire table """
        return self._get_range('entire_range')

    def convert_to_range(self):
        """ Converts the table into a normal range of cells. All data is preserved. """
        return self._get_range('convert_to_range')

    def clear_filters(self):
        """ Clears all the filters currently applied on the table. """
        url = self.build_url(self._endpoints.get('clear_filters'))
        return bool(self.session.post(url))

    def reapply_filters(self):
        """ Reapplies all the filters currently on the table. """
        url = self.build_url(self._endpoints.get('reapply_filters'))
        return bool(self.session.post(url))


class WorkSheet(ApiComponent):
    """ An Excel WorkSheet """

    _endpoints = {
        'get_tables': '/tables',
        'get_table': '/tables/{id}',
        'get_range': '/range',
        'add_table': '/tables/add',
        'get_used_range': '/usedRange',
        'get_cell': '/cell(row={row},column={column})',
    }
    table_constructor = Table
    range_constructor = Range

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

    def get_tables(self):
        """ Returns a collection of this worksheet tables"""

        url = self.build_url(self._endpoints.get('get_tables'))
        response = self.session.get(url)

        if not response:
            return []

        data = response.json()

        return [self.table_constructor(parent=self, **{self._cloud_data_key: table})
                for table in data.get('value', [])]

    def get_table(self, id_or_name):
        """
        Retrieves a Table by id or name
        :param str id_or_name: The id or name of the column
        :return: a Table instance
        """
        url = self.build_url(self._endpoints.get('get_table').format(id=id_or_name))
        response = self.session.get(url)
        if not response:
            return None
        return self.table_constructor(parent=self, **{self._cloud_data_key: response.json()})

    def add_table(self, address, has_headers):
        """
        Adds a table to this worksheet
        :param str address: a range address eg: 'A1:D4'
        :param bool has_headers: if the range address includes headers or not
        :return: a Table instance
        """
        if address is None:
            return None
        params = {
            'address': address,
            'hasHeaders': has_headers
        }
        url = self.build_url(self._endpoints.get('add_table'))
        response = self.session.post(url, data=params)
        if not response:
            return None
        return self.table_constructor(parent=self, **{self._cloud_data_key: response.json()})

    def get_range(self, address=None):
        """
        Returns a Range instance from whitin this worksheet
        :param str address: Optional, the range address you want
        :return: a Range instance
        """
        url = self.build_url(self._endpoints.get('get_range'))
        if address is not None:
            url = "{}(address='{}')".format(url, address)
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(parent=self, **{self._cloud_data_key: response.json()})

    def get_used_range(self):
        """ Returns the smallest range that encompasses any cells that
         have a value or formatting assigned to them.
        """
        url = self.build_url(self._endpoints.get('get_used_range'))
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(parent=self, **{self._cloud_data_key: response.json()})

    def get_cell(self, row, column):
        """ Gets the range object containing the single cell based on row and column numbers. """
        url = self.build_url(self._endpoints.get('get_cell').format(row=row, column=column))
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(parent=self, **{self._cloud_data_key: response.json()})


class WorkBook(ApiComponent):
    _endpoints = {
        'get_worksheets': '/worksheets',
        'get_tables': '/tables',
        'get_table': '/tables/{id}',
        'get_worksheet': '/worksheets/{id}',
        'function': '/functions/{name}',
    }
    worksheet_constructor = WorkSheet
    table_constructor = Table

    def __init__(self, file_item, *, use_session=True, persist=True):
        """ Create a workbook representation

        :param File file_item: the Drive File you want to interact with
        :param Bool use_session: Whether or not to use a session to be more efficient
        :param Bool persist: Whether or not to persist this info
        """
        if file_item is None or not isinstance(file_item, File) or file_item.mime_type != EXCEL_XLSX_MIME_TYPE:
            raise ValueError('This file is not a valid Excel xlsx file.')

        if isinstance(file_item.protocol, MSOffice365Protocol):
            raise ValueError('Excel capabilities are only allowed on the MSGraph protocol')

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

    def get_tables(self):
        """ Returns a collection of this workbook tables"""

        url = self.build_url(self._endpoints.get('get_tables'))
        response = self.session.get(url)

        if not response:
            return []

        data = response.json()

        return [self.table_constructor(parent=self, **{self._cloud_data_key: table})
                for table in data.get('value', [])]

    def get_table(self, id_or_name):
        """
        Retrieves a Table by id or name
        :param str id_or_name: The id or name of the column
        :return: a Table instance
        """
        url = self.build_url(self._endpoints.get('get_table').format(id=id_or_name))
        response = self.session.get(url)
        if not response:
            return None
        return self.table_constructor(parent=self, **{self._cloud_data_key: response.json()})

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
        return self.worksheet_constructor(parent=self, **{self._cloud_data_key: response.json()})

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
