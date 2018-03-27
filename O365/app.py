from O365.connection import Connection, ME_RESOURCE, AUTH_METHOD
from O365.message import Message
from O365.mailbox import Folder
from O365.address_book import AddressBook


class App(object):

    def __init__(self, credentials, *, auth_method=AUTH_METHOD.OAUTH, scopes=None, protocol=None, main_resource=ME_RESOURCE):
        self.main_resource = main_resource
        self.con = Connection(credentials, auth_method=auth_method, scopes=scopes, protocol=protocol)

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
        return Folder(parent=self, main_resource=resource, name='MailBox', root=True)

    def addres_book(self, address_book='personal', resource=None):
        """
        Creates Address Book instance
        :param address_book: Choose from Personal or Gal (Global Address List)
        :param resource: Custom resource to be used in this address book. defaults to parent main_resource.
        """
        if address_book == 'personal':
            return AddressBook(parent=self, main_resource=resource)
        elif address_book == 'gal':
            if self.con.auth_method == AUTH_METHOD.BASIC and self.con.protocol.api_version == 'v1.0':
                raise RuntimeError('v1.0 with basic Authentication does not have access to the Global Addres List')
            return AddressBook(parent=self, main_resource='users')
        else:
            raise RuntimeError('Addres_book must be either "personal" (resource address book) or "gal" (Global Address List)')
