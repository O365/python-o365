from O365 import *
from printing import *

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

emails = open('./emails.pw','r').read().split('\n')

if __name__ == '__main__':
	with open('./ep.pw','r') as configFile:
		config = configFile.read()
		cjson = json.loads(config)

	e = cjson ['email']
	p = cjson ['password']

	i = Inbox(e,p)
	i.getMessages()

        printer = getRicoh()
	print "messages: ",len(i.messages)
	for m in i.messages:
		m.fetchAttachments()
		m.markAsRead()
		if not verifyUser(m.address):
			print "NOT OMER!"
			continue
		print "\t attachments: ",len(m.attachments),"from:",userFromEmail(m.address)
		for att in m.attachments:
			printer.setFlag('U',userFromEmail(m.address))
			p = att.byteString()
			print "length of byte string: ",len(p),"for attachment:",att.name
			if p:
				print "ready. set. PRINT!"
				printer.setFlag('t',att.name)
				ret = printer.sendPrint(p)
				print ret

#To the King!
