import logging

from dateutil.parser import parse

from O365.address_book import Contact
from O365.drive import Storage
from O365.utils import ApiComponent

log = logging.getLogger(__name__)

class Task(ApiComponent):
    """ A Microsoft Planner task """

    _endpoints = {
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft planner task

        :param parent: parent object
        :type parent: Sharepoint
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = (kwargs.pop('main_resource', None) or
                         getattr(parent,
                                 'main_resource',
                                 None) if parent else None)

        main_resource = '{}{}'.format(main_resource, '')

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)
        
        self.object_id = cloud_data.get('id')


    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Task: {}'.format(self.object_id)

      

class Planner(ApiComponent):
    """ A microsoft planner class """

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
        assert parent or con, 'Need a parent or a connection'
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

