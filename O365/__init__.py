"""
A simple python library to interact with Microsoft Graph and Office 365 API
"""
import warnings

from .__version__ import __version__

from .account import Account
from .connection import Connection, Protocol, MSGraphProtocol, MSOffice365Protocol
from .utils import FileSystemTokenBackend
from .message import Message


# allow Deprecation warnings to appear
warnings.simplefilter('always', DeprecationWarning)
