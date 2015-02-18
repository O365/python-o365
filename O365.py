import requests
import base64
import json
import logging

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

class Attachment( object ):
	def __init__(self,json):
		self.json = json
		self.content = json['ContentBytes']
		self.name = json['Name']
		self.isPDF = '.pdf' in self.name.lower()
	
	def save(self,location):
		if not self.isPDF:
			log.debug('we only work with PDFs.')
			return False
		try:
			outs = open(location+'/'+self.name,'wb')
			outs.write(base64.b64decode(self.content))
			outs.close()
			log.debug('file saved locally.')
			
		except Exception as e:
			log.debug('file failed to be saved: %s',str(e))
			return False

		log.debug('file saving successful')
		return True



if __name__ == '__main__':
	#e = raw_input('Email: ')
	#p = raw_input('Password: ')
	#print(e,p)

	config = open('./ep.pw','r').read()
	cjson = json.loads(config)
	print cjson

	e = cjson ['email']
	p = cjson ['password']

	i = Inbox(e,p)
	i.getMessages()
	for j in i.messages:
		print j.subject
	print len(i.messages)


	m = i.messages[0]
	print m.fetchAttachments()
	a = None
	for j in m.attachments:
		print j.name, j.isPDF
		if j.isPDF:
			a = j

	print "saved attachment: ", a.save('/home/toby.archer')
