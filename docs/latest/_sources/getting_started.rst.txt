###############
Getting Started
###############

Installation
============
Stable Version (PyPI)
---------------------
The latest stable package is hosted on `PyPI <https://pypi.org>`_. 

To install using pip, run:

.. code-block:: console

   pip install o365

Requirements: >= Python 3.9

Project dependencies installed by pip:

* requests
* msal
* beatifulsoup4
* python-dateutil
* tzlocal
* tzdata

Latest Development Version (GitHub)
-----------------------------------
The latest development version is available on `GitHub <https://github.com/O365/python-o365>`_. 
This version may include new features but could be unstable. **Use at your own risk**.

To install from GitHub, run:

.. code-block:: console

   pip install git+https://github.com/O365/python-o365.git

Basic Usage
===========

The first step to be able to work with this library is to register an application and retrieve the auth token. See :ref:`authentication`.

With the access token retrieved and stored you will be able to perform api calls to the service.

A common pattern to check for authentication and use the library is this one:

.. code-block:: python

   scopes = ['my_required_scopes']  # you can use scope helpers here (see Permissions and Scopes section)

   account = Account(credentials)

   if not account.is_authenticated:  # will check if there is a token and has not expired
      # ask for a login using console based authentication. See Authentication for other flows
      if account.authenticate(scopes=scopes) is False:
         raise RuntimeError('Authentication Failed')

   # now we are authenticated
   # use the library from now on

   # ...

.. _authentication:

Authentication
==============
Types
-----
You can only authenticate using OAuth authentication because Microsoft deprecated basic auth on November 1st 2018.

.. important::

   With version 2.1 old access tokens will not work and the library will require a new authentication flow to get new access and refresh tokens.

There are currently three authentication methods:

* `Authenticate on behalf of a user <https://docs.microsoft.com/en-us/graph/auth-v2-user?context=graph%2Fapi%2F1.0&view=graph-rest-1.0/>`_: Any user will give consent to the app to access its resources. This OAuth flow is called authorization code grant flow. This is the default authentication method used by this library.

* `Authenticate on behalf of a user (public) <https://docs.microsoft.com/en-us/graph/auth-v2-user?context=graph%2Fapi%2F1.0&view=graph-rest-1.0/>`_: Same as the former but for public apps where the client secret can't be secured. Client secret is not required.

* `Authenticate with your own identity <https://docs.microsoft.com/en-us/graph/auth-v2-service?context=graph%2Fapi%2F1.0&view=graph-rest-1.0>`_: This will use your own identity (the app identity). This OAuth flow is called client credentials grant flow.

.. note::

   'Authenticate with your own identity' is not an allowed method for Microsoft Personal accounts.

When to use one or the other and requirements:



+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| Topic                      | On behalf of a user *(auth_flow_type=='authorization')* | On behalf of a user (public) *(auth_flow_type=='public')* | With your own identity *(auth_flow_type=='credentials')* |
+============================+=========================================================+===========================================================+==========================================================+
| **Register the App**       | Required                                                | Required                                                  | Required                                                 |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| **Requires Admin Consent** | Only on certain advanced permissions                    | Only on certain advanced permissions                      | Yes, for everything                                      |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| **App Permission Type**    | Delegated Permissions (on behalf of the user)           | Delegated Permissions (on behalf of the user)             | Application Permissions                                  |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| **Auth requirements**      | Client Id, Client Secret, Authorization Code            | Client Id, Authorization Code                             | Client Id, Client Secret                                 |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| **Authentication**         | 2 step authentication with user consent                 | 2 step authentication with user consent                   | 1 step authentication                                    |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| **Auth Scopes**            | Required                                                | Required                                                  | None                                                     |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| **Token Expiration**       | 60 Minutes without refresh token or 90 days*            | 60 Minutes without refresh token or 90 days*              | 60 Minutes*                                              |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| **Login Expiration**       | Unlimited if there is a refresh token and as long as a  | Unlimited if there is a refresh token and as long as a    | Unlimited                                                |
|                            | refresh is done within the 90 days                      | refresh is done within the 90 days                        |                                                          |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| **Resources**              | Access the user resources, and any shared resources     | Access the user resources, and any shared resources       | All Azure AD users the app has access to                 |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| **Microsoft Account Type** | Any                                                     | Any                                                       | Not Allowed for Personal Accounts                        |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+
| **Tenant ID Required**     | Defaults to "common"                                    | Defaults to "common"                                      | Required (can't be "common")                             |
+----------------------------+---------------------------------------------------------+-----------------------------------------------------------+----------------------------------------------------------+

*Note: *O365 will automatically refresh the token for you on either authentication method. The refresh token lasts 90 days, but it's refreshed on each connection so as long as you connect within 90 days you can have unlimited access.*

The Connection Class handles the authentication.

With auth_flow_type 'credentials' you can authenticate using a certificate based authentication by just passing the client_secret like so:

.. code-block:: python

   client_secret = {
      "thumbprint": <thumbprint of cert file>,
      "private_key": <private key from the private_key_file>
   }
   credentials = client_id, client_secret
   account = Account(credentials)


OAuth Setup (Prerequisite)
--------------------------

Before you can use python-o365, you must register your application in the 
`Microsoft Entra Admin Center <https://entra.microsoft.com/>`_. Follow the steps below:

1. **Log in to the Microsoft Entra Admin Center**

   - Visit https://entra.microsoft.com/ and sign in.

2. **Create a new application and note its App (client) ID**
   
   - In the left navigation bar, select **Applications** > **App registrations**.
   - Click **+ New registration**.
   - Provide a **Name** for the application and keep all defaults.
   - From the **Overview** of your new application, copy the (client_id) **Application (client) ID** for later reference.

3. **Generate a new password (client_secret)**
   
   - In the **Overview** window, select **Certificates & secrets**.
   - Click **New client secret**.
   - In the **Add a client secret** window, provide a Description and Expiration, then click **Add**.
   - Save the (client_secret) **Value** for later reference.

4. **Add redirect URIs**
   
   - In the **Overview** window, click **Add a redirect URI**.
   - Click **+ Add a platform**, then select **Web**.
   - Add ``https://login.microsoftonline.com/common/oauth2/nativeclient`` as the redirect URI.
   - Click **Save**.

5. **Add required permissions**
   
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

.. important::

   The offline_access permission is required for the refresh token to work.

Examples
--------
Then you need to log in for the first time to get the access token that will grant access to the user resources.

To authenticate (login) you can use :ref:`different_interfaces`. On the following examples we will be using the Console Based Interface, but you can use any of them.

.. important::

   In case you can't secure the client secret you can use the auth flow type 'public' which only requires the client id.

* When authenticating on behalf of a user:

  1. Instantiate an `Account` object with the credentials (client id and client secret).
  2. Call `account.authenticate` and pass the scopes you want (the ones you previously added on the app registration portal).

     > Note: when using the "on behalf of a user" authentication, you can pass the scopes to either the `Account` init or to the authenticate method. Either way is correct.

     You can pass "protocol scopes" (like: "https://graph.microsoft.com/Calendars.ReadWrite") to the method or use "[scope helpers](https://github.com/O365/python-o365/blob/master/O365/connection.py#L34)" like ("message_all").
     If you pass protocol scopes, then the `account` instance must be initialized with the same protocol used by the scopes. By using scope helpers you can abstract the protocol from the scopes and let this library work for you.
     Finally, you can mix and match "protocol scopes" with "scope helpers".
     Go to the [procotol section](#protocols) to know more about them.

     For Example (following the previous permissions added):

     .. code-block:: python

          from O365 import Account
          credentials = ('my_client_id', 'my_client_secret')

          # the default protocol will be Microsoft Graph
          # the default authentication method will be "on behalf of a user"

          account = Account(credentials)
          if account.authenticate(scopes=['basic', 'message_all']):
             print('Authenticated!')

          # 'basic' adds: 'https://graph.microsoft.com/User.Read'
          # 'message_all' adds: 'https://graph.microsoft.com/Mail.ReadWrite' and 'https://graph.microsoft.com/Mail.Send'

     When using the "on behalf of the user" authentication method, this method call will print an url that the user must visit to give consent to the app on the required permissions.

     The user must then visit this url and give consent to the application. When consent is given, the page will rediret to: "https://login.microsoftonline.com/common/oauth2/nativeclient" by default (you can change this) with an url query param called 'code'.

     Then the user must copy the resulting page url and paste it back on the console.
     The method will then return True if the login attempt was succesful.

* When authenticating with your own identity:

  1. Instantiate an `Account` object with the credentials (client id and client secret), specifying the parameter `auth_flow_type` to *"credentials"*. You also need to provide a 'tenant_id'. You don't need to specify any scopes.
  2. Call `account.authenticate`. This call will request a token for you and store it in the backend. No user interaction is needed. The method will store the token in the backend and return True if the authentication succeeded.

   For Example:

   .. code-block:: python

        from O365 import Account

        credentials = ('my_client_id', 'my_client_secret')

        # the default protocol will be Microsoft Graph

        account = Account(credentials, auth_flow_type='credentials', tenant_id='my-tenant-id')
        if account.authenticate():
           print('Authenticated!')

At this point you will have an access token stored that will provide valid credentials when using the api.

The access token only lasts **60 minutes**, but the app will automatically request new access tokens if you added the 'offline access' permission.

When using the "on behalf of a user" authentication method this is accomplished through the refresh tokens (if and only if you added the "offline_access" permission), but note that a refresh token only lasts for 90 days. So you must use it before, or you will need to request a new access token again (no new consent needed by the user, just a login). If your application needs to work for more than 90 days without user interaction and without interacting with the API, then you must implement a periodic call to Connection.refresh_token before the 90 days have passed.

.. important::

   Take care: the access (and refresh) token must remain protected from unauthorized users.

.. _different_interfaces:

Different interfaces
--------------------
To accomplish the authentication you can basically use different approaches. The following apply to the "on behalf of a user" authentication method as this is 2-step authentication flow. For the "with your own identity" authentication method, you can just use account.authenticate as it's not going to require a console input.

1. Console based authentication interface:

   You can authenticate using a console. The best way to achieve this is by using the authenticate method of the Account class.

   account = Account(credentials)
   account.authenticate(scopes=['basic', 'message_all'])
   The authenticate method will print into the console an url that you will have to visit to achieve authentication. Then after visiting the link and authenticate you will have to paste back the resulting url into the console. The method will return True and print a message if it was succesful.

   **Tip:** When using macOS the console is limited to 1024 characters. If your url has multiple scopes it can exceed this limit. To solve this. Just import readline at the top of your script.

2. Web app based authentication interface:

   You can authenticate your users in a web environment by following these steps:

   i. First ensure you are using an appropiate TokenBackend to store the auth tokens (See Token storage below).
   ii. From a handler redirect the user to the Microsoft login url. Provide a callback. Store the flow dictionary.
   iii. From the callback handler complete the authentication with the flow dict and other data.
   
   The following example is done using Flask.

   .. code-block:: python

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
         # if result is True, then authentication was successful
         #  and the auth token is stored in the token backend
         if result:
            return render_template('auth_complete.html')
         # else ....

3. Other authentication interfaces:

   Finally, you can configure any other flow by using ``connection.get_authorization_url`` and ``connection.request_token`` as you want.

Permissions & Scopes
====================
Permissions
-----------
When using oauth, you create an application and allow some resources to be accessed and used by its users. These resources are managed with permissions. These can either be delegated (on behalf of a user) or application permissions. The former are used when the authentication method is "on behalf of a user". Some of these require administrator consent. The latter when using the "with your own identity" authentication method. All of these require administrator consent.

Scopes
------
The scopes only matter when using the "on behalf of a user" authentication method.

.. note::
   You only need the scopes when login as those are kept stored within the token on the token backend.

The user of this library can then request access to one or more of these resources by providing scopes to the OAuth provider.

.. note::
   If you later on change the scopes requested, the current token will be invalid, and you will have to re-authenticate. The user that logins will be asked for consent.

For example your application can have Calendar.Read, Mail.ReadWrite and Mail.Send permissions, but the application can request access only to the Mail.ReadWrite and Mail.Send permission. This is done by providing scopes to the Account instance or account.authenticate method like so:

.. code-block:: python

   from O365 import Account

   credentials = ('client_id', 'client_secret')

   scopes = ['Mail.ReadWrite', 'Mail.Send']

   account = Account(credentials, scopes=scopes)
   account.authenticate()

   # The latter is exactly the same as passing scopes to the authenticate method like so:
   # account = Account(credentials)
   # account.authenticate(scopes=scopes)

Scope implementation depends on the protocol used. So by using protocol data you can automatically set the scopes needed. This is implemented by using 'scope helpers'. Those are little helpers that group scope functionality and abstract the protocol used.

=======================  ===============
Scope Helper             Scopes included
=======================  ===============
basic                    'User.Read'
mailbox                  'Mail.Read'
mailbox_shared	          'Mail.Read.Shared'
mailbox_settings	       'MailboxSettings.ReadWrite'
message_send	          'Mail.Send'
message_send_shared	    'Mail.Send.Shared'
message_all	             'Mail.ReadWrite' and 'Mail.Send'
message_all_shared       'Mail.ReadWrite.Shared' and 'Mail.Send.Shared'
address_book             'Contacts.Read'
address_book_shared      'Contacts.Read.Shared'
address_book_all         'Contacts.ReadWrite'
address_book_all_shared  'Contacts.ReadWrite.Shared'
calendar	                'Calendars.Read'
calendar_shared          'Calendars.Read.Shared'
calendar_all             'Calendars.ReadWrite'
calendar_shared_all      'Calendars.ReadWrite.Shared'
users                    'User.ReadBasic.All'
onedrive                 'Files.Read.All'
onedrive_all             'Files.ReadWrite.All'
sharepoint               'Sites.Read.All'
sharepoint_dl            'Sites.ReadWrite.All'
settings_all             'MailboxSettings.ReadWrite'
tasks                    'Tasks.Read'
tasks_all                'Tasks.ReadWrite'
presence                 'Presence.Read'
=======================  ===============

You can get the same scopes as before using protocols and scope helpers like this:

.. code-block:: python

   protocol_graph = MSGraphProtocol()

   scopes_graph = protocol.get_scopes_for('message all')
   # scopes here are: ['https://graph.microsoft.com/Mail.ReadWrite', 'https://graph.microsoft.com/Mail.Send']

   account = Account(credentials, scopes=scopes_graph)

.. note::
   
   When passing scopes at the Account initialization or on the account.authenticate method, the scope helpers are automatically converted to the protocol flavour. Those are the only places where you can use scope helpers. Any other object using scopes (such as the Connection object) expects scopes that are already set for the protocol.

Token Storage
=============

When authenticating you will retrieve OAuth tokens. If you don't want a one time access you will have to store the token somewhere. O365 makes no assumptions on where to store the token and tries to abstract this from the library usage point of view.

You can choose where and how to store tokens by using the proper Token Backend.

.. caution::

   **The access (and refresh) token must remain protected from unauthorized users.** You can plug in a "cryptography_manager" (object that can call encrypt and decrypt) into TokenBackends "cryptography_manager" attribute.
   
The library will call (at different stages) the token backend methods to load and save the token.

Methods that load tokens:

* ``account.is_authenticated`` property will try to load the token if is not already loaded.
* ``connection.get_session``: this method is called when there isn't a request session set.

Methods that stores tokens:

* ``connection.request_token``: by default will store the token, but you can set store_token=False to avoid it.
* ``connection.refresh_token``: by default will store the token. To avoid it change ``connection.store_token_after_refresh`` to False. This however it's a global setting (that only affects the ``refresh_token`` method). If you only want the next refresh operation to not store the token you will have to set it back to True afterward.

To store the token you will have to provide a properly configured TokenBackend.

There are a few ``TokenBackend`` classes implemented (and you can easily implement more like a CookieBackend, RedisBackend, etc.):

* ``FileSystemTokenBackend`` (Default backend): Stores and retrieves tokens from the file system. Tokens are stored as text files.
* ``MemoryTokenBackend``: Stores the tokens in memory. Basically load_token and save_token does nothing.
* ``EnvTokenBackend``: Stores and retrieves tokens from environment variables.
* ``FirestoreTokenBackend``: Stores and retrieves tokens from a Google Firestore Datastore. Tokens are stored as documents within a collection.
* ``AWSS3Backend``: Stores and retrieves tokens from an AWS S3 bucket. Tokens are stored as a file within a S3 bucket.
* ``AWSSecretsBackend``: Stores and retrieves tokens from an AWS Secrets Management vault.
* ``BitwardenSecretsManagerBackend``: Stores and retrieves tokens from Bitwarden Secrets Manager.
* ``DjangoTokenBackend``: Stores and retrieves tokens using a Django model.

For example using the FileSystem Token Backend:

.. code-block:: python

   from O365 import Account, FileSystemTokenBackend

   credentials = ('id', 'secret')

   # this will store the token under: "my_project_folder/my_folder/my_token.txt".
   # you can pass strings to token_path or Path instances from pathlib
   token_backend = FileSystemTokenBackend(token_path='my_folder', token_filename='my_token.txt')
   account = Account(credentials, token_backend=token_backend)

   # This account instance tokens will be stored on the token_backend configured before.
   # You don't have to do anything more
   # ...

And now using the same example using FirestoreTokenBackend:

.. code-block:: python

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

To implement a new TokenBackend:

1. Subclass ``BaseTokenBackend``

2. Implement the following methods:

   * ``__init__`` (don't forget to call ``super().__init__``)
   * ``load_token``: this should load the token from the desired backend and return a ``Token`` instance or None
   * ``save_token``: this should store the ``self.token`` in the desired backend.
   * Optionally you can implement: ``check_token``, ``delete_token`` and ``should_refresh_token``

The ``should_refresh_token`` method is intended to be implemented for environments where multiple Connection instances are running on parallel. This method should check if it's time to refresh the token or not. The chosen backend can store a flag somewhere to answer this question. This can avoid race conditions between different instances trying to refresh the token at once, when only one should make the refresh. The method should return three possible values:

* **True**: then the Connection will refresh the token.
* **False**: then the Connection will NOT refresh the token.
* None: then this method already executed the refresh and therefore the Connection does not have to.

By default, this always returns True as it's assuming there is are no parallel connections running at once.

There are two examples of this method in the examples folder `here <https://github.com/O365/python-o365/blob/master/examples/token_backends.py>`_.