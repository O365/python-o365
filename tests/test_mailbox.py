from tests.config import CLIENT_ID, CLIENT_SECRET
from pyo365 import Account


class TestMailBox:

    def setup_class(self):
        credentials = (CLIENT_ID, CLIENT_SECRET)
        self.account = Account(credentials)
        self.mailbox = self.account.mailbox()
        self.inbox = self.mailbox.inbox_folder()

    def test_get_inbox_mails(self):
        messages = self.inbox.get_messages(5)

        assert len(messages) != 0

    def test_new_email_draft(self):
        msg = self.account.new_message()
        msg.subject = 'Test Msg'
        msg.body = 'A message test'
        msg.save_draft()

        drafts = self.mailbox.drafts_folder()

        q = drafts.new_query('subject').equals('Test Msg')

        messages = drafts.get_messages(1, query=q)

        assert len(messages) == 1

    def test_update_email(self):
        drafts = self.mailbox.drafts_folder()

        q = drafts.new_query('subject').equals('Test Msg')

        messages = drafts.get_messages(1, query=q)
        message = messages[0] if messages else None
        message2 = None

        if message:
            message.to.add('test@example.com')
            message.save_draft()

            messages2 = drafts.get_messages(1, query=q)
            message2 = messages2[0] if messages2 else None

        assert messages and message2 and message2.to and message2.to[0].address == 'test@example.com'

    def test_reply(self):
        inbox = self.mailbox.inbox_folder()
        messages = inbox.get_messages(1)
        message = messages[0] if messages else None

        reply = None
        reply_text = 'New reply on top of the message trail.'

        if message:
            reply = message.reply()
            reply.body = reply_text

        assert message and reply and reply.body != reply_text

    def test_delete_email(self):
        drafts = self.mailbox.drafts_folder()

        q = drafts.new_query('subject').equals('Test Msg')

        messages = drafts.get_messages(1, query=q)

        if messages:
            messages[0].delete()

        messages = drafts.get_messages(1, query=q)

        assert len(messages) == 0
