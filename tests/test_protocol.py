import pytest
import json

from zoneinfo import ZoneInfoNotFoundError
from tzlocal import get_localzone

from O365.connection import Connection, Protocol, MSGraphProtocol, MSOffice365Protocol, DEFAULT_SCOPES

TEST_SCOPES = [
    'Calendars.Read', 'Calendars.Read.Shared', 'Calendars.ReadWrite', 'Calendars.ReadWrite.Shared',
    'Contacts.Read', 'Contacts.Read.Shared', 'Contacts.ReadWrite', 'Contacts.ReadWrite.Shared',
    'Files.Read.All', 'Files.ReadWrite.All',
    'Mail.Read', 'Mail.Read.Shared', 'Mail.ReadWrite', 'Mail.ReadWrite.Shared', 'Mail.Send', 'Mail.Send.Shared',
    'MailboxSettings.ReadWrite',
    'Presence.Read',
    'Sites.Read.All', 'Sites.ReadWrite.All',
    'Tasks.Read', 'Tasks.ReadWrite',
    'User.Read', 'User.ReadBasic.All',
    'offline_access'
    ]

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
    
    def test_get_scopes_for(self):
        with pytest.raises(ValueError):
            self.proto.get_scopes_for(123) # should error sicne it's not a list or tuple.
            
        assert(self.proto.get_scopes_for(['mailbox']) == ['mailbox'])
        
        assert(self.proto.get_scopes_for(None) == [])
        
        assert(self.proto.get_scopes_for('mailbox') == ['mailbox'])
        
        self.proto._oauth_scopes = DEFAULT_SCOPES
        
        assert(self.proto.get_scopes_for(['mailbox']) == ['Mail.Read'])
        
        # This test verifies that the scopes in the default list don't change
        #without us noticing. It makes sure that all the scopes we get back are 
        #in the current set of scopes we expect. And all the scopes that we are
        #expecting are in the scopes we are getting back. The list contains the
        #same stuff but may not be in the same order and are therefore not equal
        scopes = self.proto.get_scopes_for(None)
        for scope in scopes:
            assert(scope in TEST_SCOPES)
        for scope in TEST_SCOPES:
            assert(scope in scopes)
        
        assert(self.proto.get_scopes_for('mailbox') == ['Mail.Read'])

    def test_prefix_scope(self):
        assert(self.proto.prefix_scope('Mail.Read') == 'Mail.Read')
        
        self.proto.protocol_scope_prefix = 'test_prefix_'

        assert(self.proto.prefix_scope('test_prefix_Mail.Read') == 'test_prefix_Mail.Read')
        
        assert(self.proto.prefix_scope('Mail.Read') == 'test_prefix_Mail.Read')

    def test_decendant_MSOffice365Protocol(self):
        # Basically we just test that it can create the class w/o erroring.
        msp = MSOffice365Protocol()
        
        # Make sure these don't change without going noticed.
        assert(msp.keyword_data_store['message_type'] == 'Microsoft.OutlookServices.Message')
        assert(msp.keyword_data_store['file_attachment_type'] == '#Microsoft.OutlookServices.FileAttachment')
        assert(msp.keyword_data_store['item_attachment_type'] == '#Microsoft.OutlookServices.ItemAttachment')
        assert(msp.max_top_value == 999)
