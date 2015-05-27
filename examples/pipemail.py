#!/usr/bin/env python 
#this is a simple script that can be used in conjunction with a unix pipeline.
# args must still provide: sending email, sending email password, reciving email, and subject.
from O365 import *
from sys import argv
import sys

'''Usage:
This script is designed to provide a simple means of scripting the output of a program into
email. You pass it several arguments but the body of the email is to be sent from stdin. the
args in order are:
pipemail.py sender@example.com password recipient@example.com subject
'''

if argv[1] == '/?':
	print usage
	exit()

auth = (argv[1],argv[2])

rec = argv[3]

subject = argv[4]

body = sys.stdin.read()

#Give the authentication to the message as instantiate it. then set it's values.
m = Message(auth=auth)
m.setRecipients(rec)
m.setSubject(subject)
m.setBody(body)
m.sendMessage()



