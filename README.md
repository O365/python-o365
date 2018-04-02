# Py-O365 - Office 365 API made easy

This project aims is to make it easy to interact with Office 365 Email, Contacts, Calendar, OneDrive, etc.

This project is based on the super work done by [Toben Archer](https://github.com/Narcolapser) [Python-O365](https://github.com/Narcolapser/python-o365).
The oauth part is based on the work done by [Royce Melborn](https://github.com/roycem90) which is now integrated with the original project.

I just want to make this project different in almost every sense, and make it also more pythonic (no getters and setters, etc.) and make it also compatible with oauth and basic auth.

The result is a package that provides a lot of the Office 365 API capabilities.

This is for example how you send a message:

```python
from O365 import Account

credentials = ('username@example.com', 'my_password')

account = Account(credentials, auth_method='basic')
m = account.new_message()
m.to.add('to_example@example.com')
m.subject = 'Testing!'
m.body("George Best quote: I've stopped drinking, but only while I'm asleep.")
m.send()
```

Python 3.4 is the minimum required... I was very tempted to just go for 3.6 and use f-strings. Those are fantastic!

This project was also a learning resource for me. This is a list of not so common python characteristics used in this project:
- New unpacking technics: `def method(argument, *, with_name=None, **other_params):`
- Enums: `from enum import Enum`
- Factory paradigm.
- Package organization
- Etc. (see the code!)

> This project is in early development.

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

credentials = ('username@example.com', 'my_password')

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

It's also easy to implement a custom Class.

Just Inherit from ApiComponent, define the endpoints, and use the connection to make requests.

```python
class CustomClass(ApiComponent):
    _endpoints = {'custom': '/customendpoint'}
    
    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__()
        
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
```python
query = mailbox.new_query().on_attribute('subject').contains('george best')  # see query object in Utils
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
The address book.

#### Contact Folders

#### Contacts


## Calendar

## Utils

#### Pagination

#### The Query helper

