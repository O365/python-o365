Query
=====

.. _query_builder:

Query Builder
-------------

A query can be created for every ``ApiComponent`` (such as ``MailBox``). The ``Query`` can be used to handle the filtering, sorting, selecting, expanding and search very easily.

For example:

.. code-block:: python

    builder = mailbox.new_query()

    query = builder.chain_or(builder.contains('subject', 'george best'), builder.startswith('subject', 'quotes')

    # 'created_date_time' will automatically be converted to the protocol casing.
    # For example when using MS Graph this will become 'createdDateTime'.

    query = query & builder.greater('created_date_time', datetime(2018, 3, 21))

    print(query)

    # contains(subject, 'george best') or startswith(subject, 'quotes') and createdDateTime gt '2018-03-21T00:00:00Z'
    # note you can pass naive datetimes and those will be converted to you local timezone and then send to the api as UTC in iso8601 format

    # To use Query objects just pass it to the query parameter:
    filtered_messages = mailbox.get_messages(query=query)

You can also specify specific data to be retrieved with "select":

.. code-block:: python

    # select only some properties for the retrieved messages:
    query = builder.select('subject', 'to_recipients', 'created_date_time)

    messages_with_selected_properties = mailbox.get_messages(query=query)

You can also search content. As said in the graph docs:

    You can currently search only message and person collections. A $search request returns up to 250 results. You cannot use $filter or $orderby in a search request.
    
    If you do a search on messages and specify only a value without specific message properties, the search is carried out on the default search properties of from, subject, and body.

    .. code-block:: python

        # searching is the easy part ;)
        query = builder.search('george best is da boss')
        messages = mailbox.get_messages(query=query)

