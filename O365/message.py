import logging
import json
import base64
import iso8601
from pathlib import Path
from bs4 import BeautifulSoup as bs

from O365.connection import ApiComponent, AUTH_METHOD_BASIC

log = logging.getLogger(__name__)


class Recipient(object):
    """ A single Recipient"""

    def __init__(self, address=None, name=None):
            self.address = address or ''
            self.name = name or ''

    def __bool__(self):
        return bool(self.address)

    def __str__(self):
        if self.name:
            return '{} ({})'.format(self.name, self.address)
        else:
            return self.address

    def __repr__(self):
        return self.__str__()


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

    def __repr__(self):
        return self.__str__()

    def clear(self):
        self.recipients = []

    def add(self, recipients):
        """ Recipients must be a list of either address strings or tuples (name, address) or dictionary elements """

        if recipients:
            if isinstance(recipients, str):
                self.recipients.append(Recipient(address=recipients))
            elif isinstance(recipients, Recipient):
                self.recipients.append(recipients)
            elif isinstance(recipients, tuple):
                name, address = recipients
                if address:
                    self.recipients.append(Recipient(address=recipients, name=name))
            elif isinstance(recipients, list):
                for recipient in recipients:
                    self.add(recipient)
            else:
                raise ValueError('Recipients must be an address string, a name - address tuple  or a list')

    def remove(self, address):
        """ Remove an address or multiple addreses """
        recipients = []
        if isinstance(address, str):
            address = {address}  # set
        for recipient in self.recipients:
            if recipient.address not in address:
                recipients.append(recipient)
        self.recipients = recipients


class Attachment(ApiComponent):
    """
    Attachment class is the object for dealing with attachments in your messages. To add one to
    a message, simply append it to the message's attachment list (message.attachments).

    these are stored locally in base64 encoded strings. You can pass either a byte string or a
    base64 encoded string tot he appropriate set function to bring your attachment into the
    instance, which will of course need to happen before it could be mailed.
    """
    _endpoints = {'attach': '/messages/{id}/attachments'}

    def __init__(self, attachment=None, parent=None):
        """
        Creates a new attachment class, optionally from existing cloud data.

        :param attachment: attachment data (dict = cloud data, other = user data)
        :param parent: the parent Attachments
        """
        super().__init__(auth_method=getattr(parent, 'auth_method', None),
                         api_version=getattr(parent, 'api_version', None),
                         main_resource=getattr(parent, 'main_resource', None))

        self.attachment_id = None
        self.attachment = None
        self.name = None
        self.content = None
        self.on_disk = False

        if attachment:
            if isinstance(attachment, dict):
                if self._cloud_data_key in attachment:
                    # data from the cloud
                    attachment = attachment.get(self._cloud_data_key)
                    self.attachment_id = attachment.get(self._cc('id'), None)
                    self.name = attachment.get(self._cc('name'), None)
                    self.content = attachment.get(self._cc('contentBytes'), None)
                    self.on_disk = False
                else:
                    file_path = attachment.get('path', attachment.get('name'))
                    if file_path is None:
                        raise ValueError('Must provide a valid "path" or "name" for the attachment')
                    self.content = attachment.get('content')
                    self.on_disk = attachment.get('on_disk')
                    self.attachment_id = attachment.get('attachment_id')
                    self.attachment = Path(file_path) if self.on_disk else None
                    self.name = self.attachment.name if self.on_disk else attachment.get('name')

            elif isinstance(attachment, str):
                self.attachment = Path(attachment)
                self.name = self.attachment.name
            elif isinstance(attachment, (tuple, list)):
                file_path, custom_name = attachment
                self.attachment = Path(file_path)
                self.name = custom_name

            if self.content is None and self.attachment:
                with self.attachment.open('rb') as file:
                    self.content = base64.b64encode(file.read()).decode('utf-8')
                self.on_disk = True

    def _api_data(self):
        if self.auth_method == AUTH_METHOD_BASIC:
            data = {'@odata.type': '#Microsoft.OutlookServices.FileAttachment'}
        else:
            data = {'@odata.type': '#microsoft.graph.fileAttachment'}
        data[self._cc('contentBytes')] = self.content
        data[self._cc('name')] = self.name

        return data

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
                # message builds its own url
                url = message._build_url(self._endpoints.get('attach').format(id=message.message_id))
                try:
                    response = message.con.post(url, data=json.dumps(self._api_data()))
                except Exception as e:
                    log.error('Error attaching file to message')
                    return False

                log.debug('attached file to message')
                return response.status_code == 201
            else:
                message.attachments.add([{
                    'attachment_id': self.attachment_id,  # TODO: copy attachment id? or set to None?
                    'path': str(self.attachment) if self.attachment else None,
                    'name': self.name,
                    'content': self.content,
                    'on_disk': self.on_disk
                }])

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


class Attachments(ApiComponent):
    """ A Sequence of Attachments """

    _endpoints = {'attachments': '/messages/{id}/attachments'}

    def __init__(self, message, attachments=None):
        """ Attachments must be a list of path strings or dictionary elements """
        super().__init__(auth_method=message.auth_method, api_version=message.api_version, main_resource=message.main_resource)
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

    def _api_data(self):
        return [attachment._api_data() for attachment in self.attachments]

    def clear(self):
        self.attachments = []
        self.message.has_attachments = False

    def add(self, attachments):
        """ Attachments must be a list of path strings or dictionary elements """

        if attachments:
            if isinstance(attachments, (list, tuple)):
                # User provided attachments
                attachments_temp = [Attachment(attachment, parent=self) for attachment in attachments]
            elif isinstance(attachments, dict) and self._cloud_data_key in attachments:
                # Cloud downloaded attachments
                attachments_temp = [Attachment({self._cloud_data_key: attachment}, parent=self)
                                    for attachment in attachments.get(self._cloud_data_key, [])]
            else:
                raise ValueError('Attachments must be a list or tuple')

            self.attachments.extend(attachments_temp)
            self.message.has_attachments = True

    def download_attachments(self):
        """ Downloads this message attachments into memory. Need a call to save to save them on disk. """
        if not self.message.has_attachments:
            log.debug('message has no attachments, skipping out early.')
            return False

        if not self.message.message_id:
            raise RuntimeError('Attempt to download attachments of and unsaved message')

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

        # Everything received from the cloud must be passed with self._cloud_data_key
        self.add({self._cloud_data_key: attachments})

        return True


class MixinHandleRecipients(object):

    def _recipients_from_cloud(self, recipients):
        """ Transform a recipient from cloud data to object data """
        recipients_data = []
        for recipient in recipients:
            recipients_data.append(self._recipient_from_cloud(recipient))
        return Recipients(recipients_data)

    def _recipient_from_cloud(self, recipient):
        """ Transform a recipient from cloud data to object data """

        cc = getattr(self, '_cc')
        if recipient:
            recipient = recipient.get(cc('emailAddress'), {})
            address = recipient.get(cc('address'), '')
            name = recipient.get(cc('name'), '')
            return Recipient(address=address, name=name)
        else:
            return Recipient()

    def _recipient_to_cloud(self, recipient):
        """ Transforms a Recipient object to a cloud dict """
        data = None
        if recipient:
            cc = getattr(self, '_cc')
            data = {cc('emailAddress'): {cc('address'): recipient.address}}
            if recipient.name:
                data[cc('emailAddress')][cc('name')] = recipient.name
        return data


class Message(ApiComponent, MixinHandleRecipients):
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

    _importance_options = {'normal': 'normal', 'low': 'low', 'high': 'high'}

    draft_url = 'https://outlook.office365.com/api/v1.0/me/folders/{folder_id}/messages'  # TODO: drafts?

    def __init__(self, *, parent=None, con=None, **kwargs):
        """
        Makes a new message wrapper for sending and receiving messages.

        :param parent: the parent object
        :param con: the id of this message if it exists
        """
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # get the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None)
        if main_resource is None:
            main_resource = getattr(parent, 'main_resource', None) if parent else None
        super().__init__(auth_method=self.con.auth_method, api_version=self.con.api_version,
                         main_resource=main_resource)

        download_attachments = kwargs.get('download_attachments')

        cloud_data = kwargs.get(self._cloud_data_key, {})
        cc = self._cc  # alias to shorten the code

        self.message_id = cloud_data.get(cc('id'), None)
        self.created = cloud_data.get(cc('createdDateTime'), None)
        self.received = cloud_data.get(cc('receivedDateTime'), None)
        self.sent = cloud_data.get(cc('sentDateTime'), None)

        # parsing dates from iso8601 format to datetimes UTC. TODO: Convert UTC to Local Time
        self.created = iso8601.parse_date(self.created) if self.created else None
        self.received = iso8601.parse_date(self.received) if self.received else None
        self.sent = iso8601.parse_date(self.sent) if self.sent else None

        self.attachments = Attachments(message=self, attachments=[])
        self.has_attachments = cloud_data.get(cc('hasAttachments'), 0)
        if self.has_attachments and download_attachments:
            self.attachments.download_attachments()
        self.subject = cloud_data.get(cc('subject'), '')
        body = cloud_data.get(cc('body'), {})
        self.body = body.get(cc('content'), '')
        self.sender = self._recipient_from_cloud(cloud_data.get(cc('from'), None))
        self.to = self._recipients_from_cloud(cloud_data.get(cc('toRecipients'), []))
        self.cc = self._recipients_from_cloud(cloud_data.get(cc('ccRecipients'), []))
        self.bcc = self._recipients_from_cloud(cloud_data.get(cc('bccRecipients'), []))
        self.categories = cloud_data.get(cc('categories'), [])
        self.importance = self._importance_options.get(cloud_data.get(cc('importance'), 'normal'), 'normal')  # only allow valid importance
        self.is_read = cloud_data.get(cc('isRead'), None)
        self.is_draft = cloud_data.get(cc('isDraft'), None)
        self.conversation_id = cloud_data.get(cc('conversationId'), None)
        self.folder_id = cloud_data.get(cc('parentFolderId'), None)

    def send(self, save_to_sent_folder=True):
        """ Sends this message. """

        if self.message_id and not self.is_draft:
            return RuntimeError('Not possible to send a message that is not new or a draft. Use Reply or Forward instead.')
        cc = self._cc  # alias to shorten the code
        data = {
            cc('message'): {
                cc('subject'): self.subject,
                cc('body'): {
                    cc('contentType'): 'HTML',
                    cc('content'): self.body},
                cc('toRecipients'): [self._recipient_to_cloud(recipient) for recipient in self.to],
                cc('ccRecipients'): [self._recipient_to_cloud(recipient) for recipient in self.cc],
                cc('bccRecipients'): [self._recipient_to_cloud(recipient) for recipient in self.bcc],
                cc('attachments'): self.attachments._api_data()
            },
        }
        if save_to_sent_folder is False:
            data[cc('saveToSentItems')] = False

        if self.sender and self.sender.address:
            data[cc('message')][cc('from')] = self._recipient_to_cloud(self.sender)

        url = self._build_url(self._endpoints.get('send'))
        try:
            response = self.con.post(url, data=json.dumps(data))
        except Exception as e:
            log.error('Message could not be send error: {}'.format(str(e)))
            return False

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

        data = {self._cc('isRead'): True}

        url = self._build_url(self._endpoints.get('message').format(id=self.message_id))
        try:
            response = self.con.patch(url, data=json.dumps(data))
        except Exception as e:
            log.error('Message could not be marked as read. Error: {}'.format(str(e)))
            return False

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

        data = {self._cc('destinationId'): folder_id}
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

        if self.message_id is None:
            raise RuntimeError('Attempting to update an unsaved Message')

        data = {self._cc('categories'): categories}

        url = self._build_url(self._endpoints.get('message').format(id=self.message_id))
        try:
            response = self.con.patch(url, data=json.dumps(data))
            log.debug('changed categories on message id: {}'.format(self.message_id))
        except Exception as e:
            log.error('Categories not updated. Error: {}'.format(str(e)))
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
