Teams
=====
Teams enables the communications via Teams Chat, plus Presence management

These are the scopes needed to work with the ``Teams`` classes.

=========================  =======================================  ======================================
Raw Scope                  Included in Scope Helper                 Description
=========================  =======================================  ======================================
Channel.ReadBasic.All      —                                        To read basic channel information
ChannelMessage.Read.All    —                                        To read channel messages
ChannelMessage.Send        —                                        To send messages to a channel
Chat.Read                  —                                        To read users chat
Chat.ReadWrite             —                                        To read users chat and send chat messages
Presence.Read              presence                                 To read users presence status
Presence.Read.All          —                                        To read any users presence status
Presence.ReadWrite         —                                        To update users presence status
Team.ReadBasic.All         —                                        To read only the basic properties for all my teams
User.ReadBasic.All         users                                    To only read basic properties from users of my organization (User.Read.All requires administrator consent)
=========================  =======================================  ======================================

Presence
--------
Assuming an authenticated account.

.. code-block:: python

    # Retrieve logged-in user's presence
    from O365 import Account
    account = Account(('app_id', 'app_pw'))
    teams = account.teams()
    presence = teams.get_my_presence()

    # Retrieve another user's presence
    user = account.directory().get_user("john@doe.com")
    presence2 = teams.get_user_presence(user.object_id)

To set a users status or preferred status:

.. code-block:: python

    # Set user's presence
    from O365.teams import Activity, Availability, PreferredActivity, PreferredAvailability

    status = teams.set_my_presence(CLIENT_ID, Availability.BUSY, Activity.INACALL, "1H")

    # or set User's preferred presence (which is more likely the one you want)

    status = teams.set_my_user_preferred_presence(PreferredAvailability.OFFLINE, PreferredActivity.OFFWORK, "1H")


Chat
----
Assuming an authenticated account.

.. code-block:: python

    # Retrieve logged-in user's chats
    from O365 import Account
    account = Account(('app_id', 'app_pw'))
    teams = account.teams()
    chats = teams.get_my_chats()

    # Then to retrieve chat messages and chat members
    for chat in chats:
        if chat.chat_type != "unknownFutureValue":
            message = chat.get_messages(limit=10)
            memberlist = chat.get_members()


    # And to send a chat message

    chat.send_message(content="Hello team!", content_type="text")

| Common commands for :code:`Chat` include :code:`.get_member()` and :code:`.get_message()`


Team
----
Assuming an authenticated account.

.. code-block:: python

    # Retrieve logged-in user's teams
    from O365 import Account
    account = Account(('app_id', 'app_pw'))
    teams = account.teams()
    my_teams = teams.get_my_teams()

    # Then to retrieve team channels and messages
    for team in my_teams:
        channels = team.get_channels()
        for channel in channels:
            messages = channel.get_messages(limit=10)
            for channelmessage in messages:
                print(channelmessage)


    # To send a message to a team channel
    channel.send_message("Hello team")

    # To send a reply to a message
    channelmessage.send_message("Hello team leader")

| Common commands for :code:`Teams` include :code:`.create_channel()`, :code:`.get_apps_in_channel()` and :code:`.get_channel()`
| Common commands for :code:`Team` include :code:`.get_channel()`
| Common commands for :code:`Channel` include :code:`.get_message()`
| Common commands for :code:`ChannelMessage` include :code:`.get_replies()` and :code:`.get_reply()`

