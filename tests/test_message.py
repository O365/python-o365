
from O365 import message
import unittest
import json

class Attachment:
	'''mock up Message class'''
	def __init__(self,json):
		self.json = json

message.Attachment = Attachment

class Resp:
	def __init__(self,json_string):
		self.jsons = json_string

	def json(self):
		return json.loads(self.jsons)

read_rep = open('read_message.json','r').read()
un_rep = open('unread_message.json','r').read()
att_m_rep = open('attachment_message.json','r').read()
att_rep = open('attachment.json','r').read()

def get(url,**params):
	if url == 'https://outlook.office365.com/api/v1.0/me/messages/bigoldguid/attachments':
		ret = Resp(att_rep)
	else:
		raise
	if params['auth'][0] != 'test@unit.com':
		raise
	if params['auth'][1] != 'pass':
		raise

	return ret

message.requests.get = get

def post(url,data,headers,auth):
	if url != 'https://outlook.office365.com/api/v1.0/me/sendmail':
		raise
		if auth[0] != 'test@unit.com':
				raise
		if auth[1] != 'pass':
				raise
	if headers['Content-type'] != 'application/json':
		raise
	if headers['Accept'] != 'text/plain':
		raise	

	return True

message.requests.post = post

def patch(url,data,headers,auth):
	if url != 'https://outlook.office365.com/api/v1.0/me/messages/big guid=':
				raise
		if auth[0] != 'test@unit.com':
				raise
		if auth[1] != 'pass':
				raise
	if headers['Content-type'] != 'application/json':
		raise
	if headers['Accept'] != 'application/json':
		raise	
	return True

message.requests.patch = patch

auth = ('test@unit.com','pass')

class TestMessage (unittest.TestCase):
	
	def setUp(self):
		ur = json.loads(un_rep)['value'][0]
		self.unread = message.Message(ur,auth)
		re = json.loads(read_rep)['value'][0]
		self.read = message.Message(re,auth)
		att = json.loads(att_m_rep)['value'][0]
		self.att = message.Message(att,auth)

	def test_fetchAttachments(self):
		self.assertTrue(len(self.att.attachments) == 0)
		self.assertTrue(len(self.unread.attachments) == 0)
		self.assertTrue(len(self.read.attachments) == 0)

		self.assertEqual(1,self.att.fetchAttachments())
		self.assertEqual(0,self.unread.fetchAttachments())
		self.assertEqual(0,self.read.fetchAttachments())

		self.assertTrue(len(self.att.attachments) == 1)
		self.assertTrue(len(self.unread.attachments) == 0)
		self.assertTrue(len(self.read.attachments) == 0)

	def test_sendMessage(self):
		self.read.sendMessage()

	def test_markAsRead(self):
		self.unread.markAsRead()

	def test_setRecipients(self):
		self.assertTrue(len(self.read.json['ToRecipients']) == 1)
		self.assertTrue(len(self.unread.json['ToRecipients']) == 1)
		self.assertTrue(len(self.att.json['ToRecipients']) == 1)

		self.read.setRecipients('bob@unit.com')
		self.assertTrue(self.read.json['ToRecipients'][0]['EmailAddress']['Address'] == 'bob@unit.com')

		self.unread.setRecipients({'EmailAddress':{'Address':'bob@unit.com','Name':'What about'}})		
		self.assertTrue(self.unread.json['ToRecipients'][0]['EmailAddress']['Address'] == 'bob@unit.com')
		self.assertTrue(self.unread.json['ToRecipients'][0]['EmailAddress']['Name'] == 'What about')

		self.att.setRecipients([{'EmailAddress':{'Address':'bob@unit.com','Name':'What about'}}])
		self.assertTrue(self.att.json['ToRecipients'][0]['EmailAddress']['Address'] == 'bob@unit.com')
		self.assertTrue(self.att.json['ToRecipients'][0]['EmailAddress']['Name'] == 'What about')

	def test_addRecipient(self):
		self.assertTrue(len(self.read.json['ToRecipients']) == 1)

		self.read.addRecipient('later','second@unit.com')

		self.assertTrue(len(self.read.json['ToRecipients']) == 2)

		self.assertTrue(self.read.json['ToRecipients'][1]['EmailAddress']['Address'] == 'second@unit.com')
		self.assertTrue(self.read.json['ToRecipients'][1]['EmailAddress']['Name'] == 'later')

	def test_auth(self):
		self.assertEqual(auth[0],self.read.auth[0])
		self.assertEqual(auth[1],self.read.auth[1])
		self.assertEqual(auth[0],self.unread.auth[0])
		self.assertEqual(auth[1],self.unread.auth[1])
		self.assertEqual(auth[0],self.att.auth[0])
		self.assertEqual(auth[1],self.att.auth[1])

if __name__ == '__main__':
	unittest.main()
