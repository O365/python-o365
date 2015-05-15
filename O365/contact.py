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

import requests
import base64
import json
import logging
import time

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Contact( object ):
	'''
	Contact manages lists of events on an associated contact on office365.
	
	Methods:
		getName - Returns the name of the contact.
		getContactId - returns the GUID that identifies the contact on office365
		getId - synonym of getContactId
		getEvents - kicks off the process of fetching events.
		fetchEvents - legacy duplicate of getEvents
	
	Variable:
		events_url - the url that is actually called to fetch events. takes an ID, start, and end.
		time_string - used for converting between struct_time and json's time format.
	'''
	con_url = 'https://outlook.office365.com/api/v1.0/me/contacts'
	time_string = '%Y-%m-%dT%H:%M:%SZ'

	def __init__(self, json=None, auth=None):
		'''
		Wraps all the informaiton for managing contacts.
		'''
		self.json = json
		self.auth = auth

		if json:
			log.debug('translating contact information into local variables.')
			self.contactId = json['Id']
			self.name = json['DisplayName']

	def getName(self):
		'''Get the contact's Name.'''
		return self.json['DisplayName']

	def getContactId(self):
		'''Get contact's GUID for office 365. mostly used interally in this library.'''
		return self.json['Id']

	def getId(self):
		'''Get contact's GUID for office 365. mostly used interally in this library.'''
		return self.getContactId()

	def getFirstEmailAddress(self):
		'''Get the contact's first Email address. returns just the email address.'''
		return self.json['EmailAddresses'][0]['Address']

	def getEmailAdresses(self):
		'''Get's all the contacts email addresses. returns a list of strings.'''
		ret = []
		for e in self.json['EmailAddresses']:
			ret.append(e['Address'])

	def getFirstEmailInfo(self):
		'''gets an email address and it's associated date for the first email address.'''
		return self.json['EmailAddresses'][0]

	def getAllEmailInfo(self):
		'''Gets email addresses and any data that goes with it such as name, returns dict'''
		return self.json['EmaillAddresses']

#To the King!
