Utils
=====
Pagination
----------
When using certain methods, it is possible that you request more items than the api can return in a single api call. In this case the Api, returns a "next link" url where you can pull more data.

When this is the case, the methods in this library will return a ``Pagination`` object which abstracts all this into a single iterator. The pagination object will request "next links" as soon as they are needed.

For example:

.. code-block:: python

    mailbox = account.mailbox()

    messages = mailbox.get_messages(limit=1500)  # the MS Graph API have a 999 items limit returned per api call.

    # Here messages is a Pagination instance. It's an Iterator so you can iterate over.

    # The first 999 iterations will be normal list iterations, returning one item at a time.
    # When the iterator reaches the 1000 item, the Pagination instance will call the api again requesting exactly 500 items
    # or the items specified in the batch parameter (see later).

    for message in messages:
        print(message.subject)

When using certain methods you will have the option to specify not only a limit option (the number of items to be returned) but a batch option. This option will indicate the method to request data to the api in batches until the limit is reached or the data consumed. This is useful when you want to optimize memory or network latency.

For example:

.. code-block:: python

    messages = mailbox.get_messages(limit=100, batch=25)

    # messages here is a Pagination instance
    # when iterating over it will call the api 4 times (each requesting 25 items).

    for message in messages:  # 100 loops with 4 requests to the api server
        print(message.subject)

Query helper
------------
Every ``ApiComponent`` (such as ``MailBox``) implements a new_query method that will return a ``Query`` instance. This ``Query`` instance can handle the filtering, sorting, selecting, expanding and search very easily.

For example:

.. code-block:: python

    query = mailbox.new_query()  # you can use the shorthand: mailbox.q()

    query = query.on_attribute('subject').contains('george best').chain('or').startswith('quotes')

    # 'created_date_time' will automatically be converted to the protocol casing.
    # For example when using MS Graph this will become 'createdDateTime'.

    query = query.chain('and').on_attribute('created_date_time').greater(datetime(2018, 3, 21))

    print(query)

    # contains(subject, 'george best') or startswith(subject, 'quotes') and createdDateTime gt '2018-03-21T00:00:00Z'
    # note you can pass naive datetimes and those will be converted to you local timezone and then send to the api as UTC in iso8601 format

    # To use Query objetcs just pass it to the query parameter:
    filtered_messages = mailbox.get_messages(query=query)

You can also specify specific data to be retrieved with "select":

.. code-block:: python

    # select only some properties for the retrieved messages:
    query = mailbox.new_query().select('subject', 'to_recipients', 'created_date_time')

    messages_with_selected_properties = mailbox.get_messages(query=query)

You can also search content. As said in the graph docs:

    You can currently search only message and person collections. A $search request returns up to 250 results. You cannot use $filter or $orderby in a search request.
    
    If you do a search on messages and specify only a value without specific message properties, the search is carried out on the default search properties of from, subject, and body.

    .. code-block:: python

        # searching is the easy part ;)
        query = mailbox.q().search('george best is da boss')
        messages = mailbox.get_messages(query=query)

Request Error Handling
----------------------
Whenever a Request error raises, the connection object will raise an exception. Then the exception will be captured and logged it to the stdout with its message, and return Falsy (None, False, [], etc...)

HttpErrors 4xx (Bad Request) and 5xx (Internal Server Error) are considered exceptions and 
raised also by the connection. You can tell the ``Connection`` to not raise http errors by passing ``raise_http_errors=False`` (defaults to True).