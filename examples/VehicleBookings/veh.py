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
			
#To the King!
