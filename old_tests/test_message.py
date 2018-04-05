
from O365 import message
import unittest
import json

class Attachment:
	'''mock up Message class'''
	def __init__(self,json):
		self.json = json

message.Attachment = Attachment

class Resp:
	def __init__(self,json_string,code=200):
		self.jsons = json_string
		self.status_code = code

	def json(self):
		return json.loads(self.jsons)

read_rep = open('read_message.json','r').read()
un_rep = open('unread_message.json','r').read()
att_m_rep = open('attachment_message.json','r').read()
att_rep = open('attachment.json','r').read()
new_rep = open('newmessage.json','r').read()

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

	if isinstance(data,dict) and 'Message' in data.keys():
		if data['Message']['Body']['Content'] == 'The new Cafetaria is open.':
			return Resp(None,202)
		else:
			return Resp(None,400)
	else:
		return Resp(None,202)

		

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
		
		self.newm = message.Message(auth=auth)

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
		self.assertTrue(self.read.sendMessage())

		self.assertFalse(self.newm.sendMessage())

		self.newm.setSubject('Meet for lunch?')
		self.newm.setBody('The new cafeteria is open.')
		self.newm.setRecipients('garthf@1830edad9050849NDA1.onmicrosoft.com')
		self.assertTrue(self.newm.sendMessage())

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

		self.read.addRecipient('second@unit.com','later')

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
