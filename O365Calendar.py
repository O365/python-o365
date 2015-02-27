import requests
import base64
import json
import logging
import time
#from O365Event import Event
from O365 import *

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
			

	def fetchEvents(self,start=None,end=None):
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

		print self.events_url.format(self.calendarId,start,end)
		response = requests.get(self.events_url.format(self.calendarId,start,end),auth=self.auth)
		log.info('Response from O365: %s', str(response))
		print 'Response from O365:', str(response)
		
		for event in response.json()['value']:
			try:
				log.debug('appended event: %s',event['Subject'])
				print 'appended message:',event['Subject']
			except Exception as e:
				log.info('failed to append calendar: %',str(e))
		
		log.debug('all events retrieved and put in to the list.')
		return True


#To the King!
