"""
A simple python library to interact with Microsoft Graph and Office 365 API
"""
import warnings
import sys

from .__version__ import __version__

from .account import Account
from .connection import Connection, Protocol, MSGraphProtocol, MSOffice365Protocol
from .utils import FileSystemTokenBackend
from .message import Message


if sys.warnoptions:
    # allow Deprecation warnings to appear
    warnings.simplefilter('always', DeprecationWarning)
