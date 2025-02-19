Resources
=========
Each API endpoint requires a resource. This usually defines the owner of the data.

Usually you will work with the default 'ME' resuorce, but you can also use one of the following:

- **'me'**: the user which has given consent. the default for every protocol.
- **'user:user@domain.com'**: a shared mailbox or a user account for which you have permissions. If you don't provide 'user:' will be inferred anyways.
- **'sharepoint:sharepoint-site-id'**: a sharepoint site id.
- **'group:group-site-id'**: a office365 group id.

**ME** is the default resource used everywhere in this library. But you can change this behaviour by providing it to Protocol constructor.

This can be done however at any point (Protocol / Account / Mailbox / Message ..). Examples can be found in their respective documentation pages

Protocols
=========
A protocol is just an interface to specify various options related to an API set,
like base url, word case used for request and response attributes etc..

This project has two different set of API's inbuilt (Office 365 APIs or Microsoft Graph APIs)

But, you can use many other Microsoft APIs as long as you implement the protocol needed.

You can use one or the other:

- **MSGraphProtocol** to use the `Microsoft Graph API <https://developer.microsoft.com/en-us/graph/docs/concepts/overview>`_
- **MSOffice365Protocol** to use the `Office 365 API <https://msdn.microsoft.com/en-us/office/office365/api/api-catalog>`_

Choosing between Graph vs Office365 API
---------------------------------------
Reasons to use **MSGraphProtocol**:

- It is the recommended Protocol by Microsoft.
- It can access more resources over Office 365 (for example OneDrive)

Reasons to use **MSOffice365Protocol**:

- It can send emails with attachments up to 150 MB. MSGraph only allows 4MB on each request.

For more details, check `Graph vs Outlook API <https://docs.microsoft.com/en-us/outlook/rest/compare-graph-outlook>`_

.. note:: The default protocol used by the **Account** Class is **MSGraphProtocol**.

You can implement your own protocols by inheriting from **Protocol** to communicate with other Microsoft APIs.

Initialing Protocol
-------------------
**Using Graph Beta API**

.. code-block:: python

    from O365 import MSGraphProtocol

    # try the api version beta of the Microsoft Graph endpoint.
    protocol = MSGraphProtocol(api_version='beta')  # MSGraphProtocol defaults to v1.0 api version

**Using Shared User Account**

.. code-block:: python

    from O365 import MSGraphProtocol

    protocol = MSGraphProtocol(default_resource='shared_mailbox@example.com')

Utilizing a Protocol Instance
-----------------------------
Protocol itself does not do anything job, it has to be plugged into this library api using Account class

.. code-block:: python

    from O365 import Account, MSGraphProtocol

    my_protocol = MSGraphProtocol('beta', 'shared_mailbox@example.com')
    account = Account(credentials=('<client_id>', '<client_secret>'), protocol=my_protocol)

