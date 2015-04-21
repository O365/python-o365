from O365 import schedule
import unittest
import json

class Calendar:
	'''mock up calendar class'''
	def __init__(self,calid,auth):
		self.calid = calid
		self.auth = auth

schedule.Calendar = Calendar

class Resp:
	def __init__(self,json_string):
		self.jsons = json_string

	def json(self):
		return json.loads(self.jsons)

sch_rep = '''{"@odata.context": "https://outlook.office365.com/EWS/OData/$metadata#Me/Calendars", "value": [{"Name": "Calendar", "Color": "Auto", "@odata.id": "https://outlook.office365.com/EWS/OData/Users(\'test@unit.org\')/Calendars(\'bigolguid=\')", "ChangeKey": "littleguid=", "Id": "bigolguid=", "@odata.etag": "W/\\"littleguid=\\""}, {"Name": "dat other cal", "Color": "Auto", "@odata.id": "https://outlook.office365.com/EWS/OData/Users(\'test@unit.org\')/Calendars(\'bigolguid2=\')", "ChangeKey": "littleguid2=", "Id": "bigolguid2=", "@odata.etag": "W/\\"littleguid2=\\""}]}'''


def get(url,**params):
	if url != 'https://outlook.office365.com/EWS/OData/Me/Calendars':
		raise
	if params['auth'][0] != 'test@unit.com':
		raise
	if params['auth'][1] != 'pass':
		raise

	ret = Resp(sch_rep)
	return ret

schedule.requests.get = get

class TestSchedule (unittest.TestCase):
	
	def setUp(self):
		self.val = schedule.Schedule('test@unit.com','pass')
		
	def test_getCalendar(self):
		self.val.getCalendars()
		self.assertEqual(2,len(self.val.calendars))

if __name__ == '__main__':
	unittest.main()
