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

'''
Python library for interfacing with the Microsoft Office 365 online. 
'''
#__all__ = ['attachment','cal','contact','event','group','inbox','message','schedule']

# This imports all the libraries into the local namespace. This makes it easy to work with.

from .contact import Contact
from .group import Group
from .cal import Calendar
from .event import Event
from .attachment import Attachment
from .inbox import Inbox
from .message import Message
from .schedule import Schedule
from .connection import Connection
from .fluent_inbox import FluentInbox


#To the King!

class O365 (object):
	_inbox = None

	def __init__(self,auth):
		self.auth = auth
		Connection.login(auth[0],auth[1])
	
	def newMessage(self):
		return Message(auth=self.auth)
	
	def newEvent(self):
		schedule = Schedule(self.auth)
		schedule.getCalendars()
		return Event(auth=self.auth,cal=schedule.calendars[0])

	@property
	def inbox(self):
		if not self._inbox:
			self._inbox = FluentInbox()
		return self._inbox


def login(username,password):
	return O365((username,password))
