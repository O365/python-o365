Mailbox
=======
Mailbox groups the functionality of both the messages and the email folders.

These are the scopes needed to work with the ``MailBox`` and ``Message`` classes.

=========================  =======================================  ======================================
Raw Scope                  Included in Scope Helper                 Description
=========================  =======================================  ======================================
Mail.Read                  mailbox                                  To only read my mailbox
Mail.Read.Shared           mailbox_shared                           To only read another user / shared mailboxes
Mail.Send                  message_send, message_all                To only send message
Mail.Send.Shared           message_send_shared, message_all_shared  To only send message as another user / shared mailbox
Mail.ReadWrite             message_all                              To read and save messages in my mailbox
MailboxSettings.ReadWrite  mailbox_settings                         To read and write user mailbox settings
=========================  =======================================  ======================================

.. Useful Methods
.. ^^^^^^^^^^^^^^^^^^^^^^^^^
.. `get_folder()` and `get_folders()` are useful to fetch folders that are available under the current instance

.. Get Single Folder
.. """""""""""""""""
.. **Using Name**

.. Using name to get a folder will only search the folders directly under the current folder or root

.. .. code-block:: python

..     # By Name - Will only find direct child folder
..     mail_folder = mailbox.get_folder(folder_name='Todo')

..     # By Name - If Todo folder is under Inbox folder
..     mail_folder = (mailbox.get_folder(folder_name='Inbox')
..                           .get_folder(folder_name='Todo'))

.. **Using ID**

.. As opposed to getting folder by name, using the id you can fetch folder from any child

.. .. code-block:: python

..     # Assuming we are getting folder Todo under Inbox
..     mail_folder = mailbox.get_folder(folder_id='some_id_you_may_have_obtained')

.. **Well Known Folders**

.. There are few well know folders like **Inbox**, **Drafts**, etc..
.. As they are generally used we have added functions to quickly access them

.. .. code-block:: python

..     # Inbox
..     mail_folder = mailbox.inbox_folder()

..     # DeletedItems
..     mail_folder = mailbox.deleted_folder()

..     # Drafts
..     mail_folder = mailbox.drafts_folder()

..     # Junk
..     mail_folder = mailbox.junk_folder()

..     # Outbox
..     mail_folder = mailbox.outbox_folder()

.. Get Child Folders
.. """""""""""""""""
.. **All or Some Child Folders**

.. .. code-block:: python

..     # All child folders under root
..     mail_folders = mailbox.get_folders()

..     # All child folders under Inbox
..     mail_folders = mailbox.inbox_folder().get_folders()

..     # Limit the number or results, will get the top x results
..     mail_folders = mailbox.get_folders(limit=7)

.. **Filter the results**

.. Query is a class available, that lets you filter results

.. .. code-block:: python

..     # All child folders whose name startswith 'Top'
..     mail_folders = mailbox.get_folders(query=mailbox.new_query('displayName').startswith('Top'))

Mailbox and Messages
""""""""""""""""""""

.. code-block:: python

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


Email Folder
""""""""""""

Represents a Folder within your email mailbox.

You can get any folder in your mailbox by requesting child folders or filtering by name.

.. code-block:: python

    mailbox = account.mailbox()

    archive = mailbox.get_folder(folder_name='archive')  # get a folder with 'archive' name

    child_folders = archive.get_folders(25) # get at most 25 child folders of 'archive' folder

    for folder in child_folders:
        print(folder.name, folder.parent_id)

    new_folder = archive.create_child_folder('George Best Quotes')

Message
"""""""

**An email object with all its data and methods**

Creating a draft message is as easy as this:

.. code-block:: python

    message = mailbox.new_message()
    message.to.add(['example1@example.com', 'example2@example.com'])
    message.sender.address = 'my_shared_account@example.com'  # changing the from address
    message.body = 'George Best quote: I might go to Alcoholics Anonymous, but I think it would be difficult for me to remain anonymous'
    message.attachments.add('george_best_quotes.txt')
    message.save_draft()  # save the message on the cloud as a draft in the drafts folder

**Working with saved emails is also easy**

.. code-block:: python

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

**Sending Inline Images**

You can send inline images by doing this:

.. code-block:: python

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

**Retrieving Message Headers**

You can retrieve message headers by doing this:

.. code-block:: python

    # ...
    mb = account.mailbox()
    msg = mb.get_message(query=mb.q().select('internet_message_headers'))
    print(msg.message_headers)  # returns a list of dicts.

Note that only message headers and other properties added to the select statement will be present.

**Saving as EML**

Messages and attached messages can be saved as ``*.eml``.

Save message as "eml":

.. code-block:: python

    msg.save_as_eml(to_path=Path('my_saved_email.eml'))

**Save attached message as "eml"**

Careful: there's no way to identify that an attachment is in fact a message. You can only check if the attachment.attachment_type == 'item'. if is of type "item" then it can be a message (or an event, etc...). You will have to determine this yourself.

.. code-block:: python

    msg_attachment = msg.attachments[0]  # the first attachment is attachment.attachment_type == 'item' and I know it's a message.
    msg.attachments.save_as_eml(msg_attachment, to_path=Path('my_saved_email.eml'))

Mailbox Settings
""""""""""""""""
The mailbox settings and associated methods.

Retrieve and update mailbox auto reply settings:

.. code-block:: python

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
    Alternatively to enable and disable

    mailboxsettings.save()

    mailbox.set_automatic_reply(
        "Internal",
        "External",
        scheduled_start_date_time=start, # Status will be 'scheduled' if start/end supplied, otherwise 'alwaysEnabled'
        scheduled_end_date_time=end,
        externalAudience=ExternalAudience.NONE, # Defaults to ALL
    )
    mailbox.set_disable_reply()


Outlook Categories
""""""""""""""""""
You can retrieve, update, create and delete outlook categories. These categories can be used to categorize Messages, Events and Contacts.

These are the scopes needed to work with the SharePoint and Site classes.

=========================  =======================================  ======================================
Raw Scope                  Included in Scope Helper                 Description
=========================  =======================================  ======================================
MailboxSettings.Read       —                                        To only read outlook settings
MailboxSettings.ReadWrite  settings_all                             To read and write outlook settings
=========================  =======================================  ======================================

Example:

.. code-block:: python

    from O365.category import CategoryColor

    oc = account.outlook_categories()
    categories = oc.get_categories()
    for category in categories:
        print(category.name, category.color)

    my_category = oc.create_category('Important Category', color=CategoryColor.RED)
    my_category.update_color(CategoryColor.DARKGREEN)

    my_category.delete()  # oops!
