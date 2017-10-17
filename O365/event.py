from O365.contact import Contact
from O365.group import Group
import logging
import json
import requests
import time

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
		setStartTimeZone -- sets the timezone for the start of the event item.
		setEndTimeZone -- sets the timezone for the end of the event item.
		
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


	def __init__(self,json=None,auth=None,cal=None,verify=True):
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

		self.verify = verify


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
			response = requests.post(self.create_url.format(calId),data,headers=headers,auth=self.auth,verify=self.verify)
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
			response = requests.patch(self.update_url.format(self.json['Id']),data,headers=headers,auth=self.auth,verify=self.verify)
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
			response = requests.delete(self.delete_url.format(self.json['Id']),headers=headers,auth=self.auth,verify=self.verify)

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

	def setSubject(self,val):
		'''sets event subject line.'''
		self.json['Subject'] = val

	def setBody(self,val,contentType='Text'):
		'''
			sets event body content:
				Examples for ContentType could be 'Text' or 'HTML'
		'''
		cont = False

		while not cont:
			try:
				self.json['Body']['Content'] = val
				self.json['Body']['ContentType'] = contentType
				cont = True
			except:
				self.json['Body'] = {}

	def setStart(self,val):
		'''
		sets event start time.
		
		Argument:
			val - this argument can be passed in three different ways. You can pass it in as a int
			or float, in which case the assumption is that it's seconds since Unix Epoch. You can
			pass it in as a struct_time. Or you can pass in a string. The string must be formated
			in the json style, which is %Y-%m-%dT%H:%M:%SZ. If you stray from that in your string
			you will break the library.
		'''
		if isinstance(val,time.struct_time):
			self.json['Start'] = time.strftime(self.time_string,val)
		elif isinstance(val,int):
			self.json['Start'] = time.strftime(self.time_string,time.gmtime(val))
		elif isinstance(val,float):
			self.json['Start'] = time.strftime(self.time_string,time.gmtime(val))
		else:
			#this last one assumes you know how to format the time string. if it brakes, check
			#your time string!
			self.json['Start'] = val

	def setEnd(self,val):
		'''
		sets event end time.
		
		Argument:
			val - this argument can be passed in three different ways. You can pass it in as a int
			or float, in which case the assumption is that it's seconds since Unix Epoch. You can
			pass it in as a struct_time. Or you can pass in a string. The string must be formated
			in the json style, which is %Y-%m-%dT%H:%M:%SZ. If you stray from that in your string
			you will break the library.
		'''
		if isinstance(val,time.struct_time):
			self.json['End'] = time.strftime(self.time_string,val)
		elif isinstance(val,int):
			self.json['End'] = time.strftime(self.time_string,time.gmtime(val))
		elif isinstance(val,float):
			self.json['End'] = time.strftime(self.time_string,time.gmtime(val))
		else:
			#this last one assumes you know how to format the time string. if it brakes, check
			#your time string!
			self.json['End'] = val

	def setAttendees(self,val):
		'''
		set the attendee list.
		
		val: the one argument this method takes can be very flexible. you can send:
			a dictionary: this must to be a dictionary formated as such:
				{"EmailAddress":{"Address":"recipient@example.com"}}
				with other options such ass "Name" with address. but at minimum it must have this.
			a list: this must to be a list of libraries formatted the way specified above,
				or it can be a list of libraries objects of type Contact. The method will sort
				out the libraries from the contacts. 
			a string: this is if you just want to throw an email address. 
			a contact: type Contact from this library. 
		For each of these argument types the appropriate action will be taken to fit them to the 
		needs of the library.
		'''
		self.json['Attendees'] = []
		if isinstance(val,list):
			self.json['Attendees'] = val
		elif isinstance(val,dict):
			self.json['Attendees'] = [val]
		elif isinstance(val,str):
			if '@' in val:
				self.addAttendee(val)
		elif isinstance(val,Contact):
			self.addAttendee(val)
		elif isinstance(val,Group):
			self.addAttendee(val)
		else:
			return False
		return True
	
	def setStartTimeZone(self,val):
		'''sets event start timezone'''
		self.json['StartTimeZone'] = val

	def setEndTimeZone(self,val):
		'''sets event end timezone'''
		self.json['EndTimeZone'] = val

	def addAttendee(self,address,name=None):
		'''
		Adds a recipient to the attendee list.
		
		Arguments:
		address -- the email address of the person you are sending to. <<< Important that.
			Address can also be of type Contact or type Group.
		name -- the name of the person you are sending to. mostly just a decorator. If you
			send an email address for the address arg, this will give you the ability
			to set the name properly, other wise it uses the email address up to the
			at sign for the name. But if you send a type Contact or type Group, this
			argument is completely ignored.
		'''
		if isinstance(address,Contact):
			self.json['Attendees'].append(address.getFirstEmailAddress())
		elif isinstance(address,Group):
			for con in address.contacts:
				self.json['Attendees'].append(address.getFirstEmailAddress())
		else:
			if name is None:
				name = address[:address.index('@')]
			self.json['Attendees'].append({'EmailAddress':{'Address':address,'Name':name}})

	def setLocation(self,loc):
		'''
		Sets the event's location.

		Arguments:
		loc -- two options, you can send a dictionary in the format discribed here:
		https://msdn.microsoft.com/en-us/office/office365/api/complex-types-for-mail-contacts-calendar#LocationBeta
		this will allow you to set address, coordinates, displayname, location email
		address, location uri, or any combination of the above. If you don't need that much
		detail you can simply send a string and it will be set as the locations display
		name. If you send something not a string or a dict, it will try to cast whatever
		you send into a string and set that as the display name.
		'''
		if 'Location' not in self.json:
			self.json['Location'] = {"Address":None}

		if isinstance(loc,dict):
			self.json['Location'] = loc
		else:
			self.json['Location']['DisplayName'] = str(loc)

	def getLocation(self):
		'''
		Get the current location, if one is set.
		'''
		if 'Location' in self.json:
			return self.json['Location']
		return None
		
			

#To the King!
