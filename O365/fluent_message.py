from O365 import Connection
from O365.attachment import Attachment
from O365.connection import MicroDict
from O365.contact import Contact
from O365.group import Group
import logging
import json
import requests

from O365.utils import deprecated

log = logging.getLogger(__name__)


class FluentMessage(object):
    '''
    Management of the process of sending, receiving, reading, and editing emails.

    Note: the get and set methods are technically superflous. You can get more through control over
    a message you are trying to craft throught he use of editing the message.json, but these
    methods provide an easy way if you don't need all the power and would like the ease.

    Methods:
                    constructor -- creates a new message class, using json for existing, nothing for new.
                    fetchAttachments -- kicks off the process that downloads attachments.
                    sendMessage -- take local variables and form them to send the message.
                    markAsRead -- marks the analougs message in the cloud as read.
                    getSender -- gets a dictionary with the sender's information.
                    getSenderEmail -- gets the email address of the sender.
                    getSenderName -- gets the name of the sender, if possible.
                    getSubject -- gets the email's subject line.
                    getBody -- gets contents of the body of the email.
                    addRecipient -- adds a person to the recipient list.
                    setRecipients -- sets the list of recipients.
                    setSubject -- sets the subject line.
                    setBody -- sets the body.
                    setCategory -- sets the email's category

    Variables:
                    att_url -- url for requestiong attachments. takes message GUID
                    send_url -- url for sending an email
                    update_url -- url for updating an email already existing in the cloud.

    '''

    url_dict = {
        'attachments': '/me/messages/{message_id}/attachments',
        'send': '/me/sendmail',
        'send_as': '/me/users/{user_id}/sendmail',
        'draft': '/me/folders/{folder_id}/messages',
        'update': '/me/messages/{message_id}',
        'move': '/me/messages/{0}/move',
    }

    @staticmethod
    def _get_url(key):
        """ Fetches the url for specified key as per the connection version
        configured

        :param key: the key for which url is required
        :return: URL to use for requests
        """
        return Connection().root_url + FluentMessage.url_dict[key]

    def __init__(self, json_data=None, verify=True):
        """ Makes a new message wrapper for sending and receiving messages.

        :param json_data: Takes json if you have a pre-existing message to
         create from. this is mostly used inside the library for
         when new messages are downloaded.
        :param verify: whether or not to verify SSL certificate

        """
        if json_data:
            self.json = json_data
            self.has_attachments = json_data['hasAttachments']

        else:
            self.json = MicroDict({'Message': {'Body': {}},
                                   'ToRecipients': [], 'CcRecipients': [],
                                   'BccRecipients': []})
            self.has_attachments = False

        # Added for backward compatibility
        self.hasAttachments = self.has_attachments

        self.attachments = []
        self.receiver = None
        self.verify = verify

    def fetch_attachments(self, **kwargs):
        """ Downloads the attachments

        :return no. of attachments
        """
        if not self.has_attachments:
            log.debug('Message has no attachments, skipping out early.')
            return False

        url = FluentMessage._get_url('attachments').format(
            message_id=self.json['id'])
        response = Connection.get_response(url, verify=self.verify, **kwargs)

        for attachment in response:
            try:
                self.attachments.append(Attachment(attachment))
                log.debug('Successfully downloaded attachment {}'.format(
                    attachment['name']))
            except RuntimeError as _:
                log.info('Failed downloading attachment {}'.format(
                    attachment['name']))

        return len(self.attachments)

    def send(self, user_id=None, **kwargs):
        """ Send the email

        :param user_id: User id (email) if sending as other user
        :return True or False (Success or Fail)
        """

        headers = {'Content-Type': 'application/json', 'Accept': 'text/plain'}

        try:
            data = {'Message': {'Body': {}}}
            data['Message']['Subject'] = self.json['Subject']
            data['Message']['Body']['Content'] = self.json['Body']['Content']
            data['Message']['Body']['ContentType'] = self.json['Body'][
                'ContentType']
            data['Message']['ToRecipients'] = self.json['ToRecipients']
            data['Message']['CcRecipients'] = self.json['CcRecipients']
            data['Message']['BccRecipients'] = self.json['BccRecipients']
            data['Message']['Attachments'] = [att.json for att in
                                              self.attachments]
            data = json.dumps(data)
        except Exception as e:
            log.error(
                'Error while trying to compile the json string to send: {0}'.format(
                    str(e)))
            return False

        if user_id:
            url = FluentMessage._get_url('send_as').format(user_id=user_id)
        else:
            url = FluentMessage._get_url('send')

        try:
            response = Connection.get_response(url, method='POST', data=data,
                                               headers=headers,
                                               verify=self.verify,
                                               **kwargs)
        except RuntimeError as _:
            return False

        if response.status_code != 202:
            return False

        return True

    def mark_as_read(self, **kwargs):
        """ Marks this message as read in the cloud

        :return True or False (Success or Fail)
        """
        data = '{"IsRead":true}'
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        url = FluentMessage._get_url('update').format(
            message_id=self.json['id'])
        try:
            response = Connection.get_response(url, method='PATCH', data=data,
                                               headers=headers,
                                               verify=self.verify,
                                               **kwargs)
        except RuntimeError as _:
            return False
        return response.ok

    def move_to(self, folder_id, **kwargs):
        """ Move the message to a given folder

        :param folder_id: Folder ID to move this message to
        :return True or False (Success or Fail)
        """
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        data = {"DestinationId": folder_id}

        url = FluentMessage._get_url('move').format(
            message_id=self.json['id'])
        try:
            response = Connection.get_response(url, method='POST', data=data,
                                               headers=headers,
                                               verify=self.verify,
                                               **kwargs)
        except RuntimeError as _:
            return False
        return response.ok

    def _set_recipients(self, contacts, r_type='To'):
        """ Set the `TO` recipients list.

            Each recipient can be either of the below

            dictionary: this must to be a dictionary formatted as such:
                {"EmailAddress":{"Address":"recipient@example.com"}}
                with other options such ass "Name" with address. but at minimum
                it must have this.

            or

            simple email address

            or

            Contact object (Contact is part of this library)

            or

            Group object, which is a list of contacts
            (Group is part of this library)

        :param contacts: List of recipients
        :param r_type: 'To' or 'Bcc' or 'Cc'
        """
        self.json[r_type + 'Recipients'] = []

        if not isinstance(contacts, tuple):
            contacts = [contacts]

        log.debug('Setting recipients for {}: {}'.format(r_type, contacts))
        for contact in contacts:
            if isinstance(contact, Contact):
                self.addRecipient(contact, r_type=r_type)
            elif isinstance(contact, str):
                if '@' in contact:
                    self.addRecipient(contact, r_type=r_type)
            elif isinstance(contact, dict):
                self.json[r_type + 'Recipients'].append(contact)
            elif isinstance(contact, Group):
                for person in contact:
                    self.addRecipient(person, r_type=r_type)
            else:
                raise RuntimeError(
                    'Unknown contanct information {}'.format(contact))

    def to(self, *recipients):
        """ Set the `TO` recipients list.

            Each recipient can be either of the below

            dictionary: this must to be a dictionary formatted as such:
                {"EmailAddress":{"Address":"recipient@example.com"}}
                with other options such ass "Name" with address. but at minimum
                it must have this.

            or

            simple email address

            or

            Contact object (Contact is part of this library)

            or

            Group object, which is a list of contacts
            (Group is part of this library)

        :param recipients: List of recipients
        """
        self._set_recipients(recipients, 'To')
        return self

    def cc(self, *recipients):
        """ Set the `CC` recipients list.

            Each recipient can be either of the below

            dictionary: this must to be a dictionary formatted as such:
                {"EmailAddress":{"Address":"recipient@example.com"}}
                with other options such ass "Name" with address. but at minimum
                it must have this.

            or

            simple email address

            or

            Contact object (Contact is part of this library)

            or

            Group object, which is a list of contacts
            (Group is part of this library)

        :param recipients: List of recipients
        """
        self._set_recipients(recipients, 'Cc')
        return self

    def bcc(self, *recipients):
        """ Set the `BCC` recipients list.

            Each recipient can be either of the below

            dictionary: this must to be a dictionary formatted as such:
                {"EmailAddress":{"Address":"recipient@example.com"}}
                with other options such ass "Name" with address. but at minimum
                it must have this.

            or

            simple email address

            or

            Contact object (Contact is part of this library)

            or

            Group object, which is a list of contacts
            (Group is part of this library)

        :param recipients: List of recipients
        """
        self._set_recipients(recipients, 'Bcc')
        return self

    def getSender(self):
        '''get all available information for the sender of the email.'''
        return self.json['Sender']

    def getSenderEmail(self):
        '''get the email address of the sender.'''
        return self.json['Sender']['EmailAddress']['Address']

    def getSenderName(self):
        '''try to get the name of the sender.'''
        try:
            return self.json['Sender']['EmailAddress']['Name']
        except:
            return ''

    def getSubject(self):
        '''get email subject line.'''
        return self.json['Subject']

    def getBody(self):
        '''get email body.'''
        try:
            return self.json['Body']['Content']
        except KeyError as e:
            log.debug("Fluent inbox getBody: No body content.")
            return ""

    def setRecipients(self, val, r_type="To"):
        '''
        set the recipient list.

        val: the one argument this method takes can be very flexible. you can send:
                        a dictionary: this must to be a dictionary formated as such:
                                        {"EmailAddress":{"Address":"recipient@example.com"}}
                                        with other options such ass "Name" with address. but at minimum
                                        it must have this.
                        a list: this must to be a list of libraries formatted the way
                                        specified above, or it can be a list of dictionary objects of
                                        type Contact or it can be an email address as string. The
                                        method will sort out the libraries from the contacts.
                        a string: this is if you just want to throw an email address.
                        a contact: type Contact from this dictionary.
                        a group: type Group, which is a list of contacts.
        For each of these argument types the appropriate action will be taken
        to fit them to the needs of the library.
        '''
        log.debug(
            "Entered SET_RECIPIENTS function with type: {}".format(r_type))
        self.json[r_type + 'Recipients'] = []

        if isinstance(val, list):
            for con in val:
                if isinstance(con, Contact):
                    self.addRecipient(con, r_type=r_type)
                elif isinstance(con, str):
                    if '@' in con:
                        self.addRecipient(con, r_type=r_type)
                elif isinstance(con, dict):
                    self.json[r_type + 'Recipients'].append(con)
        elif isinstance(val, dict):
            self.json[r_type + 'Recipients'] = [val]
        elif isinstance(val, str):
            if '@' in val:
                self.addRecipient(val, r_type=r_type)
        elif isinstance(val, Contact):
            self.addRecipient(val, r_type=r_type)
        elif isinstance(val, Group):
            for person in val:
                self.addRecipient(person, r_type=r_type)
        else:
            return False
        return True

    def addRecipient(self, address, name=None, r_type="To"):
        '''
        Adds a recipient to the recipients list.

        Arguments:
        address -- the email address of the person you are sending to. <<< Important that.
                        Address can also be of type Contact or type Group.
        name -- the name of the person you are sending to. mostly just a decorator. If you
                        send an email address for the address arg, this will give you the ability
                        to set the name properly, other wise it uses the email address up to the
                        at sign for the name. But if you send a type Contact or type Group, this
                        argument is completely ignored.
        '''
        if isinstance(address, Contact):
            self.json[r_type + 'Recipients'].append(
                address.getFirstEmailAddress())
        elif isinstance(address, Group):
            for con in address.contacts:
                self.json[r_type + 'Recipients'].append(
                    address.getFirstEmailAddress())
        else:
            if name is None:
                name = address[:address.index('@')]
            self.json[r_type + 'Recipients'].append(
                {'EmailAddress': {'Address': address, 'Name': name}})

    def setSubject(self, val):
        '''Sets the subect line of the email.'''
        self.json['Subject'] = val

    def setBody(self, val):
        '''Sets the body content of the email.'''
        cont = False

        while not cont:
            try:
                self.json['Body']['Content'] = val
                self.json['Body']['ContentType'] = 'Text'
                cont = True
            except:
                self.json['Body'] = {}

    def setBodyHTML(self, val=None):
        '''
        Sets the body content type to HTML for your pretty emails.

        arguments:
        val -- Default: None. The content of the body you want set. If you don't pass a
                        value it is just ignored.
        '''
        cont = False

        while not cont:
            try:
                self.json['Body']['ContentType'] = 'HTML'
                if val:
                    self.json['Body']['Content'] = val
                cont = True
            except:
                self.json['Body'] = {}

    def category(self, category_name, **kwargs):
        """ Set the category of the message

        :param category_name: category to add to the message
        :return:
        """
        data = '{{"Categories":["{}"]}}'.format(category_name)
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        url = FluentMessage._get_url('update').format(
            message_id=self.json['id'])
        try:
            response = Connection.get_response(url, method='PATCH', data=data,
                                               headers=headers,
                                               verify=self.verify,
                                               **kwargs)
        except RuntimeError as _:
            return False
        return response.ok

    @deprecated(category)
    def setCategory(self, category_name, **kwargs):
        self.set_category(category_name, **kwargs)

    @deprecated(category)
    def update_category(self, category_name, **kwargs):
        self.set_category(category_name, **kwargs)

    @deprecated(fetch_attachments)
    def fetchAttachments(self, **kwargs):
        return self.fetch_attachments(**kwargs)

    @deprecated(send)
    def sendMessage(self, user_id=None, **kwargs):
        return self.send(user_id, **kwargs)

    @deprecated(mark_as_read)
    def markAsRead(self, **kwargs):
        return self.mark_as_read(**kwargs)

    @deprecated(move_to)
    def moveToFolder(self, folder_id, **kwargs):
        return self.move_to(folder_id, **kwargs)

    @deprecated(to, cc, bcc)
    def setRecipients(self, val, r_type='To'):
        return self._set_recipients(val, r_type)


# Below step added for backward compatibility
Message = FluentMessage
