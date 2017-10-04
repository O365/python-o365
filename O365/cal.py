import requests
import base64
import json
import logging
import time

from O365.event import Event

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
		events_url - the url that is actually called to fetch events. takes an ID, start, and end date.
		time_string - used for converting between struct_time and json's time format.
	'''
	events_url = 'https://outlook.office365.com/api/v1.0/me/calendars/{0}/calendarview?startDateTime={1}&endDateTime={2}&$top={3}'
	time_string = '%Y-%m-%dT%H:%M:%SZ'

	def __init__(self, json=None, auth=None, verify=True):
		'''
		Wraps all the information for managing calendars.
		'''
		self.json = json
		self.auth = auth
		self.events = []

		if json:
			log.debug('translating calendar information into local variables.')
			self.calendarId = json['Id']
			self.name = json['Name']

		self.verify = verify

	def getName(self):
		'''Get the calendar's Name.'''
		return self.json['Name']

	def getCalendarId(self):
		'''Get calendar's GUID for office 365. mostly used internally in this library.'''
		return self.json['Id']

	def getId(self):
		'''Get calendar's GUID for office 365. mostly used internally in this library.'''
		return self.getCalendarId()

	def fetchEvents(self,start=None,end=None):
		'''
		So I originally made this function "fetchEvents" which was a terrible idea. Everything else
		is "getX" except events which were appearenty to good for that. So this function is just a 
		pass through for legacy sake.
		'''
		return self.getEvents(start,end)


	def getEvents(self,start=None,end=None, eventCount=10):
		'''
		Pulls events in for this calendar. default range is today to a year now.
		
		Keyword Arguments:
		start -- The starting date from where you want to begin requesting events. The expected 
		type is a struct_time. Default is today.
		end -- The ending date to where you want to end requesting events. The expected 
		type is a struct_time. Default is a year from start.
		'''

		# If no start time has been supplied, it is assumed you want to start as of now.
		if not start:
			start = time.strftime(self.time_string)

		# If no end time has been supplied, it is assumed you want the end time to be a year
		# from what ever the start date was. 
		if not end:
			end = time.time()
			end += 3600*24*365
			end = time.gmtime(end)
			end = time.strftime(self.time_string,end)

		# This is where the actual call to Office365 happens.
		response = requests.get(self.events_url.format(self.json['Id'],start,end,eventCount) ,auth=self.auth, verify=self.verify)
		log.info('Response from O365: %s', str(response))
		
		#This takes that response and then parses it into individual calendar events.
		for event in response.json()['value']:
			try:
				duplicate = False

				# checks to see if the event is a duplicate. if it is local changes are clobbered.
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

# To the King!
