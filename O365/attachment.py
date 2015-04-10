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

"""
This file contains the functions for working with attachments. Including the ability to work with the
binary of the file directly. The file is stored locally as a string using base64 encoding. 
"""

import base64
import logging
import json
import requests

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Attachment( object ):
	'''
	Attachment class is the object for dealing with attachments in your messages. To add one to
	a message, simply append it to the message's attachment list (message.attachments). 
	'''
	def __init__(self,json=None):
		if json:
			self.json = json
			self.isPDF = '.pdf' in self.json['Name'].lower()
		else:
			self.json = {}

	def isType(self,typeString):
		'''
		This function lets you know what type the file is.
		'''
		return '.'+typeString.lower() in self.json['Name'].lower()

	def getType(self):
		'''
		returns the file extension
		'''
		return self.json['Name'][self.json['Name'].rindex('.'):]

	def save(self,location):
		'''
		Location: path to where the file is to be saved.

		Save the attachment locally to disk.
		'''
		try:
			outs = open(location+'/'+self.Name,'wb')
			outs.write(base64.b64decode(self.json['ContentBytes']))
			outs.close()
			log.debug('file saved locally.')
			
		except Exception as e:
			log.debug('file failed to be saved: %s',str(e))
			return False

		log.debug('file saving successful')
		return True

	def getByteString(self):
		'''
		fetch the binary representation of the file. useful for times you want to
		skip the step of saving before sending it to another program. This allows
		you to make scripts that use linux pipe lines in their execution.
		'''
		try:
			return base64.b64decode(self.json['ContentBytes'])

		except Exception as e:
			log.debug('what? no clue what went wrong here. cannot decode attachment.')

		return False

	def getBase64(self):
		'''
		fetches the base64 encoding representation of the attachment.
		'''
		try:
			return self.json['ContentBytes']
		except Exception as e:
			log.debug('what? no clue what went wrong here. probably no attachment.')
		return False

	def setByteString(self,val):
		'''
		sets the file for this attachment from a byte string.
		'''
		try:
			self.json['ContentBytes'] = base64.b64encode(val)
		except:
			log.debug('error encoding attachment.')
			return False
		return True

	def setBase64(self,val):
		'''
		Sets the file for this attachment from a base64 encoding.
		'''
		self.json['ContentBytes'] = val
		return true

#To the King!
