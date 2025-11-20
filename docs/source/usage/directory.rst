
Directory and Users
===================
The Directory object can retrieve users.

A User instance contains by default the `basic properties of the user <https://docs.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0&tabs=http#optional-query-parameters>`_. If you want to include more, you will have to select the desired properties manually.

Check :ref:`global_address_list` for further information.

These are the scopes needed to work with the Directory class.

=========================  =======================================  ======================================
Raw Scope                  Included in Scope Helper                 Description
=========================  =======================================  ======================================
User.ReadBasic.All         users                                    To read a basic set of profile properties of other users in your organization on behalf of the signed-in user. This includes display name, first and last name, email address, open extensions and photo. Also allows the app to read the full profile of the signed-in user.
User.Read.All              —                                        To read the full set of profile properties, reports, and managers of other users in your organization, on behalf of the signed-in user.
User.ReadWrite.All         —                                        To read and write the full set of profile properties, reports, and managers of other users in your organization, on behalf of the signed-in user. Also allows the app to create and delete users as well as reset user passwords on behalf of the signed-in user.
Directory.Read.All         —                                        To read data in your organization's directory, such as users, groups and apps, without a signed-in user.
Directory.ReadWrite.All    —                                        To read and write data in your organization's directory, such as users, and groups, without a signed-in user. Does not allow user or group deletion.
=========================  =======================================  ======================================

.. note::

    To get authorized with the above scopes you need a work or school account, it doesn't work with personal account.

Working with the ``Directory`` instance to read the active directory users:

.. code-block:: python

    directory = account.directory()
    for user in directory.get_users():
        print(user)
