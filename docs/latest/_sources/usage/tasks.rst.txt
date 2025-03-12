Tasks
=====
The tasks functionality is grouped in a ToDo object.

A ToDo instance can list and create task folders. It can also list or create tasks on the default user folder. To use other folders use a Folder instance.

These are the scopes needed to work with the ToDo, Folder and Task classes.

=========================  =======================================  ======================================
Raw Scope                  Included in Scope Helper                 Description
=========================  =======================================  ======================================
Tasks.Read                 tasks                                    To only read my personal tasks
Tasks.ReadWrite            tasks_all                                To read and save personal calendars
=========================  =======================================  ======================================

Working with the `ToDo`` instance:

.. code-block:: python

    import datetime as dt

    # ...
    todo = account.tasks()

    #list current tasks
    folder = todo.get_default_folder()
    new_task = folder.new_task()  # creates a new unsaved task
    new_task.subject = 'Send contract to George Best'
    new_task.due = dt.datetime(2020, 9, 25, 18, 30) 
    new_task.save()

    #some time later....

    new_task.mark_completed()
    new_task.save()

    # naive datetimes will automatically be converted to timezone aware datetime
    #  objects using the local timezone detected or the protocol provided timezone
    #  as with the Calendar functionality

Working with Folder instances:

.. code-block:: python

    #create a new folder
    new_folder = todo.new_folder('Defenders')

    #rename a folder
    folder = todo.get_folder(folder_name='Strikers')
    folder.name = 'Forwards'
    folder.update()

    #list current tasks
    task_list = folder.get_tasks()
    for task in task_list:
        print(task)
        print('')