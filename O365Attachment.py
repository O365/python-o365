logging.basicConfig(filename='o365.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

class Attachment( object ):
	def __init__(self,json):
		self.json = json
		self.content = json['ContentBytes']
		self.name = json['Name']
		self.isPDF = '.pdf' in self.name.lower()
	
	def save(self,location):
		if not self.isPDF:
			log.debug('we only work with PDFs.')
			return False
		try:
			outs = open(location+'/'+self.name,'wb')
			outs.write(base64.b64decode(self.content))
			outs.close()
			log.debug('file saved locally.')
			
		except Exception as e:
			log.debug('file failed to be saved: %s',str(e))
			return False

		log.debug('file saving successful')
		return True

	def byteString(self):
		if not self.isPDF:
			log.debug('we only work with PDFs.')
			return False

		try:
			return base64.b64decode(self.content)

		except Exception as e:
			log.debug('what? no clue went wrong here. cannot decode')

		return False

#To the King!
