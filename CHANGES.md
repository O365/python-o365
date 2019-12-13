# O365 Library Changelog

Almost every release features a lot of bugfixes but those are not listed here.


## Version 2.0.6 (2019-12-13)

### Features:
- NEW: Outlook Categories. Modified Message, Event and Contact to accept Category instances
- TokenBackends: Implementation of 'should_refresh_token' for environments where multiple account instances are racing against each other to refresh the token. The BaseTokenBackend 'get_token' is now a default and it's not intended to be subclassed. Instead a new 'load_token' is defined to be subclassed.
- User: Profile photo implemented
- Contact: Profile photo implemented
- Drive: can set a custom name when using 'upload_file'
- Utils: updated timezones


## Version 2.0.5 (2019-10-23)

### Features:
- NEW: Directory and User objects
- Removed the GAL from address_book.py. Now the users are queried from the Directory object
- Account: Added 'directory' and 'get_current_user' methods
- Message: Constructor now loads present attachments


## Version 2.0.4 (2019-10-18)

### Features:
- Connection: When using the credentials auth_flow_type the tenant_id is now required
- Message: added 'unique_body' property
- Calendar: added  'get_schedule' (get_availability)


## Version 2.0.3 (2019-09-20)

### Features:
- Message: You can now save Messages and attached messages as EML files.


## Version 2.0.2 (2019-09-18)

### Features:
- The library now features two different authentication flows:
    - 'authorization': Authenticate on behalf of a user
    - 'credentials': Authenticate with your own identity (the app)
- Drive: Added Drive.get_item_by_path(item_path)
- Drive: Now get_drives accepts limit, batch order_by and query parameters
- Mailbox: Now get_message allows to specify an object_id and expands or selects as well
- Account: scopes param on account.authenticate are now optional
- Sharepoint: some enhancements


## Version 2.0.1 (2019-08-02)

### Features:
- Bug fixing release


## Version 2.0.0 (2019-07-29)

### Features:
- It is now posible to authenticate from a web environment with the changes on Connection.
- Attachment: Added attribute size to attachments
- Attachment: You can now add in memory files to attachments. Pass a tuple (BytesIO instance, 'file name.png')
- Account: the resource ME_RESOURCE is now the default
- Message: Added new method 'mark_as_unread' to mark the message as unread.
- Message: Added Body Preview
- Query: Added Precedence Grouping
- Query: Now it's possible to pass attribute=None to the iterable method so you can iterate on the object itself. See [#271](https://github.com/O365/python-o365/issues/271)
- Connection: If timezone is unkknown default to UTC
- Connection: self.naive_session is now lazy loaded
- OutlookWellKnowFolderNames: Added ARCHIVE


## Version 1.1.10 (2019-05-31)

### Features:
- Optimized library startup time by moving imports into methods


## Version 1.1.9 (2019-05-08)

### Features:
- Calendar: Included start/end check on get_events
- Attachments: Allow inline attachments
- Scope Helpers updated


## Version 1.1.8 (2019-04-22)

### Features:
- Bug fixing release


## Version 1.1.7 (2019-04-22)

### Features:
- Excel: Added Excel capabilities to Drive Files
- When returning a potentially big list of instances, the library now returns a generator instead a list


## Version 1.1.6 (2019-04-15)

### Features:
- Message: Added Headers, internet message id and weblink


## Version 1.1.5 (2019-04-08)

### Features:
- Query: Added search capabilities


## Version 1.1.4 (2019-04-03)

### Features:
- Sharepoint: Ability to create, and edit listitems in sharepoint
- New default oauth redirect url


## Version 1.1.3 (2019-03-04)

### Features:
- Message now recognizes EventMessages: an EventMessage can retrieve the related Event
- Added isReadReceiptRequested and isDeliveryReceiptRequested to Messag


## Version 1.1.2 (2019-02-19)

### Features:
- Message can now handle flags
- ApiComponent now stores the logic to convert to/from dateTimeTimeZone resource


## Version 1.1.1 (2019-02-19)

### Features:
- Connection: add tenant_id parameter
- Mailbox: Folder allows to get a message by id ('get_message').
- Message: constructor now accepts a object_id parameter
- Message: new method 'save_message' now allows to save draft-independent properties of a message: is_read and categories for the moment.


## Version 1.1.0 (2019-02-04)

### Features:
- Added Token Backends: Now tokens can be stored anywhere with a concise api
- TokenBackends available: FileSystemTokenBackend and FirestoreTokenBackend
- Token dict: tokens expose new properties like: "expiration_datetime", "is_expired" and "is_long_lived"
- Account: New property "account.is_authenticated": Checks if the token exists and if it is expired
- Connection: The "refresh_token" method now detects if the token can indeed be refreshed.


## Version 1.0.5 (2019-01-16)

### Features:
- Bug fixing release


## Version 1.0.4 (2019-01-10)

### Features:
- Calendar: `get_events` method now includes a new param 'include_recurring' to include all recurring events. Internally will request a calendarView if 'include_recurring' is True (this is the default behaviour).


## Version 1.0.3 (2019-01-10)

### Features:
- Connection: HttpErrors now include the json error Message the server respond with
- Sharepoint: added new features
- Planner capabilites (Tasks)
- Event: Added method 'get_occurrences' to retrieve the recurring events of a seriesMaster event type.


## Version 1.0.2 (2018-11-29)

### Features:
- Contact: now tracks it's inner state
- ContactFolders: New method get_contact_by_email on ContactFolders


## Version 1.0.1 (2018-11-27)

### Features:
- Sharepoint capabilities


## Version 1.0 (2018-11-06)

Library updated from the previous implementation.
Merged from [pyo365](https://github.com/janscas/pyo365).
[Merge pull request #135 from O365/rewrite](https://github.com/O365/python-o365/commit/a3d2b038a91c3954fb8f02502e5abd429be85d3c)
