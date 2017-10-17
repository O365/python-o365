from O365.cal import Calendar
import logging
import json
import requests

log = logging.getLogger(__name__)

class Schedule( object ):
	'''
	A wrapper class that handles all the Calendars associated with a sngle Office365 account.
	
	Methods:
		constructor -- takes your email and password for authentication.
		getCalendars -- begins the actual process of downloading calendars.
	
	Variables:
		cal_url -- the url that is requested for the retrival of the calendar GUIDs.
	'''
	cal_url = 'https://outlook.office365.com/api/v1.0/me/calendars'

	def __init__(self, auth, verify=True):
		'''Creates a Schedule class for managing all calendars associated with email+password.'''
		log.debug('setting up for the schedule of the email %s',auth[0])
		self.auth = auth
		self.calendars = []

		self.verify = verify


	def getCalendars(self):
		'''Begin the process of downloading calendar metadata.'''
		log.debug('fetching calendars.')
		response = requests.get(self.cal_url,auth=self.auth,verify=self.verify)
		log.info('Response from O365: %s', str(response))
		
		for calendar in response.json()['value']:
			try:
				duplicate = False
				log.debug('Got a calendar with Name: {0} and Id: {1}'.format(calendar['Name'],calendar['Id']))
				for i,c in enumerate(self.calendars):
					if c.json['Id'] == calendar['Id']:
						c.json = calendar
						c.name = calendar['Name']
						c.calendarId = calendar['Id']
						duplicate = True
						log.debug('Calendar: {0} is a duplicate',calendar['Name'])
						break

				if not duplicate:
					self.calendars.append(Calendar(calendar,self.auth))
					log.debug('appended calendar: %s',calendar['Name'])

				log.debug('Finished with calendar {0} moving on.'.format(calendar['Name']))

			except Exception as e:
				log.info('failed to append calendar: {0}'.format(str(e)))
		
		log.debug('all calendars retrieved and put in to the list.')
		return True

#To the King!
