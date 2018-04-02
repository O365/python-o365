import O365
import time

username = 'your username'
password = 'your password'

#send a message
con = O365.login(username,password)
message = con.newMessage()
message.recipient = username
message.subject = 'I made an email script.'
message.body = 'Talk to the computer, cause the human does not want to hear it any more.'
#message.send()

#create a new event
event = con.newEvent()
event.subject = 'Coffee!'
event.start = time.gmtime(time.time()+3600) #start an hour from now.
event.end = time.gmtime(time.time()+7200) #end two hours from now.
#event.save()

print('print subject lines of first 10 messages:')
for message in con.inbox[0:10]:
	print('\t'+message.subject)

print('print the subject line of the first 10 even messages:')
for message in con.inbox[1:20:2]:
	print('\t'+message.subject)

print('print the subject line of the 7th message:')
print('\t'+con.inbox[6].subject)

print('printing the subject line of the first 5 messages:')
for message in con.inbox[:5]:
	print('\t'+message.subject)
