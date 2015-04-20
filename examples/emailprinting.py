from O365 import *
from printing import *
import json

def userFromEmail(email):
	name = email[:email.index('@')]
	fname, lname = name.split('.')
	if fname > 7:
		fname = fname[:7]
		lname = lname[0]
	if fname < 4:
		lname = lname[:2]
	name = fname+lname
	return name

def verifyUser(email):
	if '@om.org' not in email.lower():
		return False

	return True	
#	name = email[:email.index(

emails = open('./pw/emails.pw','r').read().split('\n')

if __name__ == '__main__':
	print "checking for emails"
	with open('./pw/ep.pw','r') as configFile:
		config = configFile.read()
		cjson = json.loads(config)

	e = cjson ['email']
	p = cjson ['password']

	i = Inbox(e,p)

        printer = getRicoh()
	print "messages: ",len(i.messages)
	for m in i.messages:
		m.fetchAttachments()
		m.markAsRead()
		if not verifyUser(m.json['From']['EmailAddress']['Address']):
			print "NOT OMER!"
			continue
		print "\t attachments: ",len(m.attachments),"from:",userFromEmail(m.json['From']['EmailAddress']['Address']),m.json['Subject']
		for att in m.attachments:
			printer.setFlag('U',userFromEmail(m.json['From']['EmailAddress']['Address']))
			if '.pdf' not in att.json['Name'].lower():
				print 'not a pdf. skipping!'
				continue
			p = att.getByteString()
			if not p:
				continue
			print "length of byte string: ",len(p),"for attachment:",att.json['Name']
			if p:
				print "ready. set. PRINT!"
				printer.setFlag('t',att.json['Name'])
				ret = printer.sendPrint(p)
				print ret

#To the King!
