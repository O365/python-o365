import logging
import datetime as dt
from dateutil.parser import parse
import pytz
from bs4 import BeautifulSoup as bs

from O365.utils import OutlookWellKnowFolderNames, ApiComponent, BaseAttachments, BaseAttachment, AttachableMixin, ImportanceLevel, TrackerSet

log = logging.getLogger(__name__)


class Recipient:
    """ A single Recipient """

    def __init__(self, address=None, name=None, parent=None, field=None):
        self._address = address or ''
        self._name = name or ''
        self._parent = parent
        self._field = field

    def __bool__(self):
        return bool(self.address)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if self.name:
            return '{} ({})'.format(self.name, self.address)
        else:
            return self.address

    def _track_changes(self):
        """ Update the track_changes on the parent to reflect a needed update on this field """
        if self._field and getattr(self._parent, '_track_changes', None) is not None:
            self._parent._track_changes.add(self._field)

    @property
    def address(self):
        return self._address

    @address.setter
    def address(self, value):
        self._address = value
        self._track_changes()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._track_changes()


class Recipients:
    """ A Sequence of Recipients """

    def __init__(self, recipients=None, parent=None, field=None):
        """ Recipients must be a list of either address strings or tuples (name, address) or dictionary elements """
        self._parent = parent
        self._field = field
        self._recipients = []
        self.untrack = True
        if recipients:
            self.add(recipients)
        self.untrack = False

    def __iter__(self):
        return iter(self._recipients)

    def __getitem__(self, key):
        return self._recipients[key]

    def __contains__(self, item):
        return item in {recipient.address for recipient in self._recipients}

    def __bool__(self):
        return bool(len(self._recipients))

    def __len__(self):
        return len(self._recipients)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Recipients count: {}'.format(len(self._recipients))

    def _track_changes(self):
        """ Update the track_changes on the parent to reflect a needed update on this field """
        if self._field and getattr(self._parent, '_track_changes', None) is not None and self.untrack is False:
            self._parent._track_changes.add(self._field)

    def clear(self):
        self._recipients = []
        self._track_changes()

    def add(self, recipients):
        """ Recipients must be a list of either address strings or tuples (name, address) or dictionary elements """

        if recipients:
            if isinstance(recipients, str):
                self._recipients.append(Recipient(address=recipients, parent=self._parent, field=self._field))
            elif isinstance(recipients, Recipient):
                self._recipients.append(recipients)
            elif isinstance(recipients, tuple):
                name, address = recipients
                if address:
                    self._recipients.append(Recipient(address=address, name=name, parent=self._parent, field=self._field))
            elif isinstance(recipients, list):
                for recipient in recipients:
                    self.add(recipient)
            else:
                raise ValueError('Recipients must be an address string, a'
                                 ' Recipient instance, a (name, address) tuple or a list')
            self._track_changes()

    def remove(self, address):
        """ Remove an address or multiple addreses """
        recipients = []
        if isinstance(address, str):
            address = {address}  # set
        elif isinstance(address, (list, tuple)):
            address = set(address)

        for recipient in self._recipients:
            if recipient.address not in address:
                recipients.append(recipient)
        if len(recipients) != len(self._recipients):
            self._track_changes()
        self._recipients = recipients

    def get_first_recipient_with_address(self):
        """ Returns the first recipient found with a non blank address"""
        recipients_with_address = [recipient for recipient in self._recipients if recipient.address]
        if recipients_with_address:
            return recipients_with_address[0]
        else:
            return None


class MessageAttachment(BaseAttachment):

    _endpoints = {
        'attach': '/messages/{id}/attachments',
        'attachment': '/messages/{id}/attachments/{ida}'
    }


class MessageAttachments(BaseAttachments):

    _endpoints = {
        'attachments': '/messages/{id}/attachments',
        'attachment': '/messages/{id}/attachments/{ida}'
    }
    _attachment_constructor = MessageAttachment


class HandleRecipientsMixin:

    def _recipients_from_cloud(self, recipients, field=None):
        """ Transform a recipient from cloud data to object data """
        recipients_data = []
        for recipient in recipients:
            recipients_data.append(self._recipient_from_cloud(recipient, field=field))
        return Recipients(recipients_data, parent=self, field=field)

    def _recipient_from_cloud(self, recipient, field=None):
        """ Transform a recipient from cloud data to object data """

        if recipient:
            recipient = recipient.get(self._cc('emailAddress'), recipient if isinstance(recipient, dict) else {})
            address = recipient.get(self._cc('address'), '')
            name = recipient.get(self._cc('name'), '')
            return Recipient(address=address, name=name, parent=self, field=field)
        else:
            return Recipient()

    def _recipient_to_cloud(self, recipient):
        """ Transforms a Recipient object to a cloud dict """
        data = None
        if recipient:
            data = {self._cc('emailAddress'): {self._cc('address'): recipient.address}}
            if recipient.name:
                data[self._cc('emailAddress')][self._cc('name')] = recipient.name
        return data


class Message(ApiComponent, AttachableMixin, HandleRecipientsMixin):
    """ Management of the process of sending, receiving, reading, and editing emails. """

    _endpoints = {
        'create_draft': '/messages',
        'create_draft_folder': '/mailFolders/{id}/messages',
        'send_mail': '/sendMail',
        'send_draft': '/messages/{id}/send',
        'get_message': '/messages/{id}',
        'move_message': '/messages/{id}/move',
        'copy_message': '/messages/{id}/copy',
        'create_reply': '/messages/{id}/createReply',
        'create_reply_all': '/messages/{id}/createReplyAll',
        'forward_message': '/messages/{id}/createForward'
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """
        Makes a new message wrapper for sending and receiving messages.

        :param parent: the parent object
        :param con: the id of this message if it exists
        """
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource,
                         attachment_name_property='subject', attachment_type='message_type')

        download_attachments = kwargs.get('download_attachments')

        cloud_data = kwargs.get(self._cloud_data_key, {})
        cc = self._cc  # alias to shorten the code

        self._track_changes = TrackerSet(casing=cc)  # internal to know which properties need to be updated on the server
        self.object_id = cloud_data.get(cc('id'), None)

        self.__created = cloud_data.get(cc('createdDateTime'), None)
        self.__modified = cloud_data.get(cc('lastModifiedDateTime'), None)
        self.__received = cloud_data.get(cc('receivedDateTime'), None)
        self.__sent = cloud_data.get(cc('sentDateTime'), None)

        local_tz = self.protocol.timezone
        self.__created = parse(self.__created).astimezone(local_tz) if self.__created else None
        self.__modified = parse(self.__modified).astimezone(local_tz) if self.__modified else None
        self.__received = parse(self.__received).astimezone(local_tz) if self.__received else None
        self.__sent = parse(self.__sent).astimezone(local_tz) if self.__sent else None

        self.__attachments = MessageAttachments(parent=self, attachments=[])
        self.has_attachments = cloud_data.get(cc('hasAttachments'), 0)
        if self.has_attachments and download_attachments:
            self.attachments.download_attachments()
        self.__subject = cloud_data.get(cc('subject'), '')
        body = cloud_data.get(cc('body'), {})
        self.__body = body.get(cc('content'), '')
        self.body_type = body.get(cc('contentType'), 'HTML')  # default to HTML for new messages
        self.__sender = self._recipient_from_cloud(cloud_data.get(cc('from'), None), field='from')
        self.__to = self._recipients_from_cloud(cloud_data.get(cc('toRecipients'), []), field='toRecipients')
        self.__cc = self._recipients_from_cloud(cloud_data.get(cc('ccRecipients'), []), field='ccRecipients')
        self.__bcc = self._recipients_from_cloud(cloud_data.get(cc('bccRecipients'), []), field='bccRecipients')
        self.__reply_to = self._recipients_from_cloud(cloud_data.get(cc('replyTo'), []), field='replyTo')
        self.__categories = cloud_data.get(cc('categories'), [])
        self.__importance = ImportanceLevel((cloud_data.get(cc('importance'), 'normal') or 'normal').lower())  # lower because of office365 v1.0
        self.__is_read = cloud_data.get(cc('isRead'), None)
        self.__is_draft = cloud_data.get(cc('isDraft'), kwargs.get('is_draft', True))  # a message is a draft by default
        self.conversation_id = cloud_data.get(cc('conversationId'), None)
        self.folder_id = cloud_data.get(cc('parentFolderId'), None)

    def _clear_tracker(self):
        # reset the tracked changes. Usually after a server update
        self._track_changes = TrackerSet(casing=self._cc)

    @property
    def is_read(self):
        return self.__is_read

    @is_read.setter
    def is_read(self, value):
        self.__is_read = value
        self._track_changes.add('isRead')

    @property
    def is_draft(self):
        return self.__is_draft

    @property
    def subject(self):
        return self.__subject

    @subject.setter
    def subject(self, value):
        self.__subject = value
        self._track_changes.add('subject')

    @property
    def body(self):
        return self.__body

    @body.setter
    def body(self, value):
        if self.__body:
            if not value:
                self.__body = ''
            else:
                soup = bs(self.__body, 'html.parser')
                soup.body.insert(0, bs(value, 'html.parser'))
                self.__body = str(soup)
        else:
            self.__body = value
        self._track_changes.add('body')

    @property
    def created(self):
        return self.__created

    @property
    def modified(self):
        return self.__modified

    @property
    def received(self):
        return self.__received

    @property
    def sent(self):
        return self.__sent

    @property
    def attachments(self):
        """ Just to avoid api misuse by assigning to 'attachments' """
        return self.__attachments

    @property
    def sender(self):
        """ sender is a property to force to be allways a Recipient class """
        return self.__sender

    @sender.setter
    def sender(self, value):
        """ sender is a property to force to be allways a Recipient class """
        if isinstance(value, Recipient):
            if value._parent is None:
                value._parent = self
                value._field = 'from'
            self.__sender = value
        elif isinstance(value, str):
            self.__sender.address = value
            self.__sender.name = ''
        else:
            raise ValueError('sender must be an address string or a Recipient object')
        self._track_changes.add('from')

    @property
    def to(self):
        """ Just to avoid api misuse by assigning to 'to' """
        return self.__to

    @property
    def cc(self):
        """ Just to avoid api misuse by assigning to 'cc' """
        return self.__cc

    @property
    def bcc(self):
        """ Just to avoid api misuse by assigning to 'bcc' """
        return self.__bcc

    @property
    def reply_to(self):
        """ Just to avoid api misuse by assigning to 'reply_to' """
        return self.__reply_to

    @property
    def categories(self):
        return self.__categories

    @categories.setter
    def categories(self, value):
        if isinstance(value, list):
            self.__categories = value
        elif isinstance(value, str):
            self.__categories = [value]
        elif isinstance(value, tuple):
            self.__categories = list(value)
        else:
            raise ValueError('categories must be a list')
        self._track_changes.add('categories')

    @property
    def importance(self):
        return self.__importance

    @importance.setter
    def importance(self, value):
        self.__importance = value if isinstance(value, ImportanceLevel) else ImportanceLevel(value.lower())
        self._track_changes.add('importance')

    def to_api_data(self, restrict_keys=None):
        """ Returns a dict representation of this message prepared to be send to the cloud
        :param restrict_keys: a set of keys to restrict the returned data to.
        """

        cc = self._cc  # alias to shorten the code

        message = {
            cc('subject'): self.subject,
            cc('body'): {
                cc('contentType'): self.body_type,
                cc('content'): self.body},
            cc('importance'): self.importance.value
        }

        if self.to:
            message[cc('toRecipients')] = [self._recipient_to_cloud(recipient) for recipient in self.to]
        if self.cc:
            message[cc('ccRecipients')] = [self._recipient_to_cloud(recipient) for recipient in self.cc]
        if self.bcc:
            message[cc('bccRecipients')] = [self._recipient_to_cloud(recipient) for recipient in self.bcc]
        if self.reply_to:
            message[cc('replyTo')] = [self._recipient_to_cloud(recipient) for recipient in self.reply_to]
        if self.attachments:
            message[cc('attachments')] = self.attachments.to_api_data()
        if self.sender and self.sender.address:
            message[cc('from')] = self._recipient_to_cloud(self.sender)

        if self.object_id and not self.__is_draft:
            # return the whole signature of this message

            message[cc('id')] = self.object_id
            message[cc('createdDateTime')] = self.created.astimezone(pytz.utc).isoformat()
            message[cc('receivedDateTime')] = self.received.astimezone(pytz.utc).isoformat()
            message[cc('sentDateTime')] = self.sent.astimezone(pytz.utc).isoformat()
            message[cc('hasAttachments')] = len(self.attachments) > 0
            message[cc('categories')] = self.categories
            message[cc('isRead')] = self.is_read
            message[cc('isDraft')] = self.__is_draft
            message[cc('conversationId')] = self.conversation_id
            message[cc('parentFolderId')] = self.folder_id  # this property does not form part of the message itself

        if restrict_keys:
            for key in list(message.keys()):
                if key not in restrict_keys:
                    del message[key]

        return message

    def send(self, save_to_sent_folder=True):
        """ Sends this message. """

        if self.object_id and not self.__is_draft:
            return RuntimeError('Not possible to send a message that is not new or a draft. Use Reply or Forward instead.')

        if self.__is_draft and self.object_id:
            url = self.build_url(self._endpoints.get('send_draft').format(id=self.object_id))
            data = None
        else:
            url = self.build_url(self._endpoints.get('send_mail'))
            data = {self._cc('message'): self.to_api_data()}
            if save_to_sent_folder is False:
                data[self._cc('saveToSentItems')] = False

        response = self.con.post(url, data=data)
        if not response:  # response evaluates to false if 4XX or 5XX status codes are returned
            return False

        self.object_id = 'sent_message' if not self.object_id else self.object_id
        self.__is_draft = False

        return True

    def reply(self, to_all=True):
        """
        Creates a new message that is a reply to this message.
        :param to_all: replies to all the recipients instead to just the sender
        """
        if not self.object_id or self.__is_draft:
            raise RuntimeError("Can't reply to this message")

        if to_all:
            url = self.build_url(self._endpoints.get('create_reply_all').format(id=self.object_id))
        else:
            url = self.build_url(self._endpoints.get('create_reply').format(id=self.object_id))

        response = self.con.post(url)
        if not response:
            return None

        message = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self.__class__(parent=self, **{self._cloud_data_key: message})

    def forward(self):
        """
        Creates a new message that is a forward of this message.
        """
        if not self.object_id or self.__is_draft:
            raise RuntimeError("Can't forward this message")

        url = self.build_url(self._endpoints.get('forward_message').format(id=self.object_id))

        response = self.con.post(url)
        if not response:
            return None

        message = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self.__class__(parent=self, **{self._cloud_data_key: message})

    def delete(self):
        """ Deletes a stored message """
        if self.object_id is None:
            raise RuntimeError('Attempting to delete an unsaved Message')

        url = self.build_url(self._endpoints.get('get_message').format(id=self.object_id))

        response = self.con.delete(url)

        return bool(response)

    def mark_as_read(self):
        """ Marks this message as read in the cloud."""
        if self.object_id is None or self.__is_draft:
            raise RuntimeError('Attempting to mark as read an unsaved Message')

        data = {self._cc('isRead'): True}

        url = self.build_url(self._endpoints.get('get_message').format(id=self.object_id))

        response = self.con.patch(url, data=data)
        if not response:
            return False

        self.__is_read = True

        return True

    def move(self, folder):
        """
        Move the message to a given folder

        :param folder: Folder object or Folder id or Well-known name to move this message to
        :returns: True on success
        """
        if self.object_id is None:
            raise RuntimeError('Attempting to move an unsaved Message')

        url = self.build_url(self._endpoints.get('move_message').format(id=self.object_id))

        if isinstance(folder, str):
            folder_id = folder
        else:
            folder_id = getattr(folder, 'folder_id', None)

        if not folder_id:
            raise RuntimeError('Must Provide a valid folder_id')

        data = {self._cc('destinationId'): folder_id}

        response = self.con.post(url, data=data)
        if not response:
            return False

        self.folder_id = folder_id

        return True

    def copy(self, folder):
        """
        Copy the message to a given folder

        :param folder: Folder object or Folder id or Well-known name to move this message to
        :returns: the copied message
        """
        if self.object_id is None:
            raise RuntimeError('Attempting to move an unsaved Message')

        url = self.build_url(self._endpoints.get('copy_message').format(id=self.object_id))

        if isinstance(folder, str):
            folder_id = folder
        else:
            folder_id = getattr(folder, 'folder_id', None)

        if not folder_id:
            raise RuntimeError('Must Provide a valid folder_id')

        data = {self._cc('destinationId'): folder_id}

        response = self.con.post(url, data=data)
        if not response:
            return None

        message = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self.__class__(parent=self, **{self._cloud_data_key: message})

    def save_draft(self, target_folder=OutlookWellKnowFolderNames.DRAFTS):
        """ Save this message as a draft on the cloud """

        if self.object_id:
            # update message. Attachments are NOT included nor saved.
            if not self.__is_draft:
                raise RuntimeError('Only draft messages can be updated')
            if not self._track_changes:
                return True  # there's nothing to update
            url = self.build_url(self._endpoints.get('get_message').format(id=self.object_id))
            method = self.con.patch
            data = self.to_api_data(restrict_keys=self._track_changes)

            data.pop(self._cc('attachments'), None)  # attachments are handled by the next method call
            self.attachments._update_attachments_to_cloud()
        else:
            # new message. Attachments are included and saved.
            if not self.__is_draft:
                raise RuntimeError('Only draft messages can be saved as drafts')

            target_folder = target_folder or OutlookWellKnowFolderNames.DRAFTS
            if isinstance(target_folder, OutlookWellKnowFolderNames):
                target_folder = target_folder.value
            elif not isinstance(target_folder, str):
                # a Folder instance
                target_folder = getattr(target_folder, 'folder_id', OutlookWellKnowFolderNames.DRAFTS.value)

            url = self.build_url(self._endpoints.get('create_draft_folder').format(id=target_folder))
            method = self.con.post
            data = self.to_api_data()

        self._clear_tracker()  # reset the tracked changes as they are all saved.
        if not data:
            return True

        response = method(url, data=data)
        if not response:
            return False

        if not self.object_id:
            # new message
            message = response.json()

            self.object_id = message.get(self._cc('id'), None)
            self.folder_id = message.get(self._cc('parentFolderId'), None)

            self.__created = message.get(self._cc('createdDateTime'), message.get(self._cc('dateTimeCreated'), None))  # fallback to office365 v1.0
            self.__modified = message.get(self._cc('lastModifiedDateTime'), message.get(self._cc('dateTimeModified'), None))  # fallback to office365 v1.0

            self.__created = parse(self.__created).astimezone(self.protocol.timezone) if self.__created else None
            self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

        else:
            self.__modified = self.protocol.timezone.localize(dt.datetime.now())

        return True

    def get_body_text(self):
        """ Parse the body html and returns the body text using bs4 """
        if self.body_type != 'HTML':
            return self.body

        try:
            soup = bs(self.body, 'html.parser')
        except Exception as e:
            return self.body
        else:
            return soup.body.text

    def get_body_soup(self):
        """ Returns the beautifulsoup4 of the html body"""
        if self.body_type != 'HTML':
            return None
        else:
            return bs(self.body, 'html.parser')

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Subject: {}'.format(self.subject)
