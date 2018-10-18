from O365 import *

# User's credentials
e = 'email_address'
p = 'password'

# Create Schedule object, get calendars, and create empty dict
schedule = Schedule((e, p))
result = schedule.getCalendars()

# Funciton to invoke getName() and bind to var result
def cal_name():
    result = cal.getName() # This will get the name of a calendar
    return result

# Show name of each calendar
print('\nHere are your calendars:\n')
for cal in schedule.calendars:
    print(cal_name())

# Get events for each calendar
print('\nHere are all your upcoming events:\n')
for cal in schedule.calendars:
    result = cal_name()
    events = cal.getEvents() # This will create an Event object
    for x in cal.events:
        contents = x.getSubject() # This will get the subject
        date = x.getStart() # This will get the start time and we'll parse it below
        print('{}-{} | {} : {}'.format(date.tm_mon, date.tm_mday, result, contents))
