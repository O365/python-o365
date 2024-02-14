import logging
from enum import Enum

from dateutil.parser import parse

from .utils import ApiComponent, NEXT_LINK_KEYWORD, Pagination

log = logging.getLogger(__name__)

MAX_BATCH_CHAT_MESSAGES = 50
MAX_BATCH_CHATS = 50


class Availability(Enum):
    """Valid values for Availability."""

    AVAILABLE = "Available"
    BUSY = "Busy"
    AWAY = "Away"
    DONOTDISTURB = "DoNotDisturb"


class Activity(Enum):
    """Valid values for Activity."""

    AVAILABLE = "Available"
    INACALL = "InACall"
    INACONFERENCECALL = "InAConferenceCall"
    AWAY = "Away"
    PRESENTING = "Presenting"

class PreferredAvailability(Enum):
    """Valid values for Availability."""

    AVAILABLE = "Available"
    BUSY = "Busy"
    DONOTDISTURB = "DoNotDisturb"
    BERIGHTBACK = "BeRightBack"
    AWAY = "Away"
    OFFLINE = "Offline"


class PreferredActivity(Enum):
    """Valid values for Activity."""

    AVAILABLE = "Available"
    BUSY = "Busy"
    DONOTDISTURB = "DoNotDisturb"
    BERIGHTBACK = "BeRightBack"
    AWAY = "Away"
    OFFWORK = "OffWork"

class ConversationMember(ApiComponent):
    """ A Microsoft Teams conversation member """

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft Teams conversation member
        :param parent: parent object
        :type parent: Chat
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified (kwargs)
        :param str main_resource: use this resource instead of parent resource (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con
        cloud_data = kwargs.get(self._cloud_data_key, {})
        self.object_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)
        resource_prefix = '/members/{membership_id}'.format(
            membership_id=self.object_id)
        main_resource = '{}{}'.format(main_resource, resource_prefix)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)
        self.roles = cloud_data.get('roles')
        self.display_name = cloud_data.get('displayName')
        self.user_id = cloud_data.get('userId')
        self.email = cloud_data.get('email')
        self.tenant_id = cloud_data.get('tenantId')

    def __repr__(self):
        return 'ConversationMember: {} - {}'.format(self.display_name,
                                                    self.email)

    def __str__(self):
        return self.__repr__()


class ChatMessage(ApiComponent):
    """ A Microsoft Teams chat message """

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft Teams chat message
        :param parent: parent object
        :type parent: Channel, Chat, or ChannelMessage
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified (kwargs)
        :param str main_resource: use this resource instead of parent resource (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con
        cloud_data = kwargs.get(self._cloud_data_key, {})
        self.object_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        # determine proper resource prefix based on whether the message is a reply
        self.reply_to_id = cloud_data.get('replyToId')
        if self.reply_to_id:
            resource_prefix = '/replies/{message_id}'.format(
                message_id=self.object_id)
        else:
            resource_prefix = '/messages/{message_id}'.format(
                message_id=self.object_id)

        main_resource = '{}{}'.format(main_resource, resource_prefix)
        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.message_type = cloud_data.get('messageType')
        self.subject = cloud_data.get('subject')
        self.summary = cloud_data.get('summary')
        self.importance = cloud_data.get('importance')
        self.web_url = cloud_data.get('webUrl')

        local_tz = self.protocol.timezone
        created = cloud_data.get('createdDateTime')
        last_modified = cloud_data.get('lastModifiedDateTime')
        last_edit = cloud_data.get('lastEditedDateTime')
        deleted = cloud_data.get('deletedDateTime')
        self.created_date = parse(created).astimezone(
            local_tz) if created else None
        self.last_modified_date = parse(last_modified).astimezone(
            local_tz) if last_modified else None
        self.last_edited_date = parse(last_edit).astimezone(
            local_tz) if last_edit else None
        self.deleted_date = parse(deleted).astimezone(
            local_tz) if deleted else None

        self.chat_id = cloud_data.get('chatId')
        self.channel_identity = cloud_data.get('channelIdentity')

        sent_from = cloud_data.get('from')
        if sent_from:
            from_key = 'user' if sent_from.get('user', None) else 'application'
            from_data = sent_from.get(from_key)
        else:
            from_data = {}
            from_key = None

        self.from_id = from_data.get('id') if sent_from else None
        self.from_display_name = from_data.get('displayName',
                                               None) if sent_from else None
        self.from_type = from_data.get(
            '{}IdentityType'.format(from_key)) if sent_from else None

        body = cloud_data.get('body')
        self.content_type = body.get('contentType')
        self.content = body.get('content')

    def __repr__(self):
        return 'ChatMessage: {}'.format(self.from_display_name)

    def __str__(self):
        return self.__repr__()


class ChannelMessage(ChatMessage):
    """ A Microsoft Teams chat message that is the start of a channel thread """
    _endpoints = {'get_replies': '/replies',
                  'get_reply': '/replies/{message_id}'}

    message_constructor = ChatMessage

    def __init__(self, **kwargs):
        """ A Microsoft Teams chat message that is the start of a channel thread """
        super().__init__(**kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})
        channel_identity = cloud_data.get('channelIdentity')
        self.team_id = channel_identity.get('teamId')
        self.channel_id = channel_identity.get('channelId')

    def get_reply(self, message_id):
        """ Returns a specified reply to the channel chat message
        :param message_id: the message_id of the reply to retrieve
        :type message_id: str or int
        :rtype: ChatMessage
        """
        url = self.build_url(
            self._endpoints.get('get_reply').format(message_id=message_id))
        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.message_constructor(parent=self,
                                        **{self._cloud_data_key: data})

    def get_replies(self, limit=None, batch=None):
        """ Returns a list of replies to the channel chat message
        :param int limit: number of replies to retrieve
        :param int batch: number of replies to be in each data set
        :rtype: list or Pagination
        """
        url = self.build_url(self._endpoints.get('get_replies'))

        if not batch and (limit is None or limit > MAX_BATCH_CHAT_MESSAGES):
            batch = MAX_BATCH_CHAT_MESSAGES

        params = {'$top': batch if batch else limit}
        response = self.con.get(url, params=params)
        if not response:
            return []

        data = response.json()
        next_link = data.get(NEXT_LINK_KEYWORD, None)

        replies = [self.message_constructor(parent=self,
                                            **{self._cloud_data_key: reply})
                   for reply in data.get('value', [])]

        if batch and next_link:
            return Pagination(parent=self, data=replies,
                              constructor=self.message_constructor,
                              next_link=next_link, limit=limit)
        else:
            return replies

    def send_reply(self, content=None, content_type='text'):
        """ Sends a reply to the channel chat message
        :param content: str of text, str of html, or dict representation of json body
        :type content: str or dict
        :param str content_type: 'text' to render the content as text or 'html' to render the content as html
        """
        data = content if isinstance(content, dict) else {
            'body': {'contentType': content_type, 'content': content}}
        url = self.build_url(self._endpoints.get('get_replies'))
        response = self.con.post(url, data=data)

        if not response:
            return None

        data = response.json()
        return self.message_constructor(parent=self,
                                        **{self._cloud_data_key: data})


class Chat(ApiComponent):
    """ A Microsoft Teams chat """
    _endpoints = {'get_messages': '/messages',
                  'get_message': '/messages/{message_id}',
                  'get_members': '/members',
                  'get_member': '/members/{membership_id}'}

    message_constructor = ChatMessage
    member_constructor = ConversationMember

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft Teams chat
        :param parent: parent object
        :type parent: Teams
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified (kwargs)
        :param str main_resource: use this resource instead of parent resource (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})
        self.object_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)
        resource_prefix = '/chats/{chat_id}'.format(chat_id=self.object_id)
        main_resource = '{}{}'.format(main_resource, resource_prefix)
        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.topic = cloud_data.get('topic')
        self.chat_type = cloud_data.get('chatType')
        self.web_url = cloud_data.get('webUrl')
        created = cloud_data.get('createdDateTime')
        last_update = cloud_data.get('lastUpdatedDateTime')
        local_tz = self.protocol.timezone
        self.created_date = parse(created).astimezone(
            local_tz) if created else None
        self.last_update_date = parse(last_update).astimezone(
            local_tz) if last_update else None

    def get_messages(self, limit=None, batch=None):
        """ Returns a list of chat messages from the chat
        :param int limit: number of replies to retrieve
        :param int batch: number of replies to be in each data set
        :rtype: list[ChatMessage] or Pagination of ChatMessage
        """
        url = self.build_url(self._endpoints.get('get_messages'))

        if not batch and (limit is None or limit > MAX_BATCH_CHAT_MESSAGES):
            batch = MAX_BATCH_CHAT_MESSAGES

        params = {'$top': batch if batch else limit}
        response = self.con.get(url, params=params)
        if not response:
            return []

        data = response.json()
        next_link = data.get(NEXT_LINK_KEYWORD, None)

        messages = [self.message_constructor(parent=self,
                                             **{self._cloud_data_key: message})
                    for message in data.get('value', [])]

        if batch and next_link:
            return Pagination(parent=self, data=messages,
                              constructor=self.message_constructor,
                              next_link=next_link, limit=limit)
        else:
            return messages

    def get_message(self, message_id):
        """ Returns a specified message from the chat
        :param message_id: the message_id of the message to receive
        :type message_id: str or int
        :rtype: ChatMessage
        """
        url = self.build_url(
            self._endpoints.get('get_message').format(message_id=message_id))
        response = self.con.get(url)
        if not response:
            return None
        data = response.json()
        return self.message_constructor(parent=self,
                                        **{self._cloud_data_key: data})

    def send_message(self, content=None, content_type='text'):
        """ Sends a message to the chat
        :param content: str of text, str of html, or dict representation of json body
        :type content: str or dict
        :param str content_type: 'text' to render the content as text or 'html' to render the content as html
        :rtype: ChatMessage
        """
        data = content if isinstance(content, dict) else {
            'body': {'contentType': content_type, 'content': content}}

        url = self.build_url(self._endpoints.get('get_messages'))
        response = self.con.post(url, data=data)

        if not response:
            return None

        data = response.json()
        return self.message_constructor(parent=self,
                                        **{self._cloud_data_key: data})

    def get_members(self):
        """ Returns a list of conversation members
        :rtype: list[ConversationMember]
        """
        url = self.build_url(self._endpoints.get('get_members'))
        response = self.con.get(url)
        if not response:
            return None
        data = response.json()
        members = [self.member_constructor(parent=self,
                                           **{self._cloud_data_key: member})
                   for member in data.get('value', [])]
        return members

    def get_member(self, membership_id):
        """Returns a specified conversation member
        :param str membership_id: membership_id of member to retrieve
        :rtype: ConversationMember
        """
        url = self.build_url(self._endpoints.get('get_member').format(
            membership_id=membership_id))
        response = self.con.get(url)
        if not response:
            return None
        data = response.json()
        return self.member_constructor(parent=self,
                                       **{self._cloud_data_key: data})

    def __repr__(self):
        return 'Chat: {}'.format(self.chat_type)

    def __str__(self):
        return self.__repr__()


class Presence(ApiComponent):
    """ Microsoft Teams Presence  """

    _endpoints = {}

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Microsoft Teams Presence

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

        self.availability = cloud_data.get('availability')
        self.activity = cloud_data.get('activity')

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'availability: {}'.format(self.availability)

    def __eq__(self, other):
        return self.object_id == other.object_id


class Channel(ApiComponent):
    """ A Microsoft Teams channel """

    _endpoints = {'get_messages': '/messages',
                  'get_message': '/messages/{message_id}'}

    message_constructor = ChannelMessage

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft Teams channel

        :param parent: parent object
        :type parent: Teams or Team
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

        resource_prefix = '/channels/{channel_id}'.format(
            channel_id=self.object_id)
        main_resource = '{}{}'.format(main_resource, resource_prefix)
        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.display_name = cloud_data.get(self._cc('displayName'), '')
        self.description = cloud_data.get('description')
        self.email = cloud_data.get('email')

    def get_message(self, message_id):
        """ Returns a specified channel chat messages
        :param message_id: number of messages to retrieve
        :type message_id: int or str
        :rtype: ChannelMessage
        """
        url = self.build_url(
            self._endpoints.get('get_message').format(message_id=message_id))
        response = self.con.get(url)

        if not response:
            return None

        data = response.json()
        return self.message_constructor(parent=self,
                                        **{self._cloud_data_key: data})

    def get_messages(self, limit=None, batch=None):
        """ Returns a list of channel chat messages
        :param int limit: number of messages to retrieve
        :param int batch: number of messages to be in each data set
        :rtype: list[ChannelMessage] or Pagination of ChannelMessage
        """
        url = self.build_url(self._endpoints.get('get_messages'))

        if not batch and (limit is None or limit > MAX_BATCH_CHAT_MESSAGES):
            batch = MAX_BATCH_CHAT_MESSAGES

        params = {'$top': batch if batch else limit}
        response = self.con.get(url, params=params)
        if not response:
            return []

        data = response.json()
        next_link = data.get(NEXT_LINK_KEYWORD, None)

        messages = [self.message_constructor(parent=self,
                                             **{self._cloud_data_key: message})
                    for message in data.get('value', [])]

        if batch and next_link:
            return Pagination(parent=self, data=messages,
                              constructor=self.message_constructor,
                              next_link=next_link, limit=limit)
        else:
            return messages

    def send_message(self, content=None, content_type='text'):
        """ Sends a message to the channel
        :param content: str of text, str of html, or dict representation of json body
        :type content: str or dict
        :param str content_type: 'text' to render the content as text or 'html' to render the content as html
        :rtype: ChannelMessage
        """
        data = content if isinstance(content, dict) else {
            'body': {'contentType': content_type, 'content': content}}

        url = self.build_url(self._endpoints.get('get_messages'))
        response = self.con.post(url, data=data)

        if not response:
            return None

        data = response.json()
        return self.message_constructor(parent=self,
                                        **{self._cloud_data_key: data})

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Channel: {}'.format(self.display_name)

    def __eq__(self, other):
        return self.object_id == other.object_id


class Team(ApiComponent):
    """ A Microsoft Teams team """

    _endpoints = {'get_channels': '/channels',
                  'get_channel': '/channels/{channel_id}'}

    channel_constructor = Channel

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft Teams team

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

        resource_prefix = '/teams/{team_id}'.format(team_id=self.object_id)
        main_resource = '{}{}'.format(main_resource, resource_prefix)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.display_name = cloud_data.get(self._cc('displayName'), '')
        self.description = cloud_data.get(self._cc('description'), '')
        self.is_archived = cloud_data.get(self._cc('isArchived'), '')
        self.web_url = cloud_data.get(self._cc('webUrl'), '')

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Team: {}'.format(self.display_name)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def get_channels(self):
        """ Returns a list of channels the team

        :rtype: list[Channel]
        """
        url = self.build_url(self._endpoints.get('get_channels'))
        response = self.con.get(url)

        if not response:
            return []

        data = response.json()

        return [self.channel_constructor(parent=self,
                                         **{self._cloud_data_key: channel})
                for channel in data.get('value', [])]

    def get_channel(self, channel_id):
        """ Returns a channel of the team

        :param channel_id: the team_id of the channel to be retrieved.

        :rtype: Channel
        """
        url = self.build_url(self._endpoints.get('get_channel').format(channel_id=channel_id))
        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.channel_constructor(parent=self, **{self._cloud_data_key: data})




class App(ApiComponent):
    """ A Microsoft Teams app """

    _endpoints = {}

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Microsoft Teams app

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

        self.app_definition = cloud_data.get(self._cc('teamsAppDefinition'),
                                             {})

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'App: {}'.format(self.app_definition.get('displayName'))

    def __eq__(self, other):
        return self.object_id == other.object_id


class Teams(ApiComponent):
    """ A Microsoft Teams class"""

    _endpoints = {
        "get_my_presence": "/me/presence",
        "get_user_presence": "/users/{user_id}/presence",
        "set_my_presence": "/me/presence/setPresence",
        "set_my_user_preferred_presence": "/me/presence/setUserPreferredPresence",
        "get_my_teams": "/me/joinedTeams",
        "get_channels": "/teams/{team_id}/channels",
        "create_channel": "/teams/{team_id}/channels",
        "get_channel": "/teams/{team_id}/channels/{channel_id}",
        "get_apps_in_team": "/teams/{team_id}/installedApps?$expand=teamsAppDefinition",
        "get_my_chats": "/me/chats"
    }
    presence_constructor = Presence
    team_constructor = Team
    channel_constructor = Channel
    app_constructor = App
    chat_constructor = Chat

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
        return 'Microsoft Teams'

    def get_my_presence(self):
        """ Returns my availability and activity

        :rtype: Presence
        """

        url = self.build_url(self._endpoints.get('get_my_presence'))

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.presence_constructor(parent=self,
                                         **{self._cloud_data_key: data})

    def set_my_presence(
        self,
        session_id,
        availability: Availability,
        activity: Activity,
        expiration_duration,
    ):
        """Sets my presence status

        :param session_id: the session/capplication id.
        :param availability: the availability.
        :param activity: the activity.
        :param activity: the expiration_duration when status will be unset.
        :rtype: Presence
        """

        url = self.build_url(self._endpoints.get("set_my_presence"))

        data = {
            "sessionId": session_id,
            "availability": availability.value,
            "activity": activity.value,
            "expirationDutaion": expiration_duration,
        }

        response = self.con.post(url, data=data)

        return self.get_my_presence() if response else None

    def set_my_user_preferred_presence(
        self,
        availability: PreferredAvailability,
        activity: PreferredActivity,
        expiration_duration,
    ):
        """Sets my user preferred presence status

        :param availability: the availability.
        :param activity: the activity.
        :param activity: the expiration_duration when status will be unset.
        :rtype: Presence
        """

        url = self.build_url(self._endpoints.get("set_my_user_preferred_presence"))

        data = {
            "availability": availability.value,
            "activity": activity.value,
            "expirationDutaion": expiration_duration,
        }

        response = self.con.post(url, data=data)

        return self.get_my_presence() if response else None

    def get_user_presence(self, user_id=None, email=None):
        """Returns specific user availability and activity

        :rtype: Presence
        """

        url = self.build_url(
            self._endpoints.get("get_user_presence").format(user_id=user_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.presence_constructor(parent=self, **{self._cloud_data_key: data})

    def get_my_teams(self):
        """ Returns a list of teams that I am in

        :rtype: list[Team]
        """

        url = self.build_url(self._endpoints.get('get_my_teams'))
        response = self.con.get(url)

        if not response:
            return []

        data = response.json()

        return [
            self.team_constructor(parent=self, **{self._cloud_data_key: site})
            for site in data.get('value', [])]

    def get_my_chats(self, limit=None, batch=None):
        """ Returns a list of chats that I am in
        :param int limit: number of chats to retrieve
        :param int batch: number of chats to be in each data set
        :rtype: list[ChatMessage] or Pagination of Chat
        """
        url = self.build_url(self._endpoints.get('get_my_chats'))

        if not batch and (limit is None or limit > MAX_BATCH_CHATS):
            batch = MAX_BATCH_CHATS

        params = {'$top': batch if batch else limit}
        response = self.con.get(url, params=params)
        if not response:
            return []

        data = response.json()
        next_link = data.get(NEXT_LINK_KEYWORD, None)

        chats = [self.chat_constructor(parent=self,
                                             **{self._cloud_data_key: message})
                    for message in data.get('value', [])]

        if batch and next_link:
            return Pagination(parent=self, data=chats,
                              constructor=self.chat_constructor,
                              next_link=next_link, limit=limit)
        else:
            return chats

    def get_channels(self, team_id):
        """ Returns a list of channels of a specified team

        :param team_id: the team_id of the channel to be retrieved.

        :rtype: list[Channel]
        """

        url = self.build_url(
            self._endpoints.get('get_channels').format(team_id=team_id))

        response = self.con.get(url)

        if not response:
            return []

        data = response.json()

        return [
            self.channel_constructor(parent=self,
                                     **{self._cloud_data_key: channel})
            for channel in data.get('value', [])]

    def create_channel(self, team_id, display_name, description=None):
        """ Creates a channel within a specified team

        :param team_id: the team_id where the channel is created.
        :param display_name: the channel display name.
        :param description: the channel description.
        :rtype: Channel
        """

        url = self.build_url(
            self._endpoints.get('get_channels').format(team_id=team_id))

        if description:
            data = {
                'displayName': display_name,
                'description': description,
            }
        else:
            data = {
                'displayName': display_name,
            }

        response = self.con.post(url, data=data)

        if not response:
            return None

        data = response.json()

        return self.channel_constructor(parent=self,
                                        **{self._cloud_data_key: data})

    def get_channel(self, team_id, channel_id):
        """ Returns the channel info for a given channel

        :param team_id: the team_id of the channel.
        :param channel_id: the channel_id of the channel.

        :rtype: list[Channel]
        """

        url = self.build_url(
            self._endpoints.get('get_channel').format(team_id=team_id,
                                                        channel_id=channel_id))

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.channel_constructor(parent=self,
                                        **{self._cloud_data_key: data})

    def get_apps_in_team(self, team_id):
        """ Returns a list of apps of a specified team

        :param team_id: the team_id of the team to get the apps of.

        :rtype: list[App]
        """

        url = self.build_url(
            self._endpoints.get('get_apps_in_team').format(team_id=team_id))
        response = self.con.get(url)

        if not response:
            return []

        data = response.json()

        return [
            self.app_constructor(parent=self, **{self._cloud_data_key: site})
            for site in data.get('value', [])]
