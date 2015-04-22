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

from O365.event import Event

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Calendar( object ):
	'''
	Calendar manages lists of events on an associated calendar on office365.
	
	Methods:
		getName - Returns the name of the calendar.
		getCalendarId - returns the GUID that identifies the calendar on office365
		getId - synonym of getCalendarId
		getEvents - kicks off the process of fetching events.
		fetchEvents - legacy duplicate of getEvents
	
	Variable:
		events_url - the url that is actually called to fetch events. takes an ID, start, and end.
		time_string - used for converting between struct_time and json's time format.
	'''
	events_url = 'https://outlook.office365.com/api/v1.0/me/calendars/{0}/calendarview?startDateTime={1}&endDateTime={2}'
	time_string = '%Y-%m-%dT%H:%M:%SZ'

	def __init__(self, json=None, auth=None):
		'''
		Wraps all the informaiton for managing calendars.
		'''
		self.json = json
		self.auth = auth
		self.events = []

		if json:
			log.debug('translating calendar information into local variables.')
			self.calendarId = json['Id']
			self.name = json['Name']

	def getName(self):
		'''Get the calendar's Name.'''
		return self.json['Name']

	def getCalendarId(self):
		'''Get calendar's GUID for office 365. mostly used interally in this library.'''
		return self.json['Id']

	def getId(self):
		'''Get calendar's GUID for office 365. mostly used interally in this library.'''
		return self.getCalendarId()

	def fetchEvents(self,start=None,end=None):
		'''
		So I originally made this function "fetchEvents" which was a terrible idea. Everything else
		is "getX" except events which were appearenty to good for that. So this function is just a 
		pass through for legacy sake.
		'''
		return self.getEvents(start,end)


	def getEvents(self,start=None,end=None):
		'''
		Pulls events in for this calendar. default range is today to a year now.
		
		Keyword Arguments:
		start -- The starting date from where you want to begin requesting events. The expected 
		type is a struct_time. Default is today.
		end -- The ending date to where you want to end requesting events. The expected 
		type is a struct_time. Default is a year from start.
		'''

		#If no start time has been supplied, it is assumed you want to start as of now.
		if not start:
			start = time.strftime(self.time_string)

		#If no end time has been supplied, it is assumed you want the end time to be a year
		#from what ever the start date was. 
		if not end:
			end = time.time()
			end += 3600*24*365
			end = time.gmtime(end)
			end = time.strftime(self.time_string,end)

		#This is where the actual call to Office365 happens.
		response = requests.get(self.events_url.format(self.json['Id'],start,end),auth=self.auth)
		log.info('Response from O365: %s', str(response))
		
		#This takes that response and then parses it into individual calendar events.
		for event in response.json()['value']:
			try:
				duplicate = False

				#checks to see if the event is a duplicate. if it is local changes are clobbered.
				for i,e in enumerate(self.events):
					if e.json['Id'] == event['Id']:
						self.events[i] = Event(event,self.auth,self)
						duplicate = True
						break

				if not duplicate:
					self.events.append(Event(event,self.auth,self))
				
				log.debug('appended event: %s',event['Subject'])
			except Exception as e:
				log.info('failed to append calendar: %',str(e))
		
		log.debug('all events retrieved and put in to the list.')
		return True

#To the King!
