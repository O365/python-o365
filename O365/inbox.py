from O365.message import Message
import logging
import json
import requests

log = logging.getLogger(__name__)

class Inbox( object ):
	'''
	Wrapper class for an inbox which mostly holds a list of messages.
	
	Methods:
		getMessages -- downloads messages to local memory.
		
	Variables: 
		inbox_url -- url used for fetching emails.
	'''
	#url for fetching emails. Takes a flag for whether they are read or not.
	inbox_url = 'https://outlook.office365.com/api/v1.0/me/messages'

	def __init__(self, auth, getNow=True, verify=True):
		'''
		Creates a new inbox wrapper. Send email and password for authentication.
		
		set getNow to false if you don't want to immedeatly download new messages.
		'''
		
		log.debug('creating inbox for the email %s',auth[0])
		self.auth = auth
		self.messages = []

		self.filters = ''
		self.verify = verify
		
		if getNow:
			self.filters = 'IsRead eq false'
			self.getMessages()

	def getMessages(self, number = 10):
		'''
		Downloads messages to local memory.
		
		You create an inbox to be the container class for messages, this method
		then pulls those messages down to the local disk. This is called in the
		init method, so it's kind of pointless for you. Unless you think new
		messages have come in.

		You can filter only certain emails by setting filters. See the set and
		get filters methods for more information.
		'''

		log.debug('fetching messages.')			
		response = requests.get(self.inbox_url,auth=self.auth,params={'$filter':self.filters, '$top':number},verify=self.verify)
		log.info('Response from O365: %s', str(response))
		
		for message in response.json()['value']:
			try:
				duplicate = False
				for i,m in enumerate(self.messages):
					if message['Id'] == m.json['Id']:
						self.messages[i] = Message(message,self.auth)
						duplicate = True
						break
				
				if not duplicate:
					self.messages.append(Message(message,self.auth))

				log.debug('appended message: %s',message['Subject'])
			except Exception as e:
				log.info('failed to append message: %',str(e))

		log.debug('all messages retrieved and put in to the list.')
		return True

	def getFilter(self):
		'''get the value set for a specific filter, if exists, else None'''
		return self.filters

	def setFilter(self,f_string):
		'''
		Set the value of a filter. More information on what filters are available
		can be found here:
		https://msdn.microsoft.com/office/office365/APi/complex-types-for-mail-contacts-calendar#RESTAPIResourcesMessage
		I may in the future have the ability to add these in yourself. but right now that is to complicated.
		
		Arguments:
			f_string -- The string that represents the filters you want to enact.
				should be something like: (HasAttachments eq true) and (IsRead eq false)
				or just: IsRead eq false
				test your filter stirng here: https://outlook.office365.com/api/v1.0/me/messages?$filter=
				if that accepts it then you know it works.
		'''
		self.filters = f_string
		return True

#To the King!
