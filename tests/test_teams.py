from pathlib import Path
from O365 import Account

class TestTeams:

    def setup_class(self):
        credentials = ("client id", "client secret")
        self.account = Account(credentials)
        self.teams = account.teams()

    def teardown_class(self):
        pass
    # Depends on actual teams status, use for local testing
    # def test_get_presence(self):
    #     assert(self.account.teams().get_my_presence().activity == 'Away')
    