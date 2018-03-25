from O365.connection import Connection, ME_RESOURCE
from O365.message import Message
from O365.mailbox import Folder
from O365.address_book import AddressBook


class App(object):

    def __init__(self, username=None, password=None, client_id=None, client_secret=None,
                 api_version=None, main_resource=ME_RESOURCE, scopes=None):
        self.main_resource = main_resource
        self.con = Connection(username=username, password=password, client_id=client_id, client_secret=client_secret,
                              api_version=api_version, scopes=scopes)
        self.api_version = self.con.api_version
        self._mailbox = None  # lazy instantiation
        self._addres_book = None  # lazy instantiation

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
        if self._mailbox is None:
            self._mailbox = Folder(parent=self, main_resource=resource, name='MailBox', root=True)
        return self._mailbox

    def addres_book(self, resource=None):
        """
        Creates Address Book instance
        :param resource: Custom resource to be used in this address book. defaults to parent main_resource.
        """
        if self._addres_book is None:
            self._addres_book = AddressBook(parent=self, main_resource=resource)
        return self._addres_book
