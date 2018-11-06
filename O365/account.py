from O365.connection import Connection, Protocol, MSGraphProtocol, oauth_authentication_flow
from O365.drive import Storage
from O365.utils import ME_RESOURCE
from O365.message import Message
from O365.mailbox import MailBox
from O365.address_book import AddressBook, GlobalAddressList
from O365.calendar import Schedule


class Account(object):
    """ Class helper to integrate all components into a single object """

    def __init__(self, credentials, *, protocol=None, main_resource=ME_RESOURCE, **kwargs):
        """
        Account constructor.
        :param credentials: a tuple containing the client_id and client_secret
        :param protocol: the protocol to be used in this account instance
        :param main_resource: the resource to be used by this account
        :param kwargs: any extra args to be passed to the Connection instance
        """

        protocol = protocol or MSGraphProtocol  # defaults to Graph protocol
        self.protocol = protocol(default_resource=main_resource, **kwargs) if isinstance(protocol, type) else protocol

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
        """
        Performs the oauth authentication flow resulting in a stored token.
        It uses the credentials passed on instantiation
        :param scopes: a list of protocol user scopes to be converted by the protocol
        :param kwargs: other configuration to be passed to the Connection instance
        """
        kwargs.setdefault('token_file_name', self.con.token_path.name)

        return oauth_authentication_flow(*self.con.auth, scopes=scopes, protocol=self.protocol, **kwargs)

    @property
    def connection(self):
        """ Alias for self.con """
        return self.con

    def new_message(self, resource=None):
        """
        Creates a new message to be send or stored
        :param resource: Custom resource to be used in this message. Defaults to parent main_resource.
        """
        return Message(parent=self, main_resource=resource, is_draft=True)

    def mailbox(self, resource=None):
        """
        Creates MailBox Folder instance
        :param resource: Custom resource to be used in this mailbox. Defaults to parent main_resource.
        """
        return MailBox(parent=self, main_resource=resource, name='MailBox')

    def address_book(self, *, resource=None, address_book='personal'):
        """
        Creates Address Book instance
        :param resource: Custom resource to be used in this address book. Defaults to parent main_resource.
        :param address_book: Choose from Personal or Gal (Global Address List)
        """
        if address_book == 'personal':
            return AddressBook(parent=self, main_resource=resource, name='Personal Address Book')
        elif address_book == 'gal':
            return GlobalAddressList(parent=self)
        else:
            raise RuntimeError('Addres_book must be either "personal" (resource address book) or "gal" (Global Address List)')

    def schedule(self, *, resource=None):
        """
        Creates Schedule instance to handle calendars
        :param resource: Custom resource to be used in this schedule object. Defaults to parent main_resource.
        """
        return Schedule(parent=self, main_resource=resource)

    def storage(self, *, resource=None):
        """
        Creates a Storage instance to handle file storage like OneDrive or Sharepoint document libraries
        :param resource: Custom resource to be used in this drive object. Defaults to parent main_resource.
        """
        if not isinstance(self.protocol, MSGraphProtocol):
            # TODO: a custom protocol accessing OneDrive or Sharepoint Api will fail here.
            raise RuntimeError('Drive options only works on Microsoft Graph API')

        return Storage(parent=self, main_resource=resource)
