from O365 import Account, MSGraphProtocol, Connection
from O365.excel import WorkbookApplication
from tests.config import CLIENT_ID, CLIENT_SECRET


class Workbook(object):
    pass


class TestWorkbookApplication:

    def setup_class(self):
        # credentials = ("client id", "client secret")
        self.credentials = (CLIENT_ID, CLIENT_SECRET)
        self.workbook_id = "B6EF05E2E8ABA433!646"
        self.protocol = MSGraphProtocol()
        con = Connection(self.credentials)
        main_resource = "drive/items"

        # Create Workbook Application
        self.workbook_app = WorkbookApplication(workbook_or_id=self.workbook_id, con=con, protocol=self.protocol, main_resource=main_resource)

    def teardown_class(self):
        pass

    def test_with_workbook(self):
        # wb = Workbook()
        pass

    def test_with_parent(self):
        pass

    def test_get(self):
        res = self.workbook_app.get_workbookapplication()
        print(res)

    def test_run_calculations(self):
        res = self.workbook_app.run_calculations("Recalculate")
        print(res)
