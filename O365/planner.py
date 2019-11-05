import logging

from dateutil.parser import parse
from .utils import ApiComponent

log = logging.getLogger(__name__)


class Task(ApiComponent):
    """ A Microsoft Planner task """

    _endpoints = {}

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft planner task

        :param parent: parent object
        :type parent: Planner
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        main_resource = '{}{}'.format(main_resource, '')

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.plan_id = cloud_data.get('plan_id')
        self.bucket_id = cloud_data.get('bucketId')
        self.title = cloud_data.get(self._cc('title'), '')
        self.order_hint = cloud_data.get(self._cc('orderHint'), '')
        self.assignee_priority = cloud_data.get(self._cc('assigneePriority'), '')
        self.percent_complete = cloud_data.get(self._cc('percentComplete'), '')
        self.title = cloud_data.get(self._cc('title'), '')
        self.has_description = cloud_data.get(self._cc('hasDescription'), '')
        created = cloud_data.get(self._cc('createdDateTime'), None)
        due_date = cloud_data.get(self._cc('dueDateTime'), None)
        start_date = cloud_data.get(self._cc('startDateTime'), None)
        completed_date = cloud_data.get(self._cc('completedDateTime'), None)
        local_tz = self.protocol.timezone
        self.start_date = parse(start_date).astimezone(local_tz) if start_date else None
        self.created_date = parse(created).astimezone(local_tz) if created else None
        self.due_date = parse(due_date).astimezone(local_tz) if due_date else None
        self.completed_date = parse(completed_date).astimezone(local_tz) if completed_date else None
        self.preview_type = cloud_data.get(self._cc('previewType'), None)
        self.reference_count = cloud_data.get(self._cc('referenceCount'), None)
        self.checklist_item_count = cloud_data.get(self._cc('checklistItemCount'), None)
        self.active_checklist_item_count = cloud_data.get(self._cc('activeChecklistItemCount'), None)
        self.conversation_thread_id = cloud_data.get(self._cc('conversationThreadId'), None)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Task: {}'.format(self.title)

    def __eq__(self, other):
        return self.object_id == other.object_id


class Planner(ApiComponent):
    """ A microsoft planner class
        In order to use the API following permissions are required.
        Delegated (work or school account) - Group.Read.All, Group.ReadWrite.All
    """

    _endpoints = {
        'get_my_tasks': '/me/planner/tasks',
    }
    task_constructor = Task

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Planner object

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

        # Choose the main_resource passed in kwargs over the host_name
        main_resource = kwargs.pop('main_resource',
                                   '')  # defaults to blank resource
        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Microsoft Planner'

    def get_my_tasks(self, *args):
        """ Returns a list of open planner tasks assigned to me

        :rtype: tasks
        """

        url = self.build_url(self._endpoints.get('get_my_tasks'))

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return [
            self.task_constructor(parent=self, **{self._cloud_data_key: site})
            for site in data.get('value', [])]
