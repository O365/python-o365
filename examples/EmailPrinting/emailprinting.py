from O365 import *
from printing import *
import json
import os
import sys
import time
import logging

logging.basicConfig(filename='ep.log',level=logging.DEBUG)

log = logging.getLogger('ep')

'''
This script represents a way that O365 could be used to integrate parts of your enviorment. This is
not a theoretical example, this is a production script that I use at our facility. The objective
here is to aliviate a problem where the printer rests inside a protected network but students who
want to print are outside of that network. By sending print jobs they have to send it to an email address they
do not need to install the printer on their local device, nor do they need direct access to the
device.

The basic architecture of this script is as follows:
1. spin off as a server. If you don't have access to cron or cron is not working for you, this is a
	work around.
2. Global Exception Handling. Because we don't have cron to spin us backup, we need to catch any
	problem that mich crash the whole process.
3. Check for messages
4. Check that the sender is from our domain.
5. Create a username that is compatible with the printer (max 8 chars, no punctuation)
6. Verify attachment type
7. Download attachment
8. Send attachment to be printed
5-8: notify the user if there is problems or successes at any point in here.

Feel free to rework this to your enviorment. You'll want to change the verification method and the
printer.py file to match your needs. 
'''


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

def processMessage(m,auth):
	m.fetchAttachments()
	m.markAsRead()

	resp = Message(auth=auth)
	resp.setSubject('Printing failed.')
	resp.setRecipients(m.getSender())

	sender = m.json['From']['EmailAddress']['Address']
	num_att = len(m.attachments)

	if not verifyUser(sender):
		resp.setBody('I am sorry, but you must email from your om.org email address.')
		resp.sendMessage()
		return False

	if num_att == 0:
		resp.setBody('Did you remember to attach the file?')
		resp.sendMessage()
		log.debug('No attachments found.')

	log.debug('\t I have {0} attachments from {1} in their email "{2}"'.format(num_att,sender,m.json['Subject']))
	
	printer.setFlag('U',userFromEmail(m.json['From']['EmailAddress']['Address']))

	for att in m.attachments:
		if not verifyPDF(att,resp):
			continue

		processAttachment(att,resp)

	return True

def verifyPDF(att,resp):
	if '.pdf' not in att.json['Name'].lower():
		log.debug('{0} is not a pdf. skipping!'.format(att.json['Name']))
		resp.setBody('I can only print pdfs. please convert your file and send it again.\n Problematic File: {0}'.format(att.json['Name']))
		resp.sendMessage()
		return False
	return True

def processAttachment(att,resp):
	p = att.getByteString()
	if not p:
		log.debug('Something went wrong with decoding attachment: {0} {1}'.format(att.json['Name'],str(p)))
		resp.setBody('Did you remember to attach the file?')
		resp.sendMessage()
		return False

	log.debug('length of byte string: {0} for attachment: {1}'.format(len(p),att.json['Name']))
	if p:
		log.debug('ready. set. PRINT!')
		printer.setFlag('t',att.json['Name'])
		ret = printer.sendPrint(p)
		resp.setBody('Your print has been passed on to the printer. You can now go to the printer to collect it. It will be locked, the password is 1234. \n\n{0}'.format(str(ret)))
		resp.setSubject('Printing succeeded')
		resp.sendMessage()
		log.debug('Response from printer: {0}'.format(ret))

	return True

emails = open('./emails.pw','r').read().split('\n')
printer = getRicoh()

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
		if True:
#		try:
			print "checking for emails"
			with open('./ep.pw','r') as configFile:
				config = configFile.read()
				cjson = json.loads(config)

			e = cjson ['email']
			p = cjson ['password']

			auth = (e,p)

			i = Inbox(auth)

			log.debug("messages: {0}".format(len(i.messages)))
			for m in i.messages:
				processMessage(m,auth)
			time.sleep(55)
#		except Exception as e:
			log.critical('something went really really bad: {0}'.format(str(e)))

#To the King!
