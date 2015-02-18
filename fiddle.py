import requests
import base64
import json
import logging
from inbox import Inbox
from message import Message
from attachment import Attachment

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

if __name__ == '__main__':
	#e = raw_input('Email: ')
	#p = raw_input('Password: ')
	#print(e,p)

	config = open('./ep.pw','r').read()
	cjson = json.loads(config)
	print cjson

	e = cjson ['email']
	p = cjson ['password']

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
