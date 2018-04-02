# Python-O365 - Office365 API made easy

This project aims is to make it easy to interact with Office 365 Email, Contacts, Calendar, OneDrive, etc.

This project is based on the super work done by [Toben Archer](https://github.com/Narcolapser) [Python-O365](https://github.com/Narcolapser/python-o365).
I just want it to make it different in almost every sense, and make it also more pythonic (not getters and setters, etc.) and make it also compatible with oauth and basic auth.

The result is a package that provides a lot of O365 API capabilities.

This is for example how you send a message:

```python
from O365 import Account

credentials = (username@example.com, password)

account = Account(credentials, auth_method='basic')
m = account.new_message()
m.to.add('to_example@example.com')
m.subject = 'Testing!'
m.body("George Best quote: I've stopped drinking, but only while I'm asleep.")
m.send()
```


## Table of contents

- [Protocols](#protocols)
- [Authentication](#authentication)
- [Account Class and Modularity](#account)
- [MailBox](#mailbox)
- [AddressBook](#addressbook)
- [Calendar](#calendar)
- [Utils](#utils)


## Protocols
Protocols handles the aspects of comunications between different APIs.
This project can use either the Office 365 APIs or Microsoft Graph APIs.
You use one or the other using protocols:

- `MSOffice365Protocol` to use the [Office 365 API](https://msdn.microsoft.com/en-us/office/office365/api/api-catalog)
- `MSGraphProtocol` to use the [Microsoft Graph API](https://developer.microsoft.com/en-us/graph/docs/concepts/overview)

Both allow pretty much the same options (depending on the api version used).

When using basic authentication the protocol defaults to `MSOffice365Protocol`.
When using oauth authentication the protocol defaults to `MSGraphProtocol`.

You can implement your own protocols by inheriting from `Protocol` to communicate with other Microsoft APIs.

You can instantiate protocols like this:
```python
from O365 import MSOffice365Protocol

protocol = MSOffice365Protocol(api_version='v2.0')  # MSOffice365Protocol defaults to v1.0 api version
```

##### Resources:
Each API endpoint requires a resource. This usually defines the owner of the data.
Every protocol defaults to resource 'ME'. 'ME' is the user which has given consent, but you can change this behaviour but providing a different default resource to the protocol constructor.

For example when accesing a shared mailbox:

```python
# ...
my_protocol = MSGraphProtocol(default_resource='shared_mailbox@example.com')

account = Account(credentials=my_credentials, protocol=my_protocol)

# now account is accesing the shared_mailbox@example.com in every api call.
shared_mailbox_messages = account.mailbox().get_messages()
```

Instead of defining the resource used at the protocol level, you can provide it per use case as follows:
```python
# ...
account = Account(credentials=my_credentials)  # account defaults to 'ME' resource

mailbox = account.mailbox('shared_mailbox@example.com')  # mailbox is using 'shared_mailbox@example.com' resource instead of 'ME'

# or:

message = Message(parent=account, main_resource='shared_mailbox@example.com')  # message is using 'shared_mailbox@example.com' resource
```


## Authentication
There are two types of authentication provided:

- Basic authentication: using just the username and password
- Oauth authentication: using an authentication token provided after user consent. This is the default authentication.

<span style="color:red">Basic Authentication only works with Office 365 Api version v1.0 and until November 1 2018.</span>

The `Connection` Class handles the authentication.

#### Basic Authentication
Just pass auth_method argument with 'basic' (or `AUTH_METHOD.BASIC` enum) parameter and provide the username and password as a tuple to the credentials argument of either the `Account` or the `Connection` class.
`Account` already creates a connection for you so you don't need to create a specific Connection object (See [Account Class and Modularity](#account)).
```python
from O365 import Account, AUTH_METHOD

credentials = (username@example.com, password)

account = Account(credentials, auth_method=AUTH_METHOD.BASIC)
```
#### Oauth Authentication
This is the recommended way of authenticating.
This section is explained using Microsoft Graph Protocol, almost the same applies to the Office 365 REST API, except that you have to register you app at [Azure Portal](https://portal.azure.com/).

##### Permissions and Scopes:
When using oauth you create an application and allow some resources to be accesed and used by it's users.
Then the user can request access to one or more of this resources by providing scopes to the oauth provider.

For example your application can have Calendar.Read, Mail.ReadWrite and Mail.Send permissions, but the application can request access only to the Mail.ReadWrite and Mail.Send permission.
This is done by providing scopes to the connection object like so:
```python
from O365 import Connection, AUTH_METHOD

credentials = ('client_id', 'client_secret')

scopes = ['https://graph.microsoft.com/Mail.ReadWrite', 'https://graph.microsoft.com/Mail.Send']
# This project provides some shorthand scopes like 'message_all' that group certain scopes, using scopes = ['message_all] is the same as above.
# see SCOPES_FOR and get_scopes_for inside the connection module.

con = Connection(credentials, auth_method=AUTH_METHOD.OAUTH, scopes=scopes)
```

##### Authentication Flow
1. To work with oauth you first need to register your application at [Microsoft Application Registration Portal](https://apps.dev.microsoft.com/).

    1. Login at [Microsoft Application Registration Portal](https://apps.dev.microsoft.com/)
    2. Create an app, note your app id (client_id)
    3. Generate a new password (client_secret) under "Application Secrets" section
    4. Under the "Platform" section, add a new Web platform and set "https://outlook.office365.com/owa/" as the redirect URL
    5. Under "Microsoft Graph Permissions" section, add the delegated permissions you want (see scopes), as an example, to read and send emails use:
        1. Mail.ReadWrite
        2. Mail.Send
        3. User.Read

2. Then you need to login for the first time to get the access token by consenting the application to access the resources it needs.
    1. First get the authorization url.
        ```python
        url = account.connection.get_authorization_url()
        ```
    2. The user must visit this url and give consent to the application. When consent is given, the page will rediret to: "https://outlook.office365.com/owa/".

       Then the user must copy the resulting page url and give it to the connection object:

        ```python

        result_url = input('Paste the result url here...')

        account.connection.request_token(result_url)  # This, if succesful, will store the token in a txt file on the user project folder.
        ```

        <span style="color:red">Take care, the access token must remain protected from unauthorized users.</span>

    3. At this point you will have an access token that will provide valid credentials when using the api. If you change the scope requested, then the current token won't work, and you will need the user to give consent again on the application to gain access to the new scopes requested.

    The access token only lasts 60 minutes, but the app will automatically request new tokens through the refresh tokens, but note that a refresh token only lasts for 90 days. So you must use it before or you will need to request a new access token again (no new consent needed by the user, just a login).

## Account Class and Modularity <a name="account"></a>
Usually you will only need to work with the `Account` Class. This is a wrapper around all functionality.

But you can also work only with the pieces you want.

For example, instead of:
```python
from O365 import Account

account = Account(('client_id', 'client_secret'), auth_method='oauth')
message = account.new_message()
# ...
mailbox = account.mailbox()
# ...
```

You can work only with the required pieces:

```python
from O365 import Connection, MSGraphProtocol, Message, MailBox,

my_protocol = MSGraphProtocol()
con = Connection(('client_id', 'client_secret'), auth_method='oauth')

message = Message(con=con, protocol=my_protocol)
# ...
mailbox = Mailbox(con=con, protocol=my_protocol)
message2 = Message(parent=mailbox)  # message will inherit the connection and protocol from mailbox when using parent.
# ...
```

## MailBox
Mailbox groups the funcionality of both the messages and the email folders.

```python
mailbox = account.mailbox()

inbox = mailbox.inbox_folder()

for message in inbox.get_messages():
    print(message)

sent_folder = mailbox.sent_folder()

for message in sent_folder.get_messages():
    print(message)

m = mailbox.new_message()

m.to.add('to_example@example.com')
m.body = 'George Best quote: In 1969 I gave up women and alcohol - it was the worst 20 minutes of my life.'
m.save_draft()
```

#### Email Folder
Represents a Folder within your email mailbox.

You can get any folder in your mailbox by requesting child folders or filtering by name.

```python
mailbox = account.mailbox()

archive = mailbox.get_folder(folder_name='archive')  # get a folder with 'archive' name

child_folders = archive.get_folders(25) # get at most 25 child folders of 'archive' folder

for folder in child_folders:
    print(folder.name, folder.parent_id)

archive.create_child_folder('George Best Quotes')
```

#### Message
An email object with all it's data and methods.

Creating a draft message is as easy as this:
```python
message = mailbox.new_message()
message.to.add(['example1@example.com', 'example2@example.com'])
message.sender.address = 'my_shared_account@example.com'  # changing the from address
message.body = 'George Best quote: I might go to Alcoholics Anonymous, but I think it would be difficult for me to remain anonymous'
message.attachments.add('george_best_quotes.txt')
message.save_draft()  # save the message on the cloud as a draft in the drafts folder
```

Working with saved emails is also easy:

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
The attachment class stores the files as base64 encoded files. But this doesn't matter to you! The attachment class can work with you if you want to just send/receive raw binary or base64. You can also just give it a path to a file if you want to creat an attachment:
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

## Utils

#### Pagination

#### The Query helper

## Fluent Inbox
FluentInbox is a new class introduced to enhance usage of inbox fluently (check the below example to understand clearly)
```python
from O365 import Connection, FluentInbox

# Setup connection object
# Proxy call is required only if you are behind proxy
Connection.login('email_id@company.com', 'password to login')
Connection.proxy(url='proxy.company.com', port=8080, username='proxy_username', password='proxy_password')

# Create an inbox reference
inbox = FluentInbox()

# Fetch 20 messages from "Temp" folder containing "Test" in the subject
for message in inbox.from_folder('Temp').search('Subject:Test').fetch(count=20):
    # Just print the message subject
    print(message.getSubject())

# Fetch the next 15 messages from the results
for message in inbox.fetch_next(15):
    # Just print the message subject
    print(message.getSubject())

# Alternately you can do the below for same result, just a different way of accessing the messages
inbox.from_folder('Temp').search('Subject:Test').fetch(count=20)
inbox.fetch_next(15)
for message in inbox.messages:
    # Just print the message subject
    print(message.getSubject())

# If you would like to get only the 2nd result
for message in inbox.search('Category:some_cat').skip(1).fetch(1):
    # Just print the message subject
    print(message.getSubject())

# If you want the results from beginning by ignoring any currently read count
inbox.fetch_first(10)
```

