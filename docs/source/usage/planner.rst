Planner
=======
Planner enables the creation and maintenance of plans, buckets and tasks

These are the scopes needed to work with the ``Planner`` classes.

=========================  =======================================  ======================================
Raw Scope                  Included in Scope Helper                 Description
=========================  =======================================  ======================================
Group.Read.All             —                                        To only read plans
Group.ReadWrite.All        —                                        To create and maintain a plan
=========================  =======================================  ======================================

Assuming an authenticated account and a previously created group, create a Plan instance.

.. code-block:: python

    #Create a plan instance
    from O365 import Account
    account = Account(('app_id', 'app_pw'))
    planner = account.planner()
    plan = planner.create_plan(
        owner="group_object_id", title="Test Plan"
    )

| Common commands for :code:`planner` include :code:`.create_plan()`, :code:`.get_bucket_by_id()`, :code:`.get_my_tasks()`, :code:`.list_group_plans()`, :code:`.list_group_tasks()` and :code:`.delete()`.
| Common commands for :code:`plan` include :code:`.create_bucket()`, :code:`.get_details()`, :code:`.list_buckets()`, :code:`.list_tasks()` and :code:`.delete()`.

Then to create a bucket within a plan.

.. code-block:: python

    #Create a bucket instance in a plan
    bucket = plan.create_bucket(name="Test Bucket")

Common commands for :code:`bucket` include :code:`.list_tasks()` and :code:`.delete()`.

Then to create a task, assign it to a user, set it to 50% completed and add a description.

.. code-block:: python

    #Create a task in a bucket
    assignments = {
        "user_object_id: {
            "@odata.type": "microsoft.graph.plannerAssignment",
            "orderHint": "1 !",
        }
    }
    task = bucket.create_task(title="Test Task", assignments=assignments)

    task.update(percent_complete=50)

    task_details = task.get_details()
    task_details.update(description="Test Description")

Common commands for :code:`task` include :code:`.get_details()`, :code:`.update()` and :code:`.delete()`.