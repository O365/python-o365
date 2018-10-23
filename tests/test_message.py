from pathlib import Path
from tests.config import CLIENT_ID, CLIENT_SECRET
from pyo365 import Account


class TestMessage:

    def setup_class(self):
        credentials = (CLIENT_ID, CLIENT_SECRET)
        self.account = Account(credentials)
        self.mailbox = self.account.mailbox()
        self.inbox = self.mailbox.inbox_folder()
        self.drafts = self.mailbox.drafts_folder()
        self.test_msg_subject1 = 'Test Msg 1548lop102'
        self.test_msg_subject2 = 'Test Msg 1548lop103'

    def teardown_class(self):
        pass

    def test_get_inbox_mails(self):
        messages = self.inbox.get_messages(5)

        assert len(messages) != 0

    def test_new_email_draft(self):
        msg = self.account.new_message()
        msg.subject = self.test_msg_subject1
        msg.body = 'A message test'
        msg.save_draft()

        message = self.drafts.get_message(self.drafts.q('subject').equals(self.test_msg_subject1))

        assert message is not None

    def test_update_email(self):
        q = self.drafts.q('subject').equals(self.test_msg_subject1)

        message = self.drafts.get_message(q)
        message2 = None

        if message:
            message.to.add('test@example.com')
            saved = message.save_draft()

            message2 = self.drafts.get_message(q)

        assert message and saved and message2 and message2.to and message2.to[0].address == 'test@example.com'

    def test_add_attachment(self):
        q = self.drafts.q('subject').equals(self.test_msg_subject1)

        message = self.drafts.get_message(q)
        message2 = None

        if message:
            dummy_file = Path('dummy.txt')
            with dummy_file.open(mode='w') as file:
                file.write('Test file')
            message.attachments.add(Path() / 'adjuntar.xls')  # add this file as an attachment
            saved = message.save_draft()
            dummy_file.unlink()  # delete dummy file

            message2 = self.drafts.get_message(q)

        assert message and saved and message2 and message2.has_attachments

    def test_remove_attachment(self):
        q = self.drafts.q('subject').equals(self.test_msg_subject1)

        message = self.drafts.get_message(q, download_attachments=True)
        message2 = None

        if message:
            message.attachments.clear()
            saved = message.save_draft()

            message2 = self.drafts.get_message(q)

        assert message and saved and message2 and not message2.has_attachments

    def test_delete_email(self):
        q = self.drafts.q('subject').equals(self.test_msg_subject1)

        message = self.drafts.get_message(q)

        if message:
            deleted = message.delete()

        message = self.drafts.get_message(q)

        assert deleted and message is None

    def test_reply(self):
        message = self.inbox.get_message()  # get first message in inbox

        reply = None
        reply_text = 'New reply on top of the message trail.'

        if message:
            reply = message.reply()
            reply.body = reply_text
            reply.subject = self.test_msg_subject2
            saved = reply.save_draft()

        assert message and reply and reply.body != reply_text and saved

    def test_move_to_folder(self):
        q = self.mailbox.q('subject').equals(self.test_msg_subject2)

        message = self.drafts.get_message(q)

        deleted_folder = self.mailbox.deleted_folder()
        if message:
            moved = message.move(deleted_folder)

        message = deleted_folder.get_message(q)

        assert message and moved and message

    def test_copy_message(self):
        q = self.mailbox.q('subject').equals(self.test_msg_subject2)

        deleted_folder = self.mailbox.deleted_folder()
        message = deleted_folder.get_message(q)

        if message:
            copied = message.copy(self.drafts)
            deleted = copied.delete()

        assert message and copied and deleted
