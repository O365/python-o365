Account
=======

Multi-user handling
^^^^^^^^^^^^^^^^^^^
A single ``Account`` object can hold more than one user being authenticated. You can authenticate different users and the token backend 
will hold each authentication. When using the library you can use the ``account.username`` property to get or set the current user. 
If username is not provided, the username will be set automatically to the first authentication found in the token backend. Also, 
whenever you perform a new call to request_token (manually or through a call to ``account.authenticate``), 
the username will be set to the user performing the authentication.

.. code-block:: python
    
    account.username = 'user1@domain.com'
    #  issue some calls to retrieve data using the auth of the user1
    account.username = 'user2@domain.com'
    #  now every call will use the auth of the user2

This is only possible in version 2.1. Before 2.1 you had to instantiate one Account for each user.
Account class represents a specific account you would like to connect

Setting your Account Instance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Connecting to API Account
"""""""""""""""""""""""""
.. code-block:: python

    from O365 import Account

    account = Account(credentials=('my_client_id', 'my_client_secret'))

Setting Proxy
"""""""""""""
.. code-block:: python

    # Option 1
    account = Account(credentials=('my_client_id', 'my_client_secret'),
                      proxy_server='myserver.com', proxy_port=8080,
                      proxy_username='username', proxy_password='password)

    # Option 2
    account = Account(credentials=('my_client_id', 'my_client_secret'))
    account.connection.set('myserver.com',8080,'username', 'password')

Using Different Resource
""""""""""""""""""""""""
.. code-block:: python

    from O365 import Account

    account = Account(credentials=('my_client_id', 'my_client_secret'), main_resource='shared_mail@example.com')

Setting Scopes
""""""""""""""
- You can set a list of scopes that your like to use, a huge list is available on `Microsoft Documentation <https://developer.microsoft.com/en-us/graph/docs/concepts/permissions_reference>`_
- We have built a custom list make this scopes easier

    =========================      =================================      ==================================================
          Short Scope Name                   Description                                  Scopes Included
    =========================      =================================      ==================================================
    basic                                    Read User Info                                 ['User.Read']
    mailbox                                 Read your mail                                  ['Mail.Read']
    mailbox_shared                     Read shared mailbox                           ['Mail.Read.Shared']
    message_send                        Send from your mailid                        ['Mail.Send']
    message_send_shared               Send using shared mailbox                  ['Mail.Send.Shared']
    message_all                        Full Access to your mailbox               ['Mail.ReadWrite', 'Mail.Send']
    message_all_shared               Full Access to shared mailbox            ['Mail.ReadWrite.Shared', 'Mail.Send.Shared']
    address_book                        Read your Contacts                           ['Contacts.Read']
    address_book_shared               Read shared contacts                        ['Contacts.Read.Shared']
    address_book_all                  Read/Write your Contacts                  ['Contacts.ReadWrite']
    address_book_all_shared         Read/Write your Contacts                  ['Contacts.ReadWrite.Shared']
    calendar                          Full Access to your Calendars            ['Calendars.ReadWrite']
    users                                Read info of all users                     ['User.ReadBasic.All']
    onedrive                              Access to OneDrive                           ['Files.ReadWrite.All']
    sharepoint_dl                        Access to Sharepoint                        ['Sites.ReadWrite.All']
    =========================      =================================      ==================================================

.. code-block:: python

    # Full permission to your mail
    account = Account(credentials=('my_client_id', 'my_client_secret'),
                      scopes=['message_all'])

    # Why change every time, add all at a time :)
    account = Account(credentials=('my_client_id', 'my_client_secret'),
                      scopes=['message_all', 'message_all_shared', 'address_book_all',
                              'address_book_all_shared',
                              'calendar', 'users', 'onedrive', 'sharepoint_dl'])


Authenticating your Account
^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: python

    account = Account(credentials=('my_client_id', 'my_client_secret'))
    account.authenticate()

.. warning:: The call to authenticate is only required when you haven't authenticated before. If you already did the token file would have been saved

The authenticate() method forces an authentication flow, which prints out a url

#. Open the printed url
#. Give consent(approve) to the application
#. You will be redirected out outlook home page, copy the resulting url
    .. note:: If the url is simply https://outlook.office.com/owa/?realm=blahblah, and nothing else after that, then you are currently on new Outlook look, revert to old look and try the authentication flow again
#. Paste the resulting URL into the python console.
#. That's it, you don't need this hassle again unless you want to add more scopes than you approved for


Account Class and Modularity
============================
Usually you will only need to work with the ``Account`` Class. This is a wrapper around all functionality.

But you can also work only with the pieces you want.

For example, instead of:

.. code-block:: python

    from O365 import Account

    account = Account(('client_id', 'client_secret'))
    message = account.new_message()
    # ...
    mailbox = account.mailbox()
    # ...

You can work only with the required pieces:

.. code-block:: python

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

It's also easy to implement a custom Class. Just Inherit from ApiComponent, define the endpoints, and use the connection to make requests. If needed also inherit from Protocol to handle different communications aspects with the API server.

.. code-block:: python

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

            # self.build_url just merges the protocol service_url with the endpoint passed as a parameter
            # to change the service_url implement your own protocol inheriting from Protocol Class
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


.. _accessing_services:

.. Accessing Services
.. ^^^^^^^^^^^^^^^^^^
.. Below are the currently supported services

.. - Mailbox - Read, Reply or send new mails to others
..     .. code-block:: python

..         # Access Mailbox
..         mailbox = account.mailbox()

..         # Access mailbox of another resource
..         mailbox = account.mailbox(resource='someone@example.com')

.. - Address Book - Read or add new contacts to your address book
..     .. code-block:: python

..         # Access personal address book
..         contacts = account.address_book()

..         # Access personal address book of another resource
..         contacts = account.mailbox(resource='someone@example.com')

..         # Access global shared server address book (Global Address List)
..         contacts = account.mailbox(address_book='gal')

.. - Calendar Scheduler - Read or add new events to your calendar
..     .. code-block:: python

..         # Access scheduler
..         scheduler = account.schedule()

..         # Access scheduler of another resource
..         scheduler = account.schedule(resource='someone@example.com')

.. - One Drive or Sharepoint Storage - Manipulate and Organize your Storage Drives
..     .. code-block:: python

..         # Access storage
..         storage = account.storage()

..         # Access storage of another resource
..         storage = account.storage(resource='someone@example.com')

.. - Sharepoint Sites - Read and access items in your sharepoint sites
..     .. code-block:: python

..         # Access sharepoint
..         sharepoint = account.sharepoint()

..         # Access sharepoint of another resource
..         sharepoint = account.sharepoint(resource='someone@example.com')

