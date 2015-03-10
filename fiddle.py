from O365 import *
import logging
import json
import requests

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

if __name__ == '__main__':
	#e = raw_input('Email: ')
	#p = raw_input('Password: ')
	#print(e,p)

	config = open('./test.pw','r').read()
	cjson = json.loads(config)
#	print cjson
#
	e = cjson ['email']
	p = cjson ['password']
#
#	i = Inbox(e,p)
#	i.getMessages()
#	for j in i.messages:
#		print j.subject
#	print len(i.messages)


#	m = i.messages[0]
#	print m.fetchAttachments()
#	a = None
#	for j in m.attachments:
#		print j.name, j.isPDF
#		if j.isPDF:
#			a = j

#	print m.markAsRead()

#	print "saved attachment: ", a.save('/home/toby.archer')

##########################################

#	m = Message(None,(e,p))
#	m.subject = 'Test'
#	m.body = 'testing testing testie test'
#	m.receiver = 'toby.archer@om.org'

#	print m.sendMessage()


##########################################

	s = Schedule(e,p)
	s.getCalendars()

	for cal in s.calendars:
		print 'fetch succeed:',cal.fetchEvents()

	print 'events for',e,len(cal.events)

	for eve in cal.events:
		print e,eve
#	e = Event(auth=(e,p))
#	e.subject = 'json test'
#	e.body = 'derpa derp'
#	e.start = time.localtime()
#	e.end = time.gmtime(time.time()+7200)
#	e.attendees = [{"EmailAddress":{"Address":"Toby.Archer@om.org","Name":"Toby Archer (LIFE)"}}]
#	t = e.create(s.calendars[0])
#	time.sleep(15)
#	t.subject = 'EDITED!'
#	t.start = time.gmtime(time.time()+3600)
#	print 't is ready to update'
#	print t.update()
#	print 'update sent!'
#	time.sleep(10)
#	t.delete()


#To the King!
