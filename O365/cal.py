import requests
import base64
import json
import logging
import time

from O365.event import Event

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Calendar( object ):
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
		return self.json['Name']

	def getCalendarId(self):
		return self.calendarId['Id']

	def getId(self):
		return self.getCalendarId()

	def fetchEvents(self,start=None,end=None):
		'''
		So I originally made this function "fetchEvents" which was a terrible idea. Everything else is "getX" except
		events which were appearenty to good for that. So this function is just a pass through for legacy sake.
		'''
		return self.getEvents(start,end)


	def getEvents(self,start=None,end=None):
		'''
		Pulls events in for this calendar. default range is today to a year now.
		'''

		if not start:
			start = time.strftime(self.time_string)

		if not end:
			end = time.time()
			end += 3600*24*365.25
			end = time.gmtime(end)
			end = time.strftime(self.time_string,end)

		response = requests.get(self.events_url.format(self.json['Id'],start,end),auth=self.auth)
		log.info('Response from O365: %s', str(response))
		
		for event in response.json()['value']:
			try:
				log.debug('appended event: %s',event['Subject'])
				self.events.append(Event(event,self.auth,self))
			except Exception as e:
				log.info('failed to append calendar: %',str(e))
		
		log.debug('all events retrieved and put in to the list.')
		return True

#To the King!
