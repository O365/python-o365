"""
A simple python library to interact with Microsoft Graph and Office 365 API
"""
from .__version__ import __version__

from .account import Account
from .connection import Connection, Protocol, MSGraphProtocol, MSOffice365Protocol, oauth_authentication_flow
from .mailbox import MailBox
from .message import Message, MessageAttachment, Recipient
from .address_book import AddressBook, Contact, RecipientType
from .calendar import Schedule, Calendar, Event, EventResponse, AttendeeType, EventSensitivity, EventShowAs, CalendarColors, EventAttachment
from .drive import Storage, Drive, Folder, File, Image, Photo
from .utils import OneDriveWellKnowFolderNames, OutlookWellKnowFolderNames, ImportanceLevel
from .sharepoint import Sharepoint, Site
