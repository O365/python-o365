import requests
import base64
import json
import logging

logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Event( object ):
	def __init__(self,json):
		self.json = json
		self.subject = json['Subject']
		self.body = json['BodyPreview']
		self.start = json['Start']
		self.end = json['End']
		self.Id = json['Id']
	
	def save(self):
		pass
