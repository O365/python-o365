from O365.connection import Connection, ME_RESOURCE
from O365.message import Message
from O365.inbox import Inbox
from O365.address_book import AddressBook


class App(object):

    def __init__(self, username=None, password=None, client_id=None, client_secret=None,
                 api_version=None, main_resource=ME_RESOURCE, scopes=None):
        self.main_resource = main_resource
        self.con = Connection(username=username, password=password, client_id=client_id, client_secret=client_secret,
                              api_version=api_version, scopes=scopes)
        self.api_version = self.con.api_version
        self._inbox = None  # lazy instantiation
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
        return Message(parent=self, main_resource=resource)

    def inbox(self, resource=None):
        """
        Creates Inbox instance
        :param resource: Custom resource to be used in this inbox. defaults to parent main_resource.
        """
        if self._inbox is None:
            self._inbox = Inbox(parent=self, main_resource=resource)
        return self._inbox

    def addres_book(self, resource=None):
        """
        Creates Address Book instance
        :param resource: Custom resource to be used in this address book. defaults to parent main_resource.
        """
        if self._addres_book is None:
            self._addres_book = AddressBook(parent=self, main_resource=resource)
        return self._addres_book
