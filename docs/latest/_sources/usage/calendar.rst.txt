Calendar
========
The calendar and events functionality is group in a Schedule object.

A ``Schedule`` instance can list and create calendars. It can also list or create events on the default user calendar. To use other calendars use a ``Calendar`` instance.

These are the scopes needed to work with the ``Schedule``, ``Calendar`` and ``Event`` classes.

==========================  =======================================  ======================================
Raw Scope                   Included in Scope Helper                 Description
==========================  =======================================  ======================================
Calendars.Read              calendar                                 To only read my personal calendars
Calendars.Read.Shared       calendar_shared                          To only read another user / shared mailbox calendars
Calendars.ReadWrite         calendar_all                             To read and save personal calendars
Calendars.ReadWrite.Shared  calendar_shared_all                      To read and save calendars from another user / shared mailbox
==========================  =======================================  ======================================

Working with the ``Schedule`` instance:

.. code-block:: python

    import datetime as dt

    # ...
    schedule = account.schedule()

    calendar = schedule.get_default_calendar()
    new_event = calendar.new_event()  # creates a new unsaved event
    new_event.subject = 'Recruit George Best!'
    new_event.location = 'England'

    # naive datetimes will automatically be converted to timezone aware datetime
    #  objects using the local timezone detected or the protocol provided timezone

    new_event.start = dt.datetime(2019, 9, 5, 19, 45)
    # so new_event.start becomes: datetime.datetime(2018, 9, 5, 19, 45, tzinfo=<DstTzInfo 'Europe/Paris' CEST+2:00:00 DST>)

    new_event.recurrence.set_daily(1, end=dt.datetime(2019, 9, 10))
    new_event.remind_before_minutes = 45

    new_event.save()

Working with Calendar instances:

.. code-block:: python

    calendar = schedule.get_calendar(calendar_name='Birthdays')

    calendar.name = 'Football players birthdays'
    calendar.update()

    q = calendar.new_query('start').greater_equal(dt.datetime(2018, 5, 20))
    q.chain('and').on_attribute('end').less_equal(dt.datetime(2018, 5, 24))

    birthdays = calendar.get_events(query=q, include_recurring=True)  # include_recurring=True will include repeated events on the result set.

    for event in birthdays:
        if event.subject == 'George Best Birthday':
            # He died in 2005... but we celebrate anyway!
            event.accept("I'll attend!")  # send a response accepting
        else:
            event.decline("No way I'm coming, I'll be in Spain", send_response=False)  # decline the event but don't send a response to the organizer

**Notes regarding Calendars and Events**:

1. Include_recurring=True:

    It's important to know that when querying events with include_recurring=True (which is the default), it is required that you must provide a query parameter with the start and end attributes defined. Unlike when using include_recurring=False those attributes will NOT filter the data based on the operations you set on the query (greater_equal, less, etc.) but just filter the events start datetime between the provided start and end datetimes.

2. Shared Calendars:

    There are some known issues when working with `shared calendars <https://docs.microsoft.com/en-us/graph/known-issues#calendars>`_ in Microsoft Graph.

3. Event attachments:

    For some unknown reason, Microsoft does not allow to upload an attachment at the event creation time (as opposed with message attachments). 
    See `this <https://stackoverflow.com/questions/46438302/office365-rest-api-creating-a-calendar-event-with-attachments?rq=1>`_. So, to upload attachments to Events, first save the event, then attach the message and save again.