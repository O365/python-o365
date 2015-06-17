from O365 import cal
import unittest
import json
import time

class Event:
	'''mock up event class'''
	def __init__(self,json,auth):
		self.json = json
		self.auth = auth

cal.Event = Event

class Resp:
	def __init__(self,json_string):
		self.jsons = json_string

	def json(self):
		return json.loads(self.jsons)

event_rep = open('events.json','r').read()
no_event_rep = '''{"@odata.context":"https://outlook.office365.com/api/v1.0/$metadata#Me/Calendars('bigolguid')/CalendarView","value":[]}'''

sch_rep = '''{"@odata.context": "https://outlook.office365.com/EWS/OData/$metadata#Me/Calendars", "value": [{"Name": "Calendar", "Color": "Auto", "@odata.id": "https://outlook.office365.com/EWS/OData/Users(\'test@unit.org\')/Calendars(\'bigolguid=\')", "ChangeKey": "littleguid=", "Id": "bigolguid=", "@odata.etag": "W/\\"littleguid=\\""}, {"Name": "dat other cal", "Color": "Auto", "@odata.id": "https://outlook.office365.com/EWS/OData/Users(\'test@unit.org\')/Calendars(\'bigoldguid2=\')", "ChangeKey": "littleguid2=", "Id": "bigoldguid2=", "@odata.etag": "W/\\"littleguid2=\\""}]}'''

t_string = '%Y-%m-%dT%H:%M:%SZ'

s1 = '2015-04-20T17:18:25Z'
e1 = '2016-04-20T17:18:25Z'

s2 = time.strftime(t_string)
e2 = time.time()
e2 += 3600*24*365
e2 = time.gmtime(e2)
e2 = time.strftime(t_string,e2)

s3 = s1
e3 = '2015-04-25T17:18:25Z'

def get(url,**params):
	t1_url = 'https://outlook.office365.com/api/v1.0/me/calendars/bigoldguid2=/calendarview?startDateTime={0}&endDateTime={1}'.format(s1,e1)
	t2_url = 'https://outlook.office365.com/api/v1.0/me/calendars/bigoldguid2=/calendarview?startDateTime={0}&endDateTime={1}'.format(s2,e2)
	t3_url = 'https://outlook.office365.com/api/v1.0/me/calendars/bigoldguid2=/calendarview?startDateTime={0}&endDateTime={1}'.format(s3,e3)
	if url == t1_url:
		ret = Resp(event_rep)
	elif url == t2_url:
		ret = Resp(no_event_rep)
	elif url == t3_url:
		ret = Resp(event_rep)
	else:
		print(url)
		print(t1_url)
		print(t2_url)
		print(t3_url)
		raise
	if params['auth'][0] != 'test@unit.com':
		raise
	if params['auth'][1] != 'pass':
		raise

	return ret

cal.requests.get = get

auth = ('test@unit.com','pass')

class TestCalendar (unittest.TestCase):
	
	def setUp(self):
		caljson = json.loads(sch_rep)
		self.cal = cal.Calendar(caljson['value'][1],auth)

	def test_getName(self):
		self.assertEqual('dat other cal',self.cal.getName())

	def test_getCalendarId(self):
		self.assertEqual('bigoldguid2=',self.cal.getCalendarId())

	def test_getId(self):
		self.assertEqual('bigoldguid2=',self.cal.getCalendarId())

	def test_getEvents_blank(self):
		self.assertEqual(0,len(self.cal.events))
		self.cal.getEvents()
		self.assertEqual(0,len(self.cal.events))

	def test_auth(self):
		self.assertEqual('test@unit.com',self.cal.auth[0])
		self.assertEqual('pass',self.cal.auth[1])


if __name__ == '__main__':
	unittest.main()
