import datetime as dt
import logging

# noinspection PyPep8Naming
from bs4 import BeautifulSoup as bs
from dateutil.parser import parse

from .utils import TrackerSet
from .utils import ApiComponent

log = logging.getLogger(__name__)


class Task(ApiComponent):
    """ A Microsoft To-Do task """

    _endpoints = {
        'folder': '/taskfolders/{id}',
        'task': '/tasks/{id}',
        'task_default': '/tasks',
        'task_folder': '/taskfolders/{id}/tasks',
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft To-Do task

        :param parent: parent object
        :type parent: ToDo
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
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.task_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        cc = self._cc  # alias
        # internal to know which properties need to be updated on the server
        self._track_changes = TrackerSet(casing=cc)
        self.folder_id = kwargs.get('folder_id', None)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.task_id = cloud_data.get(cc('id'), None)
        self.__subject = cloud_data.get(cc('subject'),
                                        kwargs.get('subject', '') or '')
        body = cloud_data.get(cc('body'), {})
        self.__body = body.get(cc('content'), '')
        self.body_type = body.get(cc('contentType'),
                                  'HTML')  # default to HTML for new messages

        self.__created = cloud_data.get(cc('createdDateTime'), None)
        self.__modified = cloud_data.get(cc('lastModifiedDateTime'), None)
        self.__status = cloud_data.get(cc('status'), None)
        self.__is_completed = self.__status == 'Completed'
        self.__importance = cloud_data.get(cc('importance'), None)
        
        local_tz = self.protocol.timezone
        self.__created = parse(self.__created).astimezone(
            local_tz) if self.__created else None
        self.__modified = parse(self.__modified).astimezone(
            local_tz) if self.__modified else None

        due_obj = cloud_data.get(cc('dueDateTime'), {})
        self.__due = self._parse_date_time_time_zone(due_obj)

        completed_obj = cloud_data.get(cc('completedDateTime'), {})
        self.__completed = self._parse_date_time_time_zone(completed_obj)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if self.__is_completed:
            marker = 'x'
        else:
            marker = 'o'

        if self.__due:
            due_str = '(due: {} at {}) '.format(self.due.date(), self.due.time())
        else:
            due_str = ''

        if self.__completed:
            compl_str = '(completed: {} at {}) '.format(self.completed.date(), self.completed.time())
        else:
            compl_str = ''

        return 'Task: ({}) {} {} {}'.format(marker, self.__subject, due_str, compl_str)

    def __eq__(self, other):
        return self.task_id == other.task_id

    def to_api_data(self, restrict_keys=None):
        """ Returns a dict to communicate with the server

        :param restrict_keys: a set of keys to restrict the returned data to
        :rtype: dict
        """
        cc = self._cc  # alias

        data = {
            cc('subject'): self.__subject,
            cc('body'): {
                cc('contentType'): self.body_type,
                cc('content'): self.__body},
        }

        if self.__is_completed:
            data[cc('status')] = 'Completed'
        else:
            data[cc('status')] = 'NotStarted'

        if self.__due:
            data[cc('dueDateTime')] = self._build_date_time_time_zone(self.__due)

        if self.__completed:
            data[cc('completedDateTime')] = self._build_date_time_time_zone(self.__completed)

        if restrict_keys:
            for key in list(data.keys()):
                if key not in restrict_keys:
                    del data[key]
        return data

    @property
    def created(self):
        """ Created time of the task

        :rtype: datetime
        """
        return self.__created

    @property
    def modified(self):
        """ Last modified time of the task

        :rtype: datetime
        """
        return self.__modified

    @property
    def body(self):
        """ Body of the task

        :getter: Get body text
        :setter: Set body of task
        :type: str
        """
        return self.__body

    @property
    def importance(self):
        """ Task importance (Low, Normal, High)

        :getter: Get importance level
        :type: str
        """
        return self.__importance

    @property
    def is_starred(self):
        """ Is the task starred (high importance)

        :getter: Check if importance is high
        :type: bool
        """
        return self.__importance.casefold() == "High".casefold()


    @body.setter
    def body(self, value):
        self.__body = value
        self._track_changes.add(self._cc('body'))

    @property
    def subject(self):
        """ Subject of the task

        :getter: Get subject
        :setter: Set subject of task
        :type: str
        """
        return self.__subject

    @subject.setter
    def subject(self, value):
        self.__subject = value
        self._track_changes.add(self._cc('subject'))

    @property
    def due(self):
        """ Due Time of task

        :getter: get the due time
        :setter: set the due time
        :type: datetime
        """
        return self.__due

    @due.setter
    def due(self, value):
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
        self._track_changes.add(self._cc('dueDateTime'))

    @property
    def status(self):
        """Status of task

        :getter: get status
        :type: string
        """
        return self.__status

    @property
    def completed(self):
        """ Completed Time of task

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
        self._track_changes.add(self._cc('completedDateTime'))

    @property
    def is_completed(self):
        """ Is task completed or not

        :getter: Is completed
        :setter: set the task to completted
        :type: bool
        """
        return self.__is_completed

    def mark_completed(self):
        self.__is_completed = True
        self._track_changes.add(self._cc('status'))

    def mark_uncompleted(self):
        self.__is_completed = False
        self._track_changes.add(self._cc('status'))

    def delete(self):
        """ Deletes a stored task

        :return: Success / Failure
        :rtype: bool
        """
        if self.task_id is None:
            raise RuntimeError('Attempting to delete an unsaved task')

        url = self.build_url(
            self._endpoints.get('task').format(id=self.task_id))

        response = self.con.delete(url)

        return bool(response)

    def save(self):
        """ Create a new task or update an existing one by checking what
        values have changed and update them on the server

        :return: Success / Failure
        :rtype: bool
        """

        if self.task_id:
            # update task
            if not self._track_changes:
                return True  # there's nothing to update
            url = self.build_url(
                self._endpoints.get('task').format(id=self.task_id))
            method = self.con.patch
            data = self.to_api_data(restrict_keys=self._track_changes)
        else:
            # new task
            if self.folder_id:
                url = self.build_url(
                    self._endpoints.get('task_folder').format(
                        id=self.folder_id))
            else:
                url = self.build_url(self._endpoints.get('task_default'))
            method = self.con.post
            data = self.to_api_data()

        response = method(url, data=data)
        if not response:
            return False

        self._track_changes.clear()  # clear the tracked changes

        if not self.task_id:
            # new task
            task = response.json()

            self.task_id = task.get(self._cc('id'), None)

            self.__created = task.get(self._cc('createdDateTime'), None)
            self.__modified = task.get(self._cc('lastModifiedDateTime'), None)
            self.__completed = task.get(self._cc('Completed'), None)

            self.__created = parse(self.__created).astimezone(
                self.protocol.timezone) if self.__created else None
            self.__modified = parse(self.__modified).astimezone(
                self.protocol.timezone) if self.__modified else None
            self.__is_completed = task.get(self._cc('status'), None) == 'Completed'
        else:
            self.__modified = dt.datetime.now().replace(tzinfo=self.protocol.timezone)

        return True

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
        if self.body_type != 'HTML':
            return None
        else:
            return bs(self.body, 'html.parser')


class Folder(ApiComponent):
    """ A Microsoft To-Do folder """

    _endpoints = {
        'folder': '/taskfolders/{id}',
        'get_tasks': '/taskfolders/{id}/tasks',
        'default_tasks': '/tasks',
        'get_task': '/taskfolders/{id}/tasks/{ide}',
    }
    task_constructor = Task

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft To-Do Folder Representation

        :param parent: parent object
        :type parent: ToDo
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
        self.folder_id = cloud_data.get(self._cc('id'), None)
        self._is_default = cloud_data.get(self._cc('isDefaultFolder'), '')

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        suffix = ''
        if self._is_default:
            suffix = ' (default)'
        return 'Folder: {}'.format(self.name) + suffix

    def __eq__(self, other):
        return self.folder_id == other.folder_id

    def update(self):
        """ Updates this folder. Only name can be changed.

        :return: Success / Failure
        :rtype: bool
        """

        if not self.folder_id:
            return False

        url = self.build_url(self._endpoints.get('folder'))

        data = {
            self._cc('name'): self.name,
        }

        response = self.con.patch(url, data=data)

        return bool(response)

    def delete(self):
        """ Deletes this folder

        :return: Success / Failure
        :rtype: bool
        """

        if not self.folder_id:
            return False

        url = self.build_url(self._endpoints.get('folder').format(id=self.folder_id))

        response = self.con.delete(url)
        if not response:
            return False

        self.folder_id = None

        return True

    def get_tasks(self, batch=None, order_by=None):
        """ Returns a list of tasks of a specified folder

        :param batch: the batch on to retrieve tasks.
        :param order_by: the order clause to apply to returned tasks.

        :rtype: tasks
        """

        if self.folder_id is None:
            # I'm the default folder
            url = self.build_url(self._endpoints.get('default_tasks'))
        else:
            url = self.build_url(
                self._endpoints.get('get_tasks').format(id=self.folder_id))

        # get tasks by the folder id
        params = {}
        if batch:
            params['$top'] = batch

        if order_by:
            params['$orderby'] = order_by

        response = self.con.get(url, params=params)

        if not response:
            return iter(())

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        tasks = (self.task_constructor(parent=self,
                                       **{self._cloud_data_key: task})
                 for task in data.get('value', []))
        return tasks

    def new_task(self, subject=None):
        """ Creates a task within a specified folder """

        return self.task_constructor(parent=self, subject=subject,
                                     folder_id=self.folder_id)

    def get_task(self, param):
        """ Returns an Task instance by it's id

        :param param: an task_id or a Query instance
        :return: task for the specified info
        :rtype: Event
        """

        if param is None:
            return None
        if isinstance(param, str):
            url = self.build_url(
                self._endpoints.get('get_task').format(id=self.folder_id,
                                                       ide=param))
            params = None
            by_id = True
        else:
            url = self.build_url(
                self._endpoints.get('get_tasks').format(id=self.folder_id))
            params = {'$top': 1}
            params.update(param.as_params())
            by_id = False

        response = self.con.get(url, params=params)

        if not response:
            return None

        if by_id:
            task = response.json()
        else:
            task = response.json().get('value', [])
            if task:
                task = task[0]
            else:
                return None
        return self.task_constructor(parent=self,
                                     **{self._cloud_data_key: task})


class ToDo(ApiComponent):
    """ A Microsoft To-Do class
        In order to use the API following permissions are required.
        Delegated (work or school account) - Tasks.Read, Tasks.ReadWrite
    """

    _endpoints = {
        'root_folders': '/taskfolders',
        'get_folder': '/taskfolders/{id}',
    }

    folder_constructor = Folder
    task_constructor = Task

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A ToDo object

        :param parent: parent object
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
        return 'Microsoft To-Do'

    def list_folders(self, limit=None):
        """ Gets a list of folders

        To use query an order_by check the OData specification here:
        http://docs.oasis-open.org/odata/odata/v4.0/errata03/os/complete/
        part2-url-conventions/odata-v4.0-errata03-os-part2-url-conventions
        -complete.html

        :param int limit: max no. of folders to get. Over 999 uses batch.
        :rtype: list[Folder]

        """

        url = self.build_url(self._endpoints.get('root_folders'))

        params = {}
        if limit:
            params['$top'] = limit

        response = self.con.get(url, params=params or None)
        if not response:
            return []

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        contacts = [self.folder_constructor(parent=self, **{
            self._cloud_data_key: x}) for x in data.get('value', [])]

        return contacts

    def new_folder(self, folder_name):
        """ Creates a new folder

        :param str folder_name: name of the new folder
        :return: a new Calendar instance
        :rtype: Calendar
        """
        if not folder_name:
            return None

        url = self.build_url(self._endpoints.get('root_folders'))

        response = self.con.post(url, data={self._cc('name'): folder_name})
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.folder_constructor(parent=self,
                                       **{self._cloud_data_key: data})

    def get_folder(self, folder_id=None, folder_name=None):
        """ Returns a folder by it's id or name

        :param str folder_id: the folder id to be retrieved.
        :param str folder_name: the folder name to be retrieved.
        :return: folder for the given info
        :rtype: Calendar
        """
        if folder_id and folder_name:
            raise RuntimeError('Provide only one of the options')

        if not folder_id and not folder_name:
            raise RuntimeError('Provide one of the options')

        folders = self.list_folders(limit=50)

        for f in folders:
            if folder_id and f.folder_id == folder_id:
                return f
            if folder_name and f.name == folder_name:
                return f

    def get_default_folder(self):
        """ Returns the default folder for the current user

        :rtype: Folder
        """

        folders = self.list_folders()
        for f in folders:
            if f._is_default:
                return f

    def get_tasks(self, batch=None, order_by=None):
        """ Get tasks from the default Calendar

        :param order_by: orders the result set based on this condition
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: list of items in this folder
        :rtype: list[Event] or Pagination
        """

        default_folder = self.get_default_folder()

        return default_folder.get_tasks(order_by=order_by, batch=batch)

    def new_task(self, subject=None):
        """ Returns a new (unsaved) Event object in the default folder

        :param str subject: subject text for the new task
        :return: new task
        :rtype: Event
        """
        return self.task_constructor(parent=self, subject=subject)
