"""Methods for accessing MS Tasks/Todos via the MS Graph api."""

import datetime as dt
import logging

# noinspection PyPep8Naming
from bs4 import BeautifulSoup as bs
from dateutil.parser import parse

from .utils import ApiComponent, TrackerSet

log = logging.getLogger(__name__)

CONST_FOLDER = "folder"
CONST_GET_FOLDER = "get_folder"
CONST_GET_TASK = "get_task"
CONST_GET_TASKS = "get_tasks"
CONST_ROOT_FOLDERS = "root_folders"
CONST_TASK = "task"
CONST_TASK_FOLDER = "task_folder"


class Task(ApiComponent):
    """A Microsoft To-Do task."""

    _endpoints = {
        CONST_TASK: "/todo/lists/{folder_id}/tasks/{id}",
        CONST_TASK_FOLDER: "/todo/lists/{folder_id}/tasks",
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """Representation of a Microsoft To-Do task.

        :param parent: parent object
        :type parent: Folder
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        :param str folder_id: id of the calender to add this task in
         (kwargs)
        :param str subject: subject of the task (kwargs)
        """
        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.task_id = cloud_data.get("id")

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        cc = self._cc  # pylint: disable=invalid-name
        # internal to know which properties need to be updated on the server
        self._track_changes = TrackerSet(casing=cc)
        self.folder_id = kwargs.get("folder_id")
        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.task_id = cloud_data.get(cc("id"), None)
        self.__subject = cloud_data.get(cc("title"), kwargs.get("subject", "") or "")
        body = cloud_data.get(cc("body"), {})
        self.__body = body.get(cc("content"), "")
        self.body_type = body.get(
            cc("contentType"), "html"
        )  # default to HTML for new messages

        self.__created = cloud_data.get(cc("createdDateTime"), None)
        self.__modified = cloud_data.get(cc("lastModifiedDateTime"), None)
        self.__status = cloud_data.get(cc("status"), None)
        self.__is_completed = self.__status == "completed"
        self.__importance = cloud_data.get(cc("importance"), None)

        local_tz = self.protocol.timezone
        self.__created = (
            parse(self.__created).astimezone(local_tz) if self.__created else None
        )
        self.__modified = (
            parse(self.__modified).astimezone(local_tz) if self.__modified else None
        )

        due_obj = cloud_data.get(cc("dueDateTime"), {})
        self.__due = self._parse_date_time_time_zone(due_obj)

        reminder_obj = cloud_data.get(cc("reminderDateTime"), {})
        self.__reminder = self._parse_date_time_time_zone(reminder_obj)
        self.__is_reminder_on = cloud_data.get(cc("isReminderOn"), False)

        completed_obj = cloud_data.get(cc("completedDateTime"), {})
        self.__completed = self._parse_date_time_time_zone(completed_obj)

    def __str__(self):
        """Representation of the Task via the Graph api as a string."""
        return self.__repr__()

    def __repr__(self):
        """Representation of the Task via the Graph api."""
        marker = "x" if self.__is_completed else "o"
        if self.__due:
            due_str = f"(due: {self.__due.date()} at {self.__due.time()}) "
        else:
            due_str = ""

        if self.__completed:
            compl_str = (
                f"(completed: {self.__completed.date()} at {self.__completed.time()}) "
            )

        else:
            compl_str = ""

        return f"Task: ({marker}) {self.__subject} {due_str} {compl_str}"

    def __eq__(self, other):
        """Comparison of tasks."""
        return self.task_id == other.task_id

    def to_api_data(self, restrict_keys=None):
        """Return a dict to communicate with the server.

        :param restrict_keys: a set of keys to restrict the returned data to
        :rtype: dict
        """
        cc = self._cc  # pylint: disable=invalid-name

        data = {
            cc("title"): self.__subject,
            cc("status"): "completed" if self.__is_completed else "notStarted",
        }

        if self.__body:
            data[cc("body")] = {
                cc("contentType"): self.body_type,
                cc("content"): self.__body,
            }
        else:
            data[cc("body")] = None

        if self.__due:
            data[cc("dueDateTime")] = self._build_date_time_time_zone(self.__due)
        else:
            data[cc("dueDateTime")] = None

        if self.__reminder:
            data[cc("reminderDateTime")] = self._build_date_time_time_zone(
                self.__reminder
            )
        else:
            data[cc("reminderDateTime")] = None

        if self.__completed:
            data[cc("completedDateTime")] = self._build_date_time_time_zone(
                self.__completed
            )

        if restrict_keys:
            for key in list(data.keys()):
                if key not in restrict_keys:
                    del data[key]
        return data

    @property
    def created(self):
        """Return Created time of the task.

        :rtype: datetime
        """
        return self.__created

    @property
    def modified(self):
        """Return Last modified time of the task.

        :rtype: datetime
        """
        return self.__modified

    @property
    def body(self):
        """Return Body of the task.

        :getter: Get body text
        :setter: Set body of task
        :type: str
        """
        return self.__body

    @body.setter
    def body(self, value):
        self.__body = value
        self._track_changes.add(self._cc("body"))

    @property
    def importance(self):
        """Return Task importance.

        :getter: Get importance level (Low, Normal, High)
        :type: str
        """
        return self.__importance

    @property
    def is_starred(self):
        """Is the task starred (high importance).

        :getter: Check if importance is high
        :type: bool
        """
        return self.__importance.casefold() == "high".casefold()

    @property
    def subject(self):
        """Subject of the task.

        :getter: Get subject
        :setter: Set subject of task
        :type: str
        """
        return self.__subject

    @subject.setter
    def subject(self, value):
        self.__subject = value
        self._track_changes.add(self._cc("title"))

    @property
    def due(self):
        """Due Time of task.

        :getter: get the due time
        :setter: set the due time
        :type: datetime
        """
        return self.__due

    @due.setter
    def due(self, value):
        if value:
            if not isinstance(value, dt.date):
                raise ValueError("'due' must be a valid datetime object")
            if not isinstance(value, dt.datetime):
                # force datetime
                value = dt.datetime(value.year, value.month, value.day)
            if value.tzinfo is None:
                # localize datetime
                value = value.replace(tzinfo=self.protocol.timezone)
            elif value.tzinfo != self.protocol.timezone:
                value = value.astimezone(self.protocol.timezone)
        self.__due = value
        self._track_changes.add(self._cc("dueDateTime"))

    @property
    def reminder(self):
        """Reminder Time of task.

        :getter: get the reminder time
        :setter: set the reminder time
        :type: datetime
        """
        return self.__reminder

    @reminder.setter
    def reminder(self, value):
        if value:
            if not isinstance(value, dt.date):
                raise ValueError("'reminder' must be a valid datetime object")
            if not isinstance(value, dt.datetime):
                # force datetime
                value = dt.datetime(value.year, value.month, value.day)
            if value.tzinfo is None:
                # localize datetime
                value = value.replace(tzinfo=self.protocol.timezone)
            elif value.tzinfo != self.protocol.timezone:
                value = value.astimezone(self.protocol.timezone)
        self.__reminder = value
        self._track_changes.add(self._cc("reminderDateTime"))

    @property
    def is_reminder_on(self):
        """Return isReminderOn of the task.

        :getter: Get isReminderOn
        :type: bool
        """
        return self.__is_reminder_on

    @property
    def status(self):
        """Status of task

        :getter: get status
        :type: string
        """
        return self.__status

    @property
    def completed(self):
        """Completed Time of task.

        :getter: get the completed time
        :setter: set the completed time
        :type: datetime
        """
        return self.__completed

    @completed.setter
    def completed(self, value):
        if value is None:
            self.mark_uncompleted()
        else:
            if not isinstance(value, dt.date):
                raise ValueError("'completed' must be a valid datetime object")
            if not isinstance(value, dt.datetime):
                # force datetime
                value = dt.datetime(value.year, value.month, value.day)
            if value.tzinfo is None:
                # localize datetime
                value = value.replace(tzinfo=self.protocol.timezone)
            elif value.tzinfo != self.protocol.timezone:
                value = value.astimezone(self.protocol.timezone)
            self.mark_completed()

        self.__completed = value
        self._track_changes.add(self._cc("completedDateTime"))

    @property
    def is_completed(self):
        """Is task completed or not.

        :getter: Is completed
        :setter: set the task to completted
        :type: bool
        """
        return self.__is_completed

    def mark_completed(self):
        """Mark the ask as completed."""
        self.__is_completed = True
        self._track_changes.add(self._cc("status"))

    def mark_uncompleted(self):
        """Mark the task as uncompleted."""
        self.__is_completed = False
        self._track_changes.add(self._cc("status"))

    def delete(self):
        """Delete a stored task.

        :return: Success / Failure
        :rtype: bool
        """
        if self.task_id is None:
            raise RuntimeError("Attempting to delete an unsaved task")

        url = self.build_url(
            self._endpoints.get(CONST_TASK).format(
                folder_id=self.folder_id, id=self.task_id
            )
        )

        response = self.con.delete(url)

        return bool(response)

    def save(self):
        """Create a new task or update an existing one.

        Does update by checking what values have changed and update them on the server
        :return: Success / Failure
        :rtype: bool
        """
        if self.task_id:
            # update task
            if not self._track_changes:
                return True  # there's nothing to update
            url = self.build_url(
                self._endpoints.get(CONST_TASK).format(
                    folder_id=self.folder_id, id=self.task_id
                )
            )
            method = self.con.patch
            data = self.to_api_data(restrict_keys=self._track_changes)
        else:
            # new task
            url = self.build_url(
                self._endpoints.get(CONST_TASK_FOLDER).format(folder_id=self.folder_id)
            )

            method = self.con.post
            data = self.to_api_data()

        response = method(url, data=data)
        if not response:
            return False

        self._track_changes.clear()  # clear the tracked changes

        if not self.task_id:
            # new task
            task = response.json()

            self.task_id = task.get(self._cc("id"), None)

            self.__created = task.get(self._cc("createdDateTime"), None)
            self.__modified = task.get(self._cc("lastModifiedDateTime"), None)
            self.__completed = task.get(self._cc("completed"), None)

            self.__created = (
                parse(self.__created).astimezone(self.protocol.timezone)
                if self.__created
                else None
            )
            self.__modified = (
                parse(self.__modified).astimezone(self.protocol.timezone)
                if self.__modified
                else None
            )
            self.__is_completed = task.get(self._cc("status"), None) == "completed"
        else:
            self.__modified = dt.datetime.now().replace(tzinfo=self.protocol.timezone)

        return True

    def get_body_text(self):
        """Parse the body html and returns the body text using bs4.

        :return: body text
        :rtype: str
        """
        if self.body_type != "html":
            return self.body

        try:
            soup = bs(self.body, "html.parser")
        except RuntimeError:
            return self.body
        else:
            return soup.body.text

    def get_body_soup(self):
        """Return the beautifulsoup4 of the html body.

        :return: Html body
        :rtype: BeautifulSoup
        """
        return bs(self.body, "html.parser") if self.body_type == "html" else None


class Folder(ApiComponent):
    """A Microsoft To-Do folder."""

    _endpoints = {
        CONST_FOLDER: "/todo/lists/{id}",
        CONST_GET_TASKS: "/todo/lists/{id}/tasks",
        CONST_GET_TASK: "/todo/lists/{id}/tasks/{ide}",
    }
    task_constructor = Task

    def __init__(self, *, parent=None, con=None, **kwargs):
        """Representation of a Microsoft To-Do Folder.

        :param parent: parent object
        :type parent: ToDo
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
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

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.name = cloud_data.get(self._cc("displayName"), "")
        self.folder_id = cloud_data.get(self._cc("id"), None)
        self.is_default = False
        if cloud_data.get(self._cc("wellknownListName"), "") == "defaultList":
            self.is_default = True

    def __str__(self):
        """Representation of the Folder via the Graph api as a string."""
        return self.__repr__()

    def __repr__(self):
        """Representation of the folder via the Graph api."""
        suffix = " (default)" if self.is_default else ""
        return f"Folder: {self.name}{suffix}"

    def __eq__(self, other):
        """Comparison of folders."""
        return self.folder_id == other.folder_id

    def update(self):
        """Update this folder. Only name can be changed.

        :return: Success / Failure
        :rtype: bool
        """
        if not self.folder_id:
            return False

        url = self.build_url(
            self._endpoints.get(CONST_FOLDER).format(id=self.folder_id)
        )

        data = {
            self._cc("displayName"): self.name,
        }

        response = self.con.patch(url, data=data)

        return bool(response)

    def delete(self):
        """Delete this folder.

        :return: Success / Failure
        :rtype: bool
        """
        if not self.folder_id:
            return False

        url = self.build_url(
            self._endpoints.get(CONST_FOLDER).format(id=self.folder_id)
        )

        response = self.con.delete(url)
        if not response:
            return False

        self.folder_id = None

        return True

    def get_tasks(self, query=None, batch=None, order_by=None):
        """Return list of tasks of a specified folder.

        :param query: the query string or object to query tasks
        :param batch: the batch on to retrieve tasks.
        :param order_by: the order clause to apply to returned tasks.

        :rtype: tasks
        """
        url = self.build_url(
            self._endpoints.get(CONST_GET_TASKS).format(id=self.folder_id)
        )

        # get tasks by the folder id
        params = {}
        if batch:
            params["$top"] = batch

        if order_by:
            params["$orderby"] = order_by

        if query:
            if isinstance(query, str):
                params["$filter"] = query
            else:
                params |= query.as_params()

        response = self.con.get(url, params=params)

        if not response:
            return iter(())

        data = response.json()

        return (
            self.task_constructor(parent=self, **{self._cloud_data_key: task})
            for task in data.get("value", [])
        )

    def new_task(self, subject=None):
        """Create a task within a specified folder."""
        return self.task_constructor(
            parent=self, subject=subject, folder_id=self.folder_id
        )

    def get_task(self, param):
        """Return a Task instance by it's id.

        :param param: an task_id or a Query instance
        :return: task for the specified info
        :rtype: Event
        """
        if param is None:
            return None
        if isinstance(param, str):
            url = self.build_url(
                self._endpoints.get(CONST_GET_TASK).format(id=self.folder_id, ide=param)
            )
            params = None
            by_id = True
        else:
            url = self.build_url(
                self._endpoints.get(CONST_GET_TASKS).format(id=self.folder_id)
            )
            params = {"$top": 1}
            params |= param.as_params()
            by_id = False

        response = self.con.get(url, params=params)

        if not response:
            return None

        if by_id:
            task = response.json()
        else:
            task = response.json().get("value", [])
            if task:
                task = task[0]
            else:
                return None
        return self.task_constructor(parent=self, **{self._cloud_data_key: task})


class ToDo(ApiComponent):
    """A of Microsoft To-Do class for MS Graph API.

    In order to use the API following permissions are required.
    Delegated (work or school account) - Tasks.Read, Tasks.ReadWrite
    """

    _endpoints = {
        CONST_ROOT_FOLDERS: "/todo/lists",
        CONST_GET_FOLDER: "/todo/lists/{id}",
    }

    folder_constructor = Folder
    task_constructor = Task

    def __init__(self, *, parent=None, con=None, **kwargs):
        """Initialise the ToDo object.

        :param parent: parent object
        :type parent: Account
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
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

    def __str__(self):
        """Representation of the ToDo via the Graph api as a string."""
        return self.__repr__()

    def __repr__(self):
        """Representation of the ToDo via the Graph api as."""
        return "Microsoft To-Do"

    def list_folders(self, query=None, limit=None):
        """Return a list of folders.

        To use query an order_by check the OData specification here:
        https://docs.oasis-open.org/odata/odata/v4.0/errata03/os/complete/
        part2-url-conventions/odata-v4.0-errata03-os-part2-url-conventions
        -complete.html
        :param query: the query string or object to list folders
        :param int limit: max no. of folders to get. Over 999 uses batch.
        :rtype: list[Folder]
        """
        url = self.build_url(self._endpoints.get(CONST_ROOT_FOLDERS))

        params = {}
        if limit:
            params["$top"] = limit

        if query:
            if isinstance(query, str):
                params["$filter"] = query
            else:
                params |= query.as_params()

        response = self.con.get(url, params=params or None)
        if not response:
            return []

        data = response.json()

        return [
            self.folder_constructor(parent=self, **{self._cloud_data_key: x})
            for x in data.get("value", [])
        ]

    def new_folder(self, folder_name):
        """Create a new folder.

        :param str folder_name: name of the new folder
        :return: a new Calendar instance
        :rtype: Calendar
        """
        if not folder_name:
            return None

        url = self.build_url(self._endpoints.get(CONST_ROOT_FOLDERS))

        response = self.con.post(url, data={self._cc("displayName"): folder_name})
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.folder_constructor(parent=self, **{self._cloud_data_key: data})

    def get_folder(self, folder_id=None, folder_name=None):
        """Return a folder by it's id or name.

        :param str folder_id: the folder id to be retrieved.
        :param str folder_name: the folder name to be retrieved.
        :return: folder for the given info
        :rtype: Calendar
        """
        if folder_id and folder_name:
            raise RuntimeError("Provide only one of the options")

        if not folder_id and not folder_name:
            raise RuntimeError("Provide one of the options")

        if folder_id:
            url = self.build_url(
                self._endpoints.get(CONST_GET_FOLDER).format(id=folder_id)
            )
            response = self.con.get(url)

            return (
                self.folder_constructor(
                    parent=self, **{self._cloud_data_key: response.json()}
                )
                if response
                else None
            )

        query = self.new_query("displayName").equals(folder_name)
        folders = self.list_folders(query=query)
        return folders[0]

    def get_default_folder(self):
        """Return the default folder for the current user.

        :rtype: Folder
        """
        folders = self.list_folders()
        for folder in folders:
            if folder.is_default:
                return folder

    def get_tasks(self, batch=None, order_by=None):
        """Get tasks from the default Calendar.

        :param order_by: orders the result set based on this condition
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: list of items in this folder
        :rtype: list[Event] or Pagination
        """
        default_folder = self.get_default_folder()

        return default_folder.get_tasks(order_by=order_by, batch=batch)

    def new_task(self, subject=None):
        """Return a new (unsaved) Event object in the default folder.

        :param str subject: subject text for the new task
        :return: new task
        :rtype: Event
        """
        default_folder = self.get_default_folder()
        return default_folder.new_task(subject=subject)
