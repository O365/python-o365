from .connection import Connection, Protocol, MSGraphProtocol, MSOffice365Protocol
from .utils import ME_RESOURCE, consent


class Account:

    connection_constructor = Connection

    def __init__(self, credentials, *, protocol=None, main_resource=None, **kwargs):
        """ Creates an object which is used to access resources related to the
        specified credentials

        :param tuple credentials: a tuple containing the client_id
         and client_secret
        :param Protocol protocol: the protocol to be used in this account
        :param str main_resource: the resource to be used by this account
         ('me' or 'users', etc.)
        :param kwargs: any extra args to be passed to the Connection instance
        :raises ValueError: if an invalid protocol is passed
        """

        protocol = protocol or MSGraphProtocol  # Defaults to Graph protocol
        self.protocol = protocol(default_resource=main_resource,
                                 **kwargs) if isinstance(protocol,
                                                         type) else protocol

        if not isinstance(self.protocol, Protocol):
            raise ValueError("'protocol' must be a subclass of Protocol")

        auth_flow_type = kwargs.get('auth_flow_type', 'authorization')
        scopes = kwargs.get('scopes', None)  # retrieve scopes

        if auth_flow_type in ('authorization', 'public'):
            # convert the provided scopes to protocol scopes:
            if scopes is not None:
                kwargs['scopes'] = self.protocol.get_scopes_for(scopes)
        elif auth_flow_type in ('credentials', 'certificate'):
            # for client credential grant flow solely: add the default scope if it's not provided
            if not scopes:
                kwargs['scopes'] = [self.protocol.prefix_scope('.default')]
            else:
                raise ValueError(f'Auth flow type "{auth_flow_type}" does not require scopes')

            # set main_resource to blank when it's the 'ME' resource
            if self.protocol.default_resource == ME_RESOURCE:
                self.protocol.default_resource = ''
            if main_resource == ME_RESOURCE:
                main_resource = ''

        elif auth_flow_type == 'password':
            kwargs['scopes'] = self.protocol.get_scopes_for(scopes) if scopes else [self.protocol.prefix_scope('.default')]

            # set main_resource to blank when it's the 'ME' resource
            if self.protocol.default_resource == ME_RESOURCE:
                self.protocol.default_resource = ''
            if main_resource == ME_RESOURCE:
                main_resource = ''
        else:
            raise ValueError('"auth_flow_type" must be "authorization", "credentials", "certificate", "password" or '
                             '"public"')

        self.con = self.connection_constructor(credentials, **kwargs)
        self.main_resource = main_resource or self.protocol.default_resource

    def __repr__(self):
        if self.con.auth:
            return 'Account Client Id: {}'.format(self.con.auth[0])
        else:
            return 'Unidentified Account'

    @property
    def is_authenticated(self):
        """
        Checks whether the library has the authentication and that is not expired
        :return: True if authenticated, False otherwise
        """
        token = self.con.token_backend.token
        if not token:
            token = self.con.token_backend.get_token()

        return token is not None and not token.is_expired

    def authenticate(self, *, scopes=None, handle_consent=consent.consent_input_token, **kwargs):
        """ Performs the oauth authentication flow using the console resulting in a stored token.
        It uses the credentials passed on instantiation

        :param list[str] or None scopes: list of protocol user scopes to be converted
         by the protocol or scope helpers
        :param kwargs: other configurations to be passed to the
         Connection.get_authorization_url and Connection.request_token methods
        :return: Success / Failure
        :rtype: bool
        """

        if self.con.auth_flow_type in ('authorization', 'public'):
            if scopes is not None:
                if self.con.scopes is not None:
                    raise RuntimeError('The scopes must be set either at the Account instantiation or on the account.authenticate method.')
                self.con.scopes = self.protocol.get_scopes_for(scopes)
            else:
                if self.con.scopes is None:
                    raise ValueError('The scopes are not set. Define the scopes requested.')

            consent_url, _ = self.con.get_authorization_url(**kwargs)

            token_url = handle_consent(consent_url)

            if token_url:
                result = self.con.request_token(token_url, **kwargs)  # no need to pass state as the session is the same
                if result:
                    print('Authentication Flow Completed. Oauth Access Token Stored. You can now use the API.')
                else:
                    print('Something go wrong. Please try again.')

                return bool(result)
            else:
                print('Authentication Flow aborted.')
                return False

        elif self.con.auth_flow_type in ('credentials', 'certificate', 'password'):
            return self.con.request_token(None, requested_scopes=scopes)
        else:
            raise ValueError('Connection "auth_flow_type" must be "authorization", "public", "password", "certificate"'
                             ' or "credentials"')

    def get_current_user(self):
        """ Returns the current user """
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

    def new_message(self, resource=None):
        """ Creates a new message to be sent or stored

        :param str resource: Custom resource to be used in this message
         (Defaults to parent main_resource)
        :return: New empty message
        :rtype: Message
        """
        from .message import Message
        return Message(parent=self, main_resource=resource, is_draft=True)

    def mailbox(self, resource=None):
        """ Get an instance to the mailbox for the specified account resource

        :param str resource: Custom resource to be used in this mailbox
         (Defaults to parent main_resource)
        :return: a representation of account mailbox
        :rtype: O365.mailbox.MailBox
        """
        from .mailbox import MailBox
        return MailBox(parent=self, main_resource=resource, name='MailBox')

    def address_book(self, *, resource=None, address_book='personal'):
        """ Get an instance to the specified address book for the
        specified account resource

        :param str resource: Custom resource to be used in this address book
         (Defaults to parent main_resource)
        :param str address_book: Choose from 'Personal' or 'Directory'
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

    def directory(self, resource=None):
        """ Returns the active directory instance"""
        from .directory import Directory, USERS_RESOURCE

        return Directory(parent=self, main_resource=resource or USERS_RESOURCE)

    def schedule(self, *, resource=None):
        """ Get an instance to work with calendar events for the
        specified account resource

        :param str resource: Custom resource to be used in this schedule object
         (Defaults to parent main_resource)
        :return: a representation of calendar events
        :rtype: Schedule
        """
        from .calendar import Schedule
        return Schedule(parent=self, main_resource=resource)

    def storage(self, *, resource=None):
        """ Get an instance to handle file storage (OneDrive / Sharepoint)
        for the specified account resource

        :param str resource: Custom resource to be used in this drive object
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

    def sharepoint(self, *, resource=''):
        """ Get an instance to read information from Sharepoint sites for the
        specified account resource

        :param str resource: Custom resource to be used in this sharepoint
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

    def planner(self, *, resource=''):
        """ Get an instance to read information from Microsoft planner """

        if not isinstance(self.protocol, MSGraphProtocol):
            # TODO: Custom protocol accessing OneDrive/Sharepoint Api fails here
            raise RuntimeError(
                'planner api only works on Microsoft Graph API')

        from .planner import Planner
        return Planner(parent=self, main_resource=resource)

    def tasks(self, *, resource=''):
        """ Get an instance to read information from Microsoft ToDo """

        if isinstance(self.protocol, MSOffice365Protocol):
            from .tasks import ToDo
        else:
            from .tasks_graph import ToDo as ToDo

        return ToDo(parent=self, main_resource=resource)
    
    def teams(self, *, resource=''):
        """ Get an instance to read information from Microsoft Teams """

        if not isinstance(self.protocol, MSGraphProtocol):
            raise RuntimeError(
                'teams api only works on Microsoft Graph API')

        from .teams import Teams
        return Teams(parent=self, main_resource=resource)

    def outlook_categories(self, *, resource=''):
        """ Returns a Categories object to handle the available Outlook Categories """
        from .category import Categories

        return Categories(parent=self, main_resource=resource)

    def groups(self, *, resource=''):
        """ Get an instance to read information from Microsoft Groups """

        if not isinstance(self.protocol, MSGraphProtocol):
            raise RuntimeError(
                'groups api only works on Microsoft Graph API')

        from .groups import Groups
        return Groups(parent=self, main_resource=resource)
