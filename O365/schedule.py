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

from O365 import Calendar
import logging
import json
import requests

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

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
	cal_url = 'https://outlook.office365.com/EWS/OData/Me/Calendars'

	def __init__(self, email, password):
		'''Creates a Schedule class for managing all calendars associated with email+password.'''
		log.debug('setting up for the schedule of the email %s',email)
		self.auth = (email,password)
		self.calendars = []


	def getCalendars(self):
		'''Begin the process of downloading calendar metadata.'''
		log.debug('fetching calendars.')
		response = requests.get(self.cal_url,auth=self.auth)
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
