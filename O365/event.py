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

import logging
import json
import requests
import time

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Event( object ):
	'''
	Class for managing the creation and manipluation of events in a calendar. 
	
	Methods:
		create -- Creates the event in a calendar.
		update -- Sends local changes up to the cloud.
		delete -- Deletes event from the cloud.
		toJson -- returns the json representation.
		fullcalendarioJson -- gets a specific json representation used for fullcalendario.
		getSubject -- gets the subject of the event.
		getBody -- gets the body of the event.
		getStart -- gets the starting time of the event. (struct_time)
		getEnd -- gets the ending time of the event. (struct_time)
		getAttendees -- gets the attendees of the event.
		addAttendee -- adds an attendee to the event. update needs to be called for notification.
		setSubject -- sets the subject line of the event.
		setBody -- sets the body of the event.
		setStart -- sets the starting time of the event. (struct_time)
		setEnd -- sets the starting time of the event. (struct_time)
		setAttendees -- sets the attendee list.
		
	Variables:
		time_string -- Formated time string for translation to and from json.
		create_url -- url for creating a new event.
		update_url -- url for updating an existing event.
		delete_url -- url for deleting an event.
	'''
	#Formated time string for translation to and from json.
	time_string = '%Y-%m-%dT%H:%M:%SZ'
	#takes a calendar ID
	create_url = 'https://outlook.office365.com/api/v1.0/me/calendars/{0}/events'
	#takes current event ID
	update_url = 'https://outlook.office365.com/api/v1.0/me/events/{0}'
	#takes current event ID
	delete_url = 'https://outlook.office365.com/api/v1.0/me/events/{0}'


	def __init__(self,json=None,auth=None,cal=None):
		'''
		Creates a new event wrapper.
		
		Keyword Argument:
			json (default = None) -- json representation of an existing event. mostly just used by
			this library internally for events that are downloaded by the callendar class.
			auth (default = None) -- a (email,password) tuple which will be used for authentication
			to office365.
			cal (default = None) -- an instance of the calendar for this event to associate with.
		'''
		self.auth = auth
		self.calendar = cal
		self.attendees = []

		if json:
			self.json = json
			self.isNew = False
		else:
			self.json = {}


	def create(self,calendar=None):
		'''
		this method creates an event on the calender passed.

		IMPORTANT: It returns that event now created in the calendar, if you wish
		to make any changes to this event after you make it, use the returned value
		and not this particular event any further.
		
		calendar -- a calendar class onto which you want this event to be created. If this is left
		empty then the event's default calendar, specified at instancing, will be used. If no 
		default is specified, then the event cannot be created.
		
		'''
		if not self.auth:
			log.debug('failed authentication check when creating event.')
			return False

		if calendar:
			calId = calendar.calendarId
			self.calendar = calendar
			log.debug('sent to passed calendar.')
		elif self.calendar:
			calId = self.calendar.calendarId
			log.debug('sent to default calendar.')
		else:
			log.debug('no valid calendar to upload to.')
			return False

		headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

		log.debug('creating json for request.')
		data = json.dumps(self.json)

		response = None
		try:
			log.debug('sending post request now')
			response = requests.post(self.create_url.format(calId),data,headers=headers,auth=self.auth)
			log.debug('sent post request.')
		except Exception as e:
			if response:
				log.debug('response to event creation: %s',str(response))
			else:
				log.error('No response, something is very wrong with create: %s',str(e))
			return False

		log.debug('response to event creation: %s',str(response))
		return Event(response.json(),self.auth,calendar)

	def update(self):
		'''Updates an event that already exists in a calendar.'''
		if not self.auth:
			return False

		if self.calendar:
			calId = self.calendar.calendarId
		else:
			return False


		headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

		data = json.dumps(self.json)

		response = None
		try:
			response = requests.patch(self.update_url.format(self.json['Id']),data,headers=headers,auth=self.auth)
			log.debug('sending patch request now')
		except Exception as e:
			if response:
				log.debug('response to event creation: %s',str(response))
			else:
				log.error('No response, something is very wrong with update: %s',str(e))
			return False

		log.debug('response to event creation: %s',str(response))

		return Event(response.json(),self.auth)


	def delete(self):
		'''
		Delete's an event from the calendar it is in.
		
		But leaves you this handle. You could then change the calendar and transfer the event to 
		that new calendar. You know, if that's your thing.
		'''
		if not self.auth:
			return False

		headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

		response = None
		try:
			log.debug('sending delete request')
			response = requests.delete(self.delete_url.format(self.json['Id']),headers=headers,auth=self.auth)

		except Exception as e:
			if response:
				log.debug('response to deletion: %s',str(response))
			else:
				log.error('No response, something is very wrong with delete: %s',str(e))
			return False

		return response

	def toJson(self):
		'''
		Creates a JSON representation of the calendar event.
		
		oh. uh. I mean it simply returns the json representation that has always been in self.json.
		'''
		return self.json

	def fullcalendarioJson(self):
		'''
		returns a form of the event suitable for the vehicle booking system here.
		oh the joys of having a library to yourself! 
		'''
		ret = {}
		ret['title'] = self.json['Subject']
		ret['driver'] = self.json['Organizer']['EmailAddress']['Name']
		ret['driverEmail'] = self.json['Organizer']['EmailAddress']['Address']
		ret['start'] = self.json['Start']
		ret['end'] = self.json['End']
		ret['IsAllDay'] = self.json['IsAllDay']
		return ret

	def getSubject(self):
		'''Gets event subject line.'''
		return self.json['Subject']

	def getBody(self):
		'''Gets event body content.'''
		return self.json['Body']['Content']

	def getStart(self):
		'''Gets event start struct_time'''
		return time.strptime(self.json['Start'], self.time_string)

	def getEnd(self):
		'''Gets event end struct_time'''
		return time.strptime(self.json['End'], self.time_string)

	def getAttendees(self):
		'''Gets list of event attendees.'''
		return self.json['Attendees']

	def addAttendee(self,val):
		'''adds an attendee to the event. must call update for notification to send.'''
		self.json['Attendees'].append(val)

	def setSubject(self,val):
		'''sets event subject line.'''
		self.json['Subject'] = val

	def setBody(self,val):
		'''sets event body content.'''
		self.json['Body']['Content'] = val

	def setStart(self,val):
		'''sets event start struct_time.'''
		self.json['Start'] = time.strftime(self.time_string,val)

	def setEnd(self,val):
		'''sets event end struct_time.'''
		self.json['End'] = time.strftime(self.time_string,val)

	def setAttendees(self,val):
		'''sets event attendees list.'''
		self.json['Attendees'] = val

#To the King!
