import logging

from .directory import User
from .utils import ApiComponent, NEXT_LINK_KEYWORD, Pagination 

log = logging.getLogger(__name__)


class Group(ApiComponent):
    """ A Microsoft 365 group """

    _endpoints = {
            'get_group_owners': '/groups/{group_id}/owners',
            'get_group_members': '/groups/{group_id}/members',
    }

    member_constructor = User  #: :meta private:

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft 365 group

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

        #: The unique identifier for the group. |br| **Type:** str
        self.object_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        main_resource = '{}{}'.format(main_resource, '')

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        #: The group type. |br| **Type:** str
        self.type = cloud_data.get('@odata.type')
        #: The display name for the group. |br| **Type:** str
        self.display_name = cloud_data.get(self._cc('displayName'), '')
        #: An optional description for the group. |br| **Type:** str
        self.description = cloud_data.get(self._cc('description'), '')
        #: The SMTP address for the group, for example, "serviceadmins@contoso.com". |br| **Type:** str
        self.mail = cloud_data.get(self._cc('mail'), '')
        #: The mail alias for the group, unique for Microsoft 365 groups in the organization. |br| **Type:** str
        self.mail_nickname = cloud_data.get(self._cc('mailNickname'), '')
        #: Specifies the group join policy and group content visibility for groups. |br| **Type:** str
        self.visibility = cloud_data.get(self._cc('visibility'), '')

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Group: {}'.format(self.display_name)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def __hash__(self):
        return self.object_id.__hash__()

    def get_group_members(self, recursive=False):
        """ Returns members of given group
        :param bool recursive: drill down to users if group has other group as a member
        :rtype: list[User]
        """
        if recursive:
            recursive_data = self._get_group_members_raw()
            for member in recursive_data:
                if member['@odata.type'] == '#microsoft.graph.group':
                    recursive_members = Groups(con=self.con, protocol=self.protocol).get_group_by_id(member['id'])._get_group_members_raw()
                    recursive_data.extend(recursive_members)
            return [self.member_constructor(parent=self, **{self._cloud_data_key: lst}) for lst in recursive_data]
        else:
            return [self.member_constructor(parent=self, **{self._cloud_data_key: lst}) for lst in self._get_group_members_raw()]

    def _get_group_members_raw(self):
        url = self.build_url(self._endpoints.get('get_group_members').format(group_id=self.object_id))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()
        return data.get('value', [])

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
        'get_group_by_mail': '/groups/?$search="mail:{group_mail}"&$count=true',
        'list_groups': '/groups',
    }

    group_constructor = Group  #: :meta private:

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
        """ Returns Microsoft 365/AD group with given id

        :param group_id: group id of group

        :rtype: Group
        """

        if not group_id:
            raise RuntimeError('Provide the group_id')

        # get channels by the team id
        url = self.build_url(
            self._endpoints.get("get_group_by_id").format(group_id=group_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.group_constructor(parent=self, **{self._cloud_data_key: data})

    def get_group_by_mail(self, group_mail=None):
        """Returns Microsoft 365/AD group by mail field

        :param group_name: mail of group

        :rtype: Group
        """
        if not group_mail:
            raise RuntimeError("Provide the group mail")

        # get groups by filter mail
        url = self.build_url(
            self._endpoints.get("get_group_by_mail").format(group_mail=group_mail)
        )

        response = self.con.get(url, headers={'ConsistencyLevel': 'eventual'})

        if not response:
            return None

        data = response.json()

        if '@odata.count' in data and data['@odata.count'] < 1:
            raise RuntimeError('Not found group with provided filters')

        # mail is unique field so, we expect exact match -> always use first element from list
        return self.group_constructor(parent=self,
                                **{self._cloud_data_key: data.get('value')[0]})

    def get_user_groups(self, user_id=None, limit=None, batch=None):
        """Returns list of groups that given user has membership

        :param user_id: user_id
        :param int limit: max no. of groups to get. Over 999 uses batch.
        :param int batch: batch size, retrieves items in
          batches allowing to retrieve more items than the limit.
        :rtype: list[Group] or Pagination
        """

        if not user_id:
            raise RuntimeError("Provide the user_id")

        # get channels by the team id
        url = self.build_url(
            self._endpoints.get("get_user_groups").format(user_id=user_id)
        )

        params = {}
        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value
        params["$top"] = batch if batch else limit
        response = self.con.get(url, params=params or None)

        if not response:
            return None

        data = response.json()

        groups = [
            self.group_constructor(parent=self, **{self._cloud_data_key: group})
            for group in data.get("value", [])
        ]
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(
                parent=self,
                data=groups,
                constructor=self.group_constructor,
                next_link=next_link,
                limit=limit,
            )

        return groups

    def list_groups(self):
        """Returns list of groups

        :rtype: list[Group]
        """

        url = self.build_url(
            self._endpoints.get('list_groups'))

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return [
            self.group_constructor(parent=self, **{self._cloud_data_key: group})
            for group in data.get('value', [])]
