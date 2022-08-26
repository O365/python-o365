from datetime import datetime, timedelta
import pytest
from O365 import Account
from O365.planner import Plan, Task, Bucket, PlanDetails, TaskDetails
from functools import reduce
from .config import Config
from O365.utils import EnvTokenBackend
from string import printable, ascii_lowercase, digits
from random import choices, randint
from requests.exceptions import HTTPError
import logging
log = logging.getLogger(__name__)

class TestPlanner:

    def setup_class(self):
        credentials = ("client id","client secret")
        self.account = Account(
            (Config.CLIENT_ID),
            scopes=["basic"],
            tenant_id=Config.TENANT_ID,
            username=Config.EMAIL,
            password=Config.PASSWORD,
            auth_flow_type='password',
            token_backend = EnvTokenBackend()
        )
        self.account.authenticate()
        self.planner = self.account.planner()

        test_plan_name = "plan_" + ''.join(choices(printable, k=randint(10, 20)))
        log.info(f"Creating Plan: {test_plan_name}...")
        self.plan = self.planner.create_plan(owner=Config.GROUP_ID, title=test_plan_name)

        test_bucket_name = "bucket_" + ''.join(choices(printable, k=randint(10, 20)))
        log.info(f"Creating Bucket: {test_bucket_name}...")
        self.bucket = self.plan.create_bucket(name = test_bucket_name)

        test_task_name = "task_" + ''.join(choices(printable, k=randint(10, 20)))
        log.info(f"Creating Task: {test_task_name}...")
        self.task = self.bucket.create_task(
            title=test_task_name,
            assignments={
                Config.USER_ID : {
                    "@odata.type": "microsoft.graph.plannerAssignment",
                    "orderHint": " !" #Optional
                }
            },
            #optional kwargs
            priority = choices([1, 3, 5, 9], k=1)[0], #1 -> "urgent", 3 -> "important", 5 -> "medium", 9 -> "low"
            order_hint = " !", #order_hint is a delicate matter. here i will always use default value " !"
            start_date_time = datetime.now(),
            due_date_time= datetime.now() + timedelta(days=1),
            assignee_priority = " !",
            percent_complete = randint(0, 100),
            applied_categories = {f"category{i}" : randint(0,1) == 1 for i in range(1, 25) if randint(0,1)}
        )
        self.taskDetail = self.task.get_details()
        self.planDetail = self.plan.get_details()


    def teardown_class(self):

        buckets = self.plan.list_buckets()
        tasks = self.plan.list_tasks()

        for bucket in buckets:
           log.info(f"Deleting Bucket: {bucket.name}...")
           bucket.delete()
        for task in tasks:
           log.info(f"Deleting Task: {task.title}...")
           task.delete()

        log.info(f"Deleting Plan: {self.plan.title}...")
        self.plan.delete()


    @pytest.mark.parametrize("method", [
        "get_plan_by_id",
        "get_bucket_by_id",
        "get_task_by_id",
    ])
    def test_planner_get_by_id(self, method):

        # if method == get_plan_by_id -> kwargs = {plan_id = self.plan.object_id}
        kwargs = {method.split("_")[1] + "_id": reduce(getattr, [self, method.split("_")[1], "object_id"])}
        # getting the object given the id
        assert getattr(self.planner, method)(**kwargs)


    @pytest.mark.parametrize("method, object", [
        ("list_user_tasks", Task),
        ("list_group_plans", Plan)
    ])
    def test_planner_lists(self, method, object):

        # if method == list_user_tasks -> kwargs = {user_id = Config.USER_ID}
        _id = method.split("_")[1] + "_id"
        kwargs = { _id : getattr(Config, _id.upper())}
        assert len(getattr(self.planner, method)(**kwargs)) > 0

        # if method == list_user_tasks -> method will return only Task objects
        assert all(isinstance(o, object) for o in getattr(self.planner, method)(**kwargs))


    @pytest.mark.parametrize("method, object, return_object", [
        ("list_buckets", "plan", Bucket),
        ("list_tasks", "plan", Task),
        ("get_details", "plan", PlanDetails),
        ("list_tasks", "bucket", Task),
        ("get_details", "task", TaskDetails),
    ])
    def test_get_with_no_args(self, method, object, return_object):

        result = reduce(getattr, [self, object, method])()

        if "list" in method:
            assert len(result) > 0
            assert all(isinstance(o, return_object) for o in result)
        else:
            assert isinstance(result, return_object)


    @pytest.mark.parametrize("object", [
        "plan",
        "planDetail",
        "bucket",
        "task",
        "taskDetail",
    ])
    def test_update(self, object):
        kwargs = {
            #Update Plan
            "plan_title" : "plan_update_" + ''.join(choices(printable, k=randint(10, 20))),

            #Update Plan Detail
            "planDetail_shared_with" : {Config.USER_ID : randint(0,1) == 1},
            "planDetail_category_descriptions" : {
                f"category{i}" : "category_" + ''.join(choices(printable, k=randint(10, 20)))
                for i in range(1, 25) if randint(0,1)
            },

            #Update Bucket
            "bucket_name" : "bucket_update_" + ''.join(choices(printable, k=randint(10, 20))),
            #messing with order_hint will raise error
            "bucket_order_hint" : " !",

            #Update Task
            "task_title" : "task_update_" + ''.join(choices(printable, k=randint(10, 20))),
            "task_assignments" : {Config.USER_ID : None}, #user id : None -> remove task from that user
            "task_priority" : choices([1, 3, 5, 9], k=1)[0],
            "task_order_hint" : " !",
            #if due_date_time is < start_date_time an error will be raised for inconsistency, return 400 client error
            "task_start_date_time" : datetime.now(),
            "task_due_date_time": datetime.now() + timedelta(days=randint(1, 30)), #30 is an arbitrary choice
            "task_assignee_priority" : " !",
            "task_percent_complete" : randint(0, 100),
            "task_applied_categories" : {f"category{i}" : randint(0,1) == 1 for i in range(1, 25) if randint(0,1)},

            #Update Task Detail
            "taskDetail_checklist" : {f"{i}" : {
                "isChecked": randint(0,1) == 1,
                "orderHint": " !",
                "title": "checklist_" + ''.join(choices(printable, k=randint(10, 20)))
            } for i in range(randint(1, 10))},
            "taskDetail_description" : "description " + ''.join(choices(printable, k=randint(10, 20))),
            "taskDetail_preview_type" : choices(["automatic", "noPreview", "checklist", "description", "reference"], k=1)[0],
            "taskDetail_references" : {
                #a not correctly structured url will raise error (e.g. url without .com or others)
                f"https://{''.join(choices(ascii_lowercase + digits, k=randint(5, 10)))}.com" : {
                    "alias": "alias " + ''.join(choices(printable, k=randint(10, 20))),
                    "previewPriority": " !",
                    "type": choices(["PowerPoint", "Excel", "Word", "Pdf"], k=1)[0],
                } for _ in range(randint(1,10))
            },
        }

        update_kwargs = {}
        for key, value in kwargs.items():
            if f"{object}_" in key :
                update_kwargs[key[len(f"{object}_"):]] = value

        if update_kwargs:

            previous_etag = reduce(getattr, [self, object, "_etag"])
            assert getattr(self, object).update(**update_kwargs)

            subsequent_etag = reduce(getattr, [self, object, "_etag"])
            assert previous_etag != subsequent_etag


    @pytest.mark.parametrize("method", [
        "get_plan_by_id",
        "get_bucket_by_id",
        "get_task_by_id",
        "list_user_tasks",
        "list_group_plans"
    ])
    def test_planner_get_exceptions(self, method):
        with pytest.raises(RuntimeError):
            #Error: id not provided
            kwargs = {method.split("_")[1] + "_id" : None}
            getattr(self.planner, method)(**kwargs)

        with pytest.raises(HTTPError):
            #Error: 404 id not found
            kwargs = {method.split("_")[1] + "_id": "Not existing id"}
            getattr(self.planner, method)(**kwargs)


    @pytest.mark.parametrize("creator, created", [
        ("planner", "plan"),
        ("plan", "bucket"),
        ("bucket", "task"),
    ])
    def test_create_exceptions(self, creator, created):
        with pytest.raises(TypeError):
            #Error: missing 1 required positional argument
            reduce(getattr, [self, creator, "create_" + created])()

        with pytest.raises(RuntimeError):
            #Error: required argument is None
            reduce(getattr, [self, creator, "create_" + created])(None)

        if creator == "planner":
            with pytest.raises(HTTPError):
                #Error: 400 invalid id
                reduce(getattr, [self, creator, "create_" + created])("Not existing group")

