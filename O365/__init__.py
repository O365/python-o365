"""
A simple python library to interact with Microsoft Graph and other MS api
"""

import warnings
import sys

from .__version__ import __version__

from .account import Account
from .connection import Connection, Protocol, MSGraphProtocol
from .utils import FileSystemTokenBackend, EnvTokenBackend
from .message import Message


if sys.warnoptions:
    # allow Deprecation warnings to appear
    warnings.simplefilter("always", DeprecationWarning)
