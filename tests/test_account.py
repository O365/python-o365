from O365 import Account
from O365.message import Message


class TestAccount:

    def setup_class(self):
        credentials = ("client id","client secret")
        self.account = Account(credentials)

    def teardown_class(self):
        pass
    
    def test_get_message(self):
        message = self.account.new_message()
        assert isinstance(message,Message)
