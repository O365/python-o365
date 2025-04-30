import logging
from datetime import date, datetime

from dateutil.parser import parse

from .utils import NEXT_LINK_KEYWORD, ApiComponent, Pagination

log = logging.getLogger(__name__)


class TaskDetails(ApiComponent):
    _endpoints = {"task_detail": "/planner/tasks/{id}/details"}

    def __init__(self, *, parent=None, con=None, **kwargs):
        """A Microsoft 365 plan details

        :param parent: parent object
        :type parent: Task
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """

        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #:  ID of the task details. |br| **Type:** str
        self.object_id = cloud_data.get("id")

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        main_resource = "{}{}".format(main_resource, "")

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #:  Description of the task. |br| **Type:** str
        self.description = cloud_data.get(self._cc("description"), "")
        #:  The collection of references on the task. |br| **Type:** any
        self.references = cloud_data.get(self._cc("references"), "")
        #:  The collection of checklist items on the task. |br| **Type:** any
        self.checklist = cloud_data.get(self._cc("checklist"), "")
        #:  This sets the type of preview that shows up on the task.
        #: The possible values are: automatic, noPreview, checklist, description, reference.
        #: When set to automatic the displayed preview is chosen by the app viewing the task.
        #: |br| **Type:** str
        self.preview_type = cloud_data.get(self._cc("previewType"), "")
        self._etag = cloud_data.get("@odata.etag", "")

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Task Details"

    def __eq__(self, other):
        return self.object_id == other.object_id

    def update(self, **kwargs):
        """Updates this task detail

        :param kwargs: all the properties to be updated.
        :param dict checklist: the collection of checklist items on the task.

        .. code-block::

            e.g. checklist = {
              "string GUID": {
                "isChecked": bool,
                "orderHint": string,
                "title": string
              }
            } (kwargs)

        :param str description: description of the task
        :param str preview_type: this sets the type of preview that shows up on the task.

            The possible values are: automatic, noPreview, checklist, description, reference.

        :param dict references: the collection of references on the task.

        .. code-block::

            e.g. references = {
              "URL of the resource" : {
                "alias": string,
                "previewPriority": string, #same as orderHint
                "type": string, #e.g. PowerPoint, Excel, Word, Pdf...
              }
            }

        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            return False

        _unsafe = ".:@#"

        url = self.build_url(
            self._endpoints.get("task_detail").format(id=self.object_id)
        )

        data = {
            self._cc(key): value
            for key, value in kwargs.items()
            if key
            in (
                "checklist",
                "description",
                "preview_type",
                "references",
            )
        }
        if not data:
            return False

        if "references" in data and isinstance(data["references"], dict):
            for key in list(data["references"].keys()):
                if (
                    isinstance(data["references"][key], dict)
                    and not "@odata.type" in data["references"][key]
                ):
                    data["references"][key]["@odata.type"] = (
                        "#microsoft.graph.plannerExternalReference"
                    )

                if any(u in key for u in _unsafe):
                    sanitized_key = "".join(
                        [
                            chr(b)
                            if b not in _unsafe.encode("utf-8", "strict")
                            else "%{:02X}".format(b)
                            for b in key.encode("utf-8", "strict")
                        ]
                    )
                    data["references"][sanitized_key] = data["references"].pop(key)

        if "checklist" in data:
            for key in data["checklist"].keys():
                if (
                    isinstance(data["checklist"][key], dict)
                    and not "@odata.type" in data["checklist"][key]
                ):
                    data["checklist"][key]["@odata.type"] = (
                        "#microsoft.graph.plannerChecklistItem"
                    )

        response = self.con.patch(
            url,
            data=data,
            headers={"If-Match": self._etag, "Prefer": "return=representation"},
        )
        if not response:
            return False

        new_data = response.json()

        for key in data:
            value = new_data.get(key, None)
            if value is not None:
                setattr(self, self.protocol.to_api_case(key), value)

        self._etag = new_data.get("@odata.etag")

        return True


class PlanDetails(ApiComponent):
    _endpoints = {"plan_detail": "/planner/plans/{id}/details"}

    def __init__(self, *, parent=None, con=None, **kwargs):
        """A Microsoft 365 plan details

        :param parent: parent object
        :type parent: Plan
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """

        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #:  The unique identifier for the plan details. |br| **Type:** str
        self.object_id = cloud_data.get("id")

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        main_resource = "{}{}".format(main_resource, "")

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #:  Set of user IDs that this plan is shared with. |br| **Type:** any
        self.shared_with = cloud_data.get(self._cc("sharedWith"), "")
        #:  An object that specifies the descriptions of the 25 categories
        #: that can be associated with tasks in the plan. |br| **Type:** any
        self.category_descriptions = cloud_data.get(
            self._cc("categoryDescriptions"), ""
        )
        self._etag = cloud_data.get("@odata.etag", "")

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Plan Details"

    def __eq__(self, other):
        return self.object_id == other.object_id

    def update(self, **kwargs):
        """Updates this plan detail

        :param kwargs: all the properties to be updated.
        :param dict shared_with: dict where keys are user_ids and values are boolean (kwargs)
        :param dict category_descriptions: dict where keys are category1, category2, ..., category25 and values are the label associated with (kwargs)
        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            return False

        url = self.build_url(
            self._endpoints.get("plan_detail").format(id=self.object_id)
        )

        data = {
            self._cc(key): value
            for key, value in kwargs.items()
            if key in ("shared_with", "category_descriptions")
        }
        if not data:
            return False

        response = self.con.patch(
            url,
            data=data,
            headers={"If-Match": self._etag, "Prefer": "return=representation"},
        )
        if not response:
            return False

        new_data = response.json()

        for key in data:
            value = new_data.get(key, None)
            if value is not None:
                setattr(self, self.protocol.to_api_case(key), value)

        self._etag = new_data.get("@odata.etag")

        return True


class Task(ApiComponent):
    """A Microsoft Planner task"""

    _endpoints = {
        "get_details": "/planner/tasks/{id}/details",
        "task": "/planner/tasks/{id}",
    }

    task_details_constructor = TaskDetails  #: :meta private:

    def __init__(self, *, parent=None, con=None, **kwargs):
        """A Microsoft planner task

        :param parent: parent object
        :type parent: Planner or Plan or Bucket
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #:  ID of the task. |br| **Type:** str
        self.object_id = cloud_data.get("id")

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        main_resource = "{}{}".format(main_resource, "")

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #:  Plan ID to which the task belongs. |br| **Type:** str
        self.plan_id = cloud_data.get("planId")
        #:  Bucket ID to which the task belongs. |br| **Type:** str
        self.bucket_id = cloud_data.get("bucketId")
        #:  Title of the task. |br| **Type:** str
        self.title = cloud_data.get(self._cc("title"), "")
        #:  Priority of the task. |br| **Type:** int
        self.priority = cloud_data.get(self._cc("priority"), "")
        #:  The set of assignees the task is assigned to. |br| **Type:** plannerAssignments
        self.assignments = cloud_data.get(self._cc("assignments"), "")
        #:  Hint used to order items of this type in a list view. |br| **Type:** str
        self.order_hint = cloud_data.get(self._cc("orderHint"), "")
        #:  Hint used to order items of this type in a list view. |br| **Type:** str
        self.assignee_priority = cloud_data.get(self._cc("assigneePriority"), "")
        #:  Percentage of task completion. |br| **Type:** int
        self.percent_complete = cloud_data.get(self._cc("percentComplete"), "")
        #:  Value is true if the details object of the task has a
        #: nonempty description and false otherwise. |br| **Type:** bool
        self.has_description = cloud_data.get(self._cc("hasDescription"), "")
        created = cloud_data.get(self._cc("createdDateTime"), None)
        due_date_time = cloud_data.get(self._cc("dueDateTime"), None)
        start_date_time = cloud_data.get(self._cc("startDateTime"), None)
        completed_date = cloud_data.get(self._cc("completedDateTime"), None)
        local_tz = self.protocol.timezone
        #:  Date and time at which the task starts. |br| **Type:** datetime
        self.start_date_time = (
            parse(start_date_time).astimezone(local_tz) if start_date_time else None
        )
        #:  Date and time at which the task is created. |br| **Type:** datetime
        self.created_date = parse(created).astimezone(local_tz) if created else None
        #:  Date and time at which the task is due.  |br| **Type:** datetime
        self.due_date_time = (
            parse(due_date_time).astimezone(local_tz) if due_date_time else None
        )
        #:  Date and time at which the 'percentComplete' of the task is set to '100'.
        #: |br| **Type:** datetime
        self.completed_date = (
            parse(completed_date).astimezone(local_tz) if completed_date else None
        )
        #:  his sets the type of preview that shows up on the task.
        #: The possible values are: automatic, noPreview, checklist, description, reference.
        #: |br| **Type:** str
        self.preview_type = cloud_data.get(self._cc("previewType"), None)
        #:  Number of external references that exist on the task. |br| **Type:** int
        self.reference_count = cloud_data.get(self._cc("referenceCount"), None)
        #:  Number of checklist items that are present on the task. |br| **Type:** int
        self.checklist_item_count = cloud_data.get(self._cc("checklistItemCount"), None)
        #:  Number of checklist items with value set to false, representing incomplete items.
        #: |br| **Type:** int
        self.active_checklist_item_count = cloud_data.get(
            self._cc("activeChecklistItemCount"), None
        )
        #:  Thread ID of the conversation on the task.  |br| **Type:** str
        self.conversation_thread_id = cloud_data.get(
            self._cc("conversationThreadId"), None
        )
        #:  The categories to which the task has been applied. |br| **Type:** plannerAppliedCategories
        self.applied_categories = cloud_data.get(self._cc("appliedCategories"), None)
        self._etag = cloud_data.get("@odata.etag", "")

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Task: {}".format(self.title)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def get_details(self):
        """Returns Microsoft 365/AD plan with given id

        :rtype: PlanDetails
        """

        if not self.object_id:
            raise RuntimeError("Plan is not initialized correctly. Id is missing...")

        url = self.build_url(
            self._endpoints.get("get_details").format(id=self.object_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.task_details_constructor(
            parent=self,
            **{self._cloud_data_key: data},
        )

    def update(self, **kwargs):
        """Updates this task

        :param kwargs: all the properties to be updated.
        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            return False

        url = self.build_url(self._endpoints.get("task").format(id=self.object_id))

        for k, v in kwargs.items():
            if k in ("start_date_time", "due_date_time"):
                kwargs[k] = (
                    v.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if isinstance(v, (datetime, date))
                    else v
                )

        data = {
            self._cc(key): value
            for key, value in kwargs.items()
            if key
            in (
                "title",
                "priority",
                "assignments",
                "order_hint",
                "assignee_priority",
                "percent_complete",
                "has_description",
                "start_date_time",
                "created_date",
                "due_date_time",
                "completed_date",
                "preview_type",
                "reference_count",
                "checklist_item_count",
                "active_checklist_item_count",
                "conversation_thread_id",
                "applied_categories",
                "bucket_id",
            )
        }
        if not data:
            return False

        response = self.con.patch(
            url,
            data=data,
            headers={"If-Match": self._etag, "Prefer": "return=representation"},
        )
        if not response:
            return False

        new_data = response.json()

        for key in data:
            value = new_data.get(key, None)
            if value is not None:
                setattr(self, self.protocol.to_api_case(key), value)

        self._etag = new_data.get("@odata.etag")

        return True

    def delete(self):
        """Deletes this task

        :return: Success / Failure
        :rtype: bool
        """

        if not self.object_id:
            return False

        url = self.build_url(self._endpoints.get("task").format(id=self.object_id))

        response = self.con.delete(url, headers={"If-Match": self._etag})
        if not response:
            return False

        self.object_id = None

        return True


class Bucket(ApiComponent):
    _endpoints = {
        "list_tasks": "/planner/buckets/{id}/tasks",
        "create_task": "/planner/tasks",
        "bucket": "/planner/buckets/{id}",
    }
    task_constructor = Task  #: :meta private:

    def __init__(self, *, parent=None, con=None, **kwargs):
        """A Microsoft 365 bucket

        :param parent: parent object
        :type parent: Planner or Plan
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """

        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: ID of the bucket. |br| **Type:** str
        self.object_id = cloud_data.get("id")

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        main_resource = "{}{}".format(main_resource, "")

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #: Name of the bucket. |br| **Type:** str
        self.name = cloud_data.get(self._cc("name"), "")
        #: Hint used to order items of this type in a list view. |br| **Type:** str
        self.order_hint = cloud_data.get(self._cc("orderHint"), "")
        #: Plan ID to which the bucket belongs. |br| **Type:** str
        self.plan_id = cloud_data.get(self._cc("planId"), "")
        self._etag = cloud_data.get("@odata.etag", "")

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Bucket: {}".format(self.name)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def list_tasks(self):
        """Returns list of tasks that given plan has
        :rtype: list[Task]
        """

        if not self.object_id:
            raise RuntimeError("Bucket is not initialized correctly. Id is missing...")

        url = self.build_url(
            self._endpoints.get("list_tasks").format(id=self.object_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return [
            self.task_constructor(parent=self, **{self._cloud_data_key: task})
            for task in data.get("value", [])
        ]

    def create_task(self, title, assignments=None, **kwargs):
        """Creates a Task

        :param str title: the title of the task
        :param dict assignments: the dict of users to which tasks are to be assigned.

        .. code-block:: python

            e.g. assignments = {
                  "ca2a1df2-e36b-4987-9f6b-0ea462f4eb47": null,
                  "4e98f8f1-bb03-4015-b8e0-19bb370949d8": {
                      "@odata.type": "microsoft.graph.plannerAssignment",
                      "orderHint": "String"
                    }
                }
            if "user_id": null -> task is unassigned to user.
            if "user_id": dict -> task is assigned to user

        :param dict kwargs: optional extra parameters to include in the task
        :param int priority: priority of the task. The valid range of values is between 0 and 10.

            1 -> "urgent", 3 -> "important", 5 -> "medium", 9 -> "low" (kwargs)

        :param str order_hint: the order of the bucket. Default is on top (kwargs)
        :param datetime or str start_date_time: the starting date of the task. If str format should be: "%Y-%m-%dT%H:%M:%SZ" (kwargs)
        :param datetime or str due_date_time: the due date of the task. If str format should be: "%Y-%m-%dT%H:%M:%SZ" (kwargs)
        :param str conversation_thread_id: thread ID of the conversation on the task.

            This is the ID of the conversation thread object created in the group (kwargs)

        :param str assignee_priority: hint used to order items of this type in a list view (kwargs)
        :param int percent_complete: percentage of task completion. When set to 100, the task is considered completed (kwargs)
        :param dict applied_categories: The categories (labels) to which the task has been applied.

            Format should be e.g. {"category1": true, "category3": true, "category5": true } should (kwargs)

        :return: newly created task
        :rtype: Task
        """
        if not title:
            raise RuntimeError("Provide a title for the Task")

        if not self.object_id and not self.plan_id:
            return None

        url = self.build_url(self._endpoints.get("create_task"))

        if not assignments:
            assignments = {"@odata.type": "microsoft.graph.plannerAssignments"}

        for k, v in kwargs.items():
            if k in ("start_date_time", "due_date_time"):
                kwargs[k] = (
                    v.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if isinstance(v, (datetime, date))
                    else v
                )

        kwargs = {
            self._cc(key): value
            for key, value in kwargs.items()
            if key
            in (
                "priority"
                "order_hint"
                "assignee_priority"
                "percent_complete"
                "has_description"
                "start_date_time"
                "created_date"
                "due_date_time"
                "completed_date"
                "preview_type"
                "reference_count"
                "checklist_item_count"
                "active_checklist_item_count"
                "conversation_thread_id"
                "applied_categories"
            )
        }

        data = {
            "title": title,
            "assignments": assignments,
            "bucketId": self.object_id,
            "planId": self.plan_id,
            **kwargs,
        }

        response = self.con.post(url, data=data)
        if not response:
            return None

        task = response.json()

        return self.task_constructor(parent=self, **{self._cloud_data_key: task})

    def update(self, **kwargs):
        """Updates this bucket

        :param kwargs: all the properties to be updated.
        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            return False

        url = self.build_url(self._endpoints.get("bucket").format(id=self.object_id))

        data = {
            self._cc(key): value
            for key, value in kwargs.items()
            if key in ("name", "order_hint")
        }
        if not data:
            return False

        response = self.con.patch(
            url,
            data=data,
            headers={"If-Match": self._etag, "Prefer": "return=representation"},
        )
        if not response:
            return False

        new_data = response.json()

        for key in data:
            value = new_data.get(key, None)
            if value is not None:
                setattr(self, self.protocol.to_api_case(key), value)

        self._etag = new_data.get("@odata.etag")

        return True

    def delete(self):
        """Deletes this bucket

        :return: Success / Failure
        :rtype: bool
        """

        if not self.object_id:
            return False

        url = self.build_url(self._endpoints.get("bucket").format(id=self.object_id))

        response = self.con.delete(url, headers={"If-Match": self._etag})
        if not response:
            return False

        self.object_id = None

        return True


class Plan(ApiComponent):
    _endpoints = {
        "list_buckets": "/planner/plans/{id}/buckets",
        "list_tasks": "/planner/plans/{id}/tasks",
        "get_details": "/planner/plans/{id}/details",
        "plan": "/planner/plans/{id}",
        "create_bucket": "/planner/buckets",
    }

    bucket_constructor = Bucket  #: :meta private:
    task_constructor = Task  #: :meta private:
    plan_details_constructor = PlanDetails  #: :meta private:

    def __init__(self, *, parent=None, con=None, **kwargs):
        """A Microsoft 365 plan

        :param parent: parent object
        :type parent: Planner
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """

        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: ID of the plan. |br| **Type:** str
        self.object_id = cloud_data.get("id")

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        main_resource = "{}{}".format(main_resource, "")

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        #: Date and time at which the plan is created. |br| **Type:** datetime
        self.created_date_time = cloud_data.get(self._cc("createdDateTime"), "")
        container = cloud_data.get(self._cc("container"), {})
        #: The identifier of the resource that contains the plan. |br| **Type:** str
        self.group_id = container.get(self._cc("containerId"), "")
        #: Title of the plan. |br| **Type:** str
        self.title = cloud_data.get(self._cc("title"), "")
        self._etag = cloud_data.get("@odata.etag", "")

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Plan: {}".format(self.title)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def list_buckets(self):
        """Returns list of buckets that given plan has
        :rtype: list[Bucket]
        """

        if not self.object_id:
            raise RuntimeError("Plan is not initialized correctly. Id is missing...")

        url = self.build_url(
            self._endpoints.get("list_buckets").format(id=self.object_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return [
            self.bucket_constructor(parent=self, **{self._cloud_data_key: bucket})
            for bucket in data.get("value", [])
        ]

    def list_tasks(self):
        """Returns list of tasks that given plan has
        :rtype: list[Task] or Pagination of Task
        """

        if not self.object_id:
            raise RuntimeError("Plan is not initialized correctly. Id is missing...")

        url = self.build_url(
            self._endpoints.get("list_tasks").format(id=self.object_id)
        )

        response = self.con.get(url)

        if not response:
            return []

        data = response.json()
        next_link = data.get(NEXT_LINK_KEYWORD, None)

        tasks = [
            self.task_constructor(parent=self, **{self._cloud_data_key: task})
            for task in data.get("value", [])
        ]

        if next_link:
            return Pagination(
                parent=self,
                data=tasks,
                constructor=self.task_constructor,
                next_link=next_link,
            )
        else:
            return tasks

    def get_details(self):
        """Returns Microsoft 365/AD plan with given id

        :rtype: PlanDetails
        """

        if not self.object_id:
            raise RuntimeError("Plan is not initialized correctly. Id is missing...")

        url = self.build_url(
            self._endpoints.get("get_details").format(id=self.object_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.plan_details_constructor(
            parent=self,
            **{self._cloud_data_key: data},
        )

    def create_bucket(self, name, order_hint=" !"):
        """Creates a Bucket

        :param str name: the name of the bucket
        :param str order_hint: the order of the bucket. Default is on top.
            How to use order hints here: https://docs.microsoft.com/en-us/graph/api/resources/planner-order-hint-format?view=graph-rest-1.0
        :return: newly created bucket
        :rtype: Bucket
        """

        if not name:
            raise RuntimeError("Provide a name for the Bucket")

        if not self.object_id:
            return None

        url = self.build_url(self._endpoints.get("create_bucket"))

        data = {"name": name, "orderHint": order_hint, "planId": self.object_id}

        response = self.con.post(url, data=data)
        if not response:
            return None

        bucket = response.json()

        return self.bucket_constructor(parent=self, **{self._cloud_data_key: bucket})

    def update(self, **kwargs):
        """Updates this plan

        :param kwargs: all the properties to be updated.
        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            return False

        url = self.build_url(self._endpoints.get("plan").format(id=self.object_id))

        data = {
            self._cc(key): value for key, value in kwargs.items() if key in ("title")
        }
        if not data:
            return False

        response = self.con.patch(
            url,
            data=data,
            headers={"If-Match": self._etag, "Prefer": "return=representation"},
        )
        if not response:
            return False

        new_data = response.json()

        for key in data:
            value = new_data.get(key, None)
            if value is not None:
                setattr(self, self.protocol.to_api_case(key), value)

        self._etag = new_data.get("@odata.etag")

        return True

    def delete(self):
        """Deletes this plan

        :return: Success / Failure
        :rtype: bool
        """

        if not self.object_id:
            return False

        url = self.build_url(self._endpoints.get("plan").format(id=self.object_id))

        response = self.con.delete(url, headers={"If-Match": self._etag})
        if not response:
            return False

        self.object_id = None

        return True


class Planner(ApiComponent):
    """A microsoft planner class

    In order to use the API following permissions are required.
    Delegated (work or school account) - Group.Read.All, Group.ReadWrite.All
    """

    _endpoints = {
        "get_my_tasks": "/me/planner/tasks",
        "get_plan_by_id": "/planner/plans/{plan_id}",
        "get_bucket_by_id": "/planner/buckets/{bucket_id}",
        "get_task_by_id": "/planner/tasks/{task_id}",
        "list_user_tasks": "/users/{user_id}/planner/tasks",
        "list_group_plans": "/groups/{group_id}/planner/plans",
        "create_plan": "/planner/plans",
    }
    plan_constructor = Plan  #: :meta private:
    bucket_constructor = Bucket  #: :meta private:
    task_constructor = Task  #: :meta private:

    def __init__(self, *, parent=None, con=None, **kwargs):
        """A Planner object

        :param parent: parent object
        :type parent: Account
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the host_name
        main_resource = kwargs.pop("main_resource", "")  # defaults to blank resource
        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Microsoft Planner"

    def get_my_tasks(self, *args):
        """Returns a list of open planner tasks assigned to me

        :rtype: tasks
        """

        url = self.build_url(self._endpoints.get("get_my_tasks"))

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return [
            self.task_constructor(parent=self, **{self._cloud_data_key: site})
            for site in data.get("value", [])
        ]

    def get_plan_by_id(self, plan_id=None):
        """Returns Microsoft 365/AD plan with given id

        :param plan_id: plan id of plan

        :rtype: Plan
        """

        if not plan_id:
            raise RuntimeError("Provide the plan_id")

        url = self.build_url(
            self._endpoints.get("get_plan_by_id").format(plan_id=plan_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.plan_constructor(
            parent=self,
            **{self._cloud_data_key: data},
        )

    def get_bucket_by_id(self, bucket_id=None):
        """Returns Microsoft 365/AD plan with given id

        :param bucket_id: bucket id of buckets

        :rtype: Bucket
        """

        if not bucket_id:
            raise RuntimeError("Provide the bucket_id")

        url = self.build_url(
            self._endpoints.get("get_bucket_by_id").format(bucket_id=bucket_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.bucket_constructor(parent=self, **{self._cloud_data_key: data})

    def get_task_by_id(self, task_id=None):
        """Returns Microsoft 365/AD plan with given id

        :param task_id: task id of tasks

        :rtype: Task
        """

        if not task_id:
            raise RuntimeError("Provide the task_id")

        url = self.build_url(
            self._endpoints.get("get_task_by_id").format(task_id=task_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return self.task_constructor(parent=self, **{self._cloud_data_key: data})

    def list_user_tasks(self, user_id=None):
        """Returns Microsoft 365/AD plan with given id

        :param user_id: user id

        :rtype: list[Task]
        """

        if not user_id:
            raise RuntimeError("Provide the user_id")

        url = self.build_url(
            self._endpoints.get("list_user_tasks").format(user_id=user_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return [
            self.task_constructor(parent=self, **{self._cloud_data_key: task})
            for task in data.get("value", [])
        ]

    def list_group_plans(self, group_id=None):
        """Returns list of plans that given group has
        :param group_id: group id
        :rtype: list[Plan]
        """

        if not group_id:
            raise RuntimeError("Provide the group_id")

        url = self.build_url(
            self._endpoints.get("list_group_plans").format(group_id=group_id)
        )

        response = self.con.get(url)

        if not response:
            return None

        data = response.json()

        return [
            self.plan_constructor(parent=self, **{self._cloud_data_key: plan})
            for plan in data.get("value", [])
        ]

    def create_plan(self, owner, title="Tasks"):
        """Creates a Plan

        :param str owner: the id of the group that will own the plan
        :param str title: the title of the new plan. Default set to "Tasks"
        :return: newly created plan
        :rtype: Plan
        """
        if not owner:
            raise RuntimeError("Provide the owner (group_id)")

        url = self.build_url(self._endpoints.get("create_plan"))

        data = {"owner": owner, "title": title}

        response = self.con.post(url, data=data)
        if not response:
            return None

        plan = response.json()

        return self.plan_constructor(parent=self, **{self._cloud_data_key: plan})
