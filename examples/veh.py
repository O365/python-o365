from O365 import *
from printing import *
import json



if __name__ == '__main__':
	veh = open('./pw/veh.pw','r').read()
	vj = json.loads(veh)

	schedules = []
	json_outs = {}

	for veh in vj:
		e = veh['email']
		p = veh['password']

		schedule = Schedule(e,p)
		try:
			result = schedule.getCalendars()
			print 'Fetched calendars for',e,'was successful:',result
		except:
			print 'Login failed for',e

		bookings = []

		for cal in schedule.calendars:
			print 'attempting to fetch events for',e
			try:
				result = cal.getEvents()
				print 'Got events',result,'got',len(cal.events)
			except:
				print 'failed to fetch events'
			print 'attempting for event information'
			for event in cal.events:
				print 'HERE!'
				bookings.append(event.fullcalendarioJson())
		json_outs[e] = bookings

	with open('bookings.json','w') as outs:
		outs.write(json.dumps(json_outs,sort_keys=True,indent=4))
			

#	with open('./ep.pw','r') as configFile:
#		config = configFile.read()
#		cjson = json.loads(config)
#
#	e = cjson ['email']
#	p = cjson ['password']
#
#	i = Inbox(e,p)
#	i.getMessages()
#
#	printer = getRicoh()
#	print "messages: ",len(i.messages)
#	for m in i.messages:
#		m.fetchAttachments()
#		m.markAsRead()
#		if not verifyUser(m.address):
#			print "NOT OMER!"
#			continue
#		print "\t attachments: ",len(m.attachments),"from:",userFromEmail(m.address)
#		for att in m.attachments:
#			printer.setFlag('U',userFromEmail(m.address))
#			p = att.byteString()
#			if not p:
#				continue
#			print "length of byte string: ",len(p),"for attachment:",att.name
#			if p:
#				print "ready. set. PRINT!"
#				printer.setFlag('t',att.name)
#				ret = printer.sendPrint(p)
#				print ret

#To the King!
