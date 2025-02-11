# O365 Library Changelog

Almost every release features a lot of bugfixes but those are not listed here.

## Version 2.1.0 (2025-02-11)

> [!IMPORTANT]
> **Breaking Change:** Removed custom authentication in favour of msal. Old tokens will not work with this version and will require a new authentication flow.

- Account: you can now work with multiple users by changing `account.username` when using auth flow type authorization.
- Account: The username of the logged in use was previously held in `current_username`, it is now in `username` as per the previous bullet  
- Connection methods `get_authorization_url` and `request_token` are now present in the `Account`object. You will no longer need to use the ones from the `Connection` object unless doing something fancy.
- Account and Connection: the authentication flow has changed and now returns different objects which need to be stored from and passed into `get_authorization_url` and `request_token` (if using those calls).
- TokenBackend: they now inherit from the msal cache system. You can now remove tokens, get access scopes from tokens, add a cryptography manager to encrypt and decrypt and much more.
- Scopes are now longer stored into the connection. Scopes are only needed when authenticating and will be stored inside the token data on the token backend.
- Scopes: You should no longer supply 'offline_access' as part of your requested scopes, this is added automatically by MSAL.
- Scopes are now passed in as `requested_scopes` rather than `scopes`
- Token: The token layout has substantially changes, so if you were interrogating it at all, you will need to adjust for the change.


## Version 2.0.38 (2024-11-19)
- Added 'on_premises_sam_account_name' to directory.py (Thanks @danpoltawski)
- TokenBackend: Added DjangoTokenBackend (Thanks @sdelgadoc)

## Version 2.0.37 (2024-10-23)
- TokenBackend: Added BitwardenSecretsManagerBackend (Thanks @wnagele)

## Version 2.0.36 (2024-07-04)

Removed dependency: stringcase
Upgraded requirement requests-oauthlib
Added classifier python 3.12

## Version 2.0.35 (2024-06-29)

###Features:
- Tasks: Exposed status property (Thanks @RogerSelwyn)
- Tasks: Added bucket_id to allowed update-attributes of Task (Thanks @dekiesel) 
- Drive: Added "hashes" attribute to File (Thanks @Chrisrdouglas)
- Drive: get_item_by_path now prepends a slash if it's missing (Thanks @dekiesel)
- Excel: Added "only_values" to "get_used_range" method (Thanks @zstrathe)
- Query: Added negate to iterables inside Query
- Protocol: Added 'Europe/Kyiv' as valid Iana timezone (Thanks @jackill88)
- Message: Added ability to add custom headers (Thanks @ted-mey)


## Version 2.0.34 (2024-02-29)

###Features:
- Calendar: Added weblink property (Thanks @Invincibear)


## Version 2.0.33 (2024-02-01)

###Features:
- Connection: Add support for multiple Prefer headers in Connection class (Thanks @Invincibear)
- MailBox: Added timezone & workinghours to MailboxSettings class (Thanks @sdelgadoc)


## Version 2.0.32 (2024-01-11)

###Features:
- Connection: Allow default headers to be set for GET request (see #1021)
- Teams: Add ability to set user presence status and get another users presence status (Thanks @RogerSelwyn)


## Version 2.0.31 (2023-09-27)

###Features:
- AddressBook: Added fileAs attribute (Thanks @LarsK1)
- Fixed critical bug in 2.0.30 release


## Version 2.0.30 (2023-09-27)

###Features:
- Dropped support for python <3.9 because of the need to use zoneinfo (dropped pytz).  If you need support for older versions use version 2.0.28.


## Version 2.0.29 (2023-09-27)

###Features:
- Calendar: no forwarding events (Thanks @Gregorek85)
- Account: removed pytz (Thanks @ponquersohn)

## Version 2.0.28 (2023-08-29)

###Features:
- Bug fixing release


## Version 2.0.27 (2023-05-30)

###Features:
- Added hex_color to Calendar (Thanks @Invincibear)
- Add support for filter by due datetime in Tasks (Thanks @RogerSelwyn)
- Adding option to set file created and last modified time while uploading in drive (Thanks @yeyeric)
- Add access to singleValueExtendedProperties in Message (Thanks @svmcaro)


## Version 2.0.26 (2023-02-02)

###Features:
- Connection now allows setting default headers (Thanks @yeyeric)
- Now it's possible to request inmutable Ids to the MS Graph protocol (Thanks @yeyeric and @NielsDebrier)
- Added more Well Known Folder Names (Thanks @ponquersohn)


## Version 2.0.25 (2023-01-13)

###Features:
- Added get and set of mailbox settings (Thanks @RogerSelwyn)


## Version 2.0.24 (2022-12-13)

###Features:
- Added externalAudience to automatic replies (Thanks @RogerSelwyn)


## Version 2.0.23 (2022-11-26)

###Features:
- Bug fixing release


## Version 2.0.22 (2022-11-17)

###Features:
- NEW: Added Tasks for MS GRAPH Protocol(Thanks @RogerSelwyn)
- NEW: Mailbox can now set auto reply (Thanks @lodesmets)
- Planner: Added pagination to Plan.list_tasks (Thanks @hcallen)


## Version 2.0.21 (2022-09-23)

###Features:
- Bug fixing release

## Version 2.0.20 (2022-08-26)

### Features:
- Teams: added pagination to `get_all_chats` (Thanks @jhoult).
- Message: added access to inferenceClassification in msg object (Thanks @BlueSideStrongSide).
- Connection: added proxy_http_only flag (Thanks @senor-vu).
- Connection: added ROPC authentication flow (Thanks @pierfrancesto).
- Connection: added new `EnvTokenBackend` (Thanks @pierfrancesto).
 
  
## Version 2.0.19 (2022-05-26)

### Features:
- Drive: added password and expiration date to share_with_link method (Thanks @MagestryMark).
- Drive: support uploading large attachments from memory (Thanks @sebastiant).
- Directory: added new methods: `get_user_manager` and `get_user_direct_reports` (Thanks @dionm).
- Groups: Improvements to `Group` class (Thanks @Krukosz).


## Version 2.0.18 (2022-02-03)

### Features:
- Updated requirements to use tzlocal >=4.0


## Version 2.0.17 (2022-02-01)
### Features:
 - Groups: Added groups.py with some read functionality in Office 365 Groups. Thanks @Krukosz*
 - Teams Chats and Chat Messages: Added to teams.py. Thanks @hcallen.


## Version 2.0.16 (2021-09-12)
### Features:
 - Calendar: Added 'cancel_event' method
 - Message: attachment existance is checked lazily


## Version 2.0.15 (2021-05-25)
### Features:
 - Mailbox: upload attachments bigger than 4MB using MS Graph Protocol
 - Account: added dynamic consent process using functions
 - Drive: allow pulling DriveItems external to tenant
 - Sharepoint: added support for list item fields 
 - Tasks: added Task.importance and Task.is_starred


## Version 2.0.14 (2021-01-28)
### Features:
 - NEW: added MS Teams Presence class


## Version 2.0.13 (2020-12-02)

### Features:
- Bug fixing release


## Version 2.0.12 (2020-12-02)

### Features:
- NEW: added MS Office 365 Tasks (only available using Office365 protocol)
- Connection: init now accepts params for the default FileSystemToken
- Token: added AWS token backend


## Version 2.0.11 (2020-08-25)

### Features:
- Drive: added streamable upload and download
- Drive: added conflict handling flag on uploads (only simple uploads < 4MB)
- Connection: added `verify_ssl` flag
- Calendar: added online meeting methods to change providers (teams, etc.)


## Version 2.0.10 (2020-06-04)

### Features:
- Account: added public client auth flow
- Directory: added query params to retrieve users
- Calendar: now adapted to teams online meetings
- Contact: added personal notes 


## Version 2.0.9 (2020-04-21)

### Features:
- Bug fixing release


## Version 2.0.8 (2020-04-15)

### Features:
- NEW: MS Teams available
- Drive: new method "get_drive" in DriveItems


## Version 2.0.7 (2020-02-06)

### Features:
- Connection: now allows to pass a custom Json Encoder ("json_encoder" param).
- Added WorkBookApplication on excel.py that can run manual calculations on workbooks.


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
