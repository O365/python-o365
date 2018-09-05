from O365.connection import Connection, Protocol, MSGraphProtocol
from O365.utils import ME_RESOURCE
from O365.message import Message
from O365.mailbox import MailBox
from O365.address_book import AddressBook, GlobalAddressList
from O365.calendar import Schedule


class Account(object):
    """ Class helper to integrate all components into a single object """

    def __init__(self, credentials, *, scopes=None, protocol=None, main_resource=ME_RESOURCE, **kwargs):

        protocol = protocol or MSGraphProtocol  # using oauth auth defaults to Graph protocol
        self.protocol = protocol(default_resource=main_resource, **kwargs) if isinstance(protocol, type) else protocol

        if not isinstance(self.protocol, Protocol):
            raise ValueError("'protocol' must be a subclass of Protocol")

        self.con = kwargs.get('connection') or Connection(credentials, scopes=self.protocol.get_scopes_for(scopes))
        self.main_resource = main_resource

    @property
    def connection(self):
        """ Alias for self.con """
        return self.con

    def new_message(self, resource=None):
        """
        Creates a new message to be send or stored
        :param resource: Custom resource to be used in this message. defaults to parent main_resource.
        """
        return Message(parent=self, main_resource=resource, is_draft=True)

    def mailbox(self, resource=None):
        """
        Creates MailBox Folder instance
        :param resource: Custom resource to be used in this mailbox. defaults to parent main_resource.
        """
        return MailBox(parent=self, main_resource=resource, name='MailBox')

    def address_book(self, *, resource=None, address_book='personal'):
        """
        Creates Address Book instance
        :param resource: Custom resource to be used in this address book. defaults to parent main_resource.
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
        :param resource: Custom resource to be used in this schedule object. defaults to parent main_resource.
        """
        return Schedule(parent=self, main_resource=resource)
