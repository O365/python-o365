from O365.message import Message
import logging
import json
import requests

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Inbox( object ):
	#inbox_url = 'https://outlook.office365.com/EWS/OData/Me/Messages?$filter=IsRead eq {0}'
	inbox_url = 'https://outlook.office365.com/api/v1.0/me/messages?$filter=IsRead eq {0}'

	def __init__(self, email, password):
		log.debug('creating inbox for the email %s',email)
		self.auth = (email,password)
		self.messages = []
		self.getMessages()


	def getMessages(self,IsRead=False):
		'''
		You create an inbox to be the container class for messages, this method
		then pulls those messages down to the local disk. This is called in the
		init method, so it's kind of pointless for you. Unless you think new
		messages have come in.

		IsRead: Set this as True if you want to include messages that have been read.
		'''
		log.debug('fetching messages.')
		print self.inbox_url.format(str(IsRead).lower())
		response = requests.get(self.inbox_url.format(str(IsRead).lower()),auth=self.auth)
		log.info('Response from O365: %s', str(response))
		
		for message in response.json()['value']:
			try:
				self.messages.append(Message(message,self.auth))
				log.debug('appended message: %s',message['Subject'])
			except Exception as e:
				log.info('failed to append message: %',str(e))
		
		log.debug('all messages retrieved and put in to the list.')
		return True

#To the King!
