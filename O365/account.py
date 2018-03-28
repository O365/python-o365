from O365.connection import Connection, Protocol, MSGraphProtocol, MSOffice365Protocol, ME_RESOURCE, AUTH_METHOD
from O365.message import Message
from O365.mailbox import MailBox
from O365.address_book import AddressBook, GAL_MAIN_RESOURCE


class Account(object):

    def __init__(self, credentials, *, auth_method=AUTH_METHOD.OAUTH, scopes=None, protocol=None, main_resource=ME_RESOURCE):

        if isinstance(auth_method, str):
            try:
                auth_method = AUTH_METHOD(auth_method)
            except ValueError as e:
                raise e
        self.con = Connection(credentials, auth_method=auth_method, scopes=scopes)

        if auth_method is AUTH_METHOD.BASIC:
            protocol = protocol or MSOffice365Protocol  # using basic auth defaults to Office 365 protocol
            self.protocol = protocol(default_resource=main_resource) if isinstance(protocol, type) else protocol
            if self.protocol.api_version != 'v1.0' or isinstance(self.protocol, MSGraphProtocol):
                raise RuntimeError(
                    'Basic Authentication only works with Office 365 Api version v1.0 and until November 1 2018.')
        elif auth_method is AUTH_METHOD.OAUTH:
            protocol = protocol or MSGraphProtocol  # using oauth auth defaults to Graph protocol
            self.protocol = protocol(default_resource=main_resource) if isinstance(protocol, type) else protocol

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
        return MailBox(parent=self, main_resource=resource, name='MailBox', root=True)

    def address_book(self, resource=None, *, address_book='personal'):
        """
        Creates Address Book instance
        :param resource: Custom resource to be used in this address book. defaults to parent main_resource.
        :param address_book: Choose from Personal or Gal (Global Address List)
        """
        if address_book == 'personal':
            return AddressBook(parent=self, main_resource=resource)
        elif address_book == 'gal':
            if self.con.auth_method == AUTH_METHOD.BASIC and self.protocol.api_version == 'v1.0':
                raise RuntimeError('v1.0 with basic Authentication does not have access to the Global Addres List')
            return AddressBook(parent=self, main_resource=GAL_MAIN_RESOURCE)
        else:
            raise RuntimeError('Addres_book must be either "personal" (resource address book) or "gal" (Global Address List)')
