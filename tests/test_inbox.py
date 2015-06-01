from O365 import inbox
import unittest
import json

class Message:
	'''mock up Message class'''
	def __init__(self,json,auth):
		self.json = json
		self.auth = auth

inbox.Message = Message

class Resp:
	def __init__(self,json_string):
		self.jsons = json_string

	def json(self):
		return json.loads(self.jsons)

read_rep = open('read_message.json','r').read()
un_rep = open('unread_message.json','r').read()


def get(url,auth,params):
	if url == 'https://outlook.office365.com/api/v1.0/me/messages':
#		print params
		if params == {'$filter': 'IsRead eq false'}:
#			print 'getting the unread'
			ret = Resp(un_rep)
		else:
#			print 'getting the read'
			ret = Resp(read_rep)
	else:
		raise Exception('Wrong URL')
	if auth[0] != 'test@unit.com':
		raise Exception('Wrong Email')
	if auth[1] != 'pass':
		raise Exception('Wrong Password')

	return ret

inbox.requests.get = get

class TestInbox (unittest.TestCase):
	
	def setUp(self):
		self.preFetch = inbox.Inbox(('test@unit.com','pass'))
		self.JITFetch = inbox.Inbox(('test@unit.com','pass'),getNow=False)

	def test_getMessages(self):
		#test to see if they got the messages already, should only work for prefetch
		self.assertEqual(len(self.preFetch.messages),1)
		self.assertEqual(len(self.JITFetch.messages),0)

		#test to see what happens when they try to download again. this specifically
		#addresses an issue raised in on github for issue #3
		self.preFetch.getMessages()
		self.JITFetch.setFilter('IsRead eq false')
		self.JITFetch.getMessages()
		self.assertEqual(len(self.preFetch.messages),1)
		self.assertEqual(len(self.JITFetch.messages),1)


	def test_getRead(self):
		#sanity check
		self.assertEqual(len(self.preFetch.messages),1)
		self.assertEqual(len(self.JITFetch.messages),0)


		#now fetch the un-read emails. prefetch should still have one extra.
		self.preFetch.setFilter('IsRead eq true')
		self.preFetch.getMessages()
		self.JITFetch.setFilter('IsRead eq true')
		self.JITFetch.getMessages()
		self.assertEqual(len(self.JITFetch.messages),4)
		self.assertEqual(len(self.preFetch.messages),5)
		

	def test_auth(self):
		self.assertEqual('test@unit.com',self.preFetch.auth[0])
		self.assertEqual('pass',self.preFetch.auth[1])

		self.assertEqual('test@unit.com',self.JITFetch.auth[0])
		self.assertEqual('pass',self.JITFetch.auth[1])

	def test_filters(self):
		pass


if __name__ == '__main__':
	unittest.main()
