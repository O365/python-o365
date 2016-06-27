from O365 import *
import json
import os
import sys
import time
import logging

logging.basicConfig(filename='ff.log',level=logging.DEBUG)

log = logging.getLogger('ff')

def processMessage(m):
	path = m.json['BodyPreview']

	path = path[:path.index('\n')]
	if path[-1] == '\r':
		path = path[:-1]

	att = Attachment(path=path)

	resp = Message(auth=auth)
	resp.setRecipients(m.getSender())

	resp.setSubject('Your file sir!')
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

i = Inbox( auth, getNow=False) #Email, Password, Delay fetching so I can change the filters.

i.setFilter("IsRead eq false & Subject eq 'Fetch File'")

i.getMessages()

log.debug("messages: {0}".format(len(i.messages)))
for m in i.messages:
	processMessage(m)

#To the King!
