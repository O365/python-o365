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

from O365.message import Message
import logging
import json
import requests

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

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
	inbox_url = 'https://outlook.office365.com/api/v1.0/me/messages?$filter=IsRead eq {0}'

	def __init__(self, email, password,getNow=True):
		'''
		Creates a new inbox wrapper. Send email and password for authentication.
		
		set getNow to false if you don't want to immedeatly download new messages.
		'''
		
		log.debug('creating inbox for the email %s',email)
		self.auth = (email,password)
		self.messages = []
		
		if getNow:
			self.getMessages()


	def getMessages(self,IsRead=False):
		'''
		Downloads messages to local memory.
		
		You create an inbox to be the container class for messages, this method
		then pulls those messages down to the local disk. This is called in the
		init method, so it's kind of pointless for you. Unless you think new
		messages have come in.

		IsRead: Set this as True if you want to include messages that have been read.
		'''

		log.debug('fetching messages.')
		response = requests.get(self.inbox_url.format(str(IsRead).lower()),auth=self.auth)
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

#To the King!
