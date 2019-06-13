"""
A simple python library to interact with Microsoft Graph and Office 365 API
"""
import warnings

from .__version__ import __version__
from .account import Account
from .address_book import AddressBook, Contact, RecipientType
from .calendar import AttendeeType, EventSensitivity, EventShowAs
from .calendar import CalendarColor, EventAttachment
from .calendar import Schedule, Calendar, Event, EventResponse
from .connection import Connection, Protocol, MSGraphProtocol
from .connection import MSOffice365Protocol, oauth_authentication_flow
from .drive import Storage, Drive, Folder, File, Image, Photo
from .mailbox import MailBox
from .message import Message, MessageAttachment
from .sharepoint import Sharepoint, Site
from .planner import Planner, Task
from .excel import WorkBook
from .utils import ImportanceLevel, Query, Recipient
from .utils import OneDriveWellKnowFolderNames, OutlookWellKnowFolderNames
from .utils import FileSystemTokenBackend, FirestoreBackend


# allow Deprecation warnings to appear
warnings.simplefilter('always', DeprecationWarning)
