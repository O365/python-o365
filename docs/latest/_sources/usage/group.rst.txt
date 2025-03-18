Group
=====
Groups enables viewing of groups

These are the scopes needed to work with the ``Group`` classes.

=========================  =======================================  ======================================
Raw Scope                  Included in Scope Helper                 Description
=========================  =======================================  ======================================
Group.Read.All             —                                        To read groups
=========================  =======================================  ======================================

Assuming an authenticated account and a previously created group, create a Plan instance.

.. code-block:: python

    #Create a plan instance
    from O365 import Account
    account = Account(('app_id', 'app_pw'))
    groups = account.groups()

    # To retrieve the list of groups
    group_list = groups.list_groups()

    # Or to retrieve a list of groups for a given user
    user_groups = groups.get_user_groups(user_id="object_id")

    # To retrieve a group by an identifier
    group = groups.get_group_by_id(group_id="object_id")
    group = groups.get_group_by_mail(group_mail="john@doe.com")


    # To retrieve the owners and members of a group
    owners = group.get_group_owners()
    members = group.get_group_members()

