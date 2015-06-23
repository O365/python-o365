import logging
import json
import requests

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class OneFile( object ):
	'''
	This class is designed to manage files in your one drive. Because 'File' is taken by python,
	the class is 'OneFile' instead.
	
	Methods:
		getOneFiles -- downloads oneFiles to local memory.
		
	Variables: 
		oneFile_url -- url used for fetching emails.
	'''
	#The base URL upon which all further URLs will be constructed.
	base_url = 'https://emailnet-my.sharepoint.com/_api/v1.0/me'

	#use with Put. The url for creating files.
	put_url = base_url + '/Files/{parent_id}/children/{folder_name}'

	#use with get.
	

	def __init__(self, auth):
		'''
		Creates a new oneFile wrapper. Send email and password for authentication.
		'''
		
		self.auth = auth

#To the King!
"""All the urls used by the Files REST API: 
GET {base-url}/Files/{folder-id}/children
GET {base-url}/getByPath('{folder-path}')/children

GET {base-url}/Files/{file-id}/content
GET {base-url}/getByPath('{file-path}')/content

GET {base-url}/files/{file-id}
GET {base-url}/getByPath('{file-path}')

GET {base-url}/drive

PATCH {base-url}/Files/{folder-id}
PATCH {base-url}/Files/getByPath('{folder-path}')

PATCH {base-url}/files/{file-id}
PATCH {base-url}/getByPath('{file-path}')

POST {base-url}/Files/{folder-id}/copy
POST {base-url}/getByPath('{folder-path}')/copy

POST {base-url}/Files/

POST {base-url}/Files/{parent-id}/children/{file-name}/uploadContent
POST {base-url}/Files/getByPath('{file-path}')/uploadContent

POST {baseURL}/Files/{parent-id}/children/{file-id}/add

POST {base-url}/files/{file-id}/copy
POST {base-url}/getByPath('{file-path}')/copy

DELETE {base-url}/Files/{folder-id}
DELETE {base-url}/getByPath('{folder-path}')

DELETE {base-url}/files/{file-id}
DELETE {base-url}/getByPath('{file-path}')
"""
