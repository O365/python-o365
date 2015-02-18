import requests
import base64
import json
import logging
from attachment import Attachment

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Message( object ):
	att_url = 'https://outlook.office365.com/api/v1.0/me/messages/{0}/attachments'

	def __init__(self, json, auth):
		'''
		Wraps all the informaiton for receiving messages.
		'''
		self.json = json
		self.auth = auth

		log.debug('translating message information into local variables.')
		self.messageId = json['Id']
		self.sender = json['Sender']['EmailAddress']['Name']
		self.address = json['Sender']['EmailAddress']['Address']
		self.subject = json['Subject']
		self.body = json['Body']['Content']

		self.attachments = []
		self.hasAttachments = json['HasAttachments']

	def fetchAttachments(self):
		if not self.hasAttachments:
			log.debug('message has no attachments, skipping out early.')
			return False

		response = requests.get(self.att_url.format(self.messageId),auth=self.auth)
		log.info('response from O365 for retriving message attachments: %s',str(response))
		json = response.json()

		for att in json['value']:
			try:
				self.attachments.append(Attachment(att))
				log.debug('successfully downloaded attachment for: %s.',self.auth[0])
			except Exception as e:
				log.info('failed to download attachment for: %s', self.auth[0])

		return len(self.attachments)
