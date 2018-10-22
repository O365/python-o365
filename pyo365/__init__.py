# Copyright 2018 by Janscas. All Rights Reserved.
# Copyright 2015 by Toben "Narcolapser" Archer. All Rights Reserved.
#
# Permission to use, copy, modify, and distribute this software and its documentation for any purpose 
# and without fee is hereby granted, provided that the above copyright notice appear in all copies and 
# that both that copyright notice and this permission notice appear in supporting documentation, and 
# that the name of Toben Archer not be used in advertising or publicity pertaining to distribution of 
# the software without specific, written prior permission. TOBEN ARCHER DISCLAIMS ALL WARRANTIES WITH 
# REGARD TO THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT 
# SHALL TOBEN ARCHER BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES 
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE 
# OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""
Python library for interfacing with the Microsoft Office 365 online. 
"""

from .account import Account
from .connection import Connection, Protocol, MSGraphProtocol, MSOffice365Protocol
from .mailbox import MailBox
from .message import Message, MessageAttachment, Recipient
from .address_book import AddressBook, Contact, RecipientType
from .calendar import Schedule, Calendar, Event, EventResponse, AttendeeType, EventSensitivity, EventShowAs, CalendarColors, EventAttachment
from .drive import Storage, Drive, Folder, File, Image, Photo
from .utils import OneDriveWellKnowFolderNames, OutlookWellKnowFolderNames, ImportanceLevel
