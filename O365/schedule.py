import json
import requests
from O365.cal import Calendar

class Schedule(object):
    '''
    A wrapper class that handles all the Calendars associated with a single Office365 account.
    
    Methods:
        constructor -- takes your email and password for authentication.
        getCalendars -- begins the actual process of downloading calendars.
    
    Variables:
        cal_url -- the url that is requested for the retrival of the calendar GUIDs.
    '''
    cal_url = 'https://outlook.office365.com/api/v1.0/me/calendars'

    def __init__(self, auth):
        '''Creates a Schedule class for managing all calendars associated with email+password.'''
        self.auth = auth
        self.calendars = []


    def getCalendars(self):
        '''Begin the process of downloading calendar metadata.'''
        response = requests.get(self.cal_url, auth=self.auth)
        
        for calendar in response.json()['value']:
            try:
                duplicate = False
                for i, c in enumerate(self.calendars):
                    if c.json['Id'] == calendar['Id']:
                        c.json = calendar
                        c.name = calendar['Name']
                        c.calendarId = calendar['Id']
                        duplicate = True
                        break

                if not duplicate:
                    self.calendars.append(Calendar(calendar, self.auth))

            except Exception as e:
                print 'failed to append calendar: {0}'.format(str(e))
        
        return True
