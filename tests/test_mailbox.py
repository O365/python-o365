from O365 import Account
import json

class MockConnection:

    ret_value = None

    def get(self, url, params=None, **kwargs):
        self.url = url
        self.kwargs = kwargs

class TestMailBox:

    def setup_class(self):
        credentials = ("client id","client secret")
        self.account = Account(credentials)
        self.mailbox = self.account.mailbox()
        self.mailbox.con = MockConnection()

    def teardown_class(self):
        pass
        
    def test_mailbox(self):
        assert self.mailbox.root

#    def test_get_mailbox_folders(self):
#        self.mailbox.con.ret_value = ['Inbox','Drafts']
#        
#        folders = self.mailbox.get_folders(limit=5)
#        
#        assert len(folders) > 0
