from O365 import *
import getpass
import json

#get login credentials that will be needed to send the message.
uname = raw_input('Enter your user name: ')
password = getpass.getpass('Enter your password: ')
auth = (uname,password)

#get the address that the message is to be sent to.
rec = raw_input('Reciving address: ')

#get the subject line.
subject = raw_input('Subject line: ')

#get the body.
line = 'please ignore.'
body = ''
print 'Now enter the body of the message. leave a blank line when you are done.'
while line != '':
	line = raw_input()
	body += line

#Give the authentication to the message as instantiate it. then set it's values.
m = Message(auth=auth)
m.setRecipients(rec)
m.setSubject(subject)
m.setBody(body)

#send the message and report back.
print 'Sending message...'
print m.sendMessage()

