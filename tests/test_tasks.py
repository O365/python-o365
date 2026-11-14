from unittest import mock

import pytest

from O365.connection import MSGraphProtocol
from O365.tasks import ChecklistItem, Task
from O365.utils import ImportanceLevel


@pytest.fixture
def task():
    return Task(
        con=mock.Mock(),
        protocol=MSGraphProtocol(timezone="UTC"),
        folder_id="folder",
        __cloud_data__={"id": "task", "title": "Original", "importance": "high"},
    )


@pytest.mark.parametrize("importance", ["low", "normal", "high"])
@pytest.mark.parametrize("as_enum", [False, True])
def test_save_task_importance(task, importance, as_enum):
    task.importance = ImportanceLevel.from_value(importance) if as_enum else importance

    assert task.save() is True
    task.con.patch.assert_called_once_with(
        task.protocol.service_url + "me/todo/lists/folder/tasks/task",
        data={"importance": importance},
    )
    assert task.importance == importance
    assert task.is_starred is (importance == "high")
    assert task.save() is True
    task.con.patch.assert_called_once()


@pytest.mark.parametrize("importance", ["low", "normal", "high"])
@pytest.mark.parametrize("as_enum", [False, True])
def test_create_task_importance(task, importance, as_enum):
    task.task_id = None
    task.con.post.return_value.json.return_value = {"id": "new-task"}
    task.importance = ImportanceLevel.from_value(importance) if as_enum else importance
    task.subject = "New task"

    assert task.save() is True
    task.con.post.assert_called_once_with(
        task.protocol.service_url + "me/todo/lists/folder/tasks",
        data={
            "title": "New task",
            "status": "notStarted",
            "importance": importance,
            "body": None,
            "dueDateTime": None,
            "reminderDateTime": None,
        },
    )


@pytest.mark.parametrize("value", [None, "", "urgent", 1, [], {}])
def test_invalid_task_importance(task, value):
    with pytest.raises(ValueError, match="'importance' must be"):
        task.importance = value

    assert task.importance == "high"
    assert task.save() is True
    task.con.patch.assert_not_called()


def test_task_importance_uses_shared_enum_conversion(task):
    task.importance = "High"

    assert task.save() is True
    task.con.patch.assert_called_once_with(
        task.protocol.service_url + "me/todo/lists/folder/tasks/task",
        data={"importance": "high"},
    )
    assert task.importance == "high"


def test_save_task_importance_with_other_edits(task):
    task.importance = "low"
    task.subject = "Renamed"
    task.body = "Updated notes"
    task.mark_completed()

    assert task.save() is True
    task.con.patch.assert_called_once_with(
        task.protocol.service_url + "me/todo/lists/folder/tasks/task",
        data={
            "importance": "low",
            "title": "Renamed",
            "body": {"contentType": "html", "content": "Updated notes"},
            "status": "completed",
        },
    )


@pytest.mark.parametrize("importance", ["low", "normal", "high", None])
def test_unrelated_task_edit_does_not_send_importance(task, importance):
    task = Task(
        con=task.con,
        protocol=task.protocol,
        folder_id="folder",
        __cloud_data__={
            "id": "task",
            **({"importance": importance} if importance is not None else {}),
        },
    )
    task.subject = "Renamed"

    assert task.save() is True
    task.con.patch.assert_called_once_with(
        task.protocol.service_url + "me/todo/lists/folder/tasks/task",
        data={"title": "Renamed"},
    )
    assert task.importance == importance


def test_create_task_without_importance():
    task = Task(
        con=mock.Mock(),
        protocol=MSGraphProtocol(timezone="UTC"),
        folder_id="folder",
        subject="New task",
    )
    task.con.post.return_value.json.return_value = {"id": "new-task"}

    assert task.save() is True
    assert "importance" not in task.con.post.call_args.kwargs["data"]


@pytest.fixture
def checklist_item(task):
    task.con.patch.return_value.json.return_value = {}
    return ChecklistItem(
        parent=task,
        __cloud_data__={"id": "item", "displayName": "Original", "isChecked": True},
    )


@pytest.mark.parametrize("checked", [False, True])
def test_rename_checklist_item_preserves_completion(task, checked):
    task.con.patch.return_value.json.return_value = {}
    item = ChecklistItem(
        parent=task,
        __cloud_data__={"id": "item", "displayName": "Original", "isChecked": checked},
    )
    item.displayname = "Renamed"

    assert item.save() is True
    task.con.patch.assert_called_once_with(
        task.protocol.service_url + "me/todo/lists/folder/tasks/task/checklistItems/item",
        data={"displayName": "Renamed"},
    )
    assert item.displayname == "Renamed"
    assert item.is_checked is checked
    assert item.save() is True
    task.con.patch.assert_called_once()


@pytest.mark.parametrize("checked", [False, True])
def test_rename_checklist_item_with_completion_change(checklist_item, checked):
    checklist_item.displayname = "Renamed"
    if checked:
        checklist_item.mark_checked()
    else:
        checklist_item.mark_unchecked()

    assert checklist_item.save() is True
    checklist_item.con.patch.assert_called_once_with(
        checklist_item.protocol.service_url
        + "me/todo/lists/folder/tasks/task/checklistItems/item",
        data={"displayName": "Renamed", "isChecked": checked},
    )
    assert checklist_item.is_checked is checked


@pytest.mark.parametrize("value", [None, 1, [], {}])
def test_invalid_checklist_displayname(checklist_item, value):
    with pytest.raises(ValueError, match="'displayname' must be a string"):
        checklist_item.displayname = value

    assert checklist_item.displayname == "Original"
    assert checklist_item.save() is True
    checklist_item.con.patch.assert_not_called()


def test_failed_task_save_retains_importance_change(task):
    task.con.patch.return_value = False
    task.importance = "low"

    assert task.save() is False
    task.con.patch.return_value = mock.Mock()
    assert task.save() is True
    assert task.con.patch.call_args_list == [
        mock.call(
            task.protocol.service_url + "me/todo/lists/folder/tasks/task",
            data={"importance": "low"},
        )
    ] * 2
