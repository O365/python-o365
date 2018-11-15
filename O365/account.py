from O365.address_book import AddressBook, GlobalAddressList
from O365.calendar import Schedule
from O365.connection import Connection, Protocol, MSGraphProtocol
from O365.connection import oauth_authentication_flow
from O365.drive import Storage
from O365.mailbox import MailBox
from O365.message import Message
from O365.utils import ME_RESOURCE
from O365.message import Message
from O365.mailbox import MailBox
from O365.address_book import AddressBook, GlobalAddressList
from O365.calendar import Schedule
from O365.sharepoint import Sharepoint


class Account(object):

    def __init__(self, credentials, *, protocol=None, main_resource=ME_RESOURCE,
                 **kwargs):
        """ Creates an object which is used to access resources related to the
        specified credentials

        :param tuple credentials: a tuple containing the client_id
         and client_secret
        :param Protocol protocol: the protocol to be used in this account
        :param str main_resource: the resource to be used by this account
         ('me' or 'users')
        :param kwargs: any extra args to be passed to the Connection instance
        :raises ValueError: if an invalid protocol is passed
        """

        protocol = protocol or MSGraphProtocol  # Defaults to Graph protocol
        self.protocol = protocol(default_resource=main_resource,
                                 **kwargs) if isinstance(protocol,
                                                         type) else protocol

        if not isinstance(self.protocol, Protocol):
            raise ValueError("'protocol' must be a subclass of Protocol")

        self.con = Connection(credentials, **kwargs)
        self.main_resource = main_resource

    def __repr__(self):
        if self.con.auth:
            return 'Account Client Id: {}'.format(self.con.auth[0])
        else:
            return 'Unidentified Account'

    def authenticate(self, *, scopes, **kwargs):
        """ Performs the oauth authentication flow resulting in a stored token
        It uses the credentials passed on instantiation

        :param list[str] scopes: list of protocol user scopes to be converted
         by the protocol
        :param kwargs: other configurations to be passed to the
         Connection instance
        :return: Success / Failure
        :rtype: bool
        """
        kwargs.setdefault('token_file_name', self.con.token_path.name)

        return oauth_authentication_flow(*self.con.auth, scopes=scopes,
                                         protocol=self.protocol, **kwargs)

    @property
    def connection(self):
        """ Alias for self.con

        :rtype: Connection
        """
        return self.con

    def new_message(self, resource=None):
        """ Creates a new message to be sent or stored

        :param str resource: Custom resource to be used in this message
         (Defaults to parent main_resource)
        :return: New empty message
        :rtype: Message
        """
        return Message(parent=self, main_resource=resource, is_draft=True)

    def mailbox(self, resource=None):
        """ Get an instance to the mailbox for the specified account resource

        :param str resource: Custom resource to be used in this mailbox
         (Defaults to parent main_resource)
        :return: a representation of account mailbox
        :rtype: MailBox
        """
        return MailBox(parent=self, main_resource=resource, name='MailBox')

    def address_book(self, *, resource=None, address_book='personal'):
        """ Get an instance to the specified address book for the
        specified account resource

        :param str resource: Custom resource to be used in this address book
         (Defaults to parent main_resource)
        :param str address_book: Choose from 'Personal' or
         'GAL' (Global Address List)
        :return: a representation of the specified address book
        :rtype: AddressBook or GlobalAddressList
        :raises RuntimeError: if invalid address_book is specified
        """
        if address_book.lower() == 'personal':
            return AddressBook(parent=self, main_resource=resource,
                               name='Personal Address Book')
        elif address_book.lower() == 'gal':
            return GlobalAddressList(parent=self)
        else:
            raise RuntimeError(
                'address_book must be either "personal" '
                '(resource address book) or "gal" (Global Address List)')

    def schedule(self, *, resource=None):
        """ Get an instance to work with calendar events for the
        specified account resource

        :param str resource: Custom resource to be used in this schedule object
         (Defaults to parent main_resource)
        :return: a representation of calendar events
        :rtype: Schedule
        """
        return Schedule(parent=self, main_resource=resource)

    def storage(self, *, resource=None):
        """ Get an instance to handle file storage like OneDrive or
        Sharepoint document libraries for the specified account resource

        :param str resource: Custom resource to be used in this drive object
         (Defaults to parent main_resource)
        :return: a representation of File Storage
        :rtype: Storage
        :raises RuntimeError: if protocol doesn't support the feature
        """
        if not isinstance(self.protocol, MSGraphProtocol):
            # TODO: Custom protocol accessing OneDrive/Sharepoint Api fails here
            raise RuntimeError(
                'Drive options only works on Microsoft Graph API')

        return Storage(parent=self, main_resource=resource)

    def sharepoint(self, *, resource=''):
        """
        Creates a new Sharepoint instance
        :param resource: Custom resource to be used in this sharepoint object. Defaults to blank.
        """

        if not isinstance(self.protocol, MSGraphProtocol):
            # TODO: a custom protocol accessing OneDrive or Sharepoint Api will fail here.
            raise RuntimeError('Sharepoint api only works on Microsoft Graph API')

        return Sharepoint(parent=self, main_resource=resource)
