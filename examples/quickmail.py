from O365 import *
from sys import argv

print argv

auth = (argv[1],argv[2])

rec = argv[3]

subject = argv[4]

body = argv[5]

if len(argv) > 6:
	att = argv[6]
else:
	att = None

m = Message(None,auth)
m.subject = subject
m.body = body
m.receiver = rec

print m.sendMessage()

