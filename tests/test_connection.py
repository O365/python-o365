from O365.connection import Connection, Protocol, MSGraphProtocol, MSOffice365Protocol
import pytest
import json

class TestProtocol:

    def setup_class(self):
        self.proto = Protocol(protocol_url="testing", api_version="0.0")

    def teardown_class(self):
        pass

    def test_blank_protocol(self):
        with pytest.raises(ValueError):
            p = Protocol()

    def test_to_api_case(self):
        assert(self.proto.to_api_case("CaseTest") == "case_test")

    def test_get_iana_tz(self):
        assert(self.proto.get_iana_tz('Greenwich Standard Time') == 'Atlantic/St_Helena')

class TestConnection:

    def setup_class(self):
        pass

    def teardown_class(self):
        pass

    def test_blank_connection(self):
        with pytest.raises(TypeError):
            c1 = Connection()

