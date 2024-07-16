import pytest

from O365.utils import Recipient


class TestRecipient:
    def setup_class(self):
        pass

    def teardown_class(self):
        pass

    def test_recipient_str(self):
        recipient = Recipient()
        assert str(recipient) == ""

        recipient = Recipient(address="john@example.com")
        assert str(recipient) == "john@example.com"

        recipient = Recipient(address="john@example.com", name="John Doe")
        assert str(recipient) == "John Doe <john@example.com>"
