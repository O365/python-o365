from O365 import *
import logging
import json
import requests

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Schedule( object ):
	cal_url = 'https://outlook.office365.com/EWS/OData/Me/Calendars'

	def __init__(self, email, password):
		log.debug('setting up for the schedule of the email %s',email)
		self.auth = (email,password)
		self.calendars = []

	def getCalendars(self):
		log.debug('fetching calendars.')
		response = requests.get(self.cal_url,auth=self.auth)
		log.info('Response from O365: %s', str(response))
		print 'Response from O365:', str(response)
		
		for calendar in response.json()['value']:
			try:
				log.debug('appended calendar: %s',calendar['Name'])
				self.calendars.append(Calendar(calendar,self.auth))
				print 'appended message:',calendar['Name']
			except Exception as e:
				log.info('failed to append calendar: %',str(e))
		
		log.debug('all calendars retrieved and put in to the list.')
		return True

#To the King!
