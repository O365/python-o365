OneDrive
========
The ``Storage`` class handles all functionality around One Drive and Document Library Storage in SharePoint.

The ``Storage`` instance allows retrieval of ``Drive`` instances which handles all the Files 
and Folders from within the selected ``Storage``. Usually you will only need to work with the 
default drive. But the ``Storage`` instances can handle multiple drives.

A ``Drive`` will allow you to work with Folders and Files.

These are the scopes needed to work with the ``Storage``, ``Drive`` and ``DriveItem`` classes.

=========================  =======================================  ======================================
Raw Scope                  Included in Scope Helper                 Description
=========================  =======================================  ======================================
Files.Read                 —                                        To only read my files
Files.Read.All             onedrive                                 To only read all the files the user has access
Files.ReadWrite            —                                        To read and save my files
Files.ReadWrite.All        onedrive_all                             To read and save all the files the user has access
=========================  =======================================  ======================================

.. code-block:: python

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

Both Files and Folders are DriveItems. Both Image and Photo are Files, but Photo is also an Image. All have some different methods and properties. Take care when using 'is_xxxx'.

When copying a DriveItem the api can return a direct copy of the item or a pointer to a resource that will inform on the progress of the copy operation.

.. code-block:: python

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

You can also work with share permissions:

.. code-block:: python

    current_permisions = file.get_permissions()  # get all the current permissions on this drive_item (some may be inherited)

    # share with link
    permission = file.share_with_link(share_type='edit')
    if permission:
        print(permission.share_link)  # the link you can use to share this drive item
    # share with invite
    permission = file.share_with_invite(recipients='george_best@best.com', send_email=True, message='Greetings!!', share_type='edit')
    if permission:
        print(permission.granted_to)  # the person you share this item with

You can also:

.. code-block:: python

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