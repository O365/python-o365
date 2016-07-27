# Python-O365 - Office365 for you server

The objective O365 is to make it easy to make utilities that are to be run against an Office 365 account. If you wanted to script sending an email it could be as simple as:

```python
from O365 import Message
authenticiation = ('YourAccount@office365.com','YourPassword')
m = Message(auth=authenticiation)
m.setRecipients('reciving@office365.com')
m.setSubject('I made an email script.')
m.setBody('Talk to the computer, cause the human does not want to hear it any more.')
m.sendMessage()
```

To keep the library simple but powerful there are wrapper methods to access most of the attributes:
```python
m.setBody('a body!')
```

But all attributes listed on the documenation for the [Office365 API](https://msdn.microsoft.com/office/office365/APi/api-catalog) are available through the json representation stored in the instance of every O365 object:
```python
if m.json['IsReadReceiptRequested']:
	m.reply('Got it.')
```

## Table of contents

- [Email](#email)
- [Calendar](#calendar)
- [Contacts](#contacts)

## Email
There are two classes for working with emails in O365.
#### Inbox
A collection of emails. This is used when ever you are requesting an email or emails. It can be set with filters so that you only download the emails which your script is interested in. 
#### Message
An actual email with all it's associated data.

In the [Fetch File](https://github.com/Narcolapser/python-o365/blob/master/examples/fetchFile.py) example a filter is used to get only the unread messages with the subject line "Fetch File"
```python
i = Inbox(auth,getNow=False) #Email, Password, Delay fetching so I can change the filters.

i.setFilter("IsRead eq false & Subject eq 'Fetch File'")

i.getMessages()
```

When the inbox has run it's getMessages method, whether when it is instanced or later, all the messages it retrieves will be stored in a list local to the instance of inbox. Inbox.messages

While the Inbox class is used exclusively for incoming mail, as the name might imply, the message class is incoming and out going. In the fetch file example in it's processMessage method it work with both an incoming message, "m", and prepares an out going message, "resp":
```python
def processMessage(m):
	path = m.json['BodyPreview']

	path = path[:path.index('\n')]
	if path[-1] == '\r':
		path = path[:-1]

	att = Attachment(path=path)

	resp = Message(auth=auth)
	resp.setRecipients(m.getSender())

	resp.setSubject('Your file sir!')
	resp.setBody(path)
	resp.attachments.append(att)
	resp.sendMessage()

	return True
```
In this method we pull the BodyPreview, less likely to have Markup, and pull out it's first line to get the path to a file. That path is then sent to the attachment class and a response message is created and sent. Simple and straight forward.

The attachment class is a relatively simple class for handling downloading and creating attachments. Attachments in Office365 are stored seperately from the email in most cases and as such will have to be downloaded and uploaded seperately as well. This however is also taken care of behind the scenes with O365. Simply call a message's getAttachments method to download the attachments locally to your process. This creates a list of attachments local to the instance of Message, as is seen in the [Email Printing example](https://github.com/Narcolapser/python-o365/blob/master/examples/EmailPrinting/emailprinting.py):
```python
m.fetchAttachments()
for att in m.attachments:
	processAttachment(att,resp)
#various un-related bits left out for brevity.
```
The attachment class stores the files as base64 encoded files. But this doesn't matter to you! The attachment class can work with you if you want to just send/recieve raw binary or base64. You can also just give it a path to a file if you want to creat an attachment:
```python
att = Attachment(path=path)
```
or if you want to save the file
```
att.save(path)
```

## Calendar
Events are on a Calendar, Calendars are grouped into a Schedule. In the [Vehicle Booking](https://github.com/Narcolapser/python-o365/blob/master/examples/VehicleBookings/veh.py) example the purpose of the script is to create a json file with information to be imported into another program for presentation. We want to know all of the times the vehicles are booked out, for each vehicle, and by who, etc. This is done by simple getting the schedule and calendar for each vehicle and spitting out it's events:
```python
for veh in vj:
	e = veh['email']
	p = veh['password']

	schedule = Schedule(e,p)
	try:
		result = schedule.getCalendars()
		print 'Fetched calendars for',e,'was successful:',result
	except:
		print 'Login failed for',e

	bookings = []

	for cal in schedule.calendars:
		print 'attempting to fetch events for',e
		try:
			result = cal.getEvents()
			print 'Got events',result,'got',len(cal.events)
		except:
			print 'failed to fetch events'
		print 'attempting for event information'
		for event in cal.events:
			print 'HERE!'
			bookings.append(event.fullcalendarioJson())
	json_outs[e] = bookings
```

Events can be made relatively easily too. You just have to create a event class:
```python
e = Event(authentication,parentCalendar)
```
and give it a few nesessary details:
```python
import time
e.setSubject('Coffee!')
e.setStart(time.gmtime(time.time()+3600)) #start an hour from now.
e.setEnd(time.gmtime(time.time()+7200)) #end two hours from now.
new_e = e.create()
```

## Contacts
Contacts are a small part of this library, but can have their use. You can store email addresses in your contacts list in folders and then use this as a form of mailing list:
```python
e = 'youremail@office365.com'
p = 'embarrassingly simple password.'
group = Group(e,p,'Contact folder name')
m = Message(auth=(e,p))
m.setSubject('News for today')
m.setBody(open('news.html','r').read())
m.setRecipients(group)
m.sendMessage()
```

## Looking for new maintainer
I no longer, as of October 2015, have an office365 account and so I'm looking for someone to take over this project. Please fork and carry on.

#### Soli Deo Gloria
