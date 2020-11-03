Account
=======
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

    # Why change everytime, add all at a time :)
    account = Account(credentials=('my_client_id', 'my_client_secret'),
                      scopes=['message_all', 'message_all_shared', 'address_book_all',
                              'address_book_all_shared',
                              'calendar', 'users', 'onedrive', 'sharepoint_dl'])


Authenticating your Account
^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. code-block:: python

    account = Account(credentials=('my_client_id', 'my_client_secret'))
    account.authenticate()

.. warning:: The call to authenticate is only required when u haven't authenticate before. If you already did the token file would have been saved

The authenticate() method forces a authentication flow, which prints out a url

#. Open the printed url
#. Give consent(approve) to the application
#. You will be redirected out outlook home page, copy the resulting url
    .. note:: If the url is simply https://outlook.office.com/owa/?realm=blahblah, and nothing else after that.. then you are currently on new Outlook look, revert back to old look and try the authentication flow again
#. Paste the resulting URL into the python console.
#. That's it, you don't need this hassle again unless you want to add more scopes than you approved for

.. _accessing_services:

Accessing Services
^^^^^^^^^^^^^^^^^^
Below are the currently supported services

- Mailbox - Read, Reply or send new mails to others
    .. code-block:: python

        # Access Mailbox
        mailbox = account.mailbox()

        # Access mailbox of another resource
        mailbox = account.mailbox(resource='someone@example.com')

- Address Book - Read or add new contacts to your address book
    .. code-block:: python

        # Access personal address book
        contacts = account.address_book()

        # Access personal address book of another resource
        contacts = account.mailbox(resource='someone@example.com')

        # Access global shared server address book (Global Address List)
        contacts = account.mailbox(address_book='gal')

- Calendar Scheduler - Read or add new events to your calendar
    .. code-block:: python

        # Access scheduler
        scheduler = account.schedule()

        # Access scheduler of another resource
        scheduler = account.schedule(resource='someone@example.com')

- One Drive or Sharepoint Storage - Manipulate and Organize your Storage Drives
    .. code-block:: python

        # Access storage
        storage = account.storage()

        # Access storage of another resource
        storage = account.storage(resource='someone@example.com')

- Sharepoint Sites - Read and access items in your sharepoint sites
    .. code-block:: python

        # Access sharepoint
        sharepoint = account.sharepoint()

        # Access sharepoint of another resource
        sharepoint = account.sharepoint(resource='someone@example.com')

