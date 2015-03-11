from O365 import *
import logging
import json
import requests
import time

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Event( object ):
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
		if json:
			self.json = json
			self.subject = json['Subject']
			self.body = json['BodyPreview']
			self.start = time.strptime(json['Start'], self.time_string)
			self.end = time.strptime(json['End'], self.time_string)
			self.Id = json['Id']
			self.isNew = False
			self.attendees = json['Attendees']
		else:
			self.isNew = True
			self.subject = ''
			self.body = ''
			self.start = time.localtime()
			self.start = time.localtime()
			self.attendees = []


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
			log.debug('sending post request now')
			response = requests.post(self.create_url.format(calId),data,headers=headers,auth=self.auth)
		except:
			log.debug('response to event creation: %s',str(response))
			return False

		log.debug('response to event creation: %s',str(response))
		return Event(response.json(),self.auth,calendar)

	def update(self,calendar=None):
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
			log.debug('sending patch request now')
			response = requests.patch(self.update_url.format(self.Id),data,headers=headers,auth=self.auth)
		except:
			log.debug('response to event creation: %s',str(response))
			return False

		log.debug('response to event creation: %s',str(response))

		return Event(response.json(),self.auth)		


	def delete(self):
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

	def updateJson(self):
		try:
			self.json['Subject'] = self.subject
			self.json['Body'] = {'ContentType':'HTML','Content':self.body}
			self.json['Start'] = time.strftime(self.time_string,self.start)
			self.json['End'] = time.strftime(self.time_string,self.end)
			self.json['Attendees'] = self.attendees
			self.json['Id'] = self.Id
			return True
		except:
			return False

	def toJson(self):
		return self.json

#To the King!

