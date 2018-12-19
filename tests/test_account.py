from O365 import Account
from O365 import Message


class TestAccount:

    def setup_class(self):
        credentials = ("a6b7ecf4-e94f-460d-993b-0a15fa6e535b","wejbjGH076}xvNSPEU25|+%")
        self.account = Account(credentials)

    def teardown_class(self):
        pass
    
    def test_get_message(self):
        message = self.account.new_message()
        assert isinstance(message,Message)

acc = TestAccount()
acc.setup_class()
result = acc.account.authenticate(scopes=['basic', 'message_all']) 
mailbox = acc.account.mailbox()

inbox = mailbox.inbox_folder()

for message in inbox.get_messages():
    print(message)