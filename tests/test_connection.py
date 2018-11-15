import pytest
import json

from O365.connection import Connection, Protocol, MSGraphProtocol, MSOffice365Protocol, DEFAULT_SCOPES


class TestConnection:

    def setup_class(self):
        pass

    def teardown_class(self):
        pass

    def test_blank_connection(self):
        with pytest.raises(TypeError):
            c1 = Connection()

