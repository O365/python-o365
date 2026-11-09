from unittest import mock

import pytest

from O365.connection import MSGraphProtocol
from O365.sharepoint import SharepointListItem


def list_item(fields=None, column_name_cw=None):
    parent = None
    if column_name_cw is not None:
        parent = mock.Mock(
            con=mock.Mock(),
            protocol=MSGraphProtocol(),
            main_resource="sites/site-id/lists/list-id",
            column_name_cw=column_name_cw,
        )
    cloud_data = {"id": "1"}
    if fields is not None:
        cloud_data["fields"] = fields
    if parent is None:
        return SharepointListItem(
            con=mock.Mock(),
            protocol=MSGraphProtocol(),
            **{"__cloud_data__": cloud_data},
        )
    return SharepointListItem(parent=parent, **{"__cloud_data__": cloud_data})


class TestSharepointListItemUpdateFields:
    def test_update_field_not_set_on_item(self):
        # "Status" is a column of the list but has no value on this item,
        # so the Graph API leaves it out of the item's fields
        item = list_item(
            fields={"Title": "Item 1"},
            column_name_cw={"Title": "Title", "Status": "Status"},
        )

        item.update_fields({"Status": "Inactive"})

        assert item.fields == {"Title": "Item 1", "Status": "Inactive"}

        assert item.save_updates()
        item.con.patch.assert_called_once_with(mock.ANY, {"Status": "Inactive"})

    def test_update_field_set_on_item(self):
        item = list_item(
            fields={"Title": "Item 1", "Status": "Active"},
            column_name_cw={"Title": "Title", "Status": "Status"},
        )

        item.update_fields({"Status": "Inactive"})

        assert item.fields["Status"] == "Inactive"

    def test_update_field_without_fields(self):
        item = list_item(column_name_cw={"Status": "Status"})

        item.update_fields({"Status": "Inactive"})

        assert item.fields == {"Status": "Inactive"}

    def test_update_unknown_field(self):
        item = list_item(
            fields={"Title": "Item 1"},
            column_name_cw={"Title": "Title", "Status": "Status"},
        )

        with pytest.raises(ValueError, match="not a valid internal field name"):
            item.update_fields({"Unknown": "value"})

    def test_update_field_without_parent(self):
        # Nothing to check against: let the API validate the field
        item = list_item()

        item.update_fields({"Status": "Inactive"})

        assert item.fields == {"Status": "Inactive"}
