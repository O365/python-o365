Sharepoint
==========
Assuming an authenticated account, create a Sharepoint instance, and connect
to a Sharepoint site.

.. code-block:: python

    #Create Sharepoint instance and connect to a site
    from O365 import Account
    acct = Account(('app_id', 'app_pw'))
    sp_site = acct.sharepoint().get_site('root', 'path/tosite')

Common commands for :code:`sp_site` include :code:`.display_name`,
:code:`.get_document_library()`, :code:`.get_subsites()`, :code:`.get_lists()`,
and :code:`.get_list_by_name('list_name')`.

**Accessing Subsites**

If a Sharepoint site contains subsites they can be returned as a list of
Sharepoint sites by the :code:`.get_subsites()` function.

.. code-block:: python

    #Return a List of subsites
    sp_site_subsites = sp_site.get_subsites()
    print(sp_sites_subsites)
    [Site: subsitename1, Site: subsitename2]

    #Make another Site object from a desired subsite
    new_sp_site = sp_site_subsites[0] #return the first subsite

Sharepoint Lists
^^^^^^^^^^^^^^^^

Sharepoint Lists are accessible from their Sharepoint site using :code:`.get_lists()` which
returns a Python list of Sharepoint list objects.  A known list can be accessed
by providing a :code:`list_name` to :code:`.get_list_by_name('list_name')` which will return
the requested list as a :code:`sharepointlist` object.

.. code-block:: python

    #Return a list of sharepoint lists
    sp_site_lists = sp_site.get_lists()

    #Return a specific list by name
    sp_list = sp_site.get_list_by_name('list_name')


Commmon functions on a Sharepoint list include :code:`.get_list_columns()`,
:code:`.get_items()`, :code:`.get_item_by_id()`, :code:`.create_list_item()`,
:code:`.delete_list_item()`.


Sharepoint List Items
"""""""""""""""""""""

Accessing a list item from a Sharepoint list is done by utilizing :code:`.get_items()`,
or :code:`.get_item_by_id(item_id)`.

.. code-block:: python

    #Return a list of sharepoint list Items
    sp_list_items = sp_list.get_items()

    #Return a specific sharepoint list item by its object ID
    sp_list_item = sp_list.get_item_by_id(item_id)


**Creating & Deleting Sharepoint Items**

A Sharepoint list item can be created by passing the new data in a dictionary
consisting of :code:`{'column_name': 'new_data'}`.  Not all columns in the Sharepoint list have to
be accounted for in the dictionary, any Sharepoint List column not in the dictionary
will be filled with a blank.  The `column_name` must be the internal column name
of the sharepoint list.  :code:`.column_name_cw` of a sharepoint list will provide a
dictionary of :code:`{'Display Name': 'Internal Name'}` if needed.

.. code-block:: python

    #Create a new sharepoint list item
    new_item = sp_list.create_list_item({'col1': 'New Data Col 1',
                                         'col2': 'New Data Col 2'})

    #Delete the item just created
    sp_list.delete_list_item(new_item.object_id)  #Pass the item ID to be deleted

**Updating a Sharepoint List Item**

Sharepoint list items can be updated by passing a dictionary of
:code:`{'column_name': 'Updated Data'}` to the :code:`.update_fields()` function of a
Sharepoint list item.  The `column_name` keys of the dictionary must again refer
to the internal column name, otherwise an error will occur.

.. code-block:: python

    #Update a Sharepoint List item
    new_item.update_fields({'col1': 'Updated Data Col1',
                            'col2': 'Updated Data Col2'})

    #Once done updating a sharepoint item save changes to the cloud
    new_item.save_updates() #Returns True if successful
