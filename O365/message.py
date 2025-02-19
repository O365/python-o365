import datetime as dt
import logging
from enum import Enum
from pathlib import Path

# noinspection PyPep8Naming
from bs4 import BeautifulSoup as bs
from dateutil.parser import parse

from .calendar import Event
from .category import Category
from .utils import (
    ApiComponent,
    AttachableMixin,
    BaseAttachment,
    BaseAttachments,
    CaseEnum,
    HandleRecipientsMixin,
    ImportanceLevel,
    OutlookWellKnowFolderNames,
    Recipient,
    TrackerSet,
)

log = logging.getLogger(__name__)


class RecipientType(Enum):
    TO = "to"
    CC = "cc"
    BCC = "bcc"


class MeetingMessageType(CaseEnum):
    MeetingRequest = "meetingRequest"
    MeetingCancelled = "meetingCancelled"
    MeetingAccepted = "meetingAccepted"
    MeetingTentativelyAccepted = "meetingTentativelyAccepted"
    MeetingDeclined = "meetingDeclined"


class Flag(CaseEnum):
    NotFlagged = "notFlagged"
    Complete = "complete"
    Flagged = "flagged"


class MessageAttachment(BaseAttachment):
    _endpoints = {
        "attach": "/messages/{id}/attachments",
        "attachment": "/messages/{id}/attachments/{ida}",
    }


class MessageAttachments(BaseAttachments):
    _endpoints = {
        "attachments": "/messages/{id}/attachments",
        "attachment": "/messages/{id}/attachments/{ida}",
        "get_mime": "/messages/{id}/attachments/{ida}/$value",
        "create_upload_session": "/messages/{id}/attachments/createUploadSession",
    }
    _attachment_constructor = MessageAttachment

    def save_as_eml(self, attachment, to_path=None):
        """Saves this message as and EML to the file system
        :param MessageAttachment attachment: the MessageAttachment to store as eml.
        :param Path or str to_path: the path where to store this file
        """
        mime_content = self.get_mime_content(attachment)
        if not mime_content:
            return False

        if to_path is None:
            to_path = Path("message_eml.eml")
        else:
            if not isinstance(to_path, Path):
                to_path = Path(to_path)

        if not to_path.suffix:
            to_path = to_path.with_suffix(".eml")

        with to_path.open("wb") as file_obj:
            file_obj.write(mime_content)
            return True

    def get_mime_content(self, attachment):
        """Returns the MIME contents of this attachment"""
        if (
            not attachment
            or not isinstance(attachment, MessageAttachment)
            or attachment.attachment_id is None
            or attachment.attachment_type != "item"
        ):
            raise ValueError(
                'Must provide a saved "item" attachment of type MessageAttachment'
            )

        msg_id = self._parent.object_id
        if msg_id is None:
            raise RuntimeError(
                "Attempting to get the mime contents of an unsaved message"
            )

        url = self.build_url(
            self._endpoints.get("get_mime").format(
                id=msg_id, ida=attachment.attachment_id
            )
        )

        response = self._parent.con.get(url)

        if not response:
            return None

        return response.content


class MessageFlag(ApiComponent):
    """A flag on a message"""

    def __init__(self, parent, flag_data):
        """An flag on a message
        Not available on Outlook Rest Api v2 (only in beta)

        :param parent: parent of this
        :type parent: Message
        :param dict flag_data: flag data from cloud
        """
        super().__init__(protocol=parent.protocol, main_resource=parent.main_resource)

        self.__message = parent

        self.__status = Flag.from_value(
            flag_data.get(self._cc("flagStatus"), "notFlagged")
        )

        start_obj = flag_data.get(self._cc("startDateTime"), {})
        self.__start = self._parse_date_time_time_zone(start_obj)

        due_date_obj = flag_data.get(self._cc("dueDateTime"), {})
        self.__due_date = self._parse_date_time_time_zone(due_date_obj)

        completed_date_obj = flag_data.get(self._cc("completedDateTime"), {})
        self.__completed = self._parse_date_time_time_zone(completed_date_obj)

    def __repr__(self):
        return str(self.__status)

    def __str__(self):
        return self.__repr__()

    def __bool__(self):
        return self.is_flagged

    def _track_changes(self):
        """Update the track_changes on the message to reflect a
        needed update on this field"""
        self.__message._track_changes.add("flag")

    @property
    def status(self):
        return self.__status

    def set_flagged(self, *, start_date=None, due_date=None):
        """Sets this message as flagged
        :param start_date: the start datetime of the followUp
        :param due_date: the due datetime of the followUp
        """
        self.__status = Flag.Flagged
        start_date = start_date or dt.datetime.now()
        due_date = due_date or dt.datetime.now()
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=self.protocol.timezone)
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=self.protocol.timezone)
        self.__start = start_date
        self.__due_date = due_date
        self._track_changes()

    def set_completed(self, *, completition_date=None):
        """Sets this message flag as completed
        :param completition_date: the datetime this followUp was completed
        """
        self.__status = Flag.Complete
        completition_date = completition_date or dt.datetime.now()
        if completition_date.tzinfo is None:
            completition_date = completition_date.replace(tzinfo=self.protocol.timezone)
        self.__completed = completition_date
        self._track_changes()

    def delete_flag(self):
        """Sets this message as un flagged"""
        self.__status = Flag.NotFlagged
        self.__start = None
        self.__due_date = None
        self.__completed = None
        self._track_changes()

    @property
    def start_date(self):
        return self.__start

    @property
    def due_date(self):
        return self.__due_date

    @property
    def completition_date(self):
        return self.__completed

    @property
    def is_completed(self):
        return self.__status is Flag.Complete

    @property
    def is_flagged(self):
        return self.__status is Flag.Flagged or self.__status is Flag.Complete

    def to_api_data(self):
        """Returns this data as a dict to be sent to the server"""
        data = {self._cc("flagStatus"): self._cc(self.__status.value)}
        if self.__status is Flag.Flagged:
            data[self._cc("startDateTime")] = (
                self._build_date_time_time_zone(self.__start)
                if self.__start is not None
                else None
            )
            data[self._cc("dueDateTime")] = (
                self._build_date_time_time_zone(self.__due_date)
                if self.__due_date is not None
                else None
            )

        if self.__status is Flag.Complete:
            data[self._cc("completedDateTime")] = self._build_date_time_time_zone(
                self.__completed
            )

        return data


class Message(ApiComponent, AttachableMixin, HandleRecipientsMixin):
    """Management of the process of sending, receiving, reading, and
    editing emails."""

    _endpoints = {
        "create_draft": "/messages",
        "create_draft_folder": "/mailFolders/{id}/messages",
        "send_mail": "/sendMail",
        "send_draft": "/messages/{id}/send",
        "get_message": "/messages/{id}",
        "move_message": "/messages/{id}/move",
        "copy_message": "/messages/{id}/copy",
        "create_reply": "/messages/{id}/createReply",
        "create_reply_all": "/messages/{id}/createReplyAll",
        "forward_message": "/messages/{id}/createForward",
        "get_mime": "/messages/{id}/$value",
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """Makes a new message wrapper for sending and receiving messages.

        :param parent: parent folder/account to create the message in
        :type parent: mailbox.Folder or Account
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        :param bool download_attachments: whether or not to
         download attachments (kwargs)
        """
        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
            attachment_name_property="subject",
            attachment_type="message_type",
        )

        download_attachments = kwargs.get("download_attachments")

        cloud_data = kwargs.get(self._cloud_data_key, {})
        cc = self._cc  # alias to shorten the code

        # internal to know which properties need to be updated on the server
        self._track_changes = TrackerSet(casing=cc)
        self.object_id = cloud_data.get(cc("id"), kwargs.get("object_id", None))

        self.__inference_classification = cloud_data.get(
            cc("inferenceClassification"), None
        )

        self.__created = cloud_data.get(cc("createdDateTime"), None)
        self.__modified = cloud_data.get(cc("lastModifiedDateTime"), None)
        self.__received = cloud_data.get(cc("receivedDateTime"), None)
        self.__sent = cloud_data.get(cc("sentDateTime"), None)

        local_tz = self.protocol.timezone
        self.__created = (
            parse(self.__created).astimezone(local_tz) if self.__created else None
        )
        self.__modified = (
            parse(self.__modified).astimezone(local_tz) if self.__modified else None
        )
        self.__received = (
            parse(self.__received).astimezone(local_tz) if self.__received else None
        )
        self.__sent = parse(self.__sent).astimezone(local_tz) if self.__sent else None

        self.__attachments = MessageAttachments(parent=self, attachments=[])
        self.__attachments.add(
            {self._cloud_data_key: cloud_data.get(cc("attachments"), [])}
        )
        self.__has_attachments = cloud_data.get(cc("hasAttachments"), False)
        self.__subject = cloud_data.get(cc("subject"), "")
        self.__body_preview = cloud_data.get(cc("bodyPreview"), "")
        body = cloud_data.get(cc("body"), {})
        self.__body = body.get(cc("content"), "")
        self.body_type = body.get(
            cc("contentType"), "HTML"
        )  # default to HTML for new messages

        unique_body = cloud_data.get(cc("uniqueBody"), {})
        self.__unique_body = unique_body.get(cc("content"), "")
        self.unique_body_type = unique_body.get(
            cc("contentType"), "HTML"
        )  # default to HTML for new messages

        if download_attachments and self.has_attachments:
            self.attachments.download_attachments()

        self.__sender = self._recipient_from_cloud(
            cloud_data.get(cc("from"), None), field=cc("from")
        )
        self.__to = self._recipients_from_cloud(
            cloud_data.get(cc("toRecipients"), []), field=cc("toRecipients")
        )
        self.__cc = self._recipients_from_cloud(
            cloud_data.get(cc("ccRecipients"), []), field=cc("ccRecipients")
        )
        self.__bcc = self._recipients_from_cloud(
            cloud_data.get(cc("bccRecipients"), []), field=cc("bccRecipients")
        )
        self.__reply_to = self._recipients_from_cloud(
            cloud_data.get(cc("replyTo"), []), field=cc("replyTo")
        )
        self.__categories = cloud_data.get(cc("categories"), [])

        self.__importance = ImportanceLevel.from_value(
            cloud_data.get(cc("importance"), "normal") or "normal"
        )
        self.__is_read = cloud_data.get(cc("isRead"), None)

        self.__is_read_receipt_requested = cloud_data.get(
            cc("isReadReceiptRequested"), False
        )
        self.__is_delivery_receipt_requested = cloud_data.get(
            cc("isDeliveryReceiptRequested"), False
        )

        self.__single_value_extended_properties = cloud_data.get(
            cc("singleValueExtendedProperties"), []
        )

        # if this message is an EventMessage:
        meeting_mt = cloud_data.get(cc("meetingMessageType"), "none")

        # hack to avoid typo in EventMessage between Api v1.0 and beta:
        meeting_mt = meeting_mt.replace("Tenatively", "Tentatively")

        self.__meeting_message_type = (
            MeetingMessageType.from_value(meeting_mt) if meeting_mt != "none" else None
        )

        # a message is a draft by default
        self.__is_draft = cloud_data.get(cc("isDraft"), kwargs.get("is_draft", True))
        self.conversation_id = cloud_data.get(cc("conversationId"), None)
        self.conversation_index = cloud_data.get(cc("conversationIndex"), None)
        self.folder_id = cloud_data.get(cc("parentFolderId"), None)

        flag_data = cloud_data.get(cc("flag"), {})
        self.__flag = MessageFlag(parent=self, flag_data=flag_data)

        self.internet_message_id = cloud_data.get(cc("internetMessageId"), "")
        self.web_link = cloud_data.get(cc("webLink"), "")

        # Headers only retrieved when selecting 'internetMessageHeaders'
        self.__message_headers = cloud_data.get(cc("internetMessageHeaders"), [])

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Subject: {}".format(self.subject)

    def __eq__(self, other):
        return self.object_id == other.object_id

    @property
    def is_read(self):
        """Check if the message is read or not

        :getter: Get the status of message read
        :setter: Mark the message as read
        :type: bool
        """
        return self.__is_read

    @is_read.setter
    def is_read(self, value):
        self.__is_read = value
        self._track_changes.add("isRead")

    @property
    def has_attachments(self):
        """Check if the message contains attachments

        :type: bool
        """
        if self.__has_attachments is False and self.body_type.upper() == "HTML":
            # test for inline attachments (Azure responds with hasAttachments=False when there are only inline attachments):
            if any(
                img.get("src", "").startswith("cid:")
                for img in self.get_body_soup().find_all("img")
            ):
                self.__has_attachments = True
        return self.__has_attachments

    @property
    def is_draft(self):
        """Check if the message is marked as draft

        :type: bool
        """
        return self.__is_draft

    @property
    def subject(self):
        """Subject of the email message

        :getter: Get the current subject
        :setter: Assign a new subject
        :type: str
        """
        return self.__subject

    @subject.setter
    def subject(self, value):
        self.__subject = value
        self._track_changes.add("subject")

    @property
    def body_preview(self):
        """Returns the body preview"""
        return self.__body_preview

    @property
    def body(self):
        """Body of the email message

        :getter: Get body text of current message
        :setter: set html body of the message
        :type: str
        """
        return self.__body

    @property
    def inference_classification(self):
        """Message is focused or not"""
        return self.__inference_classification

    @body.setter
    def body(self, value):
        if self.__body:
            if not value:
                self.__body = ""
            elif self.body_type == "html":
                soup = bs(self.__body, "html.parser")
                soup.body.insert(0, bs(value, "html.parser"))
                self.__body = str(soup)
            else:
                self.__body = "".join((value, "\n", self.__body))
        else:
            self.__body = value
        self._track_changes.add("body")

    @property
    def unique_body(self):
        """The unique body of this message

            Requires a select to retrieve it.

        :rtype: str
        """
        return self.__unique_body

    @property
    def created(self):
        """Created time of the message"""
        return self.__created

    @property
    def modified(self):
        """Message last modified time"""
        return self.__modified

    @property
    def received(self):
        """Message received time"""
        return self.__received

    @property
    def sent(self):
        """Message sent time"""
        return self.__sent

    @property
    def attachments(self):
        """List of attachments"""
        return self.__attachments

    @property
    def sender(self):
        """Sender of the message

        :getter: Get the current sender
        :setter: Update the from address with new value
        :type: str or Recipient
        """
        return self.__sender

    @sender.setter
    def sender(self, value):
        """sender is a property to force to be always a Recipient class"""
        if isinstance(value, Recipient):
            if value._parent is None:
                value._parent = self
                value._field = "from"
            self.__sender = value
        elif isinstance(value, str):
            self.__sender.address = value
            self.__sender.name = ""
        else:
            raise ValueError("sender must be an address string or a Recipient object")
        self._track_changes.add("from")

    @property
    def to(self):
        """'TO' list of recipients"""
        return self.__to

    @property
    def cc(self):
        """'CC' list of recipients"""
        return self.__cc

    @property
    def bcc(self):
        """'BCC' list of recipients"""
        return self.__bcc

    @property
    def reply_to(self):
        """Reply to address"""
        return self.__reply_to

    @property
    def categories(self):
        """Categories of this message

        :getter: Current list of categories
        :setter: Set new categories for the message
        :type: list[str] or str
        """
        return self.__categories

    @categories.setter
    def categories(self, value):
        if isinstance(value, list):
            self.__categories = []
            for val in value:
                if isinstance(val, Category):
                    self.__categories.append(val.name)
                else:
                    self.__categories.append(val)
        elif isinstance(value, str):
            self.__categories = [value]
        elif isinstance(value, Category):
            self.__categories = [value.name]
        else:
            raise ValueError("categories must be a list")
        self._track_changes.add("categories")

    def add_category(self, category):
        """Adds a category to this message current categories list"""

        if isinstance(category, Category):
            self.__categories.append(category.name)
        else:
            self.__categories.append(category)
        self._track_changes.add("categories")

    @property
    def importance(self):
        """Importance of the message

        :getter: Get the current priority of the message
        :setter: Set a different importance level
        :type: str or ImportanceLevel
        """
        return self.__importance

    @importance.setter
    def importance(self, value):
        self.__importance = (
            value
            if isinstance(value, ImportanceLevel)
            else ImportanceLevel.from_value(value)
        )
        self._track_changes.add("importance")

    @property
    def is_read_receipt_requested(self):
        """if the read receipt is requested for this message

        :getter: Current state of isReadReceiptRequested
        :setter: Set isReadReceiptRequested for the message
        :type: bool
        """
        return self.__is_read_receipt_requested

    @is_read_receipt_requested.setter
    def is_read_receipt_requested(self, value):
        self.__is_read_receipt_requested = bool(value)
        self._track_changes.add("isReadReceiptRequested")

    @property
    def is_delivery_receipt_requested(self):
        """if the delivery receipt is requested for this message

        :getter: Current state of isDeliveryReceiptRequested
        :setter: Set isDeliveryReceiptRequested for the message
        :type: bool
        """
        return self.__is_delivery_receipt_requested

    @is_delivery_receipt_requested.setter
    def is_delivery_receipt_requested(self, value):
        self.__is_delivery_receipt_requested = bool(value)
        self._track_changes.add("isDeliveryReceiptRequested")

    @property
    def meeting_message_type(self):
        """If this message is a EventMessage, returns the
        meeting type: meetingRequest, meetingCancelled, meetingAccepted,
        meetingTentativelyAccepted, meetingDeclined
        """
        return self.__meeting_message_type

    @property
    def is_event_message(self):
        """Returns if this message is of type EventMessage
        and therefore can return the related event.
        """
        return self.__meeting_message_type is not None

    @property
    def flag(self):
        """The Message Flag instance"""
        return self.__flag

    @property
    def single_value_extended_properties(self):
        """singleValueExtendedProperties"""
        return self.__single_value_extended_properties

    @property
    def message_headers(self):
        """Custom message headers

            List of internetMessageHeaders, see definition: https://learn.microsoft.com/en-us/graph/api/resources/internetmessageheader?view=graph-rest-1.0

        :type: list[dict[str, str]]
        """

        return self.__message_headers

    @message_headers.setter
    def message_headers(self, value):
        if not isinstance(value, list):
            raise ValueError('"message_header" must be a list')

        self.__message_headers = value
        self._track_changes.add('message_headers')

    def add_message_header(self, name, value):
        # Look if we already have the key. If we do, update it, otherwise write
        for header in self.__message_headers:
            if header["name"] == name:
                header["value"] = value
                return
        self.__message_headers.append({"name": name, "value": value})

    def to_api_data(self, restrict_keys=None):
        """ Returns a dict representation of this message prepared to be sent
        to the cloud

        :param restrict_keys: a set of keys to restrict the returned
         data to
        :type restrict_keys: dict or set
        :return: converted to cloud based keys
        :rtype: dict
        """

        cc = self._cc  # alias to shorten the code

        message = {
            cc('subject'): self.subject,
            cc('body'): {
                cc('contentType'): self.body_type,
                cc('content'): self.body},
            cc('importance'): cc(self.importance.value),
            cc('flag'): self.flag.to_api_data(),
            cc('isReadReceiptRequested'): self.is_read_receipt_requested,
            cc('isDeliveryReceiptRequested'): self.is_delivery_receipt_requested,
        }

        if self.to:
            message[cc('toRecipients')] = [self._recipient_to_cloud(recipient)
                                           for recipient in self.to]
        if self.cc:
            message[cc('ccRecipients')] = [self._recipient_to_cloud(recipient)
                                           for recipient in self.cc]
        if self.bcc:
            message[cc('bccRecipients')] = [self._recipient_to_cloud(recipient)
                                            for recipient in self.bcc]
        if self.reply_to:
            message[cc('replyTo')] = [self._recipient_to_cloud(recipient) for
                                      recipient in self.reply_to]
        if self.attachments:
            message[cc('attachments')] = self.attachments.to_api_data()
        if self.sender and self.sender.address:
            message[cc('from')] = self._recipient_to_cloud(self.sender)

        if self.categories or 'categories' in (restrict_keys or {}):
            message[cc('categories')] = self.categories

        if self.object_id and not self.__is_draft:
            # return the whole signature of this message

            message[cc('id')] = self.object_id
            if self.created:
                message[cc('createdDateTime')] = self.created.astimezone(
                    dt.timezone.utc).isoformat()
            if self.received:
                message[cc('receivedDateTime')] = self.received.astimezone(
                    dt.timezone.utc).isoformat()
            if self.sent:
                message[cc('sentDateTime')] = self.sent.astimezone(
                    dt.timezone.utc).isoformat()
            message[cc('hasAttachments')] = bool(self.attachments)
            message[cc('isRead')] = self.is_read
            message[cc('isDraft')] = self.__is_draft
            message[cc('conversationId')] = self.conversation_id
            # this property does not form part of the message itself
            message[cc('parentFolderId')] = self.folder_id

        if self.message_headers:
            message[cc('internetMessageHeaders')] = self.message_headers

        if restrict_keys:
            for key in list(message.keys()):
                if key not in restrict_keys:
                    del message[key]

        return message

    def send(self, save_to_sent_folder=True):
        """ Sends this message

        :param bool save_to_sent_folder: whether or not to save it to
         sent folder
        :return: Success / Failure
        :rtype: bool
        """

        if self.object_id and not self.__is_draft:
            return RuntimeError('Not possible to send a message that is not '
                                'new or a draft. Use Reply or Forward instead.')

        if self.__is_draft and self.object_id:
            url = self.build_url(
                self._endpoints.get('send_draft').format(id=self.object_id))
            if self._track_changes:
                # there are pending changes to be committed
                self.save_draft()
            data = None

        else:
            url = self.build_url(self._endpoints.get('send_mail'))
            data = {self._cc('message'): self.to_api_data()}
            if save_to_sent_folder is False:
                data[self._cc('saveToSentItems')] = False

        response = self.con.post(url, data=data)
        # response evaluates to false if 4XX or 5XX status codes are returned
        if not response:
            return False

        self.object_id = 'sent_message' if not self.object_id else self.object_id
        self.__is_draft = False

        return True

    def reply(self, to_all=True):
        """  Creates a new message that is a reply to this message

        :param bool to_all: whether or not to replies to all the recipients
         instead to just the sender
        :return: new message
        :rtype: Message
        """
        if not self.object_id or self.__is_draft:
            raise RuntimeError("Can't reply to this message")

        if to_all:
            url = self.build_url(self._endpoints.get('create_reply_all').format(
                id=self.object_id))
        else:
            url = self.build_url(
                self._endpoints.get('create_reply').format(id=self.object_id))

        # set prefer timezone header to protocol timezone
        headers = {'Prefer': self.protocol.get_service_keyword('prefer_timezone_header')}
        response = self.con.post(url, headers=headers)

        if not response:
            return None

        message = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.__class__(parent=self, **{self._cloud_data_key: message})

    def forward(self):
        """  Creates a new message that is a forward this message

        :return: new message
        :rtype: Message
        """
        if not self.object_id or self.__is_draft:
            raise RuntimeError("Can't forward this message")

        url = self.build_url(
            self._endpoints.get('forward_message').format(id=self.object_id))

        response = self.con.post(url)
        if not response:
            return None

        message = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.__class__(parent=self, **{self._cloud_data_key: message})

    def delete(self):
        """ Deletes a stored message

        :return: Success / Failure
        :rtype: bool
        """
        if self.object_id is None:
            raise RuntimeError('Attempting to delete an unsaved Message')

        url = self.build_url(
            self._endpoints.get('get_message').format(id=self.object_id))

        response = self.con.delete(url)

        return bool(response)

    def mark_as_read(self):
        """ Marks this message as read in the cloud

        :return: Success / Failure
        :rtype: bool
        """
        if self.object_id is None or self.__is_draft:
            raise RuntimeError('Attempting to mark as read an unsaved Message')

        data = {self._cc('isRead'): True}

        url = self.build_url(
            self._endpoints.get('get_message').format(id=self.object_id))

        response = self.con.patch(url, data=data)
        if not response:
            return False

        self.__is_read = True

        return True

    def mark_as_unread(self):
        """ Marks this message as unread in the cloud

        :return: Success / Failure
        :rtype: bool
        """
        if self.object_id is None or self.__is_draft:
            raise RuntimeError('Attempting to mark as unread an unsaved Message')

        data = {self._cc('isRead'): False}

        url = self.build_url(
            self._endpoints.get('get_message').format(id=self.object_id))

        response = self.con.patch(url, data=data)
        if not response:
            return False

        self.__is_read = False

        return True

    def move(self, folder):
        """ Move the message to a given folder

        :param folder: Folder object or Folder id or Well-known name to
         move this message to
        :type folder: str or mailbox.Folder
        :return: Success / Failure
        :rtype: bool
        """
        if self.object_id is None:
            raise RuntimeError('Attempting to move an unsaved Message')

        url = self.build_url(
            self._endpoints.get('move_message').format(id=self.object_id))

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

        message = response.json()

        self.folder_id = folder_id
        self.object_id = message.get('id')

        return True

    def copy(self, folder):
        """ Copy the message to a given folder

        :param folder: Folder object or Folder id or Well-known name to
         copy this message to
        :type folder: str or mailbox.Folder
        :returns: the copied message
        :rtype: Message
        """
        if self.object_id is None:
            raise RuntimeError('Attempting to move an unsaved Message')

        url = self.build_url(
            self._endpoints.get('copy_message').format(id=self.object_id))

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

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.__class__(parent=self, **{self._cloud_data_key: message})

    def save_message(self):
        """Saves changes to a message.
        If the message is a new or saved draft it will call 'save_draft' otherwise
        this will save only properties of a message that are draft-independent such as:

            - is_read
            - category
            - flag

        :return: Success / Failure
        :rtype: bool
        """
        if self.object_id and not self.__is_draft:
            # we are only allowed to save some properties:
            allowed_changes = {self._cc('isRead'), self._cc('categories'),
                               self._cc('flag'), self._cc('subject')}  # allowed changes to be saved by this method
            changes = {tc for tc in self._track_changes if tc in allowed_changes}

            if not changes:
                return True  # there's nothing to update

            url = self.build_url(self._endpoints.get('get_message').format(id=self.object_id))

            data = self.to_api_data(restrict_keys=changes)

            response = self.con.patch(url, data=data)

            if not response:
                return False

            self._track_changes.clear()  # reset the tracked changes as they are all saved
            self.__modified = dt.datetime.now().replace(tzinfo=self.protocol.timezone)

            return True
        else:
            # fallback to save_draft
            return self.save_draft()

    def save_draft(self, target_folder=OutlookWellKnowFolderNames.DRAFTS):
        """ Save this message as a draft on the cloud

        :param target_folder: name of the drafts folder
        :return: Success / Failure
        :rtype: bool
        """

        if self.object_id:
            # update message. Attachments are NOT included nor saved.
            if not self.__is_draft:
                raise RuntimeError('Only draft messages can be updated')
            if not self._track_changes:
                return True  # there's nothing to update
            url = self.build_url(
                self._endpoints.get('get_message').format(id=self.object_id))
            method = self.con.patch
            data = self.to_api_data(restrict_keys=self._track_changes)

            data.pop(self._cc('attachments'),
                     None)  # attachments are handled by the next method call
            # noinspection PyProtectedMember
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
                target_folder = getattr(target_folder, 'folder_id',
                                        OutlookWellKnowFolderNames.DRAFTS.value)

            url = self.build_url(
                self._endpoints.get('create_draft_folder').format(
                    id=target_folder))
            method = self.con.post
            data = self.to_api_data()

        if not data:
            return True

        response = method(url, data=data)
        if not response:
            return False

        self._track_changes.clear()  # reset the tracked changes as they are all saved

        if not self.object_id:
            # new message
            message = response.json()

            self.object_id = message.get(self._cc('id'), None)
            self.folder_id = message.get(self._cc('parentFolderId'), None)

            # fallback to office365 v1.0
            self.__created = message.get(self._cc('createdDateTime'),
                                         message.get(
                                             self._cc('dateTimeCreated'),
                                             None))
            # fallback to office365 v1.0
            self.__modified = message.get(self._cc('lastModifiedDateTime'),
                                          message.get(
                                              self._cc('dateTimeModified'),
                                              None))

            self.__created = parse(self.__created).astimezone(
                self.protocol.timezone) if self.__created else None
            self.__modified = parse(self.__modified).astimezone(
                self.protocol.timezone) if self.__modified else None

            self.web_link = message.get(self._cc('webLink'), '')
        else:
            self.__modified = dt.datetime.now().replace(tzinfo=self.protocol.timezone)

        return True

    def get_body_text(self):
        """ Parse the body html and returns the body text using bs4

        :return: body as text
        :rtype: str
        """
        if self.body_type.upper() != 'HTML':
            return self.body

        try:
            soup = bs(self.body, 'html.parser')
        except RuntimeError:
            return self.body
        else:
            return soup.body.text

    def get_body_soup(self):
        """ Returns the beautifulsoup4 of the html body

        :return: BeautifulSoup object of body
        :rtype: BeautifulSoup
        """
        if self.body_type.upper() != 'HTML':
            return None
        else:
            return bs(self.body, 'html.parser')

    def get_event(self):
        """ If this is a EventMessage it should return the related Event"""

        if not self.is_event_message:
            return None

        # select a dummy field (eg. subject) to avoid pull unneccesary data
        query = self.q().expand('event')

        url = self.build_url(self._endpoints.get('get_message').format(id=self.object_id))

        response = self.con.get(url, params=query.as_params())

        if not response:
            return None

        data = response.json()
        event_data = data.get(self._cc('event'))

        return Event(parent=self, **{self._cloud_data_key: event_data})

    def get_mime_content(self):
        """ Returns the MIME contents of this message """
        if self.object_id is None:
            raise RuntimeError('Attempting to get the mime contents of an unsaved message')

        url = self.build_url(self._endpoints.get('get_mime').format(id=self.object_id))

        response = self.con.get(url)

        if not response:
            return None

        return response.content

    def save_as_eml(self, to_path=None):
        """ Saves this message as and EML to the file system
        :param Path or str to_path: the path where to store this file
        """

        if to_path is None:
            to_path = Path('message_eml.eml')
        else:
            if not isinstance(to_path, Path):
                to_path = Path(to_path)

        if not to_path.suffix:
            to_path = to_path.with_suffix('.eml')

        mime_content = self.get_mime_content()

        if mime_content:
            with to_path.open('wb') as file_obj:
                file_obj.write(mime_content)
            return True
        return False
