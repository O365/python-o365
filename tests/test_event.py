from O365 import event
import unittest
import json
import time

class Calendar:
	'''mock up calendar class'''
	def __init__(self,json,auth):
		self.json = json
		self.auth = auth
		self.calendarId = json['Id']

class Resp:
	def __init__(self,json_string):
		self.jsons = json_string

	def json(self):
		return json.loads(self.jsons)

event_rep = open('events.json','r').read()
events_json = json.loads(event_rep)
lough = events_json['value'][0]
oughter = events_json['value'][1]

t_string = '%Y-%m-%dT%H:%M:%SZ'
urls = ['https://outlook.office365.com/api/v1.0/me/events/bigolguid=',
	'https://outlook.office365.com/api/v1.0/me/events/otherguid']

def delete(url,headers,auth):
	if url not in urls:
		raise BaseException('Url wrong')
	if auth[0] != 'test@unit.com':
		raise BaseException('wrong email')
	if auth[1] != 'pass':
		raise BaseException('wrong password')
	if headers['Content-type'] != 'application/json':
		raise BaseException('header wrong value for content-type.')
	if headers['Accept'] != 'text/plain':
		raise BaseException('header accept wrong.')

	return True

event.requests.delete = delete

def post(url,data,headers,auth):
	if url != 'https://outlook.office365.com/api/v1.0/me/calendars/0/events':
		raise BaseException('Url wrong')
	if auth[0] != 'test@unit.com':
		raise BaseException('wrong email')
	if auth[1] != 'pass':
		raise BaseException('wrong password')
	if headers['Content-type'] != 'application/json':
		raise BaseException('header wrong value for content-type.')
	if headers['Accept'] != 'application/json':
		raise BaseException('header accept wrong.')

	if json.loads(data) != lough and json.loads(data) != oughter:
		raise BaseException('data is wrong.')

	return Resp(data)

event.requests.post = post

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

	return Resp(data)

event.requests.patch = patch

auth = ('test@unit.com','pass')

cal_json = {'Id':0}
cal = Calendar(cal_json,auth)

class TestInbox (unittest.TestCase):
	
	def setUp(self):
		self.lough = event.Event(lough,auth,cal)
		self.oughter = event.Event(oughter,auth,cal)

	def test_create(self):
		self.assertTrue(self.lough.create())
		self.assertTrue(self.oughter.create())

	def test_update(self):
		self.assertTrue(self.lough.update())
		self.assertTrue(self.oughter.update())

	def test_delete(self):
		self.assertTrue(self.lough.delete())
		self.assertTrue(self.oughter.delete())

	def test_auth(self):
		self.assertEqual('test@unit.com',self.lough.auth[0])
		self.assertEqual('pass',self.lough.auth[1])

		self.assertEqual('test@unit.com',self.oughter.auth[0])
		self.assertEqual('pass',self.oughter.auth[1])

if __name__ == '__main__':
	unittest.main()
