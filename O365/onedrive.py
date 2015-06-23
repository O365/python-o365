import logging
import json
import requests

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Drive( object ):
	'''
	A wrapper class that handles the drive associated with a single Office365 account.
	
	Methods:
		constructor -- takes your email and password for authentication.
	
	Variables:
		drive_url -- the url that is requested for the retrival of the drive GUID.
	'''
	drive_url = 'https://emailnet-my.sharepoint.com/_api/v1.0/me/drive'

	def __init__(self, auth):
		'''Creates a Drive class for managing all calendars associated with email+password.'''
		log.debug('setting up for the drive of the email %s',auth[0])
		self.auth = auth
		self.calendars = []

	def getDrive(self):
		pass

#To the King!
