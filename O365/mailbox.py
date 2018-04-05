import logging
import datetime as dt

from O365.message import Message
from O365.utils import Pagination, NEXT_LINK_KEYWORD, WellKnowFolderNames, ApiComponent

log = logging.getLogger(__name__)


class Folder(ApiComponent):
    """ A Mail Folder representation """

    _endpoints = {
        'root_folders': '/mailFolders',
        'child_folders': '/mailFolders/{id}/childFolders',
        'get_folder': '/mailFolders/{id}',
        'root_messages': '/messages',
        'folder_messages': '/mailFolders/{id}/messages',
        'copy_folder': '/mailFolders/{id}/copy',
        'move_folder': '/mailFolders/{id}/move'
    }
    message_constructor = Message

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con
        self.parent = parent if isinstance(parent, Folder) else None

        self.root = kwargs.pop('root', False)  # This folder has no parents if root = True.

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.name = cloud_data.get(self._cc('displayName'), kwargs.get('name', ''))  # Fallback to manual folder
        if self.root is False:
            self.folder_id = cloud_data.get(self._cc('id'), kwargs.get('folder_id', None))  # Fallback to manual folder
            self.parent_id = cloud_data.get(self._cc('parentFolderId'), None)
            self.child_folders_count = cloud_data.get(self._cc('childFolderCount'), 0)
            self.unread_items_count = cloud_data.get(self._cc('unreadItemCount'), 0)
            self.total_items_count = cloud_data.get(self._cc('totalItemCount'), 0)
            self.updated_at = dt.datetime.now()

    def __str__(self):
        return '{} from resource: {}'.format(self.name, self.main_resource)

    def __repr__(self):
        return self.__str__()

    def get_folders(self, limit=None, *, query=None, order_by=None, batch=None):
        """
        Returns a list of child folders

        :param limit: limits the result set. Over 999 uses batch.
        :param query: applies a filter to the request such as "displayName eq 'HelloFolder'"
        :param order_by: orders the result set based on this condition
        :param batch: Returns a custom iterator that retrieves items in batches allowing to retrieve more items than the limit.
        """

        if self.root:
            url = self.build_url(self._endpoints.get('root_folders'))
        else:
            url = self.build_url(self._endpoints.get('child_folders').format(id=self.folder_id))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params = {'$top': batch if batch else limit}
        if query:
            params['$filter'] = str(query)
        if order_by:
            params['$orderby'] = order_by

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error requesting child folders of {}. Error: {}'.format(self.name, str(e)))
            return []

        if response.status_code != 200:
            log.debug('Getting folders Request failed: {}'.format(response.reason))
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        folders = [Folder(parent=self, **{self._cloud_data_key: folder}) for folder in data.get('value', [])]
        if batch:
            return Pagination(parent=self, data=folders, constructor=self.__class__,
                              next_link=data.get(NEXT_LINK_KEYWORD, None), limit=limit)
        else:
            return folders

    def get_messages(self, limit=25, *, query=None, order_by=None, batch=None, download_attachments=False):
        """
        Downloads messages from this folder

        :param limit: limits the result set. Over 999 uses batch.
        :param query: applies a filter to the request such as 'displayName:HelloFolder'
        :param order_by: orders the result set based on this condition
        :param batch: Returns a custom iterator that retrieves items in batches allowing
            to retrieve more items than the limit. Download_attachments is ignored.
        :param download_attachments: downloads message attachments
        """

        if self.root:
            url = self.build_url(self._endpoints.get('root_messages'))
        else:
            url = self.build_url(self._endpoints.get('folder_messages').format(id=self.folder_id))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        if batch:
            download_attachments = False

        params = {'$top': batch if batch else limit}

        if query:
            params['$filter'] = str(query)
        if order_by:
            params['$orderby'] = order_by

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error donwloading messages in folder {}. Error {}'.format(self.name, e))
            return []
        log.debug('Getting messages in folder {} Response: {}'.format(self.name, str(response)))

        if response.status_code != 200:
            log.debug('Getting messages Request failed: {}'.format(response.reason))
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        messages = [self.message_constructor(parent=self, download_attachments=download_attachments,
                                             **{self._cloud_data_key: message})
                    for message in data.get('value', [])]
        if batch:
            return Pagination(parent=self, data=messages, constructor=self.message_constructor,
                              next_link=data.get(NEXT_LINK_KEYWORD, None), limit=limit)
        else:
            return messages

    def create_child_folder(self, folder_name):
        """
        Creates a new child folder
        :return the new Folder Object or None
        """

        if not folder_name:
            return None

        if self.root:
            url = self.build_url(self._endpoints.get('root_folders'))
        else:
            url = self.build_url(self._endpoints.get('child_folders').format(id=self.folder_id))

        try:
            response = self.con.post(url, data={self._cc('displayName'): folder_name})
        except Exception as e:
            log.error('Error creating child folder of {}. Error: {}'.format(self.name, str(e)))
            return None

        if response.status_code != 201:
            log.debug('Creating folder Request failed: {}'.format(response.reason))
            return None

        folder = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return Folder(parent=self, **{self._cloud_data_key: folder})

    def get_folder(self, folder_id=None, folder_name=None):
        """
        Returns a folder by it's id
        :param folder_id: the folder_id to be retrieved. Can be any folder Id (child or not)
        :param folder_name: the folder name to be retrieved. Must be a child of this folder.
        """
        if folder_id and folder_name:
            raise RuntimeError('Provide only one of the options')

        if not folder_id and not folder_name:
            raise RuntimeError('Provide one of the options')

        if folder_id:
            # get folder by it's id, independent of the parent of this folder_id
            url = self.build_url(self._endpoints.get('get_folder').format(id=folder_id))
            params = None
        else:
            # get folder by name. Only looks up in child folders.
            if self.root:
                url = self.build_url(self._endpoints.get('root_folders'))
            else:
                url = self.build_url(self._endpoints.get('child_folders').format(id=self.folder_id))
            params = {'$filter': "{} eq '{}'".format(self._cc('displayName'), folder_name), '$top': 1}

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error getting folder {}. Error: {}'.format(folder_id, str(e)))
            return None

        if response.status_code != 200:
            log.debug('Getting folder Request failed: {}'.format(response.reason))
            return None

        if folder_id:
            folder = response.json()
        else:
            folder = response.json().get('value')
            folder = folder[0] if folder else None
            if folder is None:
                return None

        # Everything received from the cloud must be passed with self._cloud_data_key
        # we don't pass parent, as this folder may not be a child of self.
        return Folder(con=self.con, protocol=self.protocol, main_resource=self.main_resource, **{self._cloud_data_key: folder})

    def refresh_folder(self, update_parent_if_changed=False):
        """
        Re-donwload folder data
        Inbox Folder will be unable to download its own data (no folder_id)
        :param update_parent_if_changed: updates self.parent with the new parent Folder if changed
        """
        folder_id = getattr(self, 'folder_id', None)
        if self.root or folder_id is None:
            return False

        folder = self.get_folder(folder_id)
        if folder is None:
            return False

        self.name = folder.name
        if folder.parent_id and self.parent_id:
            if folder.parent_id != self.parent_id:
                self.parent_id = folder.parent_id
                self.parent = self.get_parent_folder() if update_parent_if_changed else None
        self.child_folders_count = folder.child_folders_count
        self.unread_items_count = folder.unread_items_count
        self.total_items_count = folder.total_items_count
        self.updated_at = folder.updated_at

        return True

    def get_parent_folder(self):
        """ Returns the parent folder from attribute self.parent or getting it from the cloud"""
        if self.root:
            return None
        if self.parent:
            return self.parent

        if self.parent_id:
            self.parent = self.get_folder(self.parent_id)
        return self.parent

    def update_folder_name(self, name, update_folder_data=True):
        """ Change this folder name """
        if self.root:
            return False
        if not name:
            return False

        url = self.build_url(self._endpoints.get('get_folder').format(id=self.folder_id))

        try:
            response = self.con.patch(url, data={self._cc('displayName'): name})
        except Exception as e:
            log.error('Error updating folder {}. Error: {}'.format(self.name, str(e)))
            return False

        if response.status_code != 200:
            log.debug('Updating folder Request failed: {}'.format(response.reason))
            return False

        self.name = name
        if not update_folder_data:
            return True

        folder = response.json()

        self.name = folder.get(self._cc('displayName'), '')
        self.parent_id = folder.get(self._cc('parentFolderId'), None)
        self.child_folders_count = folder.get(self._cc('childFolderCount'), 0)
        self.unread_items_count = folder.get(self._cc('unreadItemCount'), 0)
        self.total_items_count = folder.get(self._cc('totalItemCount'), 0)
        self.updated_at = dt.datetime.now()

        return True

    def delete(self):
        """ Deletes this folder """

        if self.root or not self.folder_id:
            return False

        url = self.build_url(self._endpoints.get('get_folder').format(id=self.folder_id))

        try:
            response = self.con.delete(url)
        except Exception as e:
            log.error('Error deleting folder {}. Error: {}'.format(self.name, str(e)))
            return False

        if response.status_code != 204:
            log.debug('Deleteing folder Request failed: {}'.format(response.reason))
            return False

        self.folder_id = None
        return True

    def copy_folder(self, to_folder_id):
        """
        Copy this folder and it's contents to into another folder
        :param to_folder_id: the destination folder_id
        :return The copied folder object
        """

        if self.root or not self.folder_id or not to_folder_id:
            return None

        url = self.build_url(self._endpoints.get('copy_folder').format(id=self.folder_id))

        try:
            response = self.con.post(url, data={self._cc('destinationId'): to_folder_id})
        except Exception as e:
            log.error('Error copying folder {}. Error: {}'.format(self.name, str(e)))
            return None

        if response.status_code != 200:
            log.debug('Copying folder Request failed: {}'.format(response.reason))
            return None

        folder = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return Folder(con=self.con, main_resource=self.main_resource, **{self._cloud_data_key: folder})

    def move_folder(self, to_folder_id, update_parent_if_changed=False):
        """
        Move this folder to another folder
        :param to_folder_id: the destination folder_id
        :param update_parent_if_changed: updates self.parent with the new parent Folder if changed
        """
        if self.root or not self.folder_id or not to_folder_id:
            return False

        url = self.build_url(self._endpoints.get('move_folder').format(id=self.folder_id))

        try:
            response = self.con.post(url, data={self._cc('destinationId'): to_folder_id})
        except Exception as e:
            log.error('Error moving folder {}. Error: {}'.format(self.name, str(e)))
            return False

        if response.status_code != 200:
            log.debug('Moving folder Request failed: {}'.format(response.reason))
            return False

        folder = response.json()

        parent_id = folder.get(self._cc('parentFolderId'), None)

        if parent_id and self.parent_id:
            if parent_id != self.parent_id:
                self.parent_id = parent_id
                self.parent = self.get_parent_folder() if update_parent_if_changed else None

        return True

    def new_message(self):
        """ Creates a new draft message in this folder """

        draft_message = self.message_constructor(parent=self, is_draft=True)

        if self.root:
            draft_message.folder_id = WellKnowFolderNames.DRAFTS.value
        else:
            draft_message.folder_id = self.folder_id

        return draft_message


class MailBox(Folder):

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, root=True, **kwargs)

    def inbox_folder(self):
        """ Returns this mailbox Inbox """
        return Folder(parent=self, name='Inbox', folder_id=WellKnowFolderNames.INBOX.value)

    def junk_folder(self):
        """ Returns this mailbox Junk Folder """
        return Folder(parent=self, name='Junk', folder_id=WellKnowFolderNames.JUNK.value)

    def deleted_folder(self):
        """ Returns this mailbox DeletedItems Folder """
        return Folder(parent=self, name='DeletedItems', folder_id=WellKnowFolderNames.DELETED.value)

    def drafts_folder(self):
        """ Returns this mailbox Drafs Folder """
        return Folder(parent=self, name='Drafs', folder_id=WellKnowFolderNames.DRAFTS.value)

    def sent_folder(self):
        """ Returns this mailbox SentItems Folder """
        return Folder(parent=self, name='SentItems', folder_id=WellKnowFolderNames.SENT.value)

    def outbox_folder(self):
        """ Returns this mailbox Outbox Folder """
        return Folder(parent=self, name='Outbox', folder_id=WellKnowFolderNames.OUTBOX.value)
