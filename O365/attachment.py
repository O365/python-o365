# Copyright 2015 by Toben "Narcolapser" Archer. All Rights Reserved.
#
# Permission to use, copy, modify, and distribute this software and its documentation for any purpose 
# and without fee is hereby granted, provided that the above copyright notice appear in all copies and 
# that both that copyright notice and this permission notice appear in supporting documentation, and 
# that the name of Toben Archer not be used in advertising or publicity pertaining to distribution of 
# the software without specific, written prior permission. TOBEN ARCHER DISCLAIMS ALL WARRANTIES WITH 
# REGARD TO THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT 
# SHALL TOBEN ARCHER BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES 
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE 
# OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

'''
This file contains the functions for working with attachments. Including the ability to work with the
binary of the file directly. The file is stored locally as a string using base64 encoding. 
'''

import base64
import logging
import json

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

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
	
	def __init__(self,json=None):
		'''
		Creates a new attachment class, optionally from existing JSON.
		
		Keyword Arguments:
		json -- json to create the class from. this is mostly used by the class internally when an
		attachment is downloaded from the cloud. If you want to create a new attachment, leave this
		empty. (default = None)
		'''
		if json:
			self.json = json
			self.isPDF = '.pdf' in self.json['Name'].lower()
		else:
			self.json = {}

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

	def setByteString(self,val):
		'''Sets the file for this attachment from a byte string.'''
		try:
			self.json['ContentBytes'] = base64.encodestring(val)
		except:
			log.debug('error encoding attachment.')
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
		return true

#To the King!
