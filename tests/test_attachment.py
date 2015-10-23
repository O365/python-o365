from O365 import attachment
import unittest
import json
import base64
from random import randint


att_rep = open('attachment.json','r').read()
att_j = json.loads(att_rep)

class TestAttachment (unittest.TestCase):

	def setUp(self):
		self.att = attachment.Attachment(att_j['value'][0])

	def test_isType(self):
		self.assertTrue(self.att.isType('txt'))

	def test_getType(self):
		self.assertEqual(self.att.getType(),'.txt')

	def test_save(self):
		name = self.att.json['Name']
		name1 = self.newFileName(name)
		self.att.json['Name'] = name1
		self.assertTrue(self.att.save('/tmp'))
		with open('/tmp/'+name1,'r') as ins:
			f = ins.read()
			self.assertEqual('testing w00t!',f)

		name2 = self.newFileName(name)
		self.att.json['Name'] = name2
		self.assertTrue(self.att.save('/tmp/'))
		with open('/tmp/'+name2,'r') as ins:
			f = ins.read()
			self.assertEqual('testing w00t!',f)

	def newFileName(self,val):
		for i in range(4):
			val = str(randint(0,9)) + val
		
		return val

	def test_getByteString(self):
		self.assertEqual(self.att.getByteString(),b'testing w00t!')

	def test_getBase64(self):
		self.assertEqual(self.att.getBase64(),'dGVzdGluZyB3MDB0IQ==\n')

	def test_setByteString(self):
		test_string = b'testing testie test'
		self.att.setByteString(test_string)

		enc = base64.encodebytes(test_string)

		self.assertEqual(self.att.json['ContentBytes'],enc)

	def setBase64(self):
		wrong_test_string = 'I am sooooo not base64 encoded.'
		right_test_string = 'Base64 <3 all around!'
		enc = base64.encodestring(right_test_string)

		self.assertRaises(self.att.setBase64(wrong_test_string))
		self.assertEqual(self.att.json['ContentBytes'],'dGVzdGluZyB3MDB0IQ==\n')

		self.att.setBase64(enc)
		self.assertEqual(self.att.json['ContentBytes'],enc)

if __name__ == '__main__':
	unittest.main()
