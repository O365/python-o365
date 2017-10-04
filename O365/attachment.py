'''
This file contains the functions for working with attachments. Including the ability to work with the
binary of the file directly. The file is stored locally as a string using base64 encoding. 
'''

import base64
import logging
import json
import requests
import sys

log = logging.getLogger(__name__)

class Attachment( object ):
	'''
	Attachment class is the object for dealing with attachments in your messages. To add one to
	a message, simply append it to the message's attachment list (message.attachments). 

	these are stored locally in base64 encoded strings. You can pass either a byte string or a
	base64 encoded string tot he appropriate set function to bring your attachment into the
	instance, which will of course need to happen before it could be mailed.
	
	Methods:
	isType - compares file extension to extension given. not case sensative.
	getType - returns file extension.
	save - save attachment locally.
	getByteString - returns the attached file as a byte string.
	setByteString - set the attached file using a byte string.
	getBase64 - returns the attached file as a base64 encoded string.
	setBase64 - set the attached file using a base64 encoded string.
	'''

	create_url = 'https://outlook.office365.com/api/v1.0/me/messages/{0}/attachments'

	def __init__(self,json=None,path=None,verify=True):
		'''
		Creates a new attachment class, optionally from existing JSON.
		
		Keyword Arguments:
		json -- json to create the class from. this is mostly used by the class internally when an
		attachment is downloaded from the cloud. If you want to create a new attachment, leave this
		empty. (default = None)
		path -- a string giving the path to a file. it is cross platform as long as you break
		windows convention and use '/' instead of '\'. Passing this argument will tend to
		the rest of the process of making an attachment. Note that passing in json as well
		will cause this argument to be ignored.
		'''
		if json:
			self.json = json
			self.isPDF = '.pdf' in self.json['Name'].lower()
		elif path:
			with open(path,'rb') as val:
				self.json = {'@odata.type':'#Microsoft.OutlookServices.FileAttachment'}
				self.isPDF = '.pdf' in path.lower()

				self.setByteString(val.read())
				try:
					self.setName(path[path.rindex('/')+1:])
				except:
					self.setName(path)
		else:
			self.json = {'@odata.type':'#Microsoft.OutlookServices.FileAttachment'}

		self.verify = verify

	def isType(self,typeString):
		'''Test to if the attachment is the same type as you are seeking. Do not include a period.'''
		return '.'+typeString.lower() in self.json['Name'].lower()

	def getType(self):
		'''returns the file extension'''
		return self.json['Name'][self.json['Name'].rindex('.'):]

	def save(self,location):
		'''Save the attachment locally to disk.

		location -- path to where the file is to be saved.
		'''
		try:
			outs = open(location+'/'+self.json['Name'],'wb')
			outs.write(base64.b64decode(self.json['ContentBytes']))
			outs.close()
			log.debug('file saved locally.')
			
		except Exception as e:
			log.debug('file failed to be saved: %s',str(e))
			return False

		log.debug('file saving successful')
		return True

	def attach(self,message):
		'''
		This does the actual creating of the attachment as well as attaching to a message.

		message -- a Message type, the message to be attached to.
		'''
		mid = message.json['Id']

		headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

		data = json.dumps(self.json)

		response = requests.post(self.create_url.format(mid),data,header=headers,auth=message.auth,verify=self.verify)
		log.debug('Response from server for attaching: {0}'.format(str(response)))

		return response

	def getByteString(self):
		'''Fetch the binary representation of the file. useful for times you want to
		skip the step of saving before sending it to another program. This allows
		you to make scripts that use linux pipe lines in their execution.
		'''
		try:
			return base64.b64decode(self.json['ContentBytes'])

		except Exception as e:
			log.debug('what? no clue what went wrong here. cannot decode attachment.')

		return False

	def getBase64(self):
		'''Returns the base64 encoding representation of the attachment.'''
		try:
			return self.json['ContentBytes']
		except Exception as e:
			log.debug('what? no clue what went wrong here. probably no attachment.')
		return False

	def getName(self):
		'''Returns the file name.'''
		try:
			return self.json['Name']
		except Exception as e:
			log.error('The attachment does not appear to have a name.')
		return False

	def setName(self,val):
		'''Set the name for the file.'''
		self.json['Name'] = val

	def setByteString(self,val):
		'''Sets the file for this attachment from a byte string.'''
		try:
			if sys.version_info[0] == 2:
				self.json['ContentBytes'] = base64.b64encode(val)
			else:
				self.json['ContentBytes'] = str(base64.encodebytes(val),'utf-8')
		except Exception as e:
			log.debug('error encoding attachment: {0}'.format(e))
			return False
		return True

	def setBase64(self,val):
		'''Sets the file for this attachment from a base64 encoding.'''
		try:
			base64.decodestring(val)
		except:
			log.error('tried to give me an attachment as a base64 and it is not.')
			raise
		self.json['ContentBytes'] = val
		return True

#To the King!
