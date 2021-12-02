import logging

from dateutil.parser import parse
from .utils import ApiComponent
from .directory import User

log = logging.getLogger(__name__)

class Group(ApiComponent):
    """ A Microsoft O365 group """

    _endpoints = {
            'get_group_owners': '/groups/{group_id}/owners',
            'get_group_members': '/groups/{group_id}/members',
    }

    member_constructor = User

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft O365 group

        :param parent: parent object
        :type parent: Teams
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

        self.display_name = cloud_data.get(self._cc('displayName'), '')
        self.description = cloud_data.get(self._cc('description'), '')
        self.mail = cloud_data.get(self._cc('mail'), '')
        self.mail_nickname = cloud_data.get(self._cc('mailNickname'), '')
        self.visibility = cloud_data.get(self._cc('visibility'), '')

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Group: {}'.format(self.display_name)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def get_group_members(self):
        """ Returns members of given group

        :rtype: list[User]
        """

        url = self.build_url(self._endpoints.get('get_group_members').format(group_id=self.object_id))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        return [self.member_constructor(parent=self, **{self._cloud_data_key: lst}) for lst in data.get('value', [])]

    def get_group_owners(self):
        """ Returns owners of given group

        :rtype: list[User]
        """
        url = self.build_url(self._endpoints.get('get_group_owners').format(group_id=self.object_id))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        return [self.member_constructor(parent=self, **{self._cloud_data_key: lst}) for lst in data.get('value', [])]

class Groups(ApiComponent):
    """ A microsoft groups class
        In order to use the API following permissions are required.
        Delegated (work or school account) - Group.Read.All, Group.ReadWrite.All
    """

    _endpoints = {
        'get_user_groups': '/users/{user_id}/memberOf',
        'get_group_by_id': '/groups/{group_id}',
        'get_group_by_nickname': '/groups/?$search="mailNickname:{group_nickname}"'
        
    }

    group_constructor = Group

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Teams object

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
        return 'Microsoft O365 Group parent class'

    def get_group_by_id(self, group_id = None):
        """ Returns Microsoft O365/AD group with given id

        :param group_id: group id of group

        :rtype: Group
        """

        if not group_id:
            raise RuntimeError('Provide the group_id')

        if group_id:
            # get channels by the team id
            url = self.build_url(
                self._endpoints.get('get_group_by_id').format(group_id=group_id))

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.group_constructor(parent=self,
                                **{self._cloud_data_key: data})

    def get_group_by_nickname(self, group_name = None):
        """ Returns Microsoft O365/AD group by mailNickname field

        :param group_name: mailNickname of group

        :rtype: Group
        """

        if not group_name:
            raise RuntimeError('Provide the group_name')

        if group_name:
            # get channels by the team id
            url = self.build_url(
                self._endpoints.get('get_group_by_id').format(group_nickname=group_name))

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.group_constructor(parent=self,
                                **{self._cloud_data_key: data})

    def get_user_groups(self, user_id = None):
        """ Returns list of groups that given user has membership

        :param user_id: user_id

        :rtype: list[Group]
        """

        if not user_id:
            raise RuntimeError('Provide the user_id')

        if user_id:
            # get channels by the team id
            url = self.build_url(
                self._endpoints.get('get_user_groups').format(user_id=user_id))

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return [
            self.group_constructor(parent=self, **{self._cloud_data_key: group})
            for group in data.get('value', [])]
