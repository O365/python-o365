"""
2019-04-15
Note: Support for workbooks stored in OneDrive Consumer platform is still not available.
At this time, only the files stored in business platform is supported by Excel REST APIs.
"""

import datetime as dt
import logging
import re
from urllib.parse import quote

from .drive import File
from .utils import ApiComponent, TrackerSet, to_snake_case

log = logging.getLogger(__name__)

PERSISTENT_SESSION_INACTIVITY_MAX_AGE = 60 * 7  # 7 minutes
NON_PERSISTENT_SESSION_INACTIVITY_MAX_AGE = 60 * 5  # 5 minutes
EXCEL_XLSX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


UnsetSentinel = object()


# TODO Excel: WorkbookFormatProtection, WorkbookRangeBorder


class FunctionException(Exception):
    pass


class WorkbookSession(ApiComponent):
    """
    See https://docs.microsoft.com/en-us/graph/api/resources/excel?view=graph-rest-1.0#sessions-and-persistence
    """

    _endpoints = {
        "create_session": "/createSession",
        "refresh_session": "/refreshSession",
        "close_session": "/closeSession",
    }

    def __init__(self, *, parent=None, con=None, persist=True, **kwargs):
        """Create a workbook session object.

        :param parent: parent for this operation
        :param Connection con: connection to use if no parent specified
        :param Bool persist: Whether or not to persist the session changes
        """
        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #: Whether or not the session changes are persisted. |br| **Type:** bool
        self.persist = persist

        #: The inactivity limit. |br| **Type:** timedelta
        self.inactivity_limit = (
            dt.timedelta(seconds=PERSISTENT_SESSION_INACTIVITY_MAX_AGE)
            if persist
            else dt.timedelta(seconds=NON_PERSISTENT_SESSION_INACTIVITY_MAX_AGE)
        )
        #: The session id. |br| **Type:** str
        self.session_id = None
        #: The time of last activity. |br| **Type:** datetime
        self.last_activity = dt.datetime.now()

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Workbook Session: {}".format(self.session_id or "Not set")

    def __bool__(self):
        return self.session_id is not None

    def create_session(self):
        """Request a new session id"""

        url = self.build_url(self._endpoints.get("create_session"))
        response = self.con.post(url, data={"persistChanges": self.persist})
        if not response:
            raise RuntimeError("Could not create session as requested by the user.")
        data = response.json()
        self.session_id = data.get("id")

        return True

    def refresh_session(self):
        """Refresh the current session id"""

        if self.session_id:
            url = self.build_url(self._endpoints.get("refresh_session"))
            response = self.con.post(
                url, headers={"workbook-session-id": self.session_id}
            )
            return bool(response)
        return False

    def close_session(self):
        """Close the current session"""

        if self.session_id:
            url = self.build_url(self._endpoints.get("close_session"))
            response = self.con.post(
                url, headers={"workbook-session-id": self.session_id}
            )
            return bool(response)
        return False

    def prepare_request(self, kwargs):
        """If session is in use, prepares the request headers and
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
                    raise RuntimeError(
                        "A non Persistent Session is expired. "
                        "For consistency reasons this exception is raised. "
                        "Please try again with manual refresh of the session "
                    )
            self.last_activity = actual

            headers = kwargs.get("headers")
            if headers is None:
                kwargs["headers"] = headers = {}
            headers["workbook-session-id"] = self.session_id

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


class RangeFormatFont:
    """A font format applied to a range"""

    def __init__(self, parent):
        #: The parent of the range format font. |br| **Type:** parent
        self.parent = parent
        self._track_changes = TrackerSet(casing=parent._cc)
        self._loaded = False

        self._bold = False
        self._color = "#000000"  # default black
        self._italic = False
        self._name = "Calibri"
        self._size = 10
        self._underline = "None"

    def _load_data(self):
        """Loads the data into this instance"""
        url = self.parent.build_url(self.parent._endpoints.get("format"))
        response = self.parent.session.get(url)
        if not response:
            return False
        data = response.json()

        self._bold = data.get("bold", False)
        self._color = data.get("color", "#000000")  # default black
        self._italic = data.get("italic", False)
        self._name = data.get("name", "Calibri")  # default Calibri
        self._size = data.get("size", 10)  # default 10
        self._underline = data.get("underline", "None")

        self._loaded = True
        return True

    def to_api_data(self, restrict_keys=None):
        """Returns a dict to communicate with the server

        :param restrict_keys: a set of keys to restrict the returned data to
        :rtype: dict
        """
        cc = self.parent._cc  # alias
        data = {
            cc("bold"): self._bold,
            cc("color"): self._color,
            cc("italic"): self._italic,
            cc("name"): self._name,
            cc("size"): self._size,
            cc("underline"): self._underline,
        }

        if restrict_keys:
            for key in list(data.keys()):
                if key not in restrict_keys:
                    del data[key]
        return data

    @property
    def bold(self):
        if not self._loaded:
            self._load_data()
        return self._bold

    @bold.setter
    def bold(self, value):
        self._bold = value
        self._track_changes.add("bold")

    @property
    def color(self):
        """The color of the range format font

        :getter: get the color
        :setter: set the color
        :type: str
        """
        if not self._color:
            self._load_data()
        return self._color

    @color.setter
    def color(self, value):
        self._color = value
        self._track_changes.add("color")

    @property
    def italic(self):
        """Is range format font in italics

        :getter: get the italic
        :setter: set the italic
        :type: bool
        """
        if not self._loaded:
            self._load_data()
        return self._italic

    @italic.setter
    def italic(self, value):
        self._italic = value
        self._track_changes.add("italic")

    @property
    def name(self):
        """The name of the range format font

        :getter: get the name
        :setter: set the name
        :type: str
        """
        if not self._loaded:
            self._load_data()
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._track_changes.add("name")

    @property
    def size(self):
        """The size of the range format font

        :getter: get the size
        :setter: set the size
        :type: int
        """
        if not self._loaded:
            self._load_data()
        return self._size

    @size.setter
    def size(self, value):
        self._size = value
        self._track_changes.add("size")

    @property
    def underline(self):
        """Is range format font underlined

        :getter: get the underline
        :setter: set the underline
        :type: bool
        """
        if not self._loaded:
            self._load_data()
        return self._underline

    @underline.setter
    def underline(self, value):
        self._underline = value
        self._track_changes.add("underline")


class RangeFormat(ApiComponent):
    """A format applied to a range"""

    _endpoints = {
        "borders": "/borders",
        "font": "/font",
        "fill": "/fill",
        "clear_fill": "/fill/clear",
        "auto_fit_columns": "/autofitColumns",
        "auto_fit_rows": "/autofitRows",
    }

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError("Need a parent or a session but not both")

        #: The range of the range format. |br| **Type:** range
        self.range = parent
        #: The session for the range format. |br| **Type:** str
        self.session = parent.session if parent else session

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        # append the format path
        main_resource = "{}/format".format(main_resource)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        self._track_changes = TrackerSet(casing=self._cc)
        self._track_background_color = False

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self._column_width = cloud_data.get("columnWidth", 11)
        self._horizontal_alignment = cloud_data.get("horizontalAlignment", "General")
        self._row_height = cloud_data.get("rowHeight", 15)
        self._vertical_alignment = cloud_data.get("verticalAlignment", "Bottom")
        self._wrap_text = cloud_data.get("wrapText", None)

        self._font = RangeFormatFont(self)
        self._background_color = UnsetSentinel

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Format for range address: {}".format(
            self.range.address if self.range else "Unkknown"
        )

    @property
    def column_width(self):
        """The width of all columns within the range

        :getter: get the column_width
        :setter: set the column_width
        :type: float
        """
        return self._column_width

    @column_width.setter
    def column_width(self, value):
        self._column_width = value
        self._track_changes.add("column_width")

    @property
    def horizontal_alignment(self):
        """The horizontal alignment for the specified object.
        Possible values are: General, Left, Center, Right, Fill, Justify,
        CenterAcrossSelection, Distributed.

        :getter: get the vertical_alignment
        :setter: set the vertical_alignment
        :type: string
        """
        return self._horizontal_alignment

    @horizontal_alignment.setter
    def horizontal_alignment(self, value):
        self._horizontal_alignment = value
        self._track_changes.add("horizontal_alignment")

    @property
    def row_height(self):
        """The height of all rows in the range.

        :getter: get the row_height
        :setter: set the row_height
        :type: float
        """
        return self._row_height

    @row_height.setter
    def row_height(self, value):
        self._row_height = value
        self._track_changes.add("row_height")

    @property
    def vertical_alignment(self):
        """The vertical alignment for the specified object.
        Possible values are: Top, Center, Bottom, Justify, Distributed.

        :getter: get the vertical_alignment
        :setter: set the vertical_alignment
        :type: string
        """
        return self._vertical_alignment

    @vertical_alignment.setter
    def vertical_alignment(self, value):
        self._vertical_alignment = value
        self._track_changes.add("vertical_alignment")

    @property
    def wrap_text(self):
        """Indicates whether Excel wraps the text in the object

        :getter: get the wrap_text
        :setter: set the wrap_text
        :type: bool
        """
        return self._wrap_text

    @wrap_text.setter
    def wrap_text(self, value):
        self._wrap_text = value
        self._track_changes.add("wrap_text")

    def to_api_data(self, restrict_keys=None):
        """Returns a dict to communicate with the server

        :param restrict_keys: a set of keys to restrict the returned data to
        :rtype: dict
        """
        cc = self._cc  # alias
        data = {
            cc("column_width"): self._column_width,
            cc("horizontal_alignment"): self._horizontal_alignment,
            cc("row_height"): self._row_height,
            cc("vertical_alignment"): self._vertical_alignment,
            cc("wrap_text"): self._wrap_text,
        }

        if restrict_keys:
            for key in list(data.keys()):
                if key not in restrict_keys:
                    del data[key]
        return data

    def update(self):
        """Updates this range format"""
        if self._track_changes:
            data = self.to_api_data(restrict_keys=self._track_changes)
            if data:
                response = self.session.patch(self.build_url(""), data=data)
                if not response:
                    return False
                self._track_changes.clear()
        if self._font._track_changes:
            data = self._font.to_api_data(restrict_keys=self._font._track_changes)
            if data:
                response = self.session.patch(
                    self.build_url(self._endpoints.get("font")), data=data
                )
                if not response:
                    return False
                self._font._track_changes.clear()
        if self._track_background_color:
            if self._background_color is None:
                url = self.build_url(self._endpoints.get("clear_fill"))
                response = self.session.post(url)
            else:
                data = {"color": self._background_color}
                url = self.build_url(self._endpoints.get("fill"))
                response = self.session.patch(url, data=data)
            if not response:
                return False
            self._track_background_color = False

        return True

    @property
    def font(self):
        """Returns the font object defined on the overall range selected

        :getter: get the font
        :setter: set the font
        :type: RangeFormatFont
        """
        return self._font

    @property
    def background_color(self):
        """The background color of the range

        :getter: get the background_color
        :setter: set the background_color
        :type: UnsentSentinel
        """
        if self._background_color is UnsetSentinel:
            self._load_background_color()
        return self._background_color

    @background_color.setter
    def background_color(self, value):
        self._background_color = value
        self._track_background_color = True

    def _load_background_color(self):
        """Loads the data related to the fill color"""
        url = self.build_url(self._endpoints.get("fill"))
        response = self.session.get(url)
        if not response:
            return None
        data = response.json()
        self._background_color = data.get("color", None)

    def auto_fit_columns(self):
        """Changes the width of the columns of the current range
        to achieve the best fit, based on the current data in the columns
        """
        url = self.build_url(self._endpoints.get("auto_fit_columns"))
        return bool(self.session.post(url))

    def auto_fit_rows(self):
        """Changes the width of the rows of the current range
        to achieve the best fit, based on the current data in the rows
        """
        url = self.build_url(self._endpoints.get("auto_fit_rows"))
        return bool(self.session.post(url))

    def set_borders(self, side_style=""):
        """Sets the border of this range"""
        pass


class Range(ApiComponent):
    """An Excel Range"""

    _endpoints = {
        "get_cell": "/cell(row={},column={})",
        "get_column": "/column(column={})",
        "get_bounding_rect": "/boundingRect",
        "columns_after": "/columnsAfter(count={})",
        "columns_before": "/columnsBefore(count={})",
        "entire_column": "/entireColumn",
        "intersection": "/intersection",
        "last_cell": "/lastCell",
        "last_column": "/lastColumn",
        "last_row": "/lastRow",
        "offset_range": "/offsetRange",
        "get_row": "/row",
        "rows_above": "/rowsAbove(count={})",
        "rows_below": "/rowsBelow(count={})",
        "get_used_range": "/usedRange(valuesOnly={})",
        "clear_range": "/clear",
        "delete_range": "/delete",
        "insert_range": "/insert",
        "merge_range": "/merge",
        "unmerge_range": "/unmerge",
        "get_resized_range": "/resizedRange(deltaRows={}, deltaColumns={})",
        "get_format": "/format",
    }
    range_format_constructor = RangeFormat  #: :meta private:

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError("Need a parent or a session but not both")

        self.session = parent.session if parent else session

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: The id of the range. |br| **Type:** str
        self.object_id = cloud_data.get("address", None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        # append the encoded range path
        if isinstance(parent, Range):
            # strip the main resource
            main_resource = main_resource.split("/range")[0]
        if isinstance(parent, (WorkSheet, Range)):
            if "!" in self.object_id:
                # remove the sheet string from the address as it's not needed
                self.object_id = self.object_id.split("!")[1]
            main_resource = "{}/range(address='{}')".format(
                main_resource, quote(self.object_id)
            )
        else:
            main_resource = "{}/range".format(main_resource)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        self._track_changes = TrackerSet(casing=self._cc)

        #: Represents the range reference in A1-style.
        #: Address value contains the Sheet reference
        #: (for example, Sheet1!A1:B4). |br| **Type:** str
        self.address = cloud_data.get("address", "")
        #: Represents range reference for the specified range in the language of the user.
        #:  |br| **Type:** str
        self.address_local = cloud_data.get("addressLocal", "")
        #: Represents the total number of columns in the range. |br| **Type:** int
        self.column_count = cloud_data.get("columnCount", 0)
        #: Returns the total number of rows in the range. |br| **Type:** int
        self.row_count = cloud_data.get("rowCount", 0)
        #: Number of cells in the range. |br| **Type:** int
        self.cell_count = cloud_data.get("cellCount", 0)
        self._column_hidden = cloud_data.get("columnHidden", False)
        #: Represents the column number of the first cell in the range. Zero-indexed.
        #: |br| **Type:** int
        self.column_index = cloud_data.get("columnIndex", 0)  # zero indexed
        self._row_hidden = cloud_data.get("rowHidden", False)
        #: Returns the row number of the first cell in the range. Zero-indexed.
        #: |br| **Type:** int
        self.row_index = cloud_data.get("rowIndex", 0)  # zero indexed
        self._formulas = cloud_data.get("formulas", [[]])
        self._formulas_local = cloud_data.get("formulasLocal", [[]])
        self._formulas_r1_c1 = cloud_data.get("formulasR1C1", [[]])
        #: Represents if all cells of the current range are hidden. |br| **Type:** bool
        self.hidden = cloud_data.get("hidden", False)
        self._number_format = cloud_data.get("numberFormat", [[]])
        #: Text values of the specified range. |br| **Type:** str
        self.text = cloud_data.get("text", [[]])
        #: Represents the type of data of each cell.
        #: The possible values are: Unknown, Empty, String,
        #: Integer, Double, Boolean, Error. |br| **Type:** list[list]
        self.value_types = cloud_data.get("valueTypes", [[]])
        self._values = cloud_data.get("values", [[]])

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Range address: {}".format(self.address)

    def __eq__(self, other):
        return self.object_id == other.object_id

    @property
    def column_hidden(self):
        """Indicates whether all columns of the current range are hidden.

        :getter: get the column_hidden
        :setter: set the column_hidden
        :type: bool
        """
        return self._column_hidden

    @column_hidden.setter
    def column_hidden(self, value):
        self._column_hidden = value
        self._track_changes.add("column_hidden")

    @property
    def row_hidden(self):
        """Indicates whether all rows of the current range are hidden.

        :getter: get the row_hidden
        :setter: set the row_hidden
        :type: bool
        """
        return self._row_hidden

    @row_hidden.setter
    def row_hidden(self, value):
        self._row_hidden = value
        self._track_changes.add("row_hidden")

    @property
    def formulas(self):
        """Represents the formula in A1-style notation.

        :getter: get the formulas
        :setter: set the formulas
        :type: any
        """
        return self._formulas

    @formulas.setter
    def formulas(self, value):
        self._formulas = value
        self._track_changes.add("formulas")

    @property
    def formulas_local(self):
        """Represents the formula in A1-style notation, in the user's language
        and number-formatting locale. For example, the English "=SUM(A1, 1.5)"
        formula would become "=SUMME(A1; 1,5)" in German.

        :getter: get the formulas_local
        :setter: set the formulas_local
        :type: list[list]
        """
        return self._formulas_local

    @formulas_local.setter
    def formulas_local(self, value):
        self._formulas_local = value
        self._track_changes.add("formulas_local")

    @property
    def formulas_r1_c1(self):
        """Represents the formula in R1C1-style notation.

        :getter: get the formulas_r1_c1
        :setter: set the formulas_r1_c1
        :type: list[list]
        """
        return self._formulas_r1_c1

    @formulas_r1_c1.setter
    def formulas_r1_c1(self, value):
        self._formulas_r1_c1 = value
        self._track_changes.add("formulas_r1_c1")

    @property
    def number_format(self):
        """Represents Excel's number format code for the given cell.

        :getter: get the number_format
        :setter: set the number_fromat
        :type: list[list]
        """
        return self._number_format

    @number_format.setter
    def number_format(self, value):
        self._number_format = value
        self._track_changes.add("number_format")

    @property
    def values(self):
        """Represents the raw values of the specified range.
        The data returned can be of type string, number, or a Boolean.
        Cell that contains an error returns the error string.

        :getter: get the number_format
        :setter: set the number_fromat
        :type: list[list]
        """
        return self._values

    @values.setter
    def values(self, value):
        if not isinstance(value, list):
            value = [[value]]  # values is always a 2 dimensional array
        self._values = value
        self._track_changes.add("values")

    def to_api_data(self, restrict_keys=None):
        """Returns a dict to communicate with the server

        :param restrict_keys: a set of keys to restrict the returned data to
        :rtype: dict
        """
        cc = self._cc  # alias
        data = {
            cc("column_hidden"): self._column_hidden,
            cc("row_hidden"): self._row_hidden,
            cc("formulas"): self._formulas,
            cc("formulas_local"): self._formulas_local,
            cc("formulas_r1_c1"): self._formulas_r1_c1,
            cc("number_format"): self._number_format,
            cc("values"): self._values,
        }

        if restrict_keys:
            for key in list(data.keys()):
                if key not in restrict_keys:
                    del data[key]
        return data

    def _get_range(self, endpoint, *args, method="GET", **kwargs):
        """Helper that returns another range"""
        if args:
            url = self.build_url(self._endpoints.get(endpoint).format(*args))
        else:
            url = self.build_url(self._endpoints.get(endpoint))
        if not kwargs:
            kwargs = None
        if method == "GET":
            response = self.session.get(url, params=kwargs)
        elif method == "POST":
            response = self.session.post(url, data=kwargs)
        if not response:
            return None
        return self.__class__(parent=self, **{self._cloud_data_key: response.json()})

    def get_cell(self, row, column):
        """
        Gets the range object containing the single cell based on row and column numbers.
        :param int row: the row number
        :param int column: the column number
        :return: a Range instance
        """
        return self._get_range("get_cell", row, column)

    def get_column(self, index):
        """
        Returns a column whitin the range
        :param int index: the index of the column. zero indexed
        :return: a Range
        """
        return self._get_range("get_column", index)

    def get_bounding_rect(self, address):
        """
        Gets the smallest range object that encompasses the given ranges.
        For example, the GetBoundingRect of "B2:C5" and "D10:E15" is "B2:E16".
        :param str address: another address to retrieve it's bounding rect
        """
        return self._get_range("get_bounding_rect", anotherRange=address)

    def get_columns_after(self, columns=1):
        """
        Gets a certain number of columns to the right of the given range.
        :param int columns: Optional. The number of columns to include in the resulting range.
        """
        return self._get_range("columns_after", columns, method="POST")

    def get_columns_before(self, columns=1):
        """
        Gets a certain number of columns to the left  of the given range.
        :param int columns: Optional. The number of columns to include in the resulting range.
        """
        return self._get_range("columns_before", columns, method="POST")

    def get_entire_column(self):
        """Gets a Range that represents the entire column of the range."""
        return self._get_range("entire_column")

    def get_intersection(self, address):
        """
        Gets the Range that represents the rectangular intersection of the given ranges.

        :param address: the address range you want ot intersect with.
        :return: Range
        """
        self._get_range("intersection", anotherRange=address)

    def get_last_cell(self):
        """Gets the last cell within the range."""
        return self._get_range("last_cell")

    def get_last_column(self):
        """Gets the last column within the range."""
        return self._get_range("last_column")

    def get_last_row(self):
        """Gets the last row within the range."""
        return self._get_range("last_row")

    def get_offset_range(self, row_offset, column_offset):
        """Gets an object which represents a range that's offset from the specified range.
            The dimension of the returned range will match this range.
            If the resulting range is forced outside the bounds of the worksheet grid,
            an exception will be thrown.

        :param int row_offset: The number of rows (positive, negative, or 0)
         by which the range is to be offset.
        :param int column_offset: he number of columns (positive, negative, or 0)
         by which the range is to be offset.
        :return: Range
        """

        return self._get_range(
            "offset_range", rowOffset=row_offset, columnOffset=column_offset
        )

    def get_row(self, index):
        """
        Gets a row contained in the range.
        :param int index: Row number of the range to be retrieved.
        :return: Range
        """
        return self._get_range("get_row", method="POST", row=index)

    def get_rows_above(self, rows=1):
        """
        Gets a certain number of rows above a given range.

        :param int rows: Optional. The number of rows to include in the resulting range.
        :return: Range
        """
        return self._get_range("rows_above", rows, method="POST")

    def get_rows_below(self, rows=1):
        """
        Gets a certain number of rows below a given range.

        :param int rows: Optional. The number of rows to include in the resulting range.
        :return: Range
        """
        return self._get_range("rows_below", rows, method="POST")

    def get_used_range(self, only_values=True):
        """
        Returns the used range of the given range object.

        :param bool only_values: Optional. Defaults to True.
          Considers only cells with values as used cells (ignores formatting).
        :return: Range
        """
        # Format the "only_values" parameter as a lowercase string to work correctly with the Graph API
        return self._get_range("get_used_range", str(only_values).lower())

    def clear(self, apply_to="all"):
        """
        Clear range values, format, fill, border, etc.

        :param str apply_to: Optional. Determines the type of clear action.
          The possible values are: all, formats, contents.
        """
        url = self.build_url(self._endpoints.get("clear_range"))
        return bool(self.session.post(url, data={"applyTo": apply_to.capitalize()}))

    def delete(self, shift="up"):
        """
        Deletes the cells associated with the range.

        :param str shift: Optional. Specifies which way to shift the cells.
          The possible values are: up, left.
        """
        url = self.build_url(self._endpoints.get("delete_range"))
        return bool(self.session.post(url, data={"shift": shift.capitalize()}))

    def insert_range(self, shift):
        """
        Inserts a cell or a range of cells into the worksheet in place of this range,
        and shifts the other cells to make space.

        :param str shift: Specifies which way to shift the cells. The possible values are: down, right.
        :return: new Range instance at the now blank space
        """
        return self._get_range("insert_range", method="POST", shift=shift.capitalize())

    def merge(self, across=False):
        """
        Merge the range cells into one region in the worksheet.

        :param bool across: Optional. Set True to merge cells in each row of the
         specified range as separate merged cells.
        """
        url = self.build_url(self._endpoints.get("merge_range"))
        return bool(self.session.post(url, data={"across": across}))

    def unmerge(self):
        """Unmerge the range cells into separate cells."""
        url = self.build_url(self._endpoints.get("unmerge_range"))
        return bool(self.session.post(url))

    def get_resized_range(self, rows, columns):
        """
        Gets a range object similar to the current range object,
        but with its bottom-right corner expanded (or contracted)
        by some number of rows and columns.

        :param int rows: The number of rows by which to expand the
          bottom-right corner, relative to the current range.
        :param int columns: The number of columns by which to expand the
          bottom-right corner, relative to the current range.
        :return: Range
        """
        return self._get_range("get_resized_range", rows, columns, method="GET")

    def update(self):
        """Update this range"""

        if not self._track_changes:
            return True  # there's nothing to update

        data = self.to_api_data(restrict_keys=self._track_changes)
        response = self.session.patch(self.build_url(""), data=data)
        if not response:
            return False

        data = response.json()

        for field in self._track_changes:
            setattr(self, to_snake_case(field), data.get(field))
        self._track_changes.clear()

        return True

    def get_worksheet(self):
        """Returns this range worksheet"""
        url = self.build_url("")
        q = self.q().select("address").expand("worksheet")
        response = self.session.get(url, params=q.as_params())
        if not response:
            return None
        data = response.json()

        ws = data.get("worksheet")
        if ws is None:
            return None
        return WorkSheet(session=self.session, **{self._cloud_data_key: ws})

    def get_format(self):
        """Returns a RangeFormat instance with the format of this range"""
        url = self.build_url(self._endpoints.get("get_format"))
        response = self.session.get(url)
        if not response:
            return None
        return self.range_format_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )


class NamedRange(ApiComponent):
    """Represents a defined name for a range of cells or value"""

    _endpoints = {
        "get_range": "/range",
    }

    range_constructor = Range  #: :meta private:

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError("Need a parent or a session but not both")

        self.session = parent.session if parent else session

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: Id of the named range |br| **Type:** str
        self.object_id = cloud_data.get("name", None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        main_resource = "{}/names/{}".format(main_resource, self.object_id)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #: The name of the object. |br| **Type:** str
        self.name = cloud_data.get("name", None)
        #: The comment associated with this name. |br| **Type:** str
        self.comment = cloud_data.get("comment", "")
        #: Indicates whether the name is scoped to the workbook or to a specific worksheet.
        #: |br| **Type:** str
        self.scope = cloud_data.get("scope", "")
        #: The type of reference is associated with the name.
        #: Possible values are: String, Integer, Double, Boolean, Range. |br| **Type:** str
        self.data_type = cloud_data.get("type", "")
        #: The formula that the name is defined to refer to.
        #: For example, =Sheet14!$B$2:$H$12 and =4.75. |br| **Type:** str
        self.value = cloud_data.get("value", "")
        #: Indicates whether the object is visible. |br| **Type:** bool
        self.visible = cloud_data.get("visible", True)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Named Range: {} ({})".format(self.name, self.value)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def get_range(self):
        """Returns the Range instance this named range refers to"""
        url = self.build_url(self._endpoints.get("get_range"))
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def update(self, *, visible=None, comment=None):
        """
        Updates this named range
        :param bool visible: Specifies whether the object is visible or not
        :param str comment: Represents the comment associated with this name
        :return: Success or Failure
        """
        if visible is None and comment is None:
            raise ValueError('Provide "visible" or "comment" to update.')
        data = {}
        if visible is not None:
            data["visible"] = visible
        if comment is not None:
            data["comment"] = comment
        data = None if not data else data
        response = self.session.patch(self.build_url(""), data=data)
        if not response:
            return False
        data = response.json()

        self.visible = data.get("visible", self.visible)
        self.comment = data.get("comment", self.comment)
        return True


class TableRow(ApiComponent):
    """An Excel Table Row"""

    _endpoints = {
        "get_range": "/range",
        "delete": "/delete",
    }
    range_constructor = Range  #: :meta private:

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError("Need a parent or a session but not both")

        #: Parent of the table row. |br| **Type:** parent
        self.table = parent
        #: Session of table row |br| **Type:** session
        self.session = parent.session if parent else session

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: Id of the Table Row |br| **Type:** str
        self.object_id = cloud_data.get("index", None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        # append the encoded column path
        main_resource = "{}/rows/itemAt(index={})".format(main_resource, self.object_id)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #: The index of the row within the rows collection of the table. Zero-based.
        #: |br| **Type:** int
        self.index = cloud_data.get("index", 0)  # zero indexed
        #: The raw values of the specified range.
        #: The data returned could be of type string, number, or a Boolean.
        #: Any cell that contain an error will return the error string.
        #: |br| **Type:** list[list]
        self.values = cloud_data.get("values", [[]])  # json string

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Row number: {}".format(self.index)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def get_range(self):
        """Gets the range object associated with the entire row"""
        url = self.build_url(self._endpoints.get("get_range"))
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def update(self, values):
        """Updates this row"""
        response = self.session.patch(self.build_url(""), data={"values": values})
        if not response:
            return False
        data = response.json()
        self.values = data.get("values", self.values)
        return True

    def delete(self):
        """Deletes this row"""
        url = self.build_url(self._endpoints.get("delete"))
        return bool(self.session.post(url))


class TableColumn(ApiComponent):
    """An Excel Table Column"""

    _endpoints = {
        "delete": "/delete",
        "data_body_range": "/dataBodyRange",
        "header_row_range": "/headerRowRange",
        "total_row_range": "/totalRowRange",
        "entire_range": "/range",
        "clear_filter": "/filter/clear",
        "apply_filter": "/filter/apply",
    }
    range_constructor = Range  #: :meta private:

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError("Need a parent or a session but not both")

        #: Parent of the table column. |br| **Type:** parent
        self.table = parent
        #: session of the table column.. |br| **Type:** session
        self.session = parent.session if parent else session

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: Id of the Table Column|br| **Type:** str
        self.object_id = cloud_data.get("id", None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        # append the encoded column path
        main_resource = "{}/columns('{}')".format(main_resource, quote(self.object_id))

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #: The name of the table column. |br| **Type:** str
        self.name = cloud_data.get("name", "")
        #: TThe index of the column within the columns collection of the table. Zero-indexed.
        #: |br| **Type:** int
        self.index = cloud_data.get("index", 0)  # zero indexed
        #: Represents the raw values of the specified range.
        #: The data returned could be of type string, number, or a Boolean.
        #: Cell that contain an error will return the error string. |br| **Type:** list[list]
        self.values = cloud_data.get("values", [[]])  # json string

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Table Column: {}".format(self.name)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def delete(self):
        """Deletes this table Column"""
        url = self.build_url(self._endpoints.get("delete"))
        return bool(self.session.post(url))

    def update(self, values):
        """
        Updates this column
        :param values: values to update
        """
        response = self.session.patch(self.build_url(""), data={"values": values})
        if not response:
            return False
        data = response.json()

        self.values = data.get("values", "")
        return True

    def _get_range(self, endpoint_name):
        """Returns a Range based on the endpoint name"""

        url = self.build_url(self._endpoints.get(endpoint_name))
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def get_data_body_range(self):
        """Gets the range object associated with the data body of the column"""
        return self._get_range("data_body_range")

    def get_header_row_range(self):
        """Gets the range object associated with the header row of the column"""
        return self._get_range("header_row_range")

    def get_total_row_range(self):
        """Gets the range object associated with the totals row of the column"""
        return self._get_range("total_row_range")

    def get_range(self):
        """Gets the range object associated with the entire column"""
        return self._get_range("entire_range")

    def clear_filter(self):
        """Clears the filter applied to this column"""
        url = self.build_url(self._endpoints.get("clear_filter"))
        return bool(self.session.post(url))

    def apply_filter(self, criteria):
        """
        Apply the given filter criteria on the given column.

        :param str criteria: the criteria to apply

            Example:

            .. code-block:: json

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
        url = self.build_url(self._endpoints.get("apply_filter"))
        return bool(self.session.post(url, data={"criteria": criteria}))

    def get_filter(self):
        """Returns the filter applie to this column"""
        q = self.q().select("name").expand("filter")
        response = self.session.get(self.build_url(""), params=q.as_params())
        if not response:
            return None
        data = response.json()
        return data.get("criteria", None)


class Table(ApiComponent):
    """An Excel Table"""

    _endpoints = {
        "get_columns": "/columns",
        "get_column": "/columns/{id}",
        "delete_column": "/columns/{id}/delete",
        "get_column_index": "/columns/itemAt",
        "add_column": "/columns/add",
        "get_rows": "/rows",
        "get_row": "/rows/{id}",
        "delete_row": "/rows/$/itemAt(index={id})",
        "get_row_index": "/rows/itemAt",
        "add_rows": "/rows/add",
        "delete": "/",
        "data_body_range": "/dataBodyRange",
        "header_row_range": "/headerRowRange",
        "total_row_range": "/totalRowRange",
        "entire_range": "/range",
        "convert_to_range": "/convertToRange",
        "clear_filters": "/clearFilters",
        "reapply_filters": "/reapplyFilters",
    }
    column_constructor = TableColumn  #: :meta private:
    row_constructor = TableRow  #: :meta private:
    range_constructor = Range  #: :meta private:

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError("Need a parent or a session but not both")

        #: Parent of the table. |br| **Type:** parent
        self.parent = parent
        #: Session of the table. |br| **Type:** session
        self.session = parent.session if parent else session

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: The unique identifier for the table in the workbook. |br| **Type:** str
        self.object_id = cloud_data.get("id", None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        # append the encoded table path
        main_resource = "{}/tables('{}')".format(main_resource, quote(self.object_id))

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #: The name of the table. |br| **Type:** str
        self.name = cloud_data.get("name", None)
        #: Indicates whether the header row is visible or not |br| **Type:** bool
        self.show_headers = cloud_data.get("showHeaders", True)
        #: Indicates whether the total row is visible or not.  |br| **Type:** bool
        self.show_totals = cloud_data.get("showTotals", True)
        #: A constant value that represents the Table style |br| **Type:** str
        self.style = cloud_data.get("style", None)
        #: Indicates whether the first column contains special formatting. |br| **Type:** bool
        self.highlight_first_column = cloud_data.get("highlightFirstColumn", False)
        #: Indicates whether the last column contains special formatting. |br| **Type:** bool
        self.highlight_last_column = cloud_data.get("highlightLastColumn", False)
        #: Indicates whether the columns show banded formatting in which odd columns
        #: are highlighted differently from even ones to make reading the table easier.
        #: |br| **Type:** bool
        self.show_banded_columns = cloud_data.get("showBandedColumns", False)
        #: The name of the table column. |br| **Type:** str
        self.show_banded_rows = cloud_data.get("showBandedRows", False)
        #: Indicates whether the rows show banded formatting in which odd rows
        #: are highlighted differently from even ones to make reading the table easier.
        #: |br| **Type:** bool
        self.show_filter_button = cloud_data.get("showFilterButton", False)
        #: A legacy identifier used in older Excel clients.  |br| **Type:** str
        self.legacy_id = cloud_data.get("legacyId", False)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Table: {}".format(self.name)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def get_columns(self, *, top=None, skip=None):
        """
        Return the columns of this table
        :param int top: specify n columns to retrieve
        :param int skip: specify n columns to skip
        """
        url = self.build_url(self._endpoints.get("get_columns"))

        params = {}
        if top is not None:
            params["$top"] = top
        if skip is not None:
            params["$skip"] = skip
        params = None if not params else params
        response = self.session.get(url, params=params)

        if not response:
            return iter(())

        data = response.json()

        return (
            self.column_constructor(parent=self, **{self._cloud_data_key: column})
            for column in data.get("value", [])
        )

    def get_column(self, id_or_name):
        """
        Gets a column from this table by id or name
        :param id_or_name: the id or name of the column
        :return: WorkBookTableColumn
        """
        url = self.build_url(
            self._endpoints.get("get_column").format(id=quote(id_or_name))
        )
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

        url = self.build_url(self._endpoints.get("get_column_index"))
        response = self.session.post(url, data={"index": index})

        if not response:
            return None

        return self.column_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def delete_column(self, id_or_name):
        """
        Deletes a Column by its id or name
        :param id_or_name: the id or name of the column
        :return bool: Success or Failure
        """
        url = self.build_url(
            self._endpoints.get("delete_column").format(id=quote(id_or_name))
        )
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

        params = {"name": name, "index": index}
        if values is not None:
            params["values"] = values

        url = self.build_url(self._endpoints.get("add_column"))
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
        :rtype: TableRow
        """
        url = self.build_url(self._endpoints.get("get_rows"))

        params = {}
        if top is not None:
            params["$top"] = top
        if skip is not None:
            params["$skip"] = skip
        params = None if not params else params
        response = self.session.get(url, params=params)

        if not response:
            return iter(())

        data = response.json()

        return (
            self.row_constructor(parent=self, **{self._cloud_data_key: row})
            for row in data.get("value", [])
        )

    def get_row(self, index):
        """Returns a Row instance at an index"""
        url = self.build_url(self._endpoints.get("get_row").format(id=index))
        response = self.session.get(url)
        if not response:
            return None
        return self.row_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def get_row_at_index(self, index):
        """
        Returns a table row by it's index
        :param int index: the zero-indexed position of the row in the table
        """
        if index is None:
            return None

        url = self.build_url(self._endpoints.get("get_row_index"))
        url = "{}(index={})".format(url, index)
        response = self.session.get(url)

        if not response:
            return None

        return self.row_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def delete_row(self, index):
        """
        Deletes a Row by it's index
        :param int index: the index of the row. zero indexed
        :return bool: Success or Failure
        """
        url = self.build_url(self._endpoints.get("delete_row").format(id=index))
        return bool(self.session.delete(url))

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
            params["values"] = values
        if index is not None:
            params["index"] = index

        params = params if params else None

        url = self.build_url(self._endpoints.get("add_rows"))
        response = self.session.post(url, data=params)
        if not response:
            return None
        return self.row_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def update(self, *, name=None, show_headers=None, show_totals=None, style=None):
        """
        Updates this table
        :param str name: the name of the table
        :param bool show_headers: whether or not to show the headers
        :param bool show_totals: whether or not to show the totals
        :param str style: the style of the table
        :return: Success or Failure
        """
        if (
            name is None
            and show_headers is None
            and show_totals is None
            and style is None
        ):
            raise ValueError("Provide at least one parameter to update")
        data = {}
        if name:
            data["name"] = name
        if show_headers is not None:
            data["showHeaders"] = show_headers
        if show_totals is not None:
            data["showTotals"] = show_totals
        if style:
            data["style"] = style

        response = self.session.patch(self.build_url(""), data=data)
        if not response:
            return False

        data = response.json()
        self.name = data.get("name", self.name)
        self.show_headers = data.get("showHeaders", self.show_headers)
        self.show_totals = data.get("showTotals", self.show_totals)
        self.style = data.get("style", self.style)

        return True

    def delete(self):
        """Deletes this table"""
        url = self.build_url(self._endpoints.get("delete"))
        return bool(self.session.delete(url))

    def _get_range(self, endpoint_name):
        """Returns a Range based on the endpoint name"""

        url = self.build_url(self._endpoints.get(endpoint_name))
        response = self.session.get(url)
        if not response:
            return None
        data = response.json()
        return self.range_constructor(parent=self, **{self._cloud_data_key: data})

    def get_data_body_range(self):
        """Gets the range object associated with the data body of the table"""
        return self._get_range("data_body_range")

    def get_header_row_range(self):
        """Gets the range object associated with the header row of the table"""
        return self._get_range("header_row_range")

    def get_total_row_range(self):
        """Gets the range object associated with the totals row of the table"""
        return self._get_range("total_row_range")

    def get_range(self):
        """Gets the range object associated with the entire table"""
        return self._get_range("entire_range")

    def convert_to_range(self):
        """Converts the table into a normal range of cells. All data is preserved."""
        return self._get_range("convert_to_range")

    def clear_filters(self):
        """Clears all the filters currently applied on the table."""
        url = self.build_url(self._endpoints.get("clear_filters"))
        return bool(self.session.post(url))

    def reapply_filters(self):
        """Reapplies all the filters currently on the table."""
        url = self.build_url(self._endpoints.get("reapply_filters"))
        return bool(self.session.post(url))

    def get_worksheet(self):
        """Returns this table worksheet"""
        url = self.build_url("")
        q = self.q().select("name").expand("worksheet")
        response = self.session.get(url, params=q.as_params())
        if not response:
            return None
        data = response.json()

        ws = data.get("worksheet")
        if ws is None:
            return None
        return WorkSheet(parent=self.parent, **{self._cloud_data_key: ws})


class WorkSheet(ApiComponent):
    """An Excel WorkSheet"""

    _endpoints = {
        "get_tables": "/tables",
        "get_table": "/tables/{id}",
        "get_range": "/range",
        "add_table": "/tables/add",
        "get_used_range": "/usedRange(valuesOnly={})",
        "get_cell": "/cell(row={row},column={column})",
        "add_named_range": "/names/add",
        "add_named_range_f": "/names/addFormulaLocal",
        "get_named_range": "/names/{name}",
    }

    table_constructor = Table  #: :meta private:
    range_constructor = Range  #: :meta private:
    named_range_constructor = NamedRange  #: :meta private:

    def __init__(self, parent=None, session=None, **kwargs):
        if parent and session:
            raise ValueError("Need a parent or a session but not both")

        #: The parent of the worksheet. |br| **Type:** parent
        self.workbook = parent
        #: Thesession of the worksheet. |br| **Type:** session
        self.session = parent.session if parent else session

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: The unique identifier for the worksheet in the workbook. |br| **Type:** str
        self.object_id = cloud_data.get("id", None)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        # append the encoded worksheet path
        main_resource = "{}/worksheets('{}')".format(
            main_resource, quote(self.object_id)
        )

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #: The display name of the worksheet. |br| **Type:** str
        self.name = cloud_data.get("name", None)
        #: The zero-based position of the worksheet within the workbook. |br| **Type:** int
        self.position = cloud_data.get("position", None)
        #: The visibility of the worksheet.
        #: The possible values are: Visible, Hidden, VeryHidden. |br| **Type:** str
        self.visibility = cloud_data.get("visibility", None)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Worksheet: {}".format(self.name)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def delete(self):
        """Deletes this worksheet"""
        return bool(self.session.delete(self.build_url("")))

    def update(self, *, name=None, position=None, visibility=None):
        """Changes the name, position or visibility of this worksheet"""

        if name is None and position is None and visibility is None:
            raise ValueError("Provide at least one parameter to update")
        data = {}
        if name:
            data["name"] = name
        if position:
            data["position"] = position
        if visibility:
            data["visibility"] = visibility

        response = self.session.patch(self.build_url(""), data=data)
        if not response:
            return False

        data = response.json()
        self.name = data.get("name", self.name)
        self.position = data.get("position", self.position)
        self.visibility = data.get("visibility", self.visibility)

        return True

    def get_tables(self):
        """Returns a collection of this worksheet tables"""

        url = self.build_url(self._endpoints.get("get_tables"))
        response = self.session.get(url)

        if not response:
            return []

        data = response.json()

        return [
            self.table_constructor(parent=self, **{self._cloud_data_key: table})
            for table in data.get("value", [])
        ]

    def get_table(self, id_or_name):
        """
        Retrieves a Table by id or name
        :param str id_or_name: The id or name of the column
        :return: a Table instance
        """
        url = self.build_url(self._endpoints.get("get_table").format(id=id_or_name))
        response = self.session.get(url)
        if not response:
            return None
        return self.table_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def add_table(self, address, has_headers):
        """
        Adds a table to this worksheet
        :param str address: a range address eg: 'A1:D4'
        :param bool has_headers: if the range address includes headers or not
        :return: a Table instance
        """
        if address is None:
            return None
        params = {"address": address, "hasHeaders": has_headers}
        url = self.build_url(self._endpoints.get("add_table"))
        response = self.session.post(url, data=params)
        if not response:
            return None
        return self.table_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def get_range(self, address=None):
        """
        Returns a Range instance from whitin this worksheet
        :param str address: Optional, the range address you want
        :return: a Range instance
        """
        url = self.build_url(self._endpoints.get("get_range"))
        if address is not None:
            address = self.remove_sheet_name_from_address(address)
            url = "{}(address='{}')".format(url, address)
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def get_used_range(self, only_values=True):
        """Returns the smallest range that encompasses any cells that
        have a value or formatting assigned to them.

        :param bool only_values: Optional. Defaults to True.
         Considers only cells with values as used cells (ignores formatting).
        :return: Range
        """
        # Format the "only_values" parameter as a lowercase string to work properly with the Graph API
        url = self.build_url(
            self._endpoints.get("get_used_range").format(str(only_values).lower())
        )
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def get_cell(self, row, column):
        """Gets the range object containing the single cell based on row and column numbers."""
        url = self.build_url(
            self._endpoints.get("get_cell").format(row=row, column=column)
        )
        response = self.session.get(url)
        if not response:
            return None
        return self.range_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def add_named_range(self, name, reference, comment="", is_formula=False):
        """
        Adds a new name to the collection of the given scope using the user's locale for the formula
        :param str name: the name of this range
        :param str reference: the reference for this range or formula
        :param str comment: a comment to describe this named range
        :param bool is_formula: True if the reference is a formula
        :return: NamedRange instance
        """
        if is_formula:
            url = self.build_url(self._endpoints.get("add_named_range_f"))
        else:
            url = self.build_url(self._endpoints.get("add_named_range"))
        params = {"name": name, "reference": reference, "comment": comment}
        response = self.session.post(url, data=params)
        if not response:
            return None
        return self.named_range_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def get_named_range(self, name):
        """Retrieves a Named range by it's name"""
        url = self.build_url(self._endpoints.get("get_named_range").format(name=name))
        response = self.session.get(url)
        if not response:
            return None
        return self.named_range_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    @staticmethod
    def remove_sheet_name_from_address(address):
        """Removes the sheet name from a given address"""
        compiled = re.compile("([a-zA-Z]+[0-9]+):.*?([a-zA-Z]+[0-9]+)")
        result = compiled.search(address)
        if result:
            return ":".join(result.groups())
        else:
            return address


class WorkbookApplication(ApiComponent):
    _endpoints = {
        "get_details": "/application",
        "post_calculation": "/application/calculate",
    }

    def __init__(self, workbook):
        """
        Create A WorkbookApplication representation

        :param workbook: A workbook object, of the workboook that you want to interact with
        """

        if not isinstance(workbook, WorkBook):
            raise ValueError("workbook was not an accepted type: Workbook")

        #: The application parent. |br| **Type:** Workbook
        self.parent = workbook  # Not really needed currently, but saving in case we need it for future functionality
        self.con = workbook.session.con
        main_resource = getattr(workbook, "main_resource", None)

        super().__init__(protocol=workbook.protocol, main_resource=main_resource)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "WorkbookApplication for Workbook: {}".format(
            self.workbook_id or "Not set"
        )

    def __bool__(self):
        return bool(self.parent)

    def get_details(self):
        """Gets workbookApplication"""
        url = self.build_url(self._endpoints.get("get_details"))
        response = self.con.get(url)

        if not response:
            return None
        return response.json()

    def run_calculations(self, calculation_type):
        """Recalculate all currently opened workbooks in Excel."""
        if calculation_type not in ["Recalculate", "Full", "FullRebuild"]:
            raise ValueError(
                "calculation type must be one of: Recalculate, Full, FullRebuild"
            )

        url = self.build_url(self._endpoints.get("post_calculation"))
        data = {"calculationType": calculation_type}
        headers = {"Content-type": "application/json"}

        if self.parent.session.session_id:
            headers["workbook-session-id"] = self.parent.session.session_id

        response = self.con.post(url, headers=headers, data=data)
        if not response:
            return False

        return response.ok


class WorkBook(ApiComponent):
    _endpoints = {
        "get_worksheets": "/worksheets",
        "get_tables": "/tables",
        "get_table": "/tables/{id}",
        "get_worksheet": "/worksheets/{id}",
        "function": "/functions/{name}",
        "get_names": "/names",
        "get_named_range": "/names/{name}",
        "add_named_range": "/names/add",
        "add_named_range_f": "/names/addFormulaLocal",
    }

    application_constructor = WorkbookApplication  #: :meta private:
    worksheet_constructor = WorkSheet  #: :meta private:
    table_constructor = Table  #: :meta private:
    named_range_constructor = NamedRange  #: :meta private:

    def __init__(self, file_item, *, use_session=True, persist=True):
        """Create a workbook representation

        :param File file_item: the Drive File you want to interact with
        :param Bool use_session: Whether or not to use a session to be more efficient
        :param Bool persist: Whether or not to persist this info
        """
        if (
            file_item is None
            or not isinstance(file_item, File)
            or file_item.mime_type != EXCEL_XLSX_MIME_TYPE
        ):
            raise ValueError("This file is not a valid Excel xlsx file.")

        # append the workbook path
        main_resource = "{}{}/workbook".format(
            file_item.main_resource,
            file_item._endpoints.get("item").format(id=file_item.object_id),
        )

        super().__init__(protocol=file_item.protocol, main_resource=main_resource)

        persist = persist if use_session is True else True
        #: The session for the workbook. |br| **Type:** WorkbookSession
        self.session = WorkbookSession(
            parent=file_item, persist=persist, main_resource=main_resource
        )

        if use_session:
            self.session.create_session()

        #: The name of the workbook. |br| **Type:**str**
        self.name = file_item.name
        #: The id of the workbook. |br| **Type:** str**
        self.object_id = "Workbook:{}".format(
            file_item.object_id
        )  # Mangle the object id

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Workbook: {}".format(self.name)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def get_tables(self):
        """Returns a collection of this workbook tables"""

        url = self.build_url(self._endpoints.get("get_tables"))
        response = self.session.get(url)

        if not response:
            return []

        data = response.json()

        return [
            self.table_constructor(parent=self, **{self._cloud_data_key: table})
            for table in data.get("value", [])
        ]

    def get_table(self, id_or_name):
        """
        Retrieves a Table by id or name
        :param str id_or_name: The id or name of the column
        :return: a Table instance
        """
        url = self.build_url(self._endpoints.get("get_table").format(id=id_or_name))
        response = self.session.get(url)
        if not response:
            return None
        return self.table_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def get_workbookapplication(self):
        return self.application_constructor(self)

    def get_worksheets(self):
        """Returns a collection of this workbook worksheets"""

        url = self.build_url(self._endpoints.get("get_worksheets"))
        response = self.session.get(url)

        if not response:
            return []

        data = response.json()

        return [
            self.worksheet_constructor(parent=self, **{self._cloud_data_key: ws})
            for ws in data.get("value", [])
        ]

    def get_worksheet(self, id_or_name):
        """Gets a specific worksheet by id or name"""
        url = self.build_url(
            self._endpoints.get("get_worksheet").format(id=quote(id_or_name))
        )
        response = self.session.get(url)
        if not response:
            return None
        return self.worksheet_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def add_worksheet(self, name=None):
        """Adds a new worksheet"""
        url = self.build_url(self._endpoints.get("get_worksheets"))
        response = self.session.post(url, data={"name": name} if name else None)
        if not response:
            return None
        data = response.json()
        return self.worksheet_constructor(parent=self, **{self._cloud_data_key: data})

    def delete_worksheet(self, worksheet_id):
        """Deletes a worksheet by it's id"""
        url = self.build_url(
            self._endpoints.get("get_worksheet").format(id=quote(worksheet_id))
        )
        return bool(self.session.delete(url))

    def invoke_function(self, function_name, **function_params):
        """Invokes an Excel Function"""
        url = self.build_url(self._endpoints.get("function").format(name=function_name))
        response = self.session.post(url, data=function_params)
        if not response:
            return None
        data = response.json()

        error = data.get("error")
        if error is None:
            return data.get("value")
        else:
            raise FunctionException(error)

    def get_named_ranges(self):
        """Returns the list of named ranges for this Workbook"""

        url = self.build_url(self._endpoints.get("get_names"))
        response = self.session.get(url)
        if not response:
            return []
        data = response.json()
        return [
            self.named_range_constructor(parent=self, **{self._cloud_data_key: nr})
            for nr in data.get("value", [])
        ]

    def get_named_range(self, name):
        """Retrieves a Named range by it's name"""
        url = self.build_url(self._endpoints.get("get_named_range").format(name=name))
        response = self.session.get(url)
        if not response:
            return None
        return self.named_range_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )

    def add_named_range(self, name, reference, comment="", is_formula=False):
        """
        Adds a new name to the collection of the given scope using the user's locale for the formula
        :param str name: the name of this range
        :param str reference: the reference for this range or formula
        :param str comment: a comment to describe this named range
        :param bool is_formula: True if the reference is a formula
        :return: NamedRange instance
        """
        if is_formula:
            url = self.build_url(self._endpoints.get("add_named_range_f"))
        else:
            url = self.build_url(self._endpoints.get("add_named_range"))
        params = {"name": name, "reference": reference, "comment": comment}
        response = self.session.post(url, data=params)
        if not response:
            return None
        return self.named_range_constructor(
            parent=self, **{self._cloud_data_key: response.json()}
        )
