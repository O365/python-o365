from tests.config import CLIENT_ID, CLIENT_SECRET
from pyo365 import Account


class TestMailBox:

    def setup_class(self):
        credentials = (CLIENT_ID, CLIENT_SECRET)
        self.account = Account(credentials)
        self.mailbox = self.account.mailbox()
        self.folder_name = 'Test Drafts Subfolder'

    def teardown_class(self):
        pass

    def test_get_mailbox_folders(self):
        folders = self.mailbox.get_folders(limit=5)

        assert len(folders) > 0

    def test_create_child_folder(self):
        drafts = self.mailbox.drafts_folder()

        new_folder = drafts.create_child_folder(self.folder_name)

        assert new_folder is not None

    def test_get_folder_by_name(self):
        drafts = self.mailbox.drafts_folder()

        q = self.mailbox.q('display_name').equals(self.folder_name)

        folder = drafts.get_folder(folder_name=self.folder_name)

        assert folder is not None

    def test_get_parent_folder(self):
        new_folder = self.mailbox.drafts_folder().get_folder(folder_name=self.folder_name)

        if new_folder:
            parent_folder = new_folder.get_parent_folder()

        assert new_folder and parent_folder is not None

    def test_get_child_folders(self):
        new_folder = self.mailbox.drafts_folder().get_folder(folder_name=self.folder_name)

        if new_folder:
            parent_folder = new_folder.get_parent_folder()
            child_folders = parent_folder.get_folders(limit=2)

        assert new_folder and parent_folder and len(child_folders) >= 1 and any(folder.name == self.folder_name for folder in child_folders)

    def test_move_folder(self):
        new_folder = self.mailbox.drafts_folder().get_folder(folder_name=self.folder_name)
        sent_folder = self.mailbox.sent_folder()
        if new_folder:
            moved = new_folder.move_folder(sent_folder)

        assert new_folder and moved

    def test_copy_folder(self):
        new_folder = self.mailbox.sent_folder().get_folder(folder_name=self.folder_name)  # new_folder is in sent folder now
        drafts_folder = self.mailbox.drafts_folder()

        if new_folder:
            copied_folder = new_folder.copy_folder(drafts_folder)
            deleted = copied_folder.delete()  # delete this copy early on

        assert new_folder and copied_folder is not None and deleted

    def test_refresh_folder(self):
        # new_folder = self.mailbox.sent_folder().get_folder(folder_name=self.folder_name)  # new_folder is in sent folder now

        sent_folder = self.mailbox.sent_folder()

        old_id = sent_folder.folder_id
        refreshed = sent_folder.refresh_folder()
        new_id = sent_folder.folder_id

        assert refreshed and old_id != new_id

    def test_update_folder_name(self):
        new_folder = self.mailbox.sent_folder().get_folder(folder_name=self.folder_name)  # new_folder is in sent folder now

        if new_folder:
            old_name = new_folder.name
            updated = new_folder.update_folder_name(self.folder_name + ' new name!')

        assert new_folder and updated and old_name != new_folder.name

    def test_delete_folder(self):
        new_folder = self.mailbox.sent_folder().get_folder(folder_name=self.folder_name)  # new_folder is in sent folder now

        if new_folder:
            deleted = new_folder.delete()

        assert new_folder and deleted
