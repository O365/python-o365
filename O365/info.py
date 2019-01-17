import logging

from dateutil.parser import parse
from .utils import ApiComponent

_LOGGER = logging.getLogger(__name__)


class Info(ApiComponent):
    """ A Microsoft info class
        In order to use the API following permissions are required.
        Delegated (work or school account) - Group.Read.All, Group.ReadWrite.All
    """

    _endpoints = {
        'info': '/me',
    }

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

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=kwargs.get('main_resource', ''))

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Microsoft Planner'

    def get_my_info(self):
        """ Returns a my info."""
        url = self.build_url(self._endpoints.get('info'))
        response = self.con.get(url)
        if not response:
            return None
        return self._get_my_info(response.json())

    async def aio_get_my_info(self):
        """ Returns my Info."""
        url = self.build_url(self._endpoints.get('info'))
        print(url)
        response = await self.con.get(url)
        if not response:
            return None
        data = await response.json()
        return self._get_my_info(data)

    def _get_my_info(self, data):
        """post-process data."""
        return data
