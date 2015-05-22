from O365 import contact
import unittest
import json
import time


class Resp:
	def __init__(self,json_string,code=None):
		self.jsons = json_string
		self.status_code = code

	def json(self):
		return json.loads(self.jsons)

contact_rep = open('contacts.json','r').read()
contacts_json = json.loads(contact_rep)
jeb = contacts_json['value'][0]
bill = contacts_json['value'][1]

t_string = '%Y-%m-%dT%H:%M:%SZ'
urls = ['https://outlook.office365.com/api/v1.0/me/contacts/',
	'https://outlook.office365.com/api/v1.0/me/contacts/bigguid1',
	'https://outlook.office365.com/api/v1.0/me/contacts/bigguid2',
	'https://outlook.office365.com/api/v1.0/me/contacts/bigguid3']

def delete(url,headers,auth):
	if url not in urls:
		print url
		raise BaseException('Url wrong')
	if auth[0] != 'test@unit.com':
		raise BaseException('wrong email')
	if auth[1] != 'pass':
		raise BaseException('wrong password')
	if headers['Content-type'] != 'application/json':
		raise BaseException('header wrong value for content-type.')
	if headers['Accept'] != 'text/plain':
		raise BaseException('header accept wrong.')

	return Resp(None,204)

contact.requests.delete = delete

def post(url,data,headers,auth):
	if url not in urls:
		raise BaseException('Url wrong')
	if auth[0] != 'test@unit.com':
		raise BaseException('wrong email')
	if auth[1] != 'pass':
		raise BaseException('wrong password')
	if headers['Content-type'] != 'application/json':
		raise BaseException('header wrong value for content-type.')
	if headers['Accept'] != 'application/json':
		raise BaseException('header accept wrong.')

	if json.loads(data) != jeb and json.loads(data) != bill:
		raise BaseException('data is wrong.')

	return Resp(data,202)
	#return True

contact.requests.post = post

def patch(url,data,headers,auth):
	if url not in urls:
		raise BaseException('Url wrong')
	if auth[0] != 'test@unit.com':
		raise BaseException('wrong email')
	if auth[1] != 'pass':
		raise BaseException('wrong password')
	if headers['Content-type'] != 'application/json':
		raise BaseException('header wrong value for content-type.')
	if headers['Accept'] != 'application/json':
		raise BaseException('header accept wrong.')

	return Resp(data,202)
	#return True

contact.requests.patch = patch

auth = ('test@unit.com','pass')

class TestInbox (unittest.TestCase):
	
	def setUp(self):
		self.jeb = contact.Contact(jeb,auth)
		self.bill = contact.Contact(bill,auth)

	def test_create(self):
		self.assertTrue(self.jeb.create())
		self.assertTrue(self.bill.create())

	def test_update(self):
		self.assertTrue(self.jeb.update())
		self.assertTrue(self.bill.update())

	def test_delete(self):
		self.assertTrue(self.jeb.delete())
		self.assertTrue(self.bill.delete())

	def test_auth(self):
		self.assertEqual('test@unit.com',self.jeb.auth[0])
		self.assertEqual('pass',self.jeb.auth[1])

		self.assertEqual('test@unit.com',self.bill.auth[0])
		self.assertEqual('pass',self.bill.auth[1])

if __name__ == '__main__':
	unittest.main()
