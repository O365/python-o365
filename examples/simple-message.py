from O365 import *
import getpass
import json

uname = raw_input('Enter your user name: ')

password = getpass.getpass('Enter your password: ')

auth = (uname,password)

rec = raw_input('Reciving address: ')

subject = raw_input('Subject line: ')

line = 'flarg!'
body = ''
print 'Now enter the body of the message. leave a blank line when you are done.'
while line != '':
	line = raw_input()
	body += line


m = Message(None,auth)
m.setRecipients(rec)
m.setSubject(subject)
m.setBody(body)

print 'Sending message...'
print json.dumps(m.json)
print m.sendMessage()

