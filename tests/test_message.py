import io
from unittest import mock
from collections import namedtuple, deque

from O365.connection import MSGraphProtocol
from O365.message import Flag, Message
from O365.utils import ImportanceLevel


class TestMessageData:
    def test_equality(self):
        msg_1 = message(__cloud_data__={"id": "123"})
        msg_2 = message(__cloud_data__={"id": "123"})
        assert msg_1 == msg_2

    def test_attachments(self):
        msg = message()
        assert repr(msg.attachments) == "Number of Attachments: 0"
        msg.attachments.add([(io.BytesIO(b"content"), "filename.txt")])
        assert len(msg.attachments) == 1
        assert repr(msg.attachments) == "Number of Attachments: 1"
        assert "filename.txt" in msg.attachments
        msg.attachments.clear()
        assert len(msg.attachments) == 0

        msg.attachments.add([(io.BytesIO(b"content"), "filename.txt")])
        assert [at.name for at in msg.attachments] == ["filename.txt"]
        assert msg.attachments[0].name == "filename.txt"
        msg.attachments.remove(["filename.txt"])

    def test_properties(self):
        msg = message(
            __cloud_data__={
                "subject": "Test",
            }
        )

        assert len(msg.bcc) == 0
        assert len(msg.cc) == 0
        assert len(msg.reply_to) == 0
        assert len(msg.to) == 0
        assert msg.sender.address == ""

        assert len(msg.attachments) == 0
        assert msg.body == ""
        assert msg.body_preview == ""
        assert msg.subject == "Test"
        assert msg.unique_body == ""
        assert str(msg) == "Subject: Test"

        assert msg.categories == []
        assert msg.created is None
        assert msg.has_attachments is False
        assert msg.is_delivery_receipt_requested is False
        assert msg.is_draft is True
        assert msg.is_event_message is False
        assert msg.is_read is None
        assert msg.is_read_receipt_requested is False
        assert msg.meeting_message_type is None
        assert msg.modified is None
        assert msg.received is None
        assert msg.sent is None

        assert msg.flag.status is Flag.NotFlagged
        assert msg.importance is ImportanceLevel.Normal

    def test_changes(self):
        msg = message()
        msg.is_read = True
        msg.subject = "Changed"
        msg.sender = "alice@example.com"
        msg.categories = ["Test"]
        msg.add_category("Test")
        msg.importance = "normal"
        msg.is_read_receipt_requested = True

    def test_body(self):
        msg = message(
            __cloud_data__={
                "body": {
                    "contentType": "text",
                    "content": "content",
                }
            }
        )
        assert msg.body_type == "text"
        assert msg.get_body_soup() is None
        assert msg.get_body_text() == "content"
        msg.body = "more content"
        assert msg.body == "more content\ncontent"
        msg.body = ""
        assert msg.body == ""

        msg = message(
            __cloud_data__={
                "body": {
                    "content": "<html><body>content",
                }
            }
        )
        assert msg.get_body_soup() is not None
        assert msg.get_body_text() == "content"

    def test_to_api_data(self):
        msg = message(
            __cloud_data__={
                "id": "123",
                "isDraft": False,
                "body": {"content": "<html><body>"},
            }
        )
        msg.to.add("alice@example.com")
        msg.cc.add("alice@example.com")
        msg.bcc.add("alice@example.com")
        msg.reply_to.add("alice@example.com")
        msg.sender = "alice@example.com"
        assert msg.to_api_data() == {
            "body": {"content": "<html><body>", "contentType": "HTML"},
            "conversationId": None,
            "flag": {"flagStatus": "notFlagged"},
            "hasAttachments": False,
            "id": "123",
            "importance": "normal",
            "isDeliveryReceiptRequested": False,
            "isDraft": False,
            "isRead": None,
            "isReadReceiptRequested": False,
            "subject": "",
            "parentFolderId": None,
            "from": {"emailAddress": {"address": "alice@example.com"}},
            "toRecipients": [{"emailAddress": {"address": "alice@example.com"}}],
            "bccRecipients": [{"emailAddress": {"address": "alice@example.com"}}],
            "ccRecipients": [{"emailAddress": {"address": "alice@example.com"}}],
            "replyTo": [{"emailAddress": {"address": "alice@example.com"}}],
        }


class TestMessageApiCalls:
    base_url = MSGraphProtocol().service_url

    def test_save_draft_with_small_attachment(self):
        msg = message()
        msg.subject = "Test"
        msg.attachments.add([(io.BytesIO(b"content"), "filename.txt")])

        assert msg.save_draft() is True
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/mailFolders/Drafts/messages"
        assert call.payload == {
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "contentBytes": "Y29udGVudA==",
                    "name": "filename.txt",
                }
            ],
            "body": {"content": "", "contentType": "HTML"},
            "flag": {"flagStatus": "notFlagged"},
            "importance": "normal",
            "isDeliveryReceiptRequested": False,
            "isReadReceiptRequested": False,
            "subject": "Test",
        }

    def test_save_draft_with_with_small_attachment_when_object_id_is_set(self):
        msg = message(__cloud_data__={"id": "123", "isDraft": True})
        msg.attachments.add([(io.BytesIO(b"content"), "filename.txt")])

        assert msg.save_draft() is True
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/messages/123/attachments"
        assert call.payload == {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "contentBytes": "Y29udGVudA==",
            "name": "filename.txt",
        }

    @mock.patch("O365.utils.attachment.UPLOAD_SIZE_LIMIT_SIMPLE", 7)
    @mock.patch("O365.utils.attachment.DEFAULT_UPLOAD_CHUNK_SIZE", 5)
    def test_save_draft_with_with_large_attachment_when_object_id_is_set(self):
        upload_url = "https://sn3302.up.1drv.com/up/foobar"

        msg = message(__cloud_data__={"id": "123", "isDraft": True})
        msg.attachments.add([(io.BytesIO(b"long-content"), "filename.txt")])

        msg.con.responses.clear()
        msg.con.responses.extend(
            [
                MockResponse({"uploadUrl": upload_url}),
                MockResponse({}),
                MockResponse({}),
                MockResponse({}),
                MockResponse({}),
            ]
        )
        assert msg.save_draft() is True
        assert [c.url for c in msg.con.calls] == [
            self.base_url + "me/messages/123/attachments/createUploadSession",
            upload_url,
            upload_url,
            upload_url,
        ]
        assert msg.con.calls[0].payload == {
            "attachmentItem": {
                "attachmentType": "file",
                "name": "filename.txt",
                "size": 12,
            },
        }
        assert msg.con.calls[1].payload == b"long-"
        assert msg.con.calls[2].payload == b"conte"
        assert msg.con.calls[3].payload == b"nt"

    def test_save_draft_with_custom_header(self):
        msg = message()
        msg.subject = "Test"
        my_custom_header = [{"name": "x-my-custom-header", "value": "myHeaderValue"}]
        msg.message_headers = my_custom_header

        assert msg.save_draft() is True
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/mailFolders/Drafts/messages"
        assert call.payload == {
            "body": {"content": "", "contentType": "HTML"},
            "flag": {"flagStatus": "notFlagged"},
            "importance": "normal",
            "isDeliveryReceiptRequested": False,
            "isReadReceiptRequested": False,
            "subject": "Test",
            "internetMessageHeaders": my_custom_header,
        }

    def test_save_message(self):
        msg = message(__cloud_data__={"id": "123", "isDraft": False})
        msg.subject = "Changed"
        msg.save_message()

    def test_delete(self):
        msg = message(__cloud_data__={"id": "123"})
        msg.delete()

    def test_forward(self):
        msg = message(__cloud_data__={"id": "123", "isDraft": False})
        msg.forward()

    def test_get_event(self):
        msg = message(
            __cloud_data__={
                "id": "123",
                "meetingMessageType": "meetingRequest",
            }
        )
        msg.con.responses.clear()
        msg.con.responses.append(MockResponse({"event": {}}))
        assert msg.is_event_message
        msg.get_event()
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/messages/123"

    def test_get_mime_content(self):
        msg = message(__cloud_data__={"id": "123"})
        msg.get_mime_content()
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/messages/123/$value"

    def test_mark_as_read(self):
        msg = message(__cloud_data__={"id": "123", "isDraft": False})
        msg.mark_as_read()
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/messages/123"
        assert call.payload == {"isRead": True}

    def test_mark_as_unread(self):
        msg = message(__cloud_data__={"id": "123", "isDraft": False})
        msg.mark_as_unread()
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/messages/123"
        assert call.payload == {"isRead": False}

    def test_copy(self):
        folder = "Test"
        msg = message(__cloud_data__={"id": "123"})
        msg.copy(folder)
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/messages/123/copy"
        assert call.payload == {"destinationId": "Test"}

    def test_move(self):
        folder = "Test"
        msg = message(__cloud_data__={"id": "123"})
        msg.move(folder)
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/messages/123/move"
        assert call.payload == {"destinationId": "Test"}

    def test_send(self):
        msg = message(__cloud_data__={})
        assert msg.send(save_to_sent_folder=False)
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/sendMail"
        assert call.payload == {
            "message": {
                "body": {"content": "", "contentType": "HTML"},
                "flag": {"flagStatus": "notFlagged"},
                "importance": "normal",
                "isDeliveryReceiptRequested": False,
                "isReadReceiptRequested": False,
                "subject": "",
            },
            "saveToSentItems": False,
        }

    def test_send_with_headers(self):
        my_testheader = {"x-my-custom-header": "some_value"}
        msg = message(__cloud_data__={"internetMessageHeaders": [my_testheader]})
        assert msg.send(save_to_sent_folder=False)
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/sendMail"
        assert call.payload == {
            "message": {
                "body": {"content": "", "contentType": "HTML"},
                "flag": {"flagStatus": "notFlagged"},
                "importance": "normal",
                "isDeliveryReceiptRequested": False,
                "isReadReceiptRequested": False,
                "subject": "",
                "internetMessageHeaders": [my_testheader],
            },
            "saveToSentItems": False,
        }

    def test_send_existing_object(self):
        msg = message(__cloud_data__={"id": "123"})
        assert msg.send()
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/messages/123/send"

    def test_reply(self):
        msg = message(__cloud_data__={"id": "123", "isDraft": False})
        msg.reply(to_all=True)
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/messages/123/createReplyAll"

    def test_save_as_eml(self):
        msg = message(__cloud_data__={"id": "123"})
        msg.save_as_eml(to_path=None)
        [call] = msg.con.calls
        assert call.url == self.base_url + "me/messages/123/$value"


def message(**kwargs):
    defaults = dict(
        con=MockConnection(),
        protocol=MSGraphProtocol(),
    )
    defaults.update(kwargs)
    return Message(**defaults)


apicall = namedtuple("apicall", ["method", "url", "payload"])


class MockConnection:
    def __init__(self, data=None):
        self.calls = []
        data = data or {
            "id": "1",
            "createdDateTime": "2010-10-10T10:10:10Z",
        }
        self.responses = deque([MockResponse(data=data)])

    def patch(self, url, data):
        return self._request("patch", url, data)

    def get(self, url, params=None):
        return self._request("get", url, None)

    def delete(self, url):
        return self._request("delete", url, None)

    def post(self, url, data=None):
        return self._request("post", url, data)

    def naive_request(self, url, method, data, headers):
        return self._request(method, url, data)

    def _request(self, method, url, data):
        self.calls.append(apicall(method, url, data))
        if self.responses:
            return self.responses.popleft()
        else:
            raise IndexError("No more MockResponses prepared")


class MockResponse:
    def __init__(self, data=None, content="", status_code=200):
        self.content = ""
        self.data = data
        self.status_code = status_code

    def json(self):
        return self.data
