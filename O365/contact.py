import requests
import base64
import json
import logging
import time

log = logging.getLogger(__name__)

class Contact( object ):
	'''
	Contact manages lists of events on an associated contact on office365.
	
	Methods:
		getName - Returns the name of the contact.
		getContactId - returns the GUID that identifies the contact on office365
		getId - synonym of getContactId
		getContacts - kicks off the process of fetching contacts.
	
	Variable:
		events_url - the url that is actually called to fetch events. takes an ID, start, and end.
		time_string - used for converting between struct_time and json's time format.
	'''
	con_url = 'https://outlook.office365.com/api/v1.0/me/contacts/{0}'
	time_string = '%Y-%m-%dT%H:%M:%SZ'

	def __init__(self, json=None, auth=None, verify=True):
		'''
		Wraps all the informaiton for managing contacts.
		'''
		self.json = json
		self.auth = auth

		if json:
			log.debug('translating contact information into local variables.')
			self.contactId = json['Id']
			self.name = json['DisplayName']
		else:
			log.debug('there was no json, putting in some dumby info.')
			self.json = {'DisplayName':'Jebediah Kerman'}

		self.verify = verify

	def delete(self):
		'''delete's a contact. cause who needs that guy anyway?'''
		headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

		log.debug('preparing to delete contact.')
		response = requests.delete(self.con_url.format(str(self.contactId)),headers=headers,auth=self.auth,verify=self.verify)
		log.debug('response from delete attempt: {0}'.format(str(response)))

		return response.status_code == 204

	def update(self):
		'''updates a contact with information in the local json.'''
		if not self.auth:
			log.debug('no authentication information, cannot update')
			return false

		headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

		data = json.dumps(self.json)

		response = None
		try:
			response = requests.patch(self.con_url.format(str(self.contactId)),data,headers=headers,auth=self.auth,verify=self.verify)
			log.debug('sent update request')
		except Exception as e:
			if response:
				log.debug('response to contact update: {0}'.format(str(response)))
			else:
				log.error('No response, something is very wrong with update: {0}'.format(str(e)))
			return False

		log.debug('Response to contact update: {0}'.format(str(response)))

		return Contact(response.json(),self.auth)

	def create(self):
		'''create a contact with information in the local json.'''
		if not self.auth:
			log.debug('no authentication information, cannot create')
			return false

		headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

		data = json.dumps(self.json)

		response = None
		try:
			response = requests.post(self.con_url.format(str(self.contactId)),data,headers=headers,auth=self.auth,verify=self.verify)
			log.debug('sent create request')
		except Exception as e:
			if response:
				log.debug('response to contact create: {0}'.format(str(response)))
			else:
				log.error('No response, something is very wrong with create: {0}'.format(str(e)))
			return False

		log.debug('Response to contact create: {0}'.format(str(response)))

		return Contact(response.json(),self.auth)

	def getContactId(self):
		'''Get contact's GUID for office 365. mostly used interally in this library.'''
		return self.json['Id']

	def getId(self):
		'''Get contact's GUID for office 365. mostly used interally in this library.'''
		return self.getContactId()

	def getName(self):
		'''Get the contact's Name.'''
		return self.json['DisplayName']

	def setName(self,val):
		'''sets the display name of the contact.'''
		self.json['DisplayName'] = val

	def getFirstEmailAddress(self):
		'''Get the contact's first Email address. returns just the email address.'''
		return self.json['EmailAddresses'][0]['Address']

	def getEmailAdresses(self):
		'''Get's all the contacts email addresses. returns a list of strings.'''
		ret = []
		for e in self.json['EmailAddresses']:
			ret.append(e['Address'])

	def getEmailAddress(self,loc):
		'''
		This method will return the email address, text only, from the specified location.
		As the order in which the addresses may have downloaded is non-deterministic, it can
		not be garunteed that the nth address will be in the same position each time.
		'''
		return self.json['EmailAddresses'][loc]['Address']

	def setEmailAddress(self,val,loc):
		'''
		Sets the email address of the specified index. The download of this information may
		not be the same each time, so besure you know which address you are editing before 
		you use this method.
		'''
		self.json['EmailAddress'][loc]['Address']

	def getFirstEmailInfo(self):
		'''gets an email address and it's associated date for the first email address.'''
		return self.json['EmailAddresses'][0]

	def getAllEmailInfo(self):
		'''Gets email addresses and any data that goes with it such as name, returns dict'''
		return self.json['EmaillAddresses']

	def setEmailInfo(self,val):
		'''set the list of email addresses. Must be formated as such:
		[{"Address":"youremail@example.com","Name","your name"},{and the next]
		this replaces current inplace email address information.
		'''
		self.json['EmailAddresses'] = val

	def addEmail(self,address,name=None):
		'''takes a plain string email, and optionally name, and appends it to list.'''
		ins = {'Address':address,'Name':None}

#To the King!
