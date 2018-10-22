import json
import logging

from .attachment import Attachment
from .connection import MicroDict, Connection
from .contact import Contact
from .group import Group
from .utils import deprecated

log = logging.getLogger(__name__)


class Message(object):
    """ Makes a new message wrapper for sending and receiving messages.

    :param json_data: Takes json if you have a pre-existing message to
     create from. this is mostly used inside the library for
     when new messages are downloaded.
    :param verify: whether or not to verify SSL certificate
    """

    url_dict = {
        'attachments': '/me/messages/{message_id}/attachments',
        'send': '/me/sendmail',
        'send_as': '/me/users/{user_id}/sendmail',
        'update': '/me/messages/{message_id}',
        'move': '/me/messages/{0}/move',
        'reply': '/me/messages/{id}/reply',
        'reply_all': '/me/messages/{id}/replyAll',
    }

    def __init__(self, json_data=None, verify=True):
        """ Makes a new message wrapper for sending and receiving messages.

        :param json_data: Takes json if you have a pre-existing message to
         create from. this is mostly used inside the library for
         when new messages are downloaded.
        :param verify: whether or not to verify SSL certificate
        """
        if json_data:
            self.json = json_data

        else:
            self.json = MicroDict({'body': {},
                                   'toRecipients': [], 'ccRecipients': [],
                                   'bccRecipients': []})

        self.attachments = []
        self.verify = verify
        self.action_success = False

    @staticmethod
    def _get_url(key):
        """ Fetches the url for specified key as per the connection version
        configured

        :param key: the key for which url is required
        :return: URL to use for requests
        """
        url = Connection().root_url + Message.url_dict[key]

        # To be removed post 1 Nov, 2018 (1.0 removal)
        if Connection().api_version == "1.0":
            url.replace('mailFolders', 'folders')
        return url

    @property
    def sender(self):
        """ Get all available information for the sender of email

        :return: Sender details
        :rtype: dict
        """
        return self.json['sender']

    @property
    def sender_email(self):
        """ Get email address of the sender

        :return: Sender email-id
        :rtype: str
        """
        return self.sender['emailAddress']['address']

    @property
    def sender_name(self):
        """ Get name of the sender if exists

        :return: Sender name
        :rtype: str
        """
        try:
            return self.sender['emailAddress']['name']
        except KeyError as _:
            return ''

    @property
    def to(self):
        """ *TO* list of the recipients

        :getter: Returns list of email id's the mail is/will be sent to
        :setter: Sets the list of email id's the mail will be sent to
        :type: List
        """
        return [x['emailAddress']['address']
                for x in self.json['toRecipients']]

    @to.setter
    def to(self, *recipients):
        self._set_recipients(*recipients, kind='to')

    @property
    def cc(self):
        """ *CC* list of the recipients

        :getter: Returns list of email id's the mail is/will be CC'ed to
        :setter: Sets the list of email id's the mail will be CC'ed to
        :type: List
        """
        return [x['emailAddress']['address']
                for x in self.json['ccRecipients']]

    @cc.setter
    def cc(self, *recipients):
        self._set_recipients(*recipients, kind='cc')

    @property
    def bcc(self):
        """ *BCC* list of the recipients

        :getter: Returns list of email id's the mail is/will be BCC'ed to
        :setter: Sets the list of email id's the mail will be BCC'ed to
        :type: List
        """
        return [x['emailAddress']['address']
                for x in self.json['bccRecipients']]

    @bcc.setter
    def bcc(self, *recipients):
        self._set_recipients(*recipients, kind='bcc')

    @property
    def subject(self):
        """ Subject of the email

        :getter: Returns the subject of this email message
        :setter: Sets the subject of this email message
        :type: str
        """
        return self.json['subject']

    @subject.setter
    def subject(self, value):
        self.json['subject'] = value

    @property
    def body(self):
        """ Body of the email

        :getter: Returns the text content of this email message
        :setter: Sets the text content of this email message
        :type: str
        """
        if 'content' in self.json['body']:
            return self.json['body']['content']
        else:
            log.debug("Fluent inbox getBody: No body content.")
            return ""

    @body.setter
    def body(self, value):
        self.json['body']['content'] = value
        self.json['body']['contentType'] = 'Text'

    def set_html_body(self, html_text=None):
        """ Sets the html text for body

        :param html_text: html content to set as body
        """
        self.json['body']['content'] = html_text
        self.json['body']['contentType'] = 'HTML'

    @property
    def has_attachments(self):
        """ Returns if the message has attachments or not

        :return: True or False
        :rtype: bool
        """
        return self.json.get('hasAttachments', len(self.attachments) > 0)

    def _set_recipients(self, recipients, kind='to'):
        """ Set the `TO` or `CC` or `BCC` recipients list.

            Each recipient can be either of the below:

            :type: dict - this must to be a dictionary formatted as such

                .. code-block:: json

                    {
                        "EmailAddress": {
                            "Address":"user@domain.com"
                        }
                    }
                with other options such as "Name" with address. but at minimum
                it must have this.
            :type: str - simple email address in form of "user@domain.com"
            :type: Contact - Contact object (Contact is part of this library)
            :type: Group - Group object, which is a list of contacts
             (Group is part of this library)

        :param recipients: List of recipients
        :param kind: 'to' or 'bcc' or 'cc'
        """
        kind = kind.lower()
        self.json[kind + 'Recipients'] = []

        if not isinstance(recipients, tuple):
            recipients = [recipients]

        log.debug('Setting recipients for {}: {}'.format(kind, recipients))
        for recipient in recipients:
            if isinstance(recipient, dict):
                self.json[kind + 'Recipients'].append(recipient)
            else:
                self.add_recipient(recipient, kind=kind)

    def add_recipient(self, address, name=None, kind="to"):
        """ Adds a recipient to the recipients list.

        :param address: the email address of the person you are sending to.
         Address can also be of type Contact or type Group.
        :param name: Name of the contact
        :param kind: 'to' or 'bcc' or 'cc'
        """
        if isinstance(address, Contact):
            self.json[kind + 'Recipients'].append(
                MicroDict({'emailAddress': {
                    'address': address.getFirstEmailAddress()}})
            )
        elif isinstance(address, Group):
            for contact in address.contacts:
                self.json[kind + 'Recipients'].append(
                    MicroDict({'emailAddress': {
                        'address': contact.getFirstEmailAddress()}})
                )
        elif isinstance(address, str):
            if name is None:
                name = address[:address.index('@')]
            self.json[kind + 'Recipients'].append(
                MicroDict({'emailAddress': {'address': address, 'name': name}}))
        else:
            raise RuntimeError('Unknown contact information {}'.format(address))

    def send(self, user_id=None, **kwargs):
        """ Send the email

        :param user_id: User id (email) if sending as other user
        :return: Success or Fail
        :rtype: bool
        """

        try:
            data = {'message': {}}
            data['message']['subject'] = self.json['subject']
            data['message']['body'] = self.json['body']
            data['message']['toRecipients'] = self.json['toRecipients']
            data['message']['ccRecipients'] = self.json['ccRecipients']
            data['message']['bccRecipients'] = self.json['bccRecipients']
            data['message']['attachments'] = [att.json for att in
                                              self.attachments]
            data = json.dumps(data)
        except RuntimeError as e:
            raise RuntimeError(
                'Error while trying to compile the json string to send: '
                '{0}'.format(
                    str(e)))

        if user_id:
            url = Message._get_url('send_as').format(user_id=user_id)
        else:
            url = Message._get_url('send')

        return _handle_request(url, method='POST', data=data,
                               verify=self.verify,
                               **kwargs)

    def reply(self, text, **kwargs):
        """ Reply to the mail

        :param text: content to add in the reply message
        :return: Success or Fail
        :rtype: bool
        """
        url = Message._get_url('reply').format(id=self.json['id'])
        data = {'comment': text}
        return _handle_request(url, method='POST', data=data,
                               verify=self.verify,
                               **kwargs)

    def reply_all(self, text, **kwargs):
        """ ReplyAll to the mail

        :param text: content to add in the reply message
        :return: Success or Fail
        :rtype: bool
        """
        url = Message._get_url('reply_all').format(id=self.json['id'])
        data = {'comment': text}
        return _handle_request(url, method='POST', data=data,
                               verify=self.verify,
                               **kwargs)

    def fetch_attachments(self, **kwargs):
        """ Downloads the attachments to local cache

        :return: no. of attachments
        :rtype: int
        """
        if not self.has_attachments:
            log.debug('Message has no attachments, skipping out early.')
            return False

        url = Message._get_url('attachments').format(
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

    def mark_as_read(self, **kwargs):
        """ Marks this message as read in the cloud

        :return: True or False (Success or Fail)
        :rtype: bool
        """

        data = MicroDict({"isRead": True})
        url = Message._get_url('update').format(
            message_id=self.json['id'])
        return _handle_request(url, method='PATCH', data=data,
                               verify=self.verify,
                               **kwargs)

    def move_to(self, folder_id, **kwargs):
        """ Move the message to a given folder

        :param folder_id: Folder ID to move this message to
        :return: True or False (Success or Fail)
        :rtype: bool
        """

        data = MicroDict({"destinationId": folder_id})

        url = Message._get_url('move').format(
            message_id=self.json['id'])
        return _handle_request(url, method='POST', data=data,
                               verify=self.verify,
                               **kwargs)

    def set_categories(self, *category_names, **kwargs):
        """ Set the category of the message

        :param category_names: category to add to the message
        :return: True or False (Success or Fail)
        :rtype: bool
        """
        data = MicroDict({"categories": list(category_names)})
        url = Message._get_url('update').format(
            message_id=self.json['id'])
        return _handle_request(url, method='PATCH', data=data,
                               verify=self.verify,
                               **kwargs)

    @deprecated('0.10.0', set_categories)
    def setCategory(self, category_name, **kwargs):
        self.set_categories(category_name, **kwargs)

    @deprecated('0.10.0', set_categories)
    def update_category(self, category_name, **kwargs):
        self.set_categories(category_name, **kwargs)

    @deprecated('0.10.0', fetch_attachments)
    def fetchAttachments(self, **kwargs):
        return self.fetch_attachments(**kwargs)

    @deprecated('0.10.0', send)
    def sendMessage(self, user_id=None, **kwargs):
        return self.send(user_id, **kwargs)

    @deprecated('0.10.0', mark_as_read)
    def markAsRead(self, **kwargs):
        return self.mark_as_read(**kwargs)

    @deprecated('0.10.0', move_to)
    def moveToFolder(self, folder_id, **kwargs):
        return self.move_to(folder_id, **kwargs)

    @deprecated('0.10.0', to, cc, bcc)
    def setRecipients(self, val, r_type="To"):
        return self._set_recipients(val, r_type)

    @deprecated('0.10.0', add_recipient)
    def addRecipient(self, address, name=None, r_type="To"):
        return self.add_recipient(address, name, r_type)

    @deprecated('0.10.0', sender)
    def getSender(self):
        return self.sender

    @deprecated('0.10.0', sender_email)
    def getSenderEmail(self):
        return self.sender_email

    @deprecated('0.10.0', sender_name)
    def getSenderName(self):
        return self.sender_name

    @deprecated('0.10.0', has_attachments)
    def hasAttachments(self):
        return self.has_attachments

    @deprecated('0.10.0', subject)
    def getSubject(self):
        return self.subject

    @deprecated('0.10.0', body)
    def getBody(self):
        return self.body

    @deprecated('0.10.0', subject)
    def setSubject(self, val):
        self.subject = val

    @deprecated('0.10.0', body)
    def setBody(self, val):
        self.body = val

    @deprecated('0.10.0', set_html_body)
    def setBodyHTML(self, val=None):
        self.set_html_body(val)


def _handle_request(*args, **kwargs):
    return_status = False
    if 'return_status' in kwargs:
        return_status = kwargs['return_status']
        del kwargs['return_status']

    try:
        response = Connection.get_response(*args, **kwargs)
    except RuntimeError as e:
        if return_status:
            return False, str(e)
        return False
    else:
        if response.status_code != 202:
            if return_status:
                return (False, '{}, {}'
                               ''.format(response.status_code,
                                         response.json(
                                             object_pairs_hook=MicroDict)[
                                             'error']['message']))
            return False
        else:
            if return_status:
                return True, None
            return True


# To the King!