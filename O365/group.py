from O365.contact import Contact
import logging
import json
import requests

log = logging.getLogger(__name__)

class Group( object ):
	'''
	A wrapper class that handles all the contacts associated with a single Office365 account.
	
	Methods:
		constructor -- takes your email and password for authentication.
		getContacts -- begins the actual process of downloading contacts.
	
	Variables:
		con_url -- the url that is requested for the retrival of the contacts.
		con_folder_url -- the url that is used for requesting contacts from a specific folder.
		folder_url -- the url that is used for finding folder Id's from folder names.
	'''
	con_url = 'https://outlook.office365.com/api/v1.0/me/contacts'
	con_folder_url = 'https://outlook.office365.com/api/v1.0/me/contactfolders/{0}/contacts'
	folder_url = 'https://outlook.office365.com/api/v1.0/me/contactfolders?$filter=DisplayName eq \'{0}\''

	def __init__(self, auth, folderName=None,verify=True):
		'''
		Creates a group class for managing all contacts associated with email+password.

		Optional: folderName -- send the name of a contacts folder and the search will limit
		it'self to only those which are in that folder.
		'''
		log.debug('setting up for the schedule of the email %s',auth[0])
		self.auth = auth
		self.contacts = []
		self.folderName = folderName

		self.verify = verify


	def getContacts(self):
		'''Begin the process of downloading contact metadata.'''
		if self.folderName is None:
			log.debug('fetching contacts.')
			response = requests.get(self.con_url,auth=self.auth,verify=self.verify)
			log.info('Response from O365: %s', str(response))

		else:
			log.debug('fetching contact folder.')
			response = requests.get(self.folder_url.format(self.folderName),auth=self.auth,verify=self.verify)
			fid = response.json()['value'][0]['Id']
			log.debug('got a response of {0} and an Id of {1}'.format(response.status_code,fid))

			log.debug('fetching contacts for {0}.'.format(self.folderName))
			response = requests.get(self.con_folder_url.format(fid),auth=self.auth,verify=self.verify)
			log.info('Response from O365: {0}'.format(str(response)))

		for contact in response.json()['value']:
			duplicate = False
			log.debug('Got a contact Named: {0}'.format(contact['DisplayName']))
			for existing in self.contacts:
				if existing.json['Id'] == contact['Id']:
					log.info('duplicate contact')
					duplicate = True
					break

			if not duplicate:
				self.contacts.append(Contact(contact,self.auth))
			
			log.debug('Appended Contact.')
				
			
		log.debug('all calendars retrieved and put in to the list.')
		return True

#To the King!
