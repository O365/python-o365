import json
from O365 import *


auth_e = 'test@emailaddres.office.com'
auth_p = 'Password1'
calauthenticiation = (auth_e, auth_p)
calschedule = Schedule(calauthenticiation)
try:
    lookupresult = calschedule.getCalendars()
    print 'Fetched calendars for', auth_e, 'was successful:', lookupresult
except:
    print 'Login failed for', auth_e

print len(calschedule.calendars), 'schedules found'


# Cycle through calendars found in account
for calcal in calschedule.calendars:
    print 'attempting to fetch events for', auth_e, calcal.getName()

    try:
        reslookupresultult = calcal.getEvents()
        print 'Got events', lookupresult, 'got', len(calcal.events)
    except:
        print 'failed to fetch events'

    print 'attempting for event information'
    for calevent in calcal.events:
        print json.dumps(calevent.fullcalendarsavejson())
