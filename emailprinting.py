from O365 import *
from printing import *
import json

if __name__ == '__main__':
	with open('./ep.pw','r') as configFile:
		config = configFile.read()
		cjson = json.loads(config)

	e = cjson ['email']
	p = cjson ['password']

	i = Inbox(e,p)
	i.getMessages()

        printer = getRicoh()

	for m in i.messages:
		m.fetchAttachments()
		for att in m.attachments:
			p = att.byteString()
			if p:
				ret = printer.sendPrint(p)
				print ret

#To the King!
