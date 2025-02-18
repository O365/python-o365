from typing import Type, Tuple, Optional, Callable, List
import warnings

from .connection import Connection, Protocol, MSGraphProtocol, MSOffice365Protocol
from .utils import ME_RESOURCE, consent_input_token


class Account:
    connection_constructor: Type = Connection

    def __init__(self, credentials: Tuple[str, str], *,
                 username: Optional[str] = None,
                 protocol: Optional[Protocol] = None,
                 main_resource: Optional[str] = None, **kwargs):
        """ Creates an object which is used to access resources related to the specified credentials.

        :param credentials: a tuple containing the client_id and client_secret
        :param username: the username to be used by this account
        :param protocol: the protocol to be used in this account
        :param main_resource: the resource to be used by this account ('me' or 'users', etc.)
        :param kwargs: any extra args to be passed to the Connection instance
        :raises ValueError: if an invalid protocol is passed
        """

        protocol = protocol or MSGraphProtocol  # Defaults to Graph protocol
        if isinstance(protocol, type):
            protocol = protocol(default_resource=main_resource, **kwargs)
        self.protocol: Protocol = protocol

        if not isinstance(self.protocol, Protocol):
            raise ValueError("'protocol' must be a subclass of Protocol")

        auth_flow_type = kwargs.get('auth_flow_type', 'authorization')

        if auth_flow_type not in ['authorization', 'public', 'credentials', 'password']:
            raise ValueError('"auth_flow_type" must be "authorization", "credentials", "password" or "public"')

        scopes = kwargs.get('scopes', None)
        if scopes:
            del kwargs['scopes']
            warnings.warn("Since 2.1 scopes are only needed during authentication.", DeprecationWarning)

        if auth_flow_type == 'credentials':
            # set main_resource to blank when it's the 'ME' resource
            if self.protocol.default_resource == ME_RESOURCE:
                self.protocol.default_resource = ''
            if main_resource == ME_RESOURCE:
                main_resource = ''

        elif auth_flow_type == 'password':
            # set main_resource to blank when it's the 'ME' resource
            if self.protocol.default_resource == ME_RESOURCE:
                self.protocol.default_resource = ''
            if main_resource == ME_RESOURCE:
                main_resource = ''

        kwargs['username'] = username

        self.con = self.connection_constructor(credentials, **kwargs)
        self.main_resource: str = main_resource or self.protocol.default_resource

    def __repr__(self):
        if self.con.auth:
            return f'Account Client Id: {self.con.auth[0]}'
        else:
            return 'Unidentified Account'

    @property
    def is_authenticated(self) -> bool:
        """
        Checks whether the library has the authentication data and that is not expired for the current username.
        This will try to load the token from the backend if not already loaded.
        Return True if authenticated, False otherwise.
        """
        if self.con.token_backend.has_data is False:
            # try to load the token from the backend
            if self.con.load_token_from_backend() is False:
                return False

        return not self.con.token_backend.token_is_expired(username=self.con.username, refresh_token=True)

    def authenticate(self, *, requested_scopes: Optional[list] = None, redirect_uri: Optional[str] = None,
                     handle_consent: Callable = consent_input_token, **kwargs) -> bool:
        """ Performs the console authentication flow resulting in a stored token.
        It uses the credentials passed on instantiation.
        Returns True if succeeded otherwise False.

        :param list[str] requested_scopes: list of protocol user scopes to be converted
         by the protocol or scope helpers or raw scopes
        :param str redirect_uri: redirect url configured in registered app
        :param handle_consent: a function to handle the consent process by default just input for the token url
        :param kwargs: other configurations to be passed to the
         Connection.get_authorization_url and Connection.request_token methods
        """

        if self.con.auth_flow_type in ('authorization', 'public'):
            consent_url, flow = self.get_authorization_url(requested_scopes, redirect_uri=redirect_uri, **kwargs)

            token_url = handle_consent(consent_url)

            if token_url:
                result = self.request_token(token_url, flow=flow, **kwargs)
                if result:
                    print('Authentication Flow Completed. Oauth Access Token Stored. You can now use the API.')
                else:
                    print('Something go wrong. Please try again.')

                return result
            else:
                print('Authentication Flow aborted.')
                return False

        elif self.con.auth_flow_type in ('credentials', 'password'):
            return self.request_token(None, requested_scopes=requested_scopes, **kwargs)

        else:
            raise ValueError('"auth_flow_type" must be "authorization", "public", "password" or "credentials"')

    def get_authorization_url(self,
                              requested_scopes: List[str],
                              redirect_uri: Optional[str] = None,
                              **kwargs) -> Tuple[str, dict]:
        """ Initializes the oauth authorization flow, getting the
        authorization url that the user must approve.

        :param list[str] requested_scopes: list of scopes to request access for
        :param str redirect_uri: redirect url configured in registered app
        :param kwargs: allow to pass unused params in conjunction with Connection
        :return: authorization url and the flow dict
        """

        # convert request scopes based on the defined protocol
        requested_scopes = self.protocol.get_scopes_for(requested_scopes)

        return self.con.get_authorization_url(requested_scopes, redirect_uri=redirect_uri, **kwargs)

    def request_token(self, authorization_url: Optional[str], *,
                      flow: dict = None,
                      requested_scopes: Optional[List[str]] = None,
                      store_token: bool = True,
                      **kwargs) -> bool:
        """ Authenticates for the specified url and gets the oauth token data. Saves the
        token in the backend if store_token is True. This will replace any other tokens stored
        for the same username and scopes requested.
        If the token data is successfully requested, then this method will try to set the username if
        not previously set.

        :param str or None authorization_url: url given by the authorization flow or None if it's client credentials
        :param dict flow: dict object holding the data used in get_authorization_url
        :param list[str] requested_scopes: list of scopes to request access for
        :param bool store_token: True to store the token in the token backend,
         so you don't have to keep opening the auth link and
         authenticating every time
        :param kwargs: allow to pass unused params in conjunction with Connection
        :return: Success/Failure
        :rtype: bool
        """
        if self.con.auth_flow_type == 'credentials':
            if not requested_scopes:
                requested_scopes = [self.protocol.prefix_scope('.default')]
            else:
                if len(requested_scopes) > 1 or requested_scopes[0] != self.protocol.prefix_scope('.default'):
                    raise ValueError('Provided scope for auth flow type "credentials" does not match '
                                     'default scope for the current protocol')
        elif self.con.auth_flow_type == 'password':
            if requested_scopes:
                requested_scopes = self.protocol.get_scopes_for(requested_scopes)
            else:
                requested_scopes = [self.protocol.prefix_scope('.default')]
        else:
            if requested_scopes:
                raise ValueError(f'Auth flow type "{self.con.auth_flow_type}" does not require scopes')

        return self.con.request_token(authorization_url,
                                      flow=flow,
                                      requested_scopes=requested_scopes,
                                      store_token=store_token, **kwargs)

    @property
    def username(self) -> Optional[str]:
        """ Returns the username in use for the account"""
        return self.con.username

    def get_authenticated_usernames(self) -> list[str]:
        """ Returns a list of usernames that are authenticated and have a valid access or refresh token. """
        usernames = []
        for account in self.con.token_backend.get_all_accounts():
            username = account.get('username')
            if username and not self.con.token_backend.token_is_expired(username=username, refresh_token=True):
                usernames.append(username)

        return usernames

    @username.setter
    def username(self, username: Optional[str]) -> None:
        """
        Sets the username in use for this account
        The username can be None, meaning the first user account retrieved from the token_backend
        """
        self.con.username = username

    def get_current_user_data(self):
        """ Returns the current user data from the active directory """
        if self.con.auth_flow_type in ('authorization', 'public'):
            directory = self.directory(resource=ME_RESOURCE)
            return directory.get_current_user()
        else:
            return None

    @property
    def connection(self):
        """ Alias for self.con

        :rtype: type(self.connection_constructor)
        """
        return self.con

    def new_message(self, resource: Optional[str] = None):
        """ Creates a new message to be sent or stored

        :param str resource: Custom resource to be used in this message
         (Defaults to parent main_resource)
        :return: New empty message
        :rtype: Message
        """
        from .message import Message
        return Message(parent=self, main_resource=resource, is_draft=True)

    def mailbox(self, resource: Optional[str] = None):
        """ Get an instance to the mailbox for the specified account resource

        :param resource: Custom resource to be used in this mailbox
         (Defaults to parent main_resource)
        :return: a representation of account mailbox
        :rtype: O365.mailbox.MailBox
        """
        from .mailbox import MailBox
        return MailBox(parent=self, main_resource=resource, name='MailBox')

    def address_book(self, *, resource: Optional[str] = None, address_book: str = 'personal'):
        """ Get an instance to the specified address book for the
        specified account resource

        :param resource: Custom resource to be used in this address book
         (Defaults to parent main_resource)
        :param address_book: Choose from 'Personal' or 'Directory'
        :return: a representation of the specified address book
        :rtype: AddressBook or GlobalAddressList
        :raises RuntimeError: if invalid address_book is specified
        """
        if address_book.lower() == 'personal':
            from .address_book import AddressBook

            return AddressBook(parent=self, main_resource=resource,
                               name='Personal Address Book')
        elif address_book.lower() in ('gal', 'directory'):
            # for backwards compatibility only
            from .directory import Directory

            return Directory(parent=self, main_resource=resource)
        else:
            raise RuntimeError(
                'address_book must be either "Personal" '
                '(resource address book) or "Directory" (Active Directory)')

    def directory(self, resource: Optional[str] = None):
        """ Returns the active directory instance"""
        from .directory import Directory, USERS_RESOURCE

        return Directory(parent=self, main_resource=resource or USERS_RESOURCE)

    def schedule(self, *, resource: Optional[str] = None):
        """ Get an instance to work with calendar events for the
        specified account resource

        :param resource: Custom resource to be used in this schedule object
         (Defaults to parent main_resource)
        :return: a representation of calendar events
        :rtype: Schedule
        """
        from .calendar import Schedule
        return Schedule(parent=self, main_resource=resource)

    def storage(self, *, resource: Optional[str] = None):
        """ Get an instance to handle file storage (OneDrive / Sharepoint)
        for the specified account resource

        :param resource: Custom resource to be used in this drive object
         (Defaults to parent main_resource)
        :return: a representation of OneDrive File Storage
        :rtype: Storage
        :raises RuntimeError: if protocol doesn't support the feature
        """
        if not isinstance(self.protocol, MSGraphProtocol):
            # TODO: Custom protocol accessing OneDrive/Sharepoint Api fails here
            raise RuntimeError(
                'Drive options only works on Microsoft Graph API')
        from .drive import Storage
        return Storage(parent=self, main_resource=resource)

    def sharepoint(self, *, resource: str = ''):
        """ Get an instance to read information from Sharepoint sites for the
        specified account resource

        :param resource: Custom resource to be used in this sharepoint
         object (Defaults to parent main_resource)
        :return: a representation of Sharepoint Sites
        :rtype: Sharepoint
        :raises RuntimeError: if protocol doesn't support the feature
        """

        if not isinstance(self.protocol, MSGraphProtocol):
            # TODO: Custom protocol accessing OneDrive/Sharepoint Api fails here
            raise RuntimeError(
                'Sharepoint api only works on Microsoft Graph API')

        from .sharepoint import Sharepoint
        return Sharepoint(parent=self, main_resource=resource)

    def planner(self, *, resource: str = ''):
        """ Get an instance to read information from Microsoft planner """

        if not isinstance(self.protocol, MSGraphProtocol):
            # TODO: Custom protocol accessing OneDrive/Sharepoint Api fails here
            raise RuntimeError(
                'planner api only works on Microsoft Graph API')

        from .planner import Planner
        return Planner(parent=self, main_resource=resource)

    def tasks(self, *, resource: str = ''):
        """ Get an instance to read information from Microsoft ToDo """

        if isinstance(self.protocol, MSOffice365Protocol):
            from .tasks import ToDo
        else:
            from .tasks_graph import ToDo as ToDo

        return ToDo(parent=self, main_resource=resource)

    def teams(self, *, resource: str = ''):
        """ Get an instance to read information from Microsoft Teams """

        if not isinstance(self.protocol, MSGraphProtocol):
            raise RuntimeError(
                'teams api only works on Microsoft Graph API')

        from .teams import Teams
        return Teams(parent=self, main_resource=resource)

    def outlook_categories(self, *, resource: str = ''):
        """ Returns a Categories object to handle the available Outlook Categories """
        from .category import Categories

        return Categories(parent=self, main_resource=resource)

    def groups(self, *, resource: str = ''):
        """ Get an instance to read information from Microsoft Groups """

        if not isinstance(self.protocol, MSGraphProtocol):
            raise RuntimeError(
                'groups api only works on Microsoft Graph API')

        from .groups import Groups
        return Groups(parent=self, main_resource=resource)
