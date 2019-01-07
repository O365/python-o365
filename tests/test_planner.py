#from O365 import Account
#from O365 import Planner

#class MockConnection:

#    ret_value = None

#    def get(self, url, params=None, **kwargs):
#        self.url = url
#        self.kwargs = kwargs

#class TestPlanner:

#    def setup_class(self):
#        credentials = ("client id","client secret")
#        self.account = Account(credentials)
#        self.planner = self.account.planner()
#        self.planner.con = MockConnection()

#    def teardown_class(self):
#        pass
        
#    def test_planner(self):
#        assert self.planner

#    def test_get_my_tasks(self):
#        tasks = self.planner.get_my_tasks()
#        assert len(tasks) > 0
