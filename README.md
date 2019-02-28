# O365 - Microsoft Graph and Office 365 API made easy


> API Documentation is available [here](https://o365.github.io/python-o365/latest/html/api.html)

> Detailed usage documentation is still in progress

This project aims is to make interact with Microsoft Graph and Office 365 easy to do in a Pythonic way. 
Access to Email, Calendar, Contacts, OneDrive, etc. Are easy to do in a way that feel easy and straight forward to beginners and feels just right to seasoned python programmer.

The project is currently developed and maintained by [Toben Archer](https://github.com/Narcolapser), [Royce Melborn](https://github.com/roycem90) and [Janscas](https://github.com/janscas), but we are always open to new pull requests.


This is for example how you send a message:

```python
from O365 import Account

credentials = ('client_id', 'client_secret')

account = Account(credentials)
m = account.new_message()
m.to.add('to_example@example.com')
m.subject = 'Testing!'
m.body = "George Best quote: I've stopped drinking, but only while I'm asleep."
m.send()
```


### Why choose O365?
- Almost Full Support for MsGraph and Office 365 Rest Api.
- Good Abstraction layer between each Api. Change the api (Graph vs Office365) and don't worry about the api internal implementation.
- Full oauth support with automatic handling of refresh tokens.
- Automatic handling between local datetimes and server datetimes. Work with your local datetime and let this library do the rest.
- Change between different resource with ease: access shared mailboxes, other users resources, sharepoint resources, etc.
- Pagination support through a custom iterator that handles future requests automatically. Request Infinite items!
- A query helper to help you build custom OData queries (filter, order and select).
- Modular ApiComponents can be created and build to achieve further functionality.

___

This project was also a learning resource for us. This is a list of not so common python idioms used in this project:
- New unpacking technics: `def method(argument, *, with_name=None, **other_params):`
- Enums: `from enum import Enum`
- Factory paradigm
- Package organization
- Timezone conversion and timezone aware datetimes
- Etc. (see the code!)


What follows is kind of a wiki... but you will get more insights by looking at the [docs](https://o365.github.io/python-o365/latest/html/api.html) or deep into the code.

## Table of contents

- [Install](#install)
- [Usage](#usage)
- [Protocols](#protocols)
- [Authentication](#authentication)
- [Account Class and Modularity](#account)
- [MailBox](#mailbox)
- [AddressBook](#addressbook)
- [Calendar](#calendar)
- [OneDrive](#onedrive)
- [Sharepoint](#sharepoint)
- [Planner](#planner)
- [Utils](#utils)


## Install
O365 is available on pypi.org. Simply run `pip install O365` to install it.

Requirements: >= Python 3.4

Project dependencies installed by pip:
 - requests
 - requests-oauthlib
 - beatifulsoup4
 - stringcase
 - python-dateutil
 - tzlocal
 - pytz
 
 

## Usage
The first step to be able to work with this library is to register an application and retrieve the auth token. See [Authentication](#authentication).

It is highly recommended to add the "offline_access" permission and request this scope when authenticating. Otherwise the library will only have access to the user resources for 1 hour. 

With the access token retrieved and stored you will be able to perform api calls to the service.

A common pattern to check for authentication and use the library is this one:

```python
scopes = ['my_required_scopes']

account = Account(credentials)

if not account.is_authenticated:  # will check if there is a token and has not expired
    # ask for a login
    account.authenticate(scopes=scopes)

# now we are autheticated
# use the library from now on

# ...
```

## Authentication
You can only authenticate using oauth athentication as Microsoft deprecated basic auth on November 1st 2018.

- Oauth authentication: using an authentication token provided after user consent.

The `Connection` Class handles the authentication.

#### Oauth Authentication
This section is explained using Microsoft Graph Protocol, almost the same applies to the Office 365 REST API.

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
        4. It is highly recommended to add "offline_access" permission. If not you will have to re-authenticate every hour.

2. Then you need to login for the first time to get the access token by consenting the application to access the resources it needs.
    1. To authenticate (login) call `account.authenticate` and pass the scopes you want (the ones you previously added on the app registration portal).
    
        You can pass "protocol scopes" (like: "https://graph.microsoft.com/Calendars.ReadWrite") to the method or use "[scope helpers](https://github.com/O365/python-o365/blob/master/O365/connection.py#L33)" like ("message_all").
        If you pass protocol scopes, then the `account` instance must be initialized with the same protocol used by the scopes. By using scope helpers you can abstract the protocol from the scopes and let this library work for you.   
        Finally, you can mix and match "protocol scopes" with "scope helpers".
        Go to the [procotol section](#protocols) to know more about them.
        
        For Example (following the previous permissions added):
        ```python
        # ...
        account = Account(credentials)  # the default protocol will be Microsoft Graph
        account.authenticate(scopes=['basic', 'message_all'])
        # 'basic' adds: 'offline_access' and 'https://graph.microsoft.com/User.Read'
        # 'message_all' adds: 'https://graph.microsoft.com/Mail.ReadWrite' and 'https://graph.microsoft.com/Mail.Send'
 
        ```
        This method call will print a url that the user must visit to give consent to the app on the required permissions.
        
        The user must then visit this url and give consent to the application. When consent is given, the page will rediret to: "https://outlook.office365.com/owa/" by default (you can change this).
        
        Then the user must copy the resulting page url and paste it back on the console.
        The method will the return True if the login attempt was succesful.

        **Take care: the access (and refresh) token must remain protected from unauthorized users.**

    3. At this point you will have an access token stored that will provide valid credentials when using the api. If you change the scope requested, then the current token won't work, and you will need the user to give consent again on the application to gain access to the new scopes requested.

    The access token only lasts **60 minutes**, but the app will automatically request new access tokens through the refresh tokens (if and only if you added the "offline_access" permission), but note that a refresh token only lasts for 90 days. So you must use it before or you will need to request a new access token again (no new consent needed by the user, just a login).
    
    If your application needs to work for more than 90 days without user interaction and without interacting with the API, then you must implement a periodic call to `Connection.refresh_token` before the 90 days have passed.
    
    Finally you can use other methods to authenticate that offer more flexibility (`account.authenticate` enforces the use of the command line). For example you can decouple the authentication steps to allow the users login within a webpage or whatever:
    ```python
    url = account.connection.get_authorization_url(requested_scopes=['scopes_required'])  # visit url
    result_url = input('Paste the result url here...')  # wait for the user input. Just use whatever mechanism you want to retrieve the url from the user.
    account.connection.request_token(result_url)  # This, if succesful, will store the token in a txt file on the user project folder. You can change how and where you store the token.
    ```
    
    or using `oauth_authentication_flow`:
    
    ```python
    from O365 import oauth_authentication_flow
    
    result = oauth_authentication_flow('client_id', 'client_secret', ['scopes_required'])
    ```


##### Permissions and Scopes:
When using oauth, you create an application and allow some resources to be accesed and used by it's users.
Then the user can request access to one or more of this resources by providing scopes to the oauth provider.

For example your application can have Calendar.Read, Mail.ReadWrite and Mail.Send permissions, but the application can request access only to the Mail.ReadWrite and Mail.Send permission.
This is done by providing scopes to the `account.authenticate` method or to a `Connection` instance like so:
```python
from O365 import Connection

credentials = ('client_id', 'client_secret')

scopes = ['https://graph.microsoft.com/Mail.ReadWrite', 'https://graph.microsoft.com/Mail.Send']

con = Connection(credentials, scopes=scopes)
```

Scope implementation depends on the protocol used. So by using protocol data you can automatically set the scopes needed:

You can get the same scopes as before using protocols like this:

```python
protocol_graph = MSGraphProtocol()

scopes_graph = protocol.get_scopes_for('message all')
# scopes here are: ['https://graph.microsoft.com/Mail.ReadWrite', 'https://graph.microsoft.com/Mail.Send']

protocol_office = MSOffice365Protocol()

scopes_office = protocol.get_scopes_for('message all')
# scopes here are: ['https://outlook.office.com/Mail.ReadWrite', 'https://outlook.office.com/Mail.Send']

con = Connection(credentials, scopes=scopes_graph)
```

However all the protocol/scope stuff can be addressed automaticaly for you when using the `account.authenticate` method.



##### Token storage:
When authenticating you will retrieve oauth tokens. If you don't want a one time access you will have to store the token somewhere.
O365 makes no assumptions on where to store the token and tries to abstract this from the library usage point of view.

You can choose where and how to store tokens by using the properly Token Backend.

**Take care: the access (and refresh) token must remain protected from unauthorized users.**

To store the token you will have to provide a properly configured TokenBackend.
Actually there are only two implemented (but you can easely implement more like a CookieBackend, etc.):
- `FileSystemTokenBackend` (Default backend): Stores and retrieves tokens from the file system. Tokens are stored as files.
- `FirestoreTokenBackend`: Stores and retrives tokens from a Google Firestore Datastore. Tokens are stored as documents whitin a collection.

For example using the FileSystem Token Backend:

```python
from O365 import Account, FileSystemTokenBackend

credentials = ('id', 'secret')

# this will store the token under: "my_project_folder/my_folder/my_token.txt".
# you can pass strings to token_path or Path instances from pathlib
token_backend = FileSystemTokenBackend(token_path='my_folder', token_filename='my_token.txt')
account = Account(credentials, token_backend=token_backend)

# This account instance tokens will be stored on the token_backend configured before.
# You don't have to do anything more
# ...
```

And now using the same example using FirestoreTokenBackend:

```python
from O365 import Account, FirestoreBackend
from google.cloud import firestore

credentials = ('id', 'secret')

# this will store the token on firestore under the tokens collection on the defined doc_id.
# you can pass strings to token_path or Path instances from pathlib
user_id = 'whatever the user id is'  # used to create the token document id
document_id = 'token_{}'.format(user_id)  # used to uniquely store this token
token_backend = FirestoreBackend(client=firestore.Client(), collection='tokens', doc_id=document_id)
account = Account(credentials, token_backend=token_backend)

# This account instance tokens will be stored on the token_backend configured before.
# You don't have to do anything more
# ...
```

To implememnt a new TokenBackend:
 
 1. Subclass `BaseTokenBackend`
 1. Implement the following methods:
 
     - `__init__` (don't forget to call `super().__init__`)
     - `get_token`: this should set `self.token` and return a `Token` instance or None
     - `save_token`: this should store the `self.token` in the desired backend.
     - Optionally you can implement: `check_token` and `delete_token`
     


## Protocols
Protocols handles the aspects of comunications between different APIs.
This project uses by default either the Office 365 APIs or Microsoft Graph APIs.
But, you can use many other Microsoft APIs as long as you implement the protocol needed.

You can use one or the other:

- `MSGraphProtocol` to use the [Microsoft Graph API](https://developer.microsoft.com/en-us/graph/docs/concepts/overview)
- `MSOffice365Protocol` to use the [Office 365 API](https://msdn.microsoft.com/en-us/office/office365/api/api-catalog)

Both protocols are similar but consider the following:

Reasons to use `MSGraphProtocol`:
- It is the recommended Protocol by Microsoft.
- It can access more resources over Office 365 (for example OneDrive)

Reasons to use `MSOffice365Protocol`:
- It can send emails with attachments up to 150 MB. MSGraph only allows 4MB on each request.

The default protocol used by the `Account` Class is `MSGraphProtocol`.

You can implement your own protocols by inheriting from `Protocol` to communicate with other Microsoft APIs.

You can instantiate protocols like this:
```python
from O365 import MSGraphProtocol

# try the api version beta of the Microsoft Graph endpoint.
protocol = MSGraphProtocol(api_version='beta')  # MSGraphProtocol defaults to v1.0 api version
```

##### Resources:
Each API endpoint requires a resource. This usually defines the owner of the data.
Every protocol defaults to resource 'ME'. 'ME' is the user which has given consent, but you can change this behaviour by providing a different default resource to the protocol constructor.

For example when accesing a shared mailbox:


```python
# ...
account = Account(credentials=my_credentials, main_resource='shared_mailbox@example.com')
# Any instance created using account will inherit the resource defined for account.
```

This can be done however at any point. For example at the protocol level:
```python
# ...
my_protocol = MSGraphProtocol(default_resource='shared_mailbox@example.com')

account = Account(credentials=my_credentials, protocol=my_protocol)

# now account is accesing the shared_mailbox@example.com in every api call.
shared_mailbox_messages = account.mailbox().get_messages()
```
 

Instead of defining the resource used at the account or protocol level, you can provide it per use case as follows:
```python
# ...
account = Account(credentials=my_credentials)  # account defaults to 'ME' resource

mailbox = account.mailbox('shared_mailbox@example.com')  # mailbox is using 'shared_mailbox@example.com' resource instead of 'ME'

# or:

message = Message(parent=account, main_resource='shared_mailbox@example.com')  # message is using 'shared_mailbox@example.com' resource
```

Usually you will work with the default 'ME' resource, but you can also use one of the following:

- **'me'**: the user which has given consent. the default for every protocol.
- **'user:user@domain.com'**: a shared mailbox or a user account for which you have permissions. If you don't provide 'user:' will be infered anyways.
- **'sharepoint:sharepoint-site-id'**: a sharepoint site id.
- **'group:group-site-id'**: a office365 group id.  


## Account Class and Modularity <a name="account"></a>
Usually you will only need to work with the `Account` Class. This is a wrapper around all functionality.

But you can also work only with the pieces you want.

For example, instead of:
```python
from O365 import Account

account = Account(('client_id', 'client_secret'))
message = account.new_message()
# ...
mailbox = account.mailbox()
# ...
```

You can work only with the required pieces:

```python
from O365 import Connection, MSGraphProtocol, Message, MailBox

my_protocol = MSGraphProtocol()
con = Connection(('client_id', 'client_secret'))

message = Message(con=con, protocol=my_protocol)
# ...
mailbox = MailBox(con=con, protocol=my_protocol)
message2 = Message(parent=mailbox)  # message will inherit the connection and protocol from mailbox when using parent.
# ...
```

It's also easy to implement a custom Class.

Just Inherit from `ApiComponent`, define the endpoints, and use the connection to make requests. If needed also inherit from Protocol to handle different comunications aspects with the API server.

```python
from O365.utils import ApiComponent 

class CustomClass(ApiComponent):
    _endpoints = {'my_url_key': '/customendpoint'}
    
    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)
        # ...

    def do_some_stuff(self):
        
        # self.build_url just merges the protocol service_url with the enpoint passed as a parameter
        # to change the service_url implement your own protocol inherinting from Protocol Class
        url = self.build_url(self._endpoints.get('my_url_key'))  
        
        my_params = {'param1': 'param1'}

        response = self.con.get(url, params=my_params)  # note the use of the connection here.

        # handle response and return to the user...
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
Represents a `Folder` within your email mailbox.

You can get any folder in your mailbox by requesting child folders or filtering by name.

```python
mailbox = account.mailbox()

archive = mailbox.get_folder(folder_name='archive')  # get a folder with 'archive' name

child_folders = archive.get_folders(25) # get at most 25 child folders of 'archive' folder

for folder in child_folders:
    print(folder.name, folder.parent_id)

new_folder = archive.create_child_folder('George Best Quotes')
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
```python
query = mailbox.new_query().on_attribute('subject').contains('george best')  # see Query object in Utils
messages = mailbox.get_messages(limit=25, query=query)

message = messages[0]  # get the first one

message.mark_as_read()
reply_msg = message.reply()

if 'example@example.com' in reply_msg.to:  # magic methods implemented
    reply_msg.body = 'George Best quote: I spent a lot of money on booze, birds and fast cars. The rest I just squandered.'
else:
    reply_msg.body = 'George Best quote: I used to go missing a lot... Miss Canada, Miss United Kingdom, Miss World.'

reply_msg.send()
```

## AddressBook
AddressBook groups the funcionality of both the Contact Folders and Contacts. Outlook Distribution Groups are not supported (By the Microsoft API's).

#### Contact Folders
Represents a Folder within your Contacts Section in Office 365.
AddressBook class represents the parent folder (it's a folder itself).

You can get any folder in your address book by requesting child folders or filtering by name.

```python
address_book = account.address_book()

contacts = address_book.get_contacts(limit=None)  # get all the contacts in the Personal Contacts root folder

work_contacts_folder = address_book.get_folder(folder_name='Work Contacts')  # get a folder with 'Work Contacts' name

message_to_all_contats_in_folder = work_contacts_folder.new_message()  # creates a draft message with all the contacts as recipients

message_to_all_contats_in_folder.subject = 'Hallo!'
message_to_all_contats_in_folder.body = """
George Best quote:

If you'd given me the choice of going out and beating four men and smashing a goal in
from thirty yards against Liverpool or going to bed with Miss World,
it would have been a difficult choice. Luckily, I had both.
"""
message_to_all_contats_in_folder.send()

# querying folders is easy:
child_folders = address_book.get_folders(25) # get at most 25 child folders

for folder in child_folders:
    print(folder.name, folder.parent_id)

# creating a contact folder:
address_book.create_child_folder('new folder')
```

#### The Global Address List
Office 365 API (Nor MS Graph API) has no concept such as the Outlook Global Address List.
However you can use the [Users API](https://developer.microsoft.com/en-us/graph/docs/api-reference/v1.0/resources/users) to access all the users within your organization.

Without admin consent you can only access a few properties of each user such as name and email and litte more.
You can search by name or retrieve a contact specifying the complete email.

- Basic Permision needed is Users.ReadBasic.All (limit info)
- Full Permision is Users.Read.All but needs admin consent.

To search the Global Address List (Users API):

```python
global_address_list = account.address_book(address_book='gal')

# start a new query:
q = global_address_list.new_query('display_name')
q.startswith('George Best')

print(global_address_list.get_contacts(query=q))
```


To retrieve a contact by it's email:

```python
contact = global_address_list.get_contact_by_email('example@example.com')
```

#### Contacts
Everything returned from an `AddressBook` instance is a `Contact` instance.
Contacts have all the information stored as attributes

Creating a contact from an `AddressBook`:

```python
new_contact = address_book.new_contact()

new_contact.name = 'George Best'
new_contact.job_title = 'football player'
new_contact.emails.add('george@best.com')

new_contact.save()  # saved on the cloud

message = new_contact.new_message()  #  Bonus: send a message to this contact

# ...

new_contact.delete()  # Bonus: deteled from the cloud
```


## Calendar
The calendar and events functionality is group in a `Schedule` object.

A `Schedule` instance can list and create calendars. It can also list or create events on the default user calendar.
To use other calendars use a `Calendar` instance.  

Working with the `Schedule` instance:
```python
import datetime as dt

# ...
schedule = account.schedule()

calendar = schedule.get_default_calendar()
new_event = calendar.new_event()  # creates a new unsaved event 
new_event.subject = 'Recruit George Best!'
new_event.location = 'England'

# naive datetimes will automatically be converted to timezone aware datetime
#  objects using the local timezone detected or the protocol provided timezone

new_event.start = dt.datetime(2019, 9, 5, 19, 45) 
# so new_event.start becomes: datetime.datetime(2018, 9, 5, 19, 45, tzinfo=<DstTzInfo 'Europe/Paris' CEST+2:00:00 DST>)

new_event.recurrence.set_daily(1, end=dt.datetime(2019, 9, 10))
new_event.remind_before_minutes = 45

new_event.save()
```

Working with `Calendar` instances:
```python
calendar = schedule.get_calendar(calendar_name='Birthdays')

calendar.name = 'Football players birthdays'
calendar.update()

q = calendar.new_query('start').greater_equal(dt.datetime(2018, 5, 20))
q.chain('and').on_attribute('end').less_equal(dt.datetime(2018, 5, 24))

birthdays = calendar.get_events(query=q)

for event in birthdays:
    if event.subject == 'George Best Birthday':
        # He died in 2005... but we celebrate anyway!
        event.accept("I'll attend!")  # send a response accepting
    else:
        event.decline("No way I'm comming, I'll be in Spain", send_response=False)  # decline the event but don't send a reponse to the organizer
```

## OneDrive
The `Storage` class handles all functionality around One Drive and Document Library Storage in Sharepoint.

The `Storage` instance allows to retrieve `Drive` instances which handles all the Files and Folders from within the selected `Storage`.
Usually you will only need to work with the default drive. But the `Storage` instances can handle multiple drives.


A `Drive` will allow you to work with Folders and Files.

```python
account = Account(credentials=my_credentials)

storage = account.storage()  # here we get the storage instance that handles all the storage options.

# list all the drives:
drives = storage.get_drives()

# get the default drive
my_drive = storage.get_default_drive()  # or get_drive('drive-id')

# get some folders:
root_folder = my_drive.get_root_folder()
attachments_folder = my_drive.get_special_folder('attachments')

# iterate over the first 25 items on the root folder
for item in root_folder.get_items(limit=25):
    if item.is_folder:
        print(item.get_items(2))  # print the first to element on this folder.
    elif item.is_file:
        if item.is_photo:
            print(item.camera_model)  # print some metadata of this photo
        elif item.is_image:
            print(item.dimensione)  # print the image dimensions
        else:
            # regular file:
            print(item.mime_type)  # print the mime type
```

Both Files and Folders are DriveItems. Both Image and Photo are Files, but Photo is also an Image. All have some different methods and properties. 
Take care when using 'is_xxxx'.

When coping a DriveItem the api can return a direct copy of the item or a pointer to a resource that will inform on the progress of the copy operation.

```python
# copy a file to the documents special folder

documents_folder = drive.get_special_folder('documents')

files = drive.search('george best quotes', limit=1)

if files:
    george_best_quotes = files[0]
    operation = george_best_quotes.copy(target=documents_folder)  # operation here is an instance of CopyOperation
    
    # to check for the result just loop over check_status.
    # check_status is a generator that will yield a new status and progress until the file is finally copied
    for status, progress in operation.check_status():  # if it's an async operations, this will request to the api for the status in every loop
        print('{} - {}'.format(status, progress))  # prints 'in progress - 77.3' until finally completed: 'completed - 100.0'
    copied_item = operation.get_item()  # the copy operation is completed so you can get the item.
    if copied_item:
        copied_item.delete()  # ... oops!
```

You can also work with share permissions:

```python
current_permisions = file.get_permissions()  # get all the current permissions on this drive_item (some may be inherited)

# share with link
permission = file.share_with_link(share_type='edit')
if permission:
    print(permission.share_link)  # the link you can use to share this drive item
# share with invite
permission = file.share_with_invite(recipients='george_best@best.com', send_email=True, message='Greetings!!', share_type='edit')
if permission:
    print(permission.granted_to)  # the person you share this item with
```

You can also:
```python
# download files:
file.download(to_path='/quotes/')

# upload files:

# if the uploaded file is bigger than 4MB the file will be uploaded in chunks of 5 MB until completed.
# this can take several requests and can be time consuming.
uploaded_file = folder.upload_file(item='path_to_my_local_file')

# restore versions:
versiones = file.get_versions()
for version in versions:
    if version.name == '2.0':
        version.restore()  # restore the version 2.0 of this file

# ... and much more ...
```


## Sharepoint
The sharepoint api is done but there are no docs yet. Look at the sharepoint.py file to get insights.


## Planner
The planner api is done but there are no docs yet. Look at the sharepoint.py file to get insights.
The planner functionality requires Administrator Permission.

## Utils

#### Pagination

When using certain methods, it is possible that you request more items than the api can return in a single api call.
In this case the Api, returns a "next link" url where you can pull more data.

When this is the case, the methods in this library will return a `Pagination` object which abstracts all this into a single iterator.
The pagination object will request "next links" as soon as they are needed.

For example:

```python
maibox = account.mailbox()

messages = mailbox.get_messages(limit=1500)  # the Office 365 and MS Graph API have a 999 items limit returned per api call.

# Here messages is a Pagination instance. It's an Iterator so you can iterate over.

# The first 999 iterations will be normal list iterations, returning one item at a time.
# When the iterator reaches the 1000 item, the Pagination instance will call the api again requesting exactly 500 items
# or the items specified in the batch parameter (see later).

for message in messages:
    print(message.subject)
```

When using certain methods you will have the option to specify not only a limit option (the number of items to be returned) but a batch option.
This option will indicate the method to request data to the api in batches until the limit is reached or the data consumed.
This is usefull when you want to optimize memory or network latency.

For example:

```python
messages = mailbox.get_messages(limit=100, batch=25)

# messages here is a Pagination instance
# when iterating over it will call the api 4 times (each requesting 25 items).

for message in messages:  # 100 loops with 4 requests to the api server
    print(message.subject)
```

#### The Query helper

When using the Office 365 API you can filter some fields.
This filtering is tedious as is using [Open Data Protocol (OData)](http://docs.oasis-open.org/odata/odata/v4.0/errata03/os/complete/part2-url-conventions/odata-v4.0-errata03-os-part2-url-conventions-complete.html).

Every `ApiComponent` (such as `MailBox`) implements a new_query method that will return a `Query` instance.
This `Query` instance can handle the filtering (and sorting and selecting) very easily.

For example:

```python
query = mailbox.new_query()

query = query.on_attribute('subject').contains('george best').chain('or').startswith('quotes')

# 'created_date_time' will automatically be converted to the protocol casing.
# For example when using MS Graph this will become 'createdDateTime'.

query = query.chain('and').on_attribute('created_date_time').greater(datetime(2018, 3, 21))

print(query)

# contains(subject, 'george best') or startswith(subject, 'quotes') and createdDateTime gt '2018-03-21T00:00:00Z'
# note you can pass naive datetimes and those will be converted to you local timezone and then send to the api as UTC in iso8601 format

# To use Query objetcs just pass it to the query parameter:
filtered_messages = mailbox.get_messages(query=query)
```

You can also specify specific data to be retrieved with "select":

```python
# select only some properties for the retrieved messages:
query = mailbox.new_query().select('subject', 'to_recipients', 'created_date_time')

messages_with_selected_properties = mailbox.get_messages(query=query)
```

#### Request Error Handling

Whenever a Request error raises, the connection object will raise an exception.
Then the exception will be captured and logged it to the stdout with it's message, an return Falsy (None, False, [], etc...)

HttpErrors 4xx (Bad Request) and 5xx (Internal Server Error) are considered exceptions and raised also by the connection.
You can tell the `Connection` to not raise http errors by passing `raise_http_errors=False` (defaults to True).

#### Soli Deo Gloria
