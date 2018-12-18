Mailbox
=======
Check :ref:`accessing_services` section for knowing how to get Mailbox instance

Accessing Various Folders
^^^^^^^^^^^^^^^^^^^^^^^^^
`get_folder()` and `get_folders()` are useful to fetch folders that are available under the current instance

Get Single Folder
"""""""""""""""""
**Using Name**

Using name to get a folder will only search the folders directly under the current folder or root

.. code-block:: python

    # By Name - Will only find direct child folder
    mail_folder = mailbox.get_folder(folder_name='Todo')

    # By Name - If Todo folder is under Inbox folder
    mail_folder = (mailbox.get_folder(folder_name='Inbox')
                          .get_folder(folder_name='Todo'))

**Using ID**

As opposed to getting folder by name, using the id you can fetch folder from any child

.. code-block:: python

    # Assuming we are getting folder Todo under Inbox
    mail_folder = mailbox.get_folder(folder_id='some_id_you_may_have_obtained')

**Well Known Folders**

There are few well know folders like **Inbox**, **Drafts**, etc..
As they are generally used we have added functions to quickly access them

.. code-block:: python

    # Inbox
    mail_folder = mailbox.inbox_folder()

    # DeletedItems
    mail_folder = mailbox.deleted_folder()

    # Drafts
    mail_folder = mailbox.drafts_folder()

    # Junk
    mail_folder = mailbox.junk_folder()

    # Outbox
    mail_folder = mailbox.outbox_folder()

Get Child Folders
"""""""""""""""""
**All or Some Child Folders**

.. code-block:: python

    # All child folders under root
    mail_folders = mailbox.get_folders()

    # All child folders under Inbox
    mail_folders = mailbox.inbox_folder().get_folders()

    # Limit the number or results, will get the top x results
    mail_folders = mailbox.get_folders(limit=7)

**Filter the results**

Query is a class available, that lets you filter results

.. code-block:: python

    # All child folders whose name startswith 'Top'
    mail_folders = mailbox.get_folders(query=mailbox.new_query('displayName').startswith('Top'))


