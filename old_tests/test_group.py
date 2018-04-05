from O365 import group
import unittest
import json

class Contact:
	'''mock up Contact class'''
	def __init__(self,json,auth):
		self.json = json
		self.auth = auth

group.Contact = Contact

class Resp:
	def __init__(self,json_string,status_code=204):
		self.jsons = json_string
		self.status_code = status_code

	def json(self):
		return json.loads(self.jsons)

cat = open('contacts.json','r').read()
grop = open('groups.json','r').read()
bill = open('conbill.json','r').read()


con_folder_url = 'https://outlook.office365.com/api/v1.0/me/contactfolders/{0}/contacts'
folder_url = 'https://outlook.office365.com/api/v1.0/me/contactfolders?$filter=DisplayName eq \'{0}\''

engiurl = 'https://outlook.office365.com/api/v1.0/me/contactfolders?$filter=DisplayName eq \'Engineers\''
billurl = 'https://outlook.office365.com/api/v1.0/me/contactfolders/engiID/contacts'
con_url = 'https://outlook.office365.com/api/v1.0/me/contacts'

def get(url,auth,params=None):
	ret = True
	if url == engiurl:
		ret = Resp(grop)
	elif url == con_url:
		ret = Resp(cat)
	elif url == billurl:
		ret = Resp(bill)
	else:
		raise Exception('Wrong URL')
	if auth[0] != 'Wernher.VonKerman@ksp.org':
		raise Exception('Wrong Email')
	if auth[1] != 'rakete':
		raise Exception('Wrong Password')

	return ret

group.requests.get = get

class TestGroup (unittest.TestCase):
	
	def setUp(self):
		self.cons = group.Group(('Wernher.VonKerman@ksp.org','rakete'))
		self.folds = group.Group(('Wernher.VonKerman@ksp.org','rakete'),'Engineers')

	def test_getContacts(self):
		#Sanity check
		self.assertEqual(len(self.cons.contacts),0)

		#real test
		self.assertTrue(self.cons.getContacts())

		self.assertEqual(len(self.cons.contacts),3)

	def test_folders(self):
		#Sanity check
		self.assertEqual(len(self.folds.contacts),0)

		#real test
		self.assertTrue(self.folds.getContacts())

		self.assertEqual(len(self.folds.contacts),1)

	def test_auth(self):
		self.assertEqual('Wernher.VonKerman@ksp.org',self.cons.auth[0])
		self.assertEqual('rakete',self.cons.auth[1])

		self.assertEqual('Wernher.VonKerman@ksp.org',self.folds.auth[0])
		self.assertEqual('rakete',self.folds.auth[1])


if __name__ == '__main__':
	unittest.main()
