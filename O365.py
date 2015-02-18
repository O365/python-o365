import requests
import base64

class Inbox( object ):
	#inbox_url = 'https://outlook.office365.com/EWS/OData/Me/Messages'
	inbox_url = 'https://outlook.office365.com/EWS/OData/Me/Messages?$filter=IsRead eq false'

	def __init__(self, email, password):
		self.auth = (email,password)
		self.messages = []

	def getMessages(self):
		response = requests.get(self.inbox_url,auth=self.auth)
		print response
		
		for message in response.json()['value']:
			self.messages.append(Message(message,self.auth))
		
		return True


class Message( object ):
	att_url = 'https://outlook.office365.com/api/v1.0/me/messages/{0}/attachments'

	def __init__(self, json, auth):
		self.json = json
		self.auth = auth

		self.messageId = json['Id']
		self.sender = json['Sender']['EmailAddress']['Name']
		self.address = json['Sender']['EmailAddress']['Address']
		self.subject = json['Subject']
		self.body = json['Body']['Content']

		self.attachments = []
		self.hasAttachments = json['HasAttachments']

	def fetchAttachments(self):
		if not self.hasAttachments:
			return False

		response = requests.get(self.att_url.format(self.messageId),auth=self.auth)
		json = response.json()

		for att in json['value']:
			self.attachments.append(Attachment(att))

		return len(self.attachments)

class Attachment( object ):
	def __init__(self,json):
		self.json = json
		self.content = json['ContentBytes']
		self.name = json['Name']
		self.isPDF = '.pdf' in self.name.lower()
	
	def save(self,location):
		if not self.isPDF:
			return False
		try:
			outs = open(location+'/'+self.name,'wb')
			outs.write(base64.b64decode(self.content))
			outs.close()
		except:
			return False
		return True



if __name__ == '__main__':
	e = raw_input('Email: ')
	p = raw_input('Password: ')
	print(e,p)
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

	














#######################################################################
"""
JSON Layout:
Top Level:
@odata.context:string
value:list

in side value is where all the messages are stored as a list.

Message layout:
@odata.id:string
@odata.etag@:string
Id: string
ChangeKey:string
Categories: list
DateTimeCreated: string "YYYY-MM-DD HH:MM:SS"
DateTimeLastModified: string
Subject: String
BodyPreview: String
Body: Library
Importance: string
HasAttachments: bool
ParentFolderId: String
From: Library
Sender: Library
ToRecipients: list
CcRecipients: list
BccRecipients: list
ReplyTo: list
ConversationId: String
DateTimeRecieved: string
DateTimeSent: String
IsDeliveryReceiptRequested: bool or null
IsReadReciptRequested: bool
IsDraft: bool
IsRead: bool

"""
#########################################################################
