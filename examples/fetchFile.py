from O365 import *
import json
import os
import sys
import time
import logging

logging.basicConfig(filename='ff.log',level=logging.DEBUG)

log = logging.getLogger('ff')

def processMessage(m):
	if m.json['Subject'] != 'Fetch File':
		return False
	m.markAsRead()

	path = m.json['BodyPreview']

	path = path[:path.index('\n')]
	if path[-1] == '\r':
		path = path[:-1]

	att = Attachment(path=path)

	resp = Message(auth=auth)
	resp.setSubject('Your file sir!')
	resp.setRecipients(m.getSender())
	resp.setBody(path)


	resp.attachments.append(att)

	resp.sendMessage()

	return True


print "checking for emails"
with open('./ff.pw','r') as configFile:
	config = configFile.read()
	cjson = json.loads(config)

e = cjson ['email']
p = cjson ['password']

auth = (e,p)

i = Inbox(e,p)

log.debug("messages: {0}".format(len(i.messages)))
for m in i.messages:
	processMessage(m)

#To the King!
