[![Downloads](https://pepy.tech/badge/O365)](https://pepy.tech/project/O365)
[![PyPI](https://img.shields.io/pypi/v/O365.svg)](https://pypi.python.org/pypi/O365)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/O365.svg)](https://pypi.python.org/pypi/O365/)
[![Build Status](https://travis-ci.org/O365/python-o365.svg?branch=master)](https://travis-ci.org/O365/python-o365)

# O365 - Microsoft Graph and Office 365 API made easy


> Detailed usage documentation is [still in progress](https://o365.github.io/python-o365/latest/index.html)

> [!IMPORTANT]
> With version 2.1 old access tokens will not work and the library will require a new authentication flow to get new access and refresh tokens.

This project aims to make interacting with Microsoft Graph and Office 365 easy to do in a Pythonic way.
Access to Email, Calendar, Contacts, OneDrive, etc. Are easy to do in a way that feel easy and straight forward to beginners and feels just right to seasoned python programmer.

The project is currently developed and maintained by [alejcas](https://github.com/alejcas).

#### Core developers
- [Alejcas](https://github.com/alejcas)
- [Toben Archer](https://github.com/Narcolapser)
- [Geethanadh](https://github.com/GeethanadhP)

**We are always open to new pull requests!**

#### Rebuilding HTML Docs
- Install `sphinx` python library

    `pip install sphinx`

- Run the shell script `build_docs.sh`, or copy the command from the file when using on windows


#### Quick example on sending a message:

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
- Change between different resource with ease: access shared mailboxes, other users resources, SharePoint resources, etc.
- Pagination support through a custom iterator that handles future requests automatically. Request Infinite items!
- A query helper to help you build custom OData queries (filter, order, select and search).
- Modular ApiComponents can be created and built to achieve further functionality.

___

This project was also a learning resource for us. This is a list of not so common python idioms used in this project:
- New unpacking technics: `def method(argument, *, with_name=None, **other_params):`
- Enums: `from enum import Enum`
- Factory paradigm
- Package organization
- Timezone conversion and timezone aware datetimes
- Etc. ([see the code!](https://github.com/O365/python-o365/tree/master/O365))


What follows is kind of a wiki...

## Table of contents

- [Install](#install)
- [Usage](#usage)
- [Authentication](#authentication)
- [Protocols](#protocols)
- [Account Class and Modularity](#account)
- [MailBox](#mailbox)
- [AddressBook](#addressbook)
- [Directory and Users](#directory-and-users)
- [Calendar](#calendar)
- [Tasks](#tasks)
- [OneDrive](#onedrive)
- [Excel](#excel)
- [SharePoint](#sharepoint)
- [Planner](#planner)
- [Outlook Categories](#outlook-categories)
- [Utils](#utils)


## Install
O365 is available on pypi.org. Simply run `pip install O365` to install it.

Requirements: >= Python 3.9

Project dependencies installed by pip:
 - requests
 - msal
 - beatifulsoup4
 - python-dateutil
 - tzlocal
 - tzdata


## Usage
The first step to be able to work with this library is to register an application and retrieve the auth token. See [Authentication](#authentication).

With the access token retrieved and stored you will be able to perform api calls to the service.

A common pattern to check for authentication and use the library is this one:

```python
scopes = ['my_required_scopes']  # you can use scope helpers here (see Permissions and Scopes section)

account = Account(credentials)

if not account.is_authenticated:  # will check if there is a token and has not expired
    # ask for a login using console based authentication. See Authentication for other flows
    if account.authenticate(scopes=scopes) is False:
        raise RuntimeError('Authentication Failed')

# now we are authenticated
# use the library from now on

# ...
```

## Authentication
You can only authenticate using oauth authentication because Microsoft deprecated basic auth on November 1st 2018.

> [!IMPORTANT]
> Until version 2.1 this library was using a custom authentication mechanism. On 2.1 we moved to using **[msal](https://learn.microsoft.com/es-es/entra/identity-platform/msal-overview)** to achieve the authentication.

There are currently three authentication methods:

- [Authenticate on behalf of a user](https://docs.microsoft.com/en-us/graph/auth-v2-user?context=graph%2Fapi%2F1.0&view=graph-rest-1.0):
Any user will give consent to the app to access its resources.
This oauth flow is called **authorization code grant flow**. This is the default authentication method used by this library.
- [Authenticate on behalf of a user (public)](https://docs.microsoft.com/en-us/graph/auth-v2-user?context=graph%2Fapi%2F1.0&view=graph-rest-1.0):
Same as the former but for public apps where the client secret can't be secured. Client secret is not required.
- [Authenticate with your own identity](https://docs.microsoft.com/en-us/graph/auth-v2-service?context=graph%2Fapi%2F1.0&view=graph-rest-1.0):
This will use your own identity (the app identity). This oauth flow is called **client credentials grant flow**.

    > [!NOTE]
    > 'Authenticate with your own identity' is not an allowed method for **Microsoft Personal accounts**.

When to use one or the other and requirements:

  Topic                             | On behalf of a user *(auth_flow_type=='authorization')*  | On behalf of a user (public) *(auth_flow_type=='public')*  | With your own identity *(auth_flow_type=='credentials')*
 :---:                              | :---:                                                    | :---:                                                      | :---:
 **Register the App**               | Required                                                 | Required                                                   | Required
 **Requires Admin Consent**         | Only on certain advanced permissions                     | Only on certain advanced permissions                       | Yes, for everything
 **App Permission Type**            | Delegated Permissions (on behalf of the user)            | Delegated Permissions (on behalf of the user)              | Application Permissions
 **Auth requirements**              | Client Id, Client Secret, Authorization Code             | Client Id, Authorization Code                              | Client Id, Client Secret
 **Authentication**                 | 2 step authentication with user consent                  | 2 step authentication with user consent                    | 1 step authentication
 **Auth Scopes**                    | Required                                                 | Required                                                   | None
 **Token Expiration**               | 60 Minutes without refresh token or 90 days*             | 60 Minutes without refresh token or 90 days*               | 60 Minutes*
 **Login Expiration**               | Unlimited if there is a refresh token and as long as a refresh is done within the 90 days | Unlimited if there is a refresh token and as long as a refresh is done within the 90 days          | Unlimited
 **Resources**                      | Access the user resources, and any shared resources      | Access the user resources, and any shared resources        | All Azure AD users the app has access to
 **Microsoft Account Type**         | Any                                                      | Any                                                        | Not Allowed for Personal Accounts
 **Tenant ID Required**             | Defaults to "common"                                     | Defaults to "common"                                       | Required (can't be "common")

**O365 will automatically refresh the token for you on either authentication method. The refresh token lasts 90 days but it's refreshed on each connection so as long as you connect within 90 days you can have unlimited access.*

The `Connection` Class handles the authentication.

With auth_flow_type 'credentials' you can authenticate using a certificate based authentication by just passing the client_secret like so:

```python
client_secret = {
    "thumbprint": <thumbprint of cert file>,
    "private_key": <private key from the private_key_file>
 }
credentials = client_id, client_secret
account = Account(credentials)
```

#### Oauth Authentication
This section is explained using Microsoft Graph Protocol, almost the same applies to the Office 365 REST API.

##### Authentication Steps
1. **Log in to the Microsoft Entra Admin Center**  
   - Visit [https://entra.microsoft.com/](https://entra.microsoft.com/) and sign in.

1. **Create a new application and note its App (client) ID**  
   - In the left navigation bar, select **Applications** > **App registrations**.  
   - Click **+ New registration**.  
   - Provide a **Name** for the application and keep all defaults.  
   - From the **Overview** of your new application, copy the (client_id) **Application (client) ID** for later reference.

1. **Generate a new password (client_secret)**  
   - In the **Overview** window, select **Certificates & secrets**.  
   - Click **New client secret**.  
   - In the **Add a client secret** window, provide a Description and Expiration, then click **Add**.  
   - Save the (client_secret) **Value** for later reference.

1. **Add redirect URIs and set Multitenant Account Type**  
   - In the **Overview** window, click **Add a redirect URI**.  
   - Click **+ Add a platform**, then select **Web**.  
   - Add `https://login.microsoftonline.com/common/oauth2/nativeclient` as the redirect URI.
   - Scroll down to **Supported account types**
   - Select the radio button in front of **Accounts in any organizational directory (Any Microsoft Entra ID tenant - Multitenant)**
   - Click **Save**.

1. **Add required permissions**  
   - In the left navigation bar, select **API permissions**.  
   - Click **+ Add a permission**.  
   - Under **Microsoft Graph**, select **Delegated permissions**.  
   - Add the delegated permissions you plan to use (for example):
     - Mail.Read
     - Mail.ReadWrite
     - Mail.Send
     - User.Read
     - User.ReadBasic.All
     - offline_access
   - Click **Add permissions**.

> [!IMPORTANT]
> The offline_access permission is required for the refresh token to work.

1. Then you need to log in for the first time to get the access token that will grant access to the user resources.

    To authenticate (login) you can use [different authentication interfaces](#different-authentication-interfaces). On the following examples we will be using the Console Based Interface, but you can use any one.

    - When authenticating on behalf of a user:

> [!IMPORTANT]
>  In case you can't secure the client secret you can use the auth flow type 'public' which only requires the client id.

        1. Instantiate an `Account` object with the credentials (client id and client secret).
        1. Call `account.authenticate` and pass the scopes you want (the ones you previously added on the app registration portal).

            > Note: when using the "on behalf of a user" authentication, you can pass the scopes to either the `Account` init or to the authenticate method. Either way is correct.

            You can pass "protocol scopes" (like: "https://graph.microsoft.com/Calendars.ReadWrite") to the method or use "[scope helpers](https://github.com/O365/python-o365/blob/master/O365/connection.py#L34)" like ("message_all").
            If you pass protocol scopes, then the `account` instance must be initialized with the same protocol used by the scopes. By using scope helpers you can abstract the protocol from the scopes and let this library work for you.
            Finally, you can mix and match "protocol scopes" with "scope helpers".
            Go to the [procotol section](#protocols) to know more about them.

            For Example (following the previous permissions added):

            ```python
            from O365 import Account
            credentials = ('my_client_id', 'my_client_secret')

            # the default protocol will be Microsoft Graph
            # the default authentication method will be "on behalf of a user"

            account = Account(credentials)
            if account.authenticate(scopes=['basic', 'message_all']):
               print('Authenticated!')

            # 'basic' adds: 'https://graph.microsoft.com/User.Read'
            # 'message_all' adds: 'https://graph.microsoft.com/Mail.ReadWrite' and 'https://graph.microsoft.com/Mail.Send'
            ```
            When using the "on behalf of the user" authentication method, this method call will print an url that the user must visit to give consent to the app on the required permissions.

            The user must then visit this url and give consent to the application. When consent is given, the page will rediret to: "https://login.microsoftonline.com/common/oauth2/nativeclient" by default (you can change this) with an url query param called 'code'.

            Then the user must copy the resulting page url and paste it back on the console.
            The method will then return True if the login attempt was succesful.

    - When authenticating with your own identity:

        1. Instantiate an `Account` object with the credentials (client id and client secret), specifying the parameter `auth_flow_type` to *"credentials"*. You also need to provide a 'tenant_id'. You don't need to specify any scopes.
        1. Call `account.authenticate`. This call will request a token for you and store it in the backend. No user interaction is needed. The method will store the token in the backend and return True if the authentication succeeded.

            For Example:
            ```python
            from O365 import Account

            credentials = ('my_client_id', 'my_client_secret')

            # the default protocol will be Microsoft Graph

            account = Account(credentials, auth_flow_type='credentials', tenant_id='my-tenant-id')
            if account.authenticate():
               print('Authenticated!')
            ```

1. At this point you will have an access token stored that will provide valid credentials when using the api.

    The access token only lasts **60 minutes**, but the app will automatically request new access tokens if you added the 'offline access' permission.

    When using the "on behalf of a user" authentication method this is accomplished through the refresh tokens (if and only if you added the "offline_access" permission), but note that a refresh token only lasts for 90 days. So you must use it before, or you will need to request a new access token again (no new consent needed by the user, just a login).
    If your application needs to work for more than 90 days without user interaction and without interacting with the API, then you must implement a periodic call to `Connection.refresh_token` before the 90 days have passed.

> [!IMPORTANT]
> Take care: the access (and refresh) token must **remain protected from unauthorized users**.

    Under the "on behalf of a user" authentication method, if you change the scope requested, then the current token won't work, and you will need the user to give consent again on the application to gain access to the new scopes requested.


##### Different Authentication Interfaces

To acomplish the authentication you can basically use different approaches.
The following apply to the "on behalf of a user" authentication method as this is 2-step authentication flow.
For the "with your own identity" authentication method, you can just use `account.authenticate` as it's not going to require a console input.

1. Console based authentication interface:

    You can authenticate using a console. The best way to achieve this is by using the `authenticate` method of the `Account` class.

    ```python
    account = Account(credentials)
    account.authenticate(scopes=['basic', 'message_all'])
    ```

    The `authenticate` method will print into the console an url that you will have to visit to achieve authentication.
    Then after visiting the link and authenticate you will have to paste back the resulting url into the console.
    The method will return `True` and print a message if it was succesful.

    **Tip:** When using macOS the console is limited to 1024 characters. If your url has multiple scopes it can exceed this limit. To solve this. Just `import readline` at the top of your script.

1. Web app based authentication interface:

    You can authenticate your users in a web environment by following these steps:

    1. First ensure you are using an appropiate TokenBackend to store the auth tokens (See Token storage below).
    1. From a handler redirect the user to the Microsoft login url. Provide a callback. Store the flow dictionary.
    1. From the callback handler complete the authentication with the flow dict and other data.

    The following example is done using Flask.
    ```python
    from flask import request
    from O365 import Account
    
    
    @route('/stepone')
    def auth_step_one():
        # callback = absolute url to auth_step_two_callback() page, https://domain.tld/steptwo
        callback = url_for('auth_step_two_callback', _external=True)  # Flask example

        account = Account(credentials)
        url, flow = account.con.get_authorization_url(requested_scopes=my_scopes,
                                                       redirect_uri=callback)
        
        flow_as_string = serialize(flow)  # convert the dict into a string using json for example
        # the flow must be saved somewhere as it will be needed later
        my_db.store_flow(flow_as_string) # example...

        return redirect(url)

    @route('/steptwo')
    def auth_step_two_callback():
        account = Account(credentials)

        # retrieve the state saved in auth_step_one
        my_saved_flow_str = my_db.get_flow()  # example...
        my_saved_flow = deserialize(my_saved_flow_str)  # convert from a string to a dict using json for example.

        # rebuild the redirect_uri used in auth_step_one
        callback = 'my absolute url to auth_step_two_callback'

        # get the request URL of the page which will include additional auth information
        # Example request: /steptwo?code=abc123&state=xyz456
        requested_url = request.url  # uses Flask's request() method

        result = account.con.request_token(requested_url,
                                           flow=my_saved_flow)
        # if result is True, then authentication was succesful
        #  and the auth token is stored in the token backend
        if result:
            return render_template('auth_complete.html')
        # else ....
    ```

1. Other authentication interfaces:

    Finally you can configure any other flow by using `connection.get_authorization_url` and `connection.request_token` as you want.


##### Permissions and Scopes:

###### Permissions

When using oauth, you create an application and allow some resources to be accessed and used by its users.
These resources are managed with permissions. These can either be delegated (on behalf of a user) or aplication permissions.
The former are used when the authentication method is "on behalf of a user". Some of these require administrator consent.
The latter when using the "with your own identity" authentication method. All of these require administrator consent.

###### Scopes

The scopes only matter when using the "on behalf of a user" authentication method.

> Note: You only need the scopes when login as those are kept stored within the token on the token backend.

The user of this library can then request access to one or more of these resources by providing scopes to the oauth provider.

> Note: If you later on change the scopes requested, the current token will be invaled, and you will have to re-authenticate. The user that logins will be asked for consent.

For example your application can have Calendar.Read, Mail.ReadWrite and Mail.Send permissions, but the application can request access only to the Mail.ReadWrite and Mail.Send permission.
This is done by providing scopes to the `Account` instance or `account.authenticate` method like so:

```python
from O365 import Account

credentials = ('client_id', 'client_secret')

scopes = ['Mail.ReadWrite', 'Mail.Send']

account = Account(credentials, scopes=scopes)
account.authenticate()

# The later is exactly the same as passing scopes to the authenticate method like so:
# account = Account(credentials)
# account.authenticate(scopes=scopes)
```

Scope implementation depends on the protocol used. So by using protocol data you can automatically set the scopes needed.
This is implemented by using 'scope helpers'. Those are little helpers that group scope functionality and abstract the protocol used.

Scope Helper                       | Scopes included
:---                               | :---
basic                              | 'User.Read'
mailbox                            | 'Mail.Read'
mailbox_shared                     | 'Mail.Read.Shared'
mailbox_settings                   | 'MailboxSettings.ReadWrite'
message_send                       | 'Mail.Send'
message_send_shared                | 'Mail.Send.Shared'
message_all                        | 'Mail.ReadWrite' and 'Mail.Send'
message_all_shared                 | 'Mail.ReadWrite.Shared' and 'Mail.Send.Shared'
address_book                       | 'Contacts.Read'
address_book_shared                | 'Contacts.Read.Shared'
address_book_all                   | 'Contacts.ReadWrite'
address_book_all_shared            | 'Contacts.ReadWrite.Shared'
calendar                           | 'Calendars.Read'
calendar_shared                    | 'Calendars.Read.Shared'
calendar_all                       | 'Calendars.ReadWrite'
calendar_shared_all                | 'Calendars.ReadWrite.Shared'
users                              | 'User.ReadBasic.All'
onedrive                           | 'Files.Read.All'
onedrive_all                       | 'Files.ReadWrite.All'
sharepoint                         | 'Sites.Read.All'
sharepoint_dl                      | 'Sites.ReadWrite.All'
settings_all                       | 'MailboxSettings.ReadWrite'
tasks                              | 'Tasks.Read'
tasks_all                          | 'Tasks.ReadWrite'
presence                           | 'Presence.Read'


You can get the same scopes as before using protocols and scope helpers like this:

```python
protocol_graph = MSGraphProtocol()

scopes_graph = protocol.get_scopes_for('message all')
# scopes here are: ['https://graph.microsoft.com/Mail.ReadWrite', 'https://graph.microsoft.com/Mail.Send']

account = Account(credentials, scopes=scopes_graph)
```

```python
protocol_office = MSOffice365Protocol()

scopes_office = protocol.get_scopes_for('message all')
# scopes here are: ['https://outlook.office.com/Mail.ReadWrite', 'https://outlook.office.com/Mail.Send']

account = Account(credentials, scopes=scopes_office)
```

> Note: When passing scopes at the `Account` initialization or on the `account.authenticate` method, the scope helpers are autommatically converted to the protocol flavor.
>Those are the only places where you can use scope helpers. Any other object using scopes (such as the `Connection` object) expects scopes that are already set for the protocol.



##### Token storage:
When authenticating you will retrieve oauth tokens. If you don't want a one time access you will have to store the token somewhere.
O365 makes no assumptions on where to store the token and tries to abstract this from the library usage point of view.

You can choose where and how to store tokens by using the proper Token Backend.

> **Take care: the access (and refresh) token must remain protected from unauthorized users.** You can plug in a "cryptography_manager" (object that can call encrypt and decrypt) into TokenBackends "cryptography_manager" attribute. 

The library will call (at different stages) the token backend methods to load and save the token.

Methods that load tokens:
- `account.is_authenticated` property will try to load the token if is not already loaded.
- `connection.get_session`: this method is called when there isn't a request session set.

Methods that stores tokens:
- `connection.request_token`: by default will store the token, but you can set `store_token=False` to avoid it.
- `connection.refresh_token`: by default will store the token. To avoid it change `connection.store_token_after_refresh` to False. This however it's a global setting (that only affects the `refresh_token` method). If you only want the next refresh operation to not store the token you will have to set it back to True afterward.

To store the token you will have to provide a properly configured TokenBackend.

There are a few `TokenBackend` classes implemented (and you can easily implement more like a CookieBackend, RedisBackend, etc.):
- `FileSystemTokenBackend` (Default backend): Stores and retrieves tokens from the file system. Tokens are stored as text files.
- `MemoryTokenBackend`: Stores the tokens in memory. Basically load_token and save_token does nothing.
- `EnvTokenBackend`: Stores and retrieves tokens from environment variables.
- `FirestoreTokenBackend`: Stores and retrives tokens from a Google Firestore Datastore. Tokens are stored as documents within a collection.
- `AWSS3Backend`: Stores and retrieves tokens from an AWS S3 bucket. Tokens are stored as a file within a S3 bucket.
- `AWSSecretsBackend`: Stores and retrieves tokens from an AWS Secrets Management vault.
- `BitwardenSecretsManagerBackend`: Stores and retrieves tokens from Bitwarden Secrets Manager.
- `DjangoTokenBackend`: Stores and retrieves tokens using a Django model. 

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
from O365 import Account
from O365.utils import FirestoreBackend
from google.cloud import firestore

credentials = ('id', 'secret')

# this will store the token on firestore under the tokens collection on the defined doc_id.
# you can pass strings to token_path or Path instances from pathlib
user_id = 'whatever the user id is'  # used to create the token document id
document_id = f"token_{user_id}"  # used to uniquely store this token
token_backend = FirestoreBackend(client=firestore.Client(), collection='tokens', doc_id=document_id)
account = Account(credentials, token_backend=token_backend)

# This account instance tokens will be stored on the token_backend configured before.
# You don't have to do anything more
# ...
```

To implement a new TokenBackend:

 1. Subclass `BaseTokenBackend`
 1. Implement the following methods:

     - `__init__` (don't forget to call `super().__init__`)
     - `load_token`: this should load the token from the desired backend and return a `Token` instance or None
     - `save_token`: this should store the `self.token` in the desired backend.
     - Optionally you can implement: `check_token`, `delete_token` and `should_refresh_token`

The `should_refresh_token` method is intended to be implemented for environments where multiple Connection instances are running on paralel.
This method should check if it's time to refresh the token or not.
The chosen backend can store a flag somewhere to answer this question.
This can avoid race conditions between different instances trying to refresh the token at once, when only one should make the refresh.
The method should return three posible values:
- **True**: then the Connection will refresh the token.
- **False**: then the Connection will NOT refresh the token.
- **None**: then this method already executed the refresh and therefore the Connection does not have to.

By default, this always returns True as it's assuming there is are no parallel connections running at once.

There are two examples of this method in the examples folder [here](https://github.com/O365/python-o365/blob/master/examples/token_backends.py).


## Multi user handling
A single `Account` object can hold more than one user being authenticated. You can authenticate different users and the token backend will hold each authentication.
When using the library you can use the `account.username` property to get or set the current user.
If username is not provided, the username will be set automatically to the first authentication found in the token backend.
Also, whenever you perform a new call to `request_token` (manually or through a call to `account.authenticate`), the username will be set to the user performing the authentication.

```python
account.username = 'user1@domain.com'
#  issue some calls to retrieve data using the auth of the user1
account.username = 'user2@domain.com'
#  now every call will use the auth of the user2
```
> This is only possible in version 2.1. Before 2.1 you had to instantiate one Account for each user.

## Protocols
Protocols handles the aspects of communications between different APIs.
This project uses either the Microsoft Graph APIs (by default) or the Office 365 APIs.
But, you can use many other Microsoft APIs as long as you implement the protocol needed.

You can use one or the other:

- `MSGraphProtocol` to use the [Microsoft Graph API](https://developer.microsoft.com/en-us/graph/docs/concepts/overview)
- `MSOffice365Protocol` to use the [Office 365 API](https://msdn.microsoft.com/en-us/office/office365/api/api-catalog)

Both protocols are similar but consider the following:

Reasons to use `MSGraphProtocol`:
- It is the recommended Protocol by Microsoft.
- It can access more resources over Office 365 (for example OneDrive)

Reasons to use `MSOffice365Protocol`:
- It can send emails with attachments up to 150 MB. MSGraph only allows 4MB on each request (UPDATE: Starting 22 October'19 you can [upload files up to 150MB with MSGraphProtocol **beta** version](https://developer.microsoft.com/en-us/office/blogs/attaching-large-files-to-outlook-messages-in-microsoft-graph-preview/)) However, this will still run into an issue and return a HTTP 413 error. The workaround for the moment is to do as follows:
```python
from O365 import Account

credentials = ('client_id', 'client_secret')

account = Account(credentials, auth_flow_type='credentials', tenant_id='my_tenant_id')
if account.authenticate():
   print('Authenticated!')
   mailbox = account.mailbox('sender_email@my_domain.com') 
   m = mailbox.new_message()
   m.to.add('to_example@example.com')
   m.subject = 'Testing!'
   m.body = "George Best quote: I've stopped drinking, but only while I'm asleep."
   m.save_message()
   m.attachment.add = 'filename.txt'
   m.send()
```

The default protocol used by the `Account` Class is `MSGraphProtocol`.

You can implement your own protocols by inheriting from `Protocol` to communicate with other Microsoft APIs.

You can instantiate and use protocols like this:
```python
from O365 import Account, MSGraphProtocol  # same as from O365.connection import MSGraphProtocol

# ...

# try the api version beta of the Microsoft Graph endpoint.
protocol = MSGraphProtocol(api_version='beta')  # MSGraphProtocol defaults to v1.0 api version
account = Account(credentials, protocol=protocol)
```

##### Resources:
Each API endpoint requires a resource. This usually defines the owner of the data.
Every protocol defaults to resource 'ME'. 'ME' is the user which has given consent, but you can change this behaviour by providing a different default resource to the protocol constructor.

> Note: When using the "with your own identity" authentication method the resource 'ME' is overwritten to be blank as the authentication method already states that you are login with your own identity.

For example when accessing a shared mailbox:


```python
# ...
account = Account(credentials=my_credentials, main_resource='shared_mailbox@example.com')
# Any instance created using account will inherit the resource defined for account.
```

This can be done however at any point. For example at the protocol level:
```python
# ...
protocol = MSGraphProtocol(default_resource='shared_mailbox@example.com')

account = Account(credentials=my_credentials, protocol=protocol)

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

- **'me'**: the user which has given consent. the default for every protocol. Overwritten when using "with your own identity" authentication method (Only available on the authorization auth_flow_type).
- **'user:user@domain.com'**: a shared mailbox or a user account for which you have permissions. If you don't provide 'user:' will be infered anyways.
- **'site:sharepoint-site-id'**: a sharepoint site id.
- **'group:group-site-id'**: a office365 group id.

By setting the resource prefix (such as **'user:'** or **'group:'**) you help the library understand the type of resource. You can also pass it like 'users/example@exampl.com'. Same applies to the other resource prefixes.


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
from O365 import Connection, MSGraphProtocol
from O365.message import Message
from O365.mailbox import MailBox

protocol = MSGraphProtocol()
scopes = ['...']
con = Connection(('client_id', 'client_secret'), scopes=scopes)

message = Message(con=con, protocol=protocol)
# ...
mailbox = MailBox(con=con, protocol=protocol)
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
        # connection is only needed if you want to communicate with the api provider
        self.con = parent.con if parent else con
        protocol = parent.protocol if parent else kwargs.get('protocol')
        main_resource = parent.main_resource

        super().__init__(protocol=protocol, main_resource=main_resource)
        # ...

    def do_some_stuff(self):

        # self.build_url just merges the protocol service_url with the enpoint passed as a parameter
        # to change the service_url implement your own protocol inherinting from Protocol Class
        url = self.build_url(self._endpoints.get('my_url_key'))

        my_params = {'param1': 'param1'}

        response = self.con.get(url, params=my_params)  # note the use of the connection here.

        # handle response and return to the user...

# the use it as follows:
from O365 import Connection, MSGraphProtocol

protocol = MSGraphProtocol()  # or maybe a user defined protocol
con = Connection(('client_id', 'client_secret'), scopes=protocol.get_scopes_for(['...']))
custom_class = CustomClass(con=con, protocol=protocol)

custom_class.do_some_stuff()
```

## MailBox
Mailbox groups the funcionality of both the messages and the email folders.

These are the scopes needed to work with the `MailBox` and `Message` classes.

 Raw Scope                   |  Included in Scope Helper                  | Description
 :---:                       |  :---:                                     | ---
 *Mail.Read*                 |  *mailbox*                                 | To only read my mailbox
 *Mail.Read.Shared*          |  *mailbox_shared*                          | To only read another user / shared mailboxes
 *Mail.Send*                 |  *message_send, message_all*               | To only send message
 *Mail.Send.Shared*          |  *message_send_shared, message_all_shared* | To only send message as another user / shared mailbox
 *Mail.ReadWrite*            |  *message_all*                             | To read and save messages in my mailbox
 *MailboxSettings.ReadWrite* |  *mailbox_settings*                        | To read and write suer mailbox settings

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
An email object with all its data and methods.

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

##### Sending Inline Images
You can send inline images by doing this:

```python
# ...
msg = account.new_message()
msg.to.add('george@best.com')
msg.attachments.add('my_image.png')
att = msg.attachments[0]  # get the attachment object

# this is super important for this to work.
att.is_inline = True
att.content_id = 'image.png'

# notice we insert an image tag with source to: "cid:{content_id}"
body = """
    <html>
        <body>
            <strong>There should be an image here:</strong>
            <p>
                <img src="cid:image.png">
            </p>
        </body>
    </html>
    """
msg.body = body
msg.send()
```

##### Retrieving Message Headers
You can retrieve message headers by doing this:

```python
# ...
mb = account.mailbox()
msg = mb.get_message(query=mb.q().select('internet_message_headers'))
print(msg.message_headers)  # returns a list of dicts.
```

Note that only message headers and other properties added to the select statement will be present.

##### Saving as EML
Messages and attached messages can be saved as *.eml.

 - Save message as "eml":
    ```python
        msg.save_as_eml(to_path=Path('my_saved_email.eml'))
    ```
- Save attached message as "eml":

    Carefull: there's no way to identify that an attachment is in fact a message. You can only check if the attachment.attachment_type == 'item'.
    if is of type "item" then it can be a message (or an event, etc...). You will have to determine this yourself.

    ```python
        msg_attachment = msg.attachments[0]  # the first attachment is attachment.attachment_type == 'item' and I know it's a message.
        msg.attachments.save_as_eml(msg_attachment, to_path=Path('my_saved_email.eml'))
    ```

#### Mailbox Settings
The mailbox settings and associated methods.

Retrieve and update mailbox auto reply settings:
```python
from O365.mailbox import AutoReplyStatus, ExternalAudience

mailboxsettings = mailbox.get_settings()
ars = mailboxsettings.automaticrepliessettings

ars.scheduled_startdatetime = start # Sets the start date/time
ars.scheduled_enddatetime = end # Sets the end date/time
ars.status = AutoReplyStatus.SCHEDULED # DISABLED/SCHEDULED/ALWAYSENABLED - Uses start/end date/time if scheduled.
ars.external_audience = ExternalAudience.NONE # NONE/CONTACTSONLY/ALL
ars.internal_reply_message = "ARS Internal" # Internal message
ars.external_reply_message = "ARS External" # External message
mailboxsettings.save()
```

Alternatively to enable and disable
```python
mailboxsettings.save()

mailbox.set_automatic_reply(
    "Internal",
    "External",
    scheduled_start_date_time=start, # Status will be 'scheduled' if start/end supplied, otherwise 'alwaysEnabled'
    scheduled_end_date_time=end,
    externalAudience=ExternalAudience.NONE, # Defaults to ALL
)
mailbox.set_disable_reply()
```

## AddressBook
AddressBook groups the functionality of both the Contact Folders and Contacts. Outlook Distribution Groups are not supported (By the Microsoft API's).

These are the scopes needed to work with the `AddressBook` and `Contact` classes.

 Raw Scope                       |  Included in Scope Helper                        | Description
 :---:                           |  :---:                                          | ---
 *Contacts.Read*                 |  *address_book*                                 | To only read my personal contacts
 *Contacts.Read.Shared*          |  *address_book_shared*                          | To only read another user / shared mailbox contacts
 *Contacts.ReadWrite*            |  *address_book_all*                             | To read and save personal contacts
 *Contacts.ReadWrite.Shared*     |  *address_book_all_shared*                      | To read and save contacts from another user / shared mailbox
 *User.ReadBasic.All*            |  *users*                                        | To only read basic properties from users of my organization (User.Read.All requires administrator consent).

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
global_address_list = account.directory()

# for backwards compatibilty only this also works and returns a Directory object:
# global_address_list = account.address_book(address_book='gal')

# start a new query:
q = global_address_list.new_query('display_name')
q.startswith('George Best')

for user in global_address_list.get_users(query=q):
    print(user)
```


To retrieve a contact by their email:

```python
contact = global_address_list.get_user('example@example.com')
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


## Directory and Users
The Directory object can retrieve users.

A User instance contains by default the [basic properties of the user](https://docs.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0&tabs=http#optional-query-parameters).
If you want to include more, you will have to select the desired properties manually.

Check [The Global Address List](#the-global-address-list) for further information.

These are the scopes needed to work with the `Directory` class.

 Raw Scope                        |  Included in Scope Helper                       | Description
 :---:                            |  :---:                                          | ---
 *User.ReadBasic.All*             |  *users*                                        | To read a basic set of profile properties of other users in your organization on behalf of the signed-in user. This includes display name, first and last name, email address, open extensions and photo. Also allows the app to read the full profile of the signed-in user.
 *User.Read.All*                  |  *—*                                            | To read the full set of profile properties, reports, and managers of other users in your organization, on behalf of the signed-in user.
 *User.ReadWrite.All*             |  *—*                                            | To read and write the full set of profile properties, reports, and managers of other users in your organization, on behalf of the signed-in user. Also allows the app to create and delete users as well as reset user passwords on behalf of the signed-in user.
 *Directory.Read.All*             |  *—*                                            | To read data in your organization's directory, such as users, groups and apps, without a signed-in user.
 *Directory.ReadWrite.All*        |  *—*                                            | To read and write data in your organization's directory, such as users, and groups, without a signed-in user. Does not allow user or group deletion.

Note: To get authorized with the above scopes you need a work or school account, it doesn't work with personal account.

Working with the `Directory` instance to read the active directory users:

```python
directory = account.directory()
for user in directory.get_users():
    print(user)
```


## Calendar
The calendar and events functionality is group in a `Schedule` object.

A `Schedule` instance can list and create calendars. It can also list or create events on the default user calendar.
To use other calendars use a `Calendar` instance.

These are the scopes needed to work with the `Schedule`, `Calendar` and `Event` classes.

 Raw Scope                        |  Included in Scope Helper                        | Description
 :---:                            |  :---:                                          | ---
 *Calendars.Read*                 |  *calendar*                                     | To only read my personal calendars
 *Calendars.Read.Shared*          |  *calendar_shared*                              | To only read another user / shared mailbox calendars
 *Calendars.ReadWrite*            |  *calendar_all*                                 | To read and save personal calendars
 *Calendars.ReadWrite.Shared*     |  *calendar_shared_all*                          | To read and save calendars from another user / shared mailbox


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

birthdays = calendar.get_events(query=q, include_recurring=True)  # include_recurring=True will include repeated events on the result set.

for event in birthdays:
    if event.subject == 'George Best Birthday':
        # He died in 2005... but we celebrate anyway!
        event.accept("I'll attend!")  # send a response accepting
    else:
        event.decline("No way I'm comming, I'll be in Spain", send_response=False)  # decline the event but don't send a reponse to the organizer
```

#### Notes regarding Calendars and Events:

1. Include_recurring=True:
    > It's important to know that when querying events with `include_recurring=True` (which is the default), it is required that you must provide a query parameter with the start and end attributes defined.
    > Unlike when using `include_recurring=False` those attributes will NOT filter the data based on the operations you set on the query (greater_equal, less, etc.) but just filter the events start datetime between the provided start and end datetimes.

1. Shared Calendars:

    There are some known issues when working with [shared calendars](https://docs.microsoft.com/en-us/graph/known-issues#calendars) in Microsoft Graph.

1. Event attachments:

    For some unknow reason, microsoft does not allow to upload an attachment at the event creation time (as opposed with message attachments).
    See [this](https://stackoverflow.com/questions/46438302/office365-rest-api-creating-a-calendar-event-with-attachments?rq=1).
    So, to upload attachments to Events, first save the event, then attach the message and save again.

## Tasks

The tasks functionality is grouped in a `ToDo` object.

A `ToDo` instance can list and create task folders. It can also list or create tasks on the default user folder. To use other folders use a `Folder` instance.

These are the scopes needed to work with the `ToDo`, `Folder` and `Task` classes.

 Raw Scope                        |  Included in Scope Helper                       | Description
 :---:                            |  :---:                                          | ---
 *Tasks.Read*                     |  *tasks*                                        | To only read my personal tasks
 *Tasks.ReadWrite*                |  *tasks_all*                                    | To read and save personal calendars

 Working with the `ToDo` instance:
```python
import datetime as dt

# ...
todo = account.tasks()

#list current tasks
folder = todo.get_default_folder()
new_task = folder.new_task()  # creates a new unsaved task
new_task.subject = 'Send contract to George Best'
new_task.due = dt.datetime(2020, 9, 25, 18, 30) 
new_task.save()

#some time later....

new_task.mark_completed()
new_task.save()

# naive datetimes will automatically be converted to timezone aware datetime
#  objects using the local timezone detected or the protocol provided timezone
#  as with the Calendar functionality

```

Working with `Folder` instances:

```python
#create a new folder
new_folder = todo.new_folder('Defenders')

#rename a folder
folder = todo.get_folder(folder_name='Strikers')
folder.name = 'Forwards'
folder.update()

#list current tasks
task_list = folder.get_tasks()
for task in task_list:
    print(task)
    print('')
```

## OneDrive
The `Storage` class handles all functionality around One Drive and Document Library Storage in SharePoint.

The `Storage` instance allows to retrieve `Drive` instances which handles all the Files and Folders from within the selected `Storage`.
Usually you will only need to work with the default drive. But the `Storage` instances can handle multiple drives.

A `Drive` will allow you to work with Folders and Files.

These are the scopes needed to work with the `Storage`, `Drive` and `DriveItem` classes.

 Raw Scope                  |  Included in Scope Helper     | Description
 :---:                      |  :---:                       | ---
 *Files.Read*               |                              | To only read my files
 *Files.Read.All*           |  *onedrive*                  | To only read all the files the user has access
 *Files.ReadWrite*          |                              | To read and save my files
 *Files.ReadWrite.All*      |  *onedrive_all*              | To read and save all the files the user has access


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
        print(list(item.get_items(2)))  # print the first to element on this folder.
    elif item.is_file:
        if item.is_photo:
            print(item.camera_model)  # print some metadata of this photo
        elif item.is_image:
            print(item.dimensions)  # print the image dimensions
        else:
            # regular file:
            print(item.mime_type)  # print the mime type
```

Both Files and Folders are DriveItems. Both Image and Photo are Files, but Photo is also an Image. All have some different methods and properties.
Take care when using 'is_xxxx'.

When copying a DriveItem the api can return a direct copy of the item or a pointer to a resource that will inform on the progress of the copy operation.

```python
# copy a file to the documents special folder

documents_folder = my_drive.get_special_folder('documents')

files = my_drive.search('george best quotes', limit=1)

if files:
    george_best_quotes = files[0]
    operation = george_best_quotes.copy(target=documents_folder)  # operation here is an instance of CopyOperation

    # to check for the result just loop over check_status.
    # check_status is a generator that will yield a new status and progress until the file is finally copied
    for status, progress in operation.check_status():  # if it's an async operations, this will request to the api for the status in every loop
        print(f"{status} - {progress}")  # prints 'in progress - 77.3' until finally completed: 'completed - 100.0'
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
versions = file.get_versions()
for version in versions:
    if version.name == '2.0':
        version.restore()  # restore the version 2.0 of this file

# ... and much more ...
```


## Excel
You can interact with new Excel files (.xlsx) stored in OneDrive or a SharePoint Document Library.
You can retrieve workbooks, worksheets, tables, and even cell data.
You can also write to any excel online.

To work with Excel files, first you have to retrieve a `File` instance using the OneDrive or SharePoint functionallity.

The scopes needed to work with the `WorkBook` and Excel related classes are the same used by OneDrive.

This is how you update a cell value:

```python
from O365.excel import WorkBook

# given a File instance that is a xlsx file ...
excel_file = WorkBook(my_file_instance)  # my_file_instance should be an instance of File.

ws = excel_file.get_worksheet('my_worksheet')
cella1 = ws.get_range('A1')
cella1.values = 35
cella1.update()
```

#### Workbook Sessions
When interacting with Excel, you can use a workbook session to efficiently make changes in a persistent or nonpersistent way.
These sessions become usefull if you perform numerous changes to the Excel file.

The default is to use a session in a persistent way.
Sessions expire after some time of inactivity. When working with persistent sessions, new sessions will automatically be created when old ones expire.

You can however change this when creating the `Workbook` instance:

```python
excel_file = WorkBook(my_file_instance, use_session=False, persist=False)
```

#### Available Objects

After creating the `WorkBook` instance you will have access to the following objects:

- WorkSheet
- Range and NamedRange
- Table, TableColumn and TableRow
- RangeFormat (to format ranges)
- Charts (not available for now)

Some examples:

Set format for a given range
```python
# ...
my_range = ws.get_range('B2:C10')
fmt = myrange.get_format()
fmt.font.bold = True
fmt.update()
```
Autofit Columns:
```python
ws.get_range('B2:C10').get_format().auto_fit_columns()
```

Get values from Table:
```python
table = ws.get_table('my_table')
column = table.get_column_at_index(1)
values = column.values[0]  # values returns a two dimensional array.
```

## SharePoint
The SharePoint api is done but there are no docs yet. Look at the sharepoint.py file to get insights.

These are the scopes needed to work with the `SharePoint` and `Site` classes.

 Raw Scope                  |  Included in Scope Helper    | Description
 :---:                      |  :---:                       | ---
 *Sites.Read.All*           |  *sharepoint*                | To only read sites, lists and items
 *Sites.ReadWrite.All*      |  *sharepoint_dl*             | To read and save sites, lists and items

## Planner
The planner api is done but there are no docs yet. Look at the planner.py file to get insights.

The planner functionality requires Administrator Permission.

## Outlook Categories
You can retrive, update, create and delete outlook categories.
These categories can be used to categorize Messages, Events and Contacts.

These are the scopes needed to work with the `SharePoint` and `Site` classes.

 Raw Scope                      |  Included in Scope Helper     | Description
 :---:                          |  :---:                        | ---
 *MailboxSettings.Read*         |  *-*                          | To only read outlook settingss
 *MailboxSettings.ReadWrite*    |  *settings_all*               | To read and write outlook settings

Example:

```python
from O365.category import CategoryColor

oc = account.outlook_categories()
categories = oc.get_categories()
for category in categories:
    print(category.name, category.color)

my_category = oc.create_category('Important Category', color=CategoryColor.RED)
my_category.update_color(CategoryColor.DARKGREEN)

my_category.delete()  # oops!
```

## Utils

#### Pagination

When using certain methods, it is possible that you request more items than the api can return in a single api call.
In this case the Api, returns a "next link" url where you can pull more data.

When this is the case, the methods in this library will return a `Pagination` object which abstracts all this into a single iterator.
The pagination object will request "next links" as soon as they are needed.

For example:

```python
mailbox = account.mailbox()

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

When using the Office 365 API you can filter, order, select, expand or search on some fields.
This filtering is tedious as is using [Open Data Protocol (OData)](http://docs.oasis-open.org/odata/odata/v4.0/errata03/os/complete/part2-url-conventions/odata-v4.0-errata03-os-part2-url-conventions-complete.html).

Every `ApiComponent` (such as `MailBox`) implements a new_query method that will return a `Query` instance.
This `Query` instance can handle the filtering, sorting, selecting, expanding and search very easily.

For example:

```python
query = mailbox.new_query()  # you can use the shorthand: mailbox.q()

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

You can also search content. As said in the graph docs:

> You can currently search only message and person collections. A $search request returns up to 250 results. You cannot use $filter or $orderby in a search request.

> If you do a search on messages and specify only a value without specific message properties, the search is carried out on the default search properties of from, subject, and body.

```python
# searching is the easy part ;)
query = mailbox.q().search('george best is da boss')
messages = mailbox.get_messages(query=query)
```

#### Request Error Handling

Whenever a Request error raises, the connection object will raise an exception.
Then the exception will be captured and logged it to the stdout with its message, and return Falsy (None, False, [], etc...)

HttpErrors 4xx (Bad Request) and 5xx (Internal Server Error) are considered exceptions and raised also by the connection.
You can tell the `Connection` to not raise http errors by passing `raise_http_errors=False` (defaults to True).
