from O365.contact import Contact
import json
import requests

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

	def __init__(self, auth, folderName=None):
		'''
		Creates a group class for managing all contacts associated with email+password.

		Optional: folderName -- send the name of a contacts folder and the search will limit
		it'self to only those which are in that folder.
		'''
		self.auth = auth
		self.contacts = []
		self.folderName = folderName


	def getContacts(self):
		'''Begin the process of downloading contact metadata.'''
		if self.folderName is None:
			response = requests.get(self.con_url,auth=self.auth)
		else:
			response = requests.get(self.folder_url.format(self.folderName),auth=self.auth)
			fid = response.json()['value'][0]['Id']
			response = requests.get(self.con_folder_url.format(fid),auth=self.auth)

		for contact in response.json()['value']:
			duplicate = False
			for existing in self.contacts:
				if existing.json['Id'] == contact['Id']:
					duplicate = True
					break

			if not duplicate:
				self.contacts.append(Contact(contact,self.auth))
			
		return True
