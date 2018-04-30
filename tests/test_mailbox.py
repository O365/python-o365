from tests.config import USERNAME, PASSWORD, CLIENT_ID, CLIENT_SECRET
from O365 import Account, Connection, MSOffice365Protocol, AUTH_METHOD


class TestMailBoxBasicAuth:

    def setup_class(self):
        credentials = (USERNAME, PASSWORD)
        self.account = Account(credentials, auth_method=AUTH_METHOD.BASIC)
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

    def test_delete_email(self):
        drafts = self.mailbox.drafts_folder()

        q = drafts.new_query('subject').equals('Test Msg')

        messages = drafts.get_messages(1, query=q)

        if messages:
            messages[0].delete()

        messages = drafts.get_messages(1, query=q)

        assert len(messages) == 0


class TestMailBoxOauth(TestMailBoxBasicAuth):

    def setup_class(self):
        credentials = (CLIENT_ID, CLIENT_SECRET)
        self.account = Account(credentials, auth_method=AUTH_METHOD.OAUTH)
        self.mailbox = self.account.mailbox()
        self.inbox = self.mailbox.inbox_folder()
