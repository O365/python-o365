Work Hours and Locations
========================

Read-only support for Microsoft Graph work-hours and location occurrences.

These are the scopes commonly used for this feature.

==========================  ========================  ==========================================================
Raw Scope                   Included in Scope Helper  Description
==========================  ========================  ==========================================================
MailboxSettings.Read        —                         Read work-hours/location settings for the signed-in user
MailboxSettings.ReadWrite   mailbox_settings          Read/write mailbox settings (also permits reading occurrences)
User.Read.All               —                         Read another user via ``/users/{id|upn}`` in delegated flows
==========================  ========================  ==========================================================

.. note::
    Endpoint availability depends on cloud/tenant support. ``/me`` is recommended for delegated usage when available.
    A ``403`` or ``404`` from this endpoint usually indicates the feature is unavailable for the current tenant/user.

Example:

.. code-block:: python

    from datetime import datetime, timedelta, timezone

    whl = account.work_hours_and_locations()
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=7)

    # /me endpoint
    occurrences = whl.occurrences_view(start, end)

    # /users/{id|upn} endpoint
    other_user_occurrences = whl.occurrences_view(start, end, user="user@contoso.com")

    for item in occurrences:
        print(item.object_id, item.work_location_type, item.start, item.end, item.time_zone)

Getting valid ``workLocationType`` values
""""""""""""""""""""""""""""""""""""""""""

Microsoft Graph doesn't expose a dedicated enum endpoint, but the wrapper can resolve
the values from Graph ``/$metadata`` and fallback to known defaults if metadata is unavailable.

.. code-block:: python

    valid_values = whl.get_valid_work_location_types()
    print(valid_values)

You can also attach these values to each returned occurrence object:

.. code-block:: python

    occurrences = whl.occurrences_view(start, end, include_valid_values=True)
    print(occurrences[0].valid_work_location_types)
