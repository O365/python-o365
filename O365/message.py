import logging
import json
import base64
import iso8601
from pathlib import Path
from bs4 import BeautifulSoup as bs

from O365.connection import BaseApi

log = logging.getLogger(__name__)


class Recipient(object):
    """ A single Recipient"""

    def __init__(self, address=None, name=None, recipient=None):
        assert address is None or recipient is None, 'Provide a recipient or and address'
        if recipient is not None:
            # recipient from the cloud
            recipient = recipient.get('emailAddress')
            self.address = recipient.get('address', '')
            self.name = recipient.get('name', '')
        else:
            self.address = address or ''
            self.name = name or ''

    def _to_data(self):
        if self.address:
            data = {'emailAddress': {'address': self.address}}
            if self.name:
                data['emailAddress']['name'] = self.name
            return data
        else:
            return None

    def __bool__(self):
        return bool(self.address)

    def __str__(self):
        if self.name:
            return '{} ({})'.format(self.name, self.address)
        else:
            return self.address


class Recipients(object):
    """ A Sequence of Recipients """

    def __init__(self, recipients=None):
        """ Recipients must be a list of either address strings or tuples (name, address) or dictionary elements """

        self.recipients = []
        if recipients:
            self.add(recipients)

    def __iter__(self):
        return iter(self.recipients)

    def __len__(self):
        return len(self.recipients)

    def __str__(self):
        return 'Recipients count: {}'.format(len(self.recipients))

    def _to_data(self):
        return [recipient._to_data() for recipient in self.recipients]

    def clear(self):
        self.recipients = []

    def add(self, recipients):
        """ Recipients must be a list of either address strings or tuples (name, address) or dictionary elements """

        if recipients:
            if not isinstance(recipients, (list, tuple)):
                raise ValueError('Recipients must be a list or tuple')

            recipients_temp = []
            # Check first element and assume all elements are the same

            if isinstance(recipients[0], str):
                recipients_temp = [Recipient(address=address) for address in recipients]
            elif isinstance(recipients[0], tuple):
                recipients_temp = [Recipient(name=name, address=address) for name, address in recipients]
            elif isinstance(recipients[0], dict):
                recipients_temp = [Recipient(recipient=recipient) for recipient in recipients]

            self.recipients.extend(recipients_temp)

    def remove(self, address):
        """ Remove an address or multiple addreses """
        recipients = []
        if isinstance(address, str):
            address = {address}  # set
        for recipient in self.recipients:
            if recipient.address not in address:
                recipients.append(recipient)
        self.recipients = recipients


class Attachment(BaseApi):
    """
    Attachment class is the object for dealing with attachments in your messages. To add one to
    a message, simply append it to the message's attachment list (message.attachments).

    these are stored locally in base64 encoded strings. You can pass either a byte string or a
    base64 encoded string tot he appropriate set function to bring your attachment into the
    instance, which will of course need to happen before it could be mailed.
    """
    _endpoints = {
        'attach': '/messages/{id}/attachments'
    }

    def __init__(self, attachment=None, **kwargs):
        """
        Creates a new attachment class, optionally from existing JSON.

        Keyword Arguments:
        json -- json to create the class from. this is mostly used by the class internally when an
        attachment is downloaded from the cloud. If you want to create a new attachment, leave this
        empty. (default = None)
        path -- a string giving the path to a file. it is cross platform as long as you break
        windows convention and use '/' instead of '\'. Passing this argument will tend to
        the rest of the process of making an attachment. Note that passing in json as well
        will cause this argument to be ignored.
        """
        super().__init__(**kwargs)

        if attachment:
            if isinstance(attachment, str):
                self.attachment = Path(attachment)
                self.name = self.attachment.name
                with self.attachment.open('rb') as file:
                    # str(base64.encodebytes(file.read()), 'utf-8') ?
                    self.content = base64.b64encode(file.read()).decode('utf-8')
                self.on_disk = True
            elif isinstance(attachment, (tuple, list)):
                file_path, custom_name = attachment
                self.attachment = Path(file_path)
                self.name = custom_name
                with self.attachment.open('rb') as file:
                    self.content = base64.b64encode(file.read()).decode('utf-8')
                self.on_disk = True
            elif isinstance(attachment, dict):
                # from the cloud
                self.attachment = None
                self.name = attachment.get('name', None)
                self.content = attachment.get('contentBytes', None)
                self.on_disk = False
        else:
            self.attachment = None
            self.name = None
            self.content = None
            self.on_disk = False

    def _to_data(self):
        return {'@odata.type': '#microsoft.graph.fileAttachment', 'contentBytes': self.content, 'name': self.name}

    def save(self, location=None, custom_name=None):
        """  Save the attachment locally to disk.
        :param location: path string to where the file is to be saved.
        :param custom_name: a custom name to be saved as
        """
        location = Path(location or '')
        if not location.exists():
            log.debug('the location provided does not exist')
            return False
        try:
            path = location / (custom_name or self.name)
            with path.open('wb') as file:
                file.write(base64.b64decode(self.content))
            self.attachment = path
            self.on_disk = True
            log.debug('file saved locally.')
        except Exception as e:
            log.debug('file failed to be saved: %s', str(e))
            return False
        return True

    def attach(self, message, on_cloud=False):
        """ Attach a file to an existing message """
        if message:
            if on_cloud:
                if not message.message_id:
                    raise RuntimeError('A valid message id is needed in order to attach a file')
                url = self._build_url(self._endpoints.get('attach').format(id=message.message_id))
                response = message.con.post(url, data=json.dumps(self._to_data()))
                log.debug('attached file to message')
                return response.status_code == 201
            else:
                message.attachments.add([self._to_data()])

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


class Attachments(BaseApi):
    """ A Sequence of Attachments """

    _endpoints = {'attachments': '/messages/{id}/attachments'}

    def __init__(self, message, attachments=None, **kwargs):
        """ Attachments must be a list of path strings or dictionary elements """
        super().__init__(**kwargs)
        self.message = message
        self.attachments = []
        if attachments:
            self.add(attachments)

    def __iter__(self):
        return iter(self.attachments)

    def __len__(self):
        return len(self.attachments)

    def __str__(self):
        attachments = len(self.attachments)
        if self.message.has_attachments and attachments == 0:
            return 'Message Has Attachments: # Download attachments'
        else:
            return 'Message Attachments: {}'.format(attachments)

    def _to_data(self):
        return [attachment._to_data() for attachment in self.attachments]

    def clear(self):
        self.attachments = []

    def add(self, attachments):
        """ Attachments must be a list of path strings or dictionary elements """

        if attachments:
            if not isinstance(attachments, (list, tuple)):
                raise ValueError('Attachments must be a list or tuple')

            attachments_temp = []
            # Check first element and assume all elements are the same

            api_data = dict(api_version=self.api_version, main_resource=self.main_resource)
            attachments_temp = [Attachment(attachment, **api_data) for attachment in attachments]

            self.attachments.extend(attachments_temp)

    def download_attachments(self):
        """ Downloads this message attachments into memory. Need a call to save to save them on disk. """
        if not self.message.has_attachments:
            log.debug('message has no attachments, skipping out early.')
            return False

        url = self._build_url(self._endpoints.get('attachments').format(id=self.message.message_id))

        try:
            response = self.message.con.get(url)
        except Exception as e:
            log.error('Error downloading attachments for message id: {}'.format(self.message.message_id))
            return False

        if response.status_code != 200:
            return False
        log.debug('successfully downloaded attachments for message id: {}'.format(self.message.message_id))

        attachments = response.json().get('value', [])

        self.add(attachments)

        return True


class Message(BaseApi):
    """Management of the process of sending, receiving, reading, and editing emails.

    Note: the get and set methods are technically superflous. You can get more through control over
    a message you are trying to craft throught he use of editing the message.json, but these
    methods provide an easy way if you don't need all the power and would like the ease.
    """

    _endpoints = {
        'send': '/sendMail',
        'message': '/messages/{id}',
        'move': 'messages/{id}/move',
        'attachments': '/messages/{id}/attachments'
    }

    send_url = 'https://outlook.office365.com/api/v1.0/me/sendmail'
    draft_url = 'https://outlook.office365.com/api/v1.0/me/folders/{folder_id}/messages'

    def __init__(self, con, **kwargs):
        """
        Makes a new message wrapper for sending and receiving messages.

        :param message_id: the id of this message if it exists
        """
        super().__init__(**kwargs)
        self.con = con
        self.message_id = kwargs.get('id', None)
        self.created = kwargs.get('createdDateTime', None)
        self.received = kwargs.get('receivedDateTime', None)
        self.sent = kwargs.get('sentDateTime', None)

        # parsing dates from iso8601 format to datetimes UTC. TODO: Convert UTC to Local Time
        self.created = iso8601.parse_date(self.created) if self.created else None
        self.received = iso8601.parse_date(self.received) if self.received else None
        self.sent = iso8601.parse_date(self.sent) if self.sent else None

        self.has_attachments = kwargs.get('hasAttachments', False)
        self.attachments = Attachments(message=self, attachments=kwargs.get('attachments', []), **kwargs)
        if self.has_attachments and kwargs.get('download_attachments'):
            self.attachments.download_attachments()
        self.subject = kwargs.get('subject', '')
        self.body = kwargs.get('body', {}).get('content', '')
        self.sender = Recipient(recipient=kwargs.get('from', None))
        self.to = Recipients(kwargs.get('toRecipients', []))
        self.cc = Recipients(kwargs.get('ccRecipients', []))
        self.bcc = Recipients(kwargs.get('bccRecipients', []))
        self.categories = kwargs.get('categories', [])
        self.importance = kwargs.get('importance', 'normal')
        self.is_read = kwargs.get('isRead', None)
        self.is_draft = kwargs.get('isDraft', None)
        self.conversation_id = kwargs.get('conversationId', None)
        self.folder_id = kwargs.get('parentFolderId', None)

    def send(self):
        """ Sends this message. """

        if self.message_id and not self.is_draft:
            return RuntimeError('Not possible to send a message that is not new or a draft. Use Reply or Forward instead.')
        data = {
            'message': {
                'subject': self.subject,
                'body': {
                    'contentType': 'HTML',
                    'content': self.body},
                'toRecipients': self.to._to_data(),
                'ccRecipients': self.cc._to_data(),
                'bccRecipients': self.bcc._to_data(),
                'attachments': self.attachments._to_data()
            },
        }
        if self.sender:
            data['message']['from'] = self.sender._to_data()

        url = self._build_url(self._endpoints.get('send'))

        response = self.con.post(url, data=json.dumps(data))
        log.debug('response from server for sending message:' + str(response))
        log.debug('response body: {}'.format(response.text))

        return response.status_code == 202

    def delete(self):
        """ Deletes a stored message """
        if self.message_id is None:
            raise RuntimeError('Attempting to delete an unsaved Message')

        url = self._build_url(self._endpoints.get('message').format(id=self.message_id))

        log.debug('deleting message id: {id}'.format(id=self.message_id))
        response = self.con.delete(url)
        log.debug('response from server for deleting message:' + str(response))

        return response.status_code == 204

    def mark_as_read(self):
        """ Marks this message as read in the cloud."""
        if self.message_id is None:
            raise RuntimeError('Attempting to mark as read an unsaved Message')

        data = {'isRead': True}

        url = self._build_url(self._endpoints.get('message').format(id=self.message_id))
        response = self.con.patch(url, data=json.dumps(data))

        return response.status_code == 200

    def move(self, folder_id):
        """
        Move the message to a given folder

        :param folder_id: Folder id or Well-known name to move this message to
        :returns: True on success
        """
        if self.message_id is None:
            raise RuntimeError('Attempting to move an unsaved Message')

        url = self._build_url(self._endpoints.get('move').format(id=self.message_id))

        data = {'destinationId': folder_id}
        try:
            response = self.con.post(url, data=json.dumps(data))
            log.debug('message moved to folder: {}'.format(folder_id))
        except Exception as e:
            log.error('message (id: {}) could not be moved to folder id: {}'.format(self.message_id, folder_id))
            return False

        return response.status_code == 201

    def update_category(self, categories):
        """ Update this message categories """
        if not isinstance(categories, (list, tuple)):
            raise ValueError('Categories must be a list or tuple')

        data = {'categories': categories}

        url = self._build_url(self._endpoints.get('message').format(id=self.message_id))
        try:
            response = self.con.patch(url, data=json.dumps(data))
            log.debug('changed categories on message id: {}'.format(self.message_id))
        except:
            return False

        return response.status_code == 200

    def get_body_text(self):
        """ Parse the body html and returns the body text using bs4 """
        try:
            soup = bs(self.body, 'html.parser')
        except Exception as e:
            return self.body
        else:
            return soup.body.text

    def __str__(self):
        return 'subject: {}'.format(self.subject)

    def __repr__(self):
        return self.__str__()




