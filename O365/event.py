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
	#Formated time string for translation to and from json.
	time_string = '%Y-%m-%dT%H:%M:%SZ'
	#takes a calendar ID
	create_url = 'https://outlook.office365.com/api/v1.0/me/calendars/{0}/events'
	#takes current event ID
	update_url = 'https://outlook.office365.com/api/v1.0/me/events/{0}'
	#takes current event ID
	delete_url = 'https://outlook.office365.com/api/v1.0/me/events/{0}'


	def __init__(self,json=None,auth=None,cal=None):
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
		'''
		if not self.auth:
			return False

		if calendar:
			calId = calendar.calendarId
			self.calendar = calendar
		elif self.calendar:
			calId = self.calendar.calendarId
		else:
			return False

		headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

		try:
			self.json['Attendees'] = self.attendees
		except:
			return False

		log.debug('creating json for request.')
		data = json.dumps(req)

		try:
			log.debug('sending post request now')
			response = requests.post(self.create_url.format(calId),data,headers=headers,auth=self.auth)
		except:
			log.debug('response to event creation: %s',str(response))
			return False

		log.debug('response to event creation: %s',str(response))
		return Event(response.json(),self.auth,calendar)

	def update(self,calendar=None):
		'''
		This method updates an event that already exists in a calendar. It simply 
		re-uploads the local json, so change things before you call this function.
		'''
                if not self.auth:
                        return False

                if calendar:
                        calId = calendar.calendarId
                        self.calendar = calendar
                elif self.calendar:
                        calId = self.calendar.calendarId
                else:
                        return False


                headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

                try:
                        req = {}
                        req['Subject'] = self.subject
                        req['Body'] = {'ContentType':'HTML','Content':self.body}
                        req['Start'] = time.strftime(self.time_string,self.start)
                        req['End'] = time.strftime(self.time_string,self.end)
                        req['Attendees'] = self.attendees
                except:
                        return False

                log.debug('creating json for request.')
                data = json.dumps(req)

		try:
			response = requests.patch(self.update_url.format(self.Id),data,headers=headers,auth=self.auth)
			log.debug('sending patch request now')
		except:
			log.debug('response to event creation: %s',str(response))
			return False

		log.debug('response to event creation: %s',str(response))

		return Event(response.json(),self.auth)		


	def delete(self):
		'''
		delete's an event from the calendar it is in. But leaves you this handle.
		You could, in theory, then change the calendar and transfer the event to
		that new calendar. You know, if that's your thing.
		'''
		if not self.auth:
			return False
		if not self.Id:
			return False

		headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

		try:
			log.debug('sending delete request')
			response = requests.delete(self.delete_url.format(self.Id),headers=headers,auth=self.auth)
		except:
			return False
		finally:
			log.debug('response to deletion: %s',str(response))

		return response

	def toJson(self):
		'''
		Creates a JSON representation of the calendar event! oh. uh. I mean it
		simply returns the json representation that has always been in self.json.
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
		return self.json['Subject']

	def getBody(self):
		return self.json['Body']['Content']

	def getStart(self):
		return time.strptime(self.json['Start'], self.time_string)

	def getEnd(self):
		return time.strptime(self.json['End'], self.time_string)

	def getAttendees(self):
		return self.json['Attendees']

	def addAttendee(self,val):
		self.json['Attendees'].append(val)

	def setSubject(self,val):
		self.json['Subject'] = val

	def setBody(self,val):
		self.json['Body']['Content'] = val

	def setStart(self,val):
		self.json['Start'] = time.strftime(self.time_string,val)

	def setEnd(self,val):
		self.json['End'] = time.strftime(self.time_string,val)

	def setAttendees(self,val):
		self.json['Attendees'] = val

#To the King!
