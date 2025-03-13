Address Book
============
AddressBook groups the functionality of both the Contact Folders and Contacts. Outlook Distribution Groups are not supported (By the Microsoft API's).

These are the scopes needed to work with the ``AddressBook`` and ``Contact`` classes.

=========================  =======================================  ======================================
Raw Scope                  Included in Scope Helper                 Description
=========================  =======================================  ======================================
Contacts.Read              address_book                             To only read my personal contacts
Contacts.Read.Shared       address_book_shared                      To only read another user / shared mailbox contacts
Contacts.ReadWrite         address_book_all                         To read and save personal contacts
Contacts.ReadWrite.Shared  address_book_all_shared                  To read and save contacts from another user / shared mailbox
User.ReadBasic.All         users                                    To only read basic properties from users of my organization (User.Read.All requires administrator consent).
=========================  =======================================  ======================================

Contact Folders
---------------
Represents a Folder within your Contacts Section in Office 365. AddressBook class represents the parent folder (it's a folder itself).

You can get any folder in your address book by requesting child folders or filtering by name.

.. code-block:: python

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

.. _global_address_list:

Global Address List
-------------------
MS Graph API has no concept such as the Outlook Global Address List. 
However you can use the `Users API <https://developer.microsoft.com/en-us/graph/docs/api-reference/v1.0/resources/users>`_ to access all the users within your organization.

Without admin consent you can only access a few properties of each user such as name and email and little more. You can search by name or retrieve a contact specifying the complete email.

* Basic Permission needed is Users.ReadBasic.All (limit info)
* Full Permission is Users.Read.All but needs admin consent.

To search the Global Address List (Users API):

.. code-block:: python

    global_address_list = account.directory()

    # for backwards compatibility only this also works and returns a Directory object:
    # global_address_list = account.address_book(address_book='gal')

    # start a new query:
    q = global_address_list.new_query('display_name')
    q.startswith('George Best')

    for user in global_address_list.get_users(query=q):
        print(user)

To retrieve a contact by their email:

.. code-block:: python

    contact = global_address_list.get_user('example@example.com')
    Contacts

    Everything returned from an AddressBook instance is a Contact instance. Contacts have all the information stored as attributes

    Creating a contact from an AddressBook:

    new_contact = address_book.new_contact()

    new_contact.name = 'George Best'
    new_contact.job_title = 'football player'
    new_contact.emails.add('george@best.com')

    new_contact.save()  # saved on the cloud

    message = new_contact.new_message()  #  Bonus: send a message to this contact

    # ...

    new_contact.delete()  # Bonus: deleted from the cloud