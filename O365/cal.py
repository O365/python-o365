from O365.event import Event
import requests
import base64
import json
import time

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
		events_url - the url that is actually called to fetch events. takes an ID, start, end date, and max number (between 1 and 50).
		time_string - used for converting between struct_time and json's time format.
	'''
	events_url = 'https://outlook.office365.com/api/v1.0/me/calendars/{0}/calendarview?startDateTime={1}&endDateTime={2}&$top={3}'
	time_string = '%Y-%m-%dT%H:%M:%SZ'
	timemorning_string = '%Y-%m-%dT00:00:00Z'

	def __init__(self, json=None, auth=None):
		'''
		Wraps all the information for managing calendars.
		'''
		self.json = json
		self.auth = auth
		self.events = []

		if json:
			self.calendarId = json['Id']
			self.name = json['Name']

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


	def getEvents(self,start=None,end=None,top=None):
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
		
		if not top:
			top = 20

		# This is where the actual call to Office365 happens.
		response = requests.get(self.events_url.format(self.json['Id'],start,end,top),auth=self.auth)
		
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
				
			except Exception as e:
				print('failed to append calendar: %',str(e))
		
		return True
