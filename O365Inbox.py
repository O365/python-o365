import requests
import base64
import json
import logging
from O365 import *
from O365Message import Message

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Inbox( object ):
	#inbox_url = 'https://outlook.office365.com/EWS/OData/Me/Messages'
	inbox_url = 'https://outlook.office365.com/EWS/OData/Me/Messages?$filter=IsRead eq false'

	def __init__(self, email, password):
		log.debug('creating inbox for the email %s',email)
		self.auth = (email,password)
		self.messages = []

	def getMessages(self):
		log.debug('fetching messages.')
		response = requests.get(self.inbox_url,auth=self.auth)
		log.info('Response from O365: %s', str(response))
		
		for message in response.json()['value']:
			try:
				self.messages.append(Message(message,self.auth))
				log.debug('appended message: %s',message['Subject'])
			except Exception as e:
				log.info('failed to append message: %',str(e))
		
		log.debug('all messages retrieved and put in to the list.')
		return True
