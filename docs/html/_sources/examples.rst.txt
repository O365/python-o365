########
Examples
########


Connection
==========

Connection is a singleton class to take care of all authentication to the Office 365 api.

Connection has 2 different types of authentication and 1 additional function

#. Basic - using Username and Password
#. OAuth2 - using client id and client secret

Basic Authentication
--------------------
.. code-block:: python

    from O365 import Connection, FluentInbox

    # Setup connection object
    # Proxy call is required only if you are behind proxy
    Connection.login('email_id@company.com', 'password to login')
    Connection.proxy(url='proxy.company.com', port=8080, username='proxy_username', password='proxy_password')

OAuth2 Authentication
---------------------
You will need to register your application at Microsoft Apps(https://apps.dev.microsoft.com/). Steps below

#. Login to https://apps.dev.microsoft.com/
#. Create an app, note your app id (client_id)
#. Generate a new password (client_secret) under "Application Secrets" section
#. Under the "Platform" section, add a new Web platform and set "https://outlook.office365.com/owa/" as the redirect URL
#. Under "Microsoft Graph Permissions" section, Add the below delegated permission
    #. email
    #. Mail.ReadWrite
    #. Mail.Send
    #. User.Read

.. code-block:: python

    from O365 import Connection, FluentInbox

    # Setup connection object
    # This will provide you with auth url, open it and authentication and copy the resulting page url and paste it back in the input
    c = Connection.oauth2("your client_id", "your client_secret", store_token=True)

    # Proxy call is required only if you are behind proxy
    Connection.proxy(url='proxy.company.com', port=8080, username='proxy_username', password='proxy_password')


Fluent Inbox
============
FluentInbox is a new class introduced to enhance usage of inbox fluently (check the below example to understand clearly)

.. code-block:: python

    from O365 import Connection, FluentInbox

    # Setup connection object
    # Proxy call is required only if you are behind proxy
    Connection.oauth2("your client_id", "your client_secret", store_token=True)\
              .proxy(url='proxy.company.com', port=8080, username='proxy_username', password='proxy_password')

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
        print(message.subject)

    # If you would like to get only the 2nd result
    for message in inbox.search('Category:some_cat').skip(1).fetch(1):
        # Just print the message subject
        print(message.subject)

    # If you want the results from beginning by ignoring any currently read count
    inbox.fetch_first(10)

Support for shared mailboxes
----------------------------
Basic support for working with shared mailboxes exists. The following functions take `user_id` as a keyword argument specifying the email address of the shared mailbox.

* :func:`FluentInbox.from_folder` - read messages messages
* :func:`FluentInbox.get_folder` - list folders
* :func:`FluentMessage.sendMessage` - send as shared mailbox


Message
=======
Message class is representation of a single mail in your inbox.
You can fetch the messages in your mailbox using `FluentInbox`.

Reading or Updating Existing Message
------------------------------------
.. code-block:: python

    # Assuming message is object obtained by reading the inbox

    # Read subject
    print(message.subject)

    # Print body of the mail
    print(message.body)

    # Print list of users the mail is sent to
    print(message.to)
    print(message.cc)
    print(message.bcc)

    # Get sender information
    print(message.sender)
    print(message.sender_name)
    print(message.sender_email)

    # Download attachments
    count = message.fetch_attachments()

    # Mark the message as read
    message.mark_as_read()

    # Move message to a different folder
    message.move_to(...<folder_id>)

    # Set categories for the message
    message.set_categories('prod incidents', 'resolved')

Sending Message
---------------
.. code-block:: python

    from O365 import Message

    message = Message()
    message.to = 'user@gmail.com', 'user@outlook.com', 'example@domain.com'
    message.cc = 'cc_user@gmail.com'
    message.bcc = 'user_bcc@gmail.com', 'user_bcc@outlook.com'
    message.subject = 'Just a test mail'
    message.body = 'Just testing the python-o365 python package'
    message.send()

    # adding recipients
    message.add_recipient('another_user@gmail.com', kind='cc')

    # Use html to set body
    message.set_html_body('<html><p>hey how are you<p><html>')
    message.send()

FluentMessage
=============
FluentMessage is an alternative way of creating message using a fluent interface

.. code-block:: python

    from O365 import FluentMessage

    message = (FluentMessage()
               .to('user@gmail.com', 'user@outlook.com', 'example@domain.com')
               .cc('cc_user@gmail.com')
               .bcc('user_bcc@gmail.com', 'user_bcc@outlook.com')
               .subject('Just a test mail')
               .body('Just testing the python-o365 python package')
             # .html_body('<html><p>hey how are you<p><html>')
               .send())


    if not message.is_success:
        print(message.error_message)
