Protocols
=========
Protocols handles the aspects of communications between different APIs. This project uses the Microsoft Graph APIs. But, you can use many other Microsoft APIs as long as you implement the protocol needed.

You can use:

* MSGraphProtocol to use the `Microsoft Graph API <https://developer.microsoft.com/en-us/graph/docs/concepts/overview>`_

.. code-block:: python

    from O365 import Account

    credentials = ('client_id', 'client_secret')

    account = Account(credentials, auth_flow_type='credentials', tenant_id='my_tenant_id')
    if account.authenticate():
    print('Authenticated!')
    mailbox = account.mailbox('sender_email@my_domain.com') 
    m = mailbox.new_message()
    m.to.add('to_example@example.com')
    m.subject = 'Testing!'
    m.body = "George Best quote: I've stopped drinking, but only while I'm asleep."
    m.save_message()
    m.attachment.add = 'filename.txt'
    m.send()

The default protocol used by the ``Account`` Class is ``MSGraphProtocol``.

You can implement your own protocols by inheriting from Protocol to communicate with other Microsoft APIs.

You can instantiate and use protocols like this:

.. code-block:: python

    from O365 import Account, MSGraphProtocol  # same as from O365.connection import MSGraphProtocol

    # ...

    # try the api version beta of the Microsoft Graph endpoint.
    protocol = MSGraphProtocol(api_version='beta')  # MSGraphProtocol defaults to v1.0 api version
    account = Account(credentials, protocol=protocol)


Resources
=========
Each API endpoint requires a resource. This usually defines the owner of the data. Every protocol defaults to resource 'ME'. 'ME' is the user which has given consent, but you can change this behaviour by providing a different default resource to the protocol constructor.

.. note::

    When using the "with your own identity" authentication method the resource 'ME' is overwritten to be blank as the authentication method already states that you are login with your own identity.

For example when accessing a shared mailbox:

.. code-block:: python

    # ...
    account = Account(credentials=my_credentials, main_resource='shared_mailbox@example.com')
    # Any instance created using account will inherit the resource defined for account.

This can be done however at any point. For example at the protocol level:

.. code-block:: python

    # ...
    protocol = MSGraphProtocol(default_resource='shared_mailbox@example.com')

    account = Account(credentials=my_credentials, protocol=protocol)

    # now account is accessing the shared_mailbox@example.com in every api call.
    shared_mailbox_messages = account.mailbox().get_messages()

Instead of defining the resource used at the account or protocol level, you can provide it per use case as follows:

.. code-block:: python

    # ...
    account = Account(credentials=my_credentials)  # account defaults to 'ME' resource

    mailbox = account.mailbox('shared_mailbox@example.com')  # mailbox is using 'shared_mailbox@example.com' resource instead of 'ME'

    # or:

    message = Message(parent=account, main_resource='shared_mailbox@example.com')  # message is using 'shared_mailbox@example.com' resource

Usually you will work with the default 'ME' resource, but you can also use one of the following:

* 'me': the user which has given consent. The default for every protocol. Overwritten when using "with your own identity" authentication method (Only available on the authorization auth_flow_type).
* 'user:user@domain.com': a shared mailbox or a user account for which you have permissions. If you don't provide 'user:' it will be inferred anyway.
* 'site:sharepoint-site-id': a Sharepoint site id.
* 'group:group-site-id': an Office 365 group id.

By setting the resource prefix (such as 'user:' or 'group:') you help the library understand the type of resource. You can also pass it like 'users/example@exampl.com'. The same applies to the other resource prefixes.