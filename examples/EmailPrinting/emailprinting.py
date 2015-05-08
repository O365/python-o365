from O365 import *
from printing import *
import json
import os
import sys
import time
import logging

logging.basicConfig(filename='ep.log',level=logging.DEBUG)

log = logging.getLogger('ep')

def userFromEmail(email):
	name = email[:email.index('@')]
	fname, lname = name.split('.')
	if fname > 7:
		fname = fname[:7]
		lname = lname[0]
	if fname < 4:
		lname = lname[:2]
	name = fname+lname
	log.debug('Exctracted username: {0}'.format(name))
	return name

def verifyUser(email):
	if '@om.org' not in email.lower():
		log.debug('Not an OM address: {0}'.format(email))
		return False

	log.debug('Valid OM address: {0}'.format(email))
	return True	

def getLock():
	f = open('emailprinting.lock','r').read()
	lock = int(f)
	return lock

emails = open('./emails.pw','r').read().split('\n')

if __name__ == '__main__':
	newpid = os.fork()
	if newpid > 0:
		print newpid
		f = open('pid','a')
		f.write(str(newpid))
		f.write('\n')
		f.close()
		sys.exit(0)
	
	while getLock():
		print "checking for emails"
		with open('./ep.pw','r') as configFile:
			config = configFile.read()
			cjson = json.loads(config)

		e = cjson ['email']
		p = cjson ['password']

		i = Inbox(e,p)

	        printer = getRicoh()
		log.debug("messages: {0}".format(len(i.messages)))
		for m in i.messages:
			m.fetchAttachments()
			m.markAsRead()

			resp = Message(auth=(e,p))
			resp.setSubject('Printing failed.')
			resp.setRecipients(m.getSender())

			if not verifyUser(m.json['From']['EmailAddress']['Address']):
				resp.setBody('I am sorry, but you must email from your om.org email address.')
				resp.sendMessage()
				continue

			log.debug('\t I have {0} attachments from {1} in their email "{2}"'.format(len(m.attachments),userFromEmail(m.json['From']['EmailAddress']['Address']),m.json['Subject']))
			if len(m.attachments) == 0:
				resp.setBody('Did you remember to attach the file?')
				resp.sendMessage()
				log.debug('No attachments found.')
			for att in m.attachments:
				printer.setFlag('U',userFromEmail(m.json['From']['EmailAddress']['Address']))
				if '.pdf' not in att.json['Name'].lower():
					log.debug('{0} is not a pdf. skipping!'.format(att.json['Name']))
					resp.setBody('I can only print pdfs. please convert your file and send it again.\n Problematic File: {0}'.format(att.json['Name']))
					resp.sendMessage()
					continue

				p = att.getByteString()
				if not p:
					log.debug('Something went wrong with decoding attachment: {0} {1}'.format(att.json['Name'],str(p)))
					resp.setBody('Did you remember to attach the file?')
					resp.sendMessage()
					continue

				log.debug('length of byte string: {0} for attachment: {1}'.format(len(p),att.json['Name']))
				if p:
					log.debug('ready. set. PRINT!')
					printer.setFlag('t',att.json['Name'])
					ret = printer.sendPrint(p)
					resp.setBody('Your print has been passed on to the printer. You can now go to the printer to collect it. It will be locked, the password is 1234. \n\n{0}'.format(str(ret)))
					resp.setSubject('Printing succeeded')
					resp.sendMessage()
					log.debug('Response from printer: {0}'.format(ret))
		time.sleep(55)

#To the King!
