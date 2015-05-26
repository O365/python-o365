from O365 import *
import getpass
import json

from sys import argv

usage = '''Welcome to the O365 simple message script! Usage is pretty straight forward.
Run the script and you will be asked for username, password, reciving address,
subject, and then a body. When these have all come and gone your message will
be sent straight way. 

For attachments, include the path to the attachment in the call and the script
will attach the files or crash trying. (hopefully not the latter) 
e.g.: python simple-message.py that_file_you_want_but_could_only_ssh_in.jpg
'''

if len(argv) > 1:
	if argv[1] == '/?':
		print usage
		exit()

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

if len(argv) > 1:
	for arg in argv[1:]:
		a = Attachment(path=arg)
		m.attachments.append(a)

#send the message and report back.
print 'Sending message...'
print m.sendMessage()

