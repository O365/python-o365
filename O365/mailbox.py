import logging
import datetime as dt

from O365.connection import ApiComponent
from O365.message import Message

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

        # get the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None)
        if main_resource is None:
            main_resource = getattr(parent, 'main_resource', None) if parent else None
        super().__init__(auth_method=self.con.auth_method, api_version=self.con.api_version,
                         main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.name = cloud_data.get(self._cc('displayName'), kwargs.get('name', ''))
        if self.root is False:
            self.folder_id = cloud_data.get(self._cc('id'), kwargs.get('folder_id', None))  # Create Folder manually
            self.parent_id = cloud_data.get(self._cc('parentFolderId'), None)
            self.child_folders_count = cloud_data.get(self._cc('childFolderCount'), 0)
            self.unread_items_count = cloud_data.get(self._cc('unreadItemCount'), 0)
            self.total_items_count = cloud_data.get(self._cc('totalItemCount'), 0)
            self.updated_at = dt.datetime.now()

    def __str__(self):
        return '{} from resource: {}'.format(self.name, self.main_resource)

    def __repr__(self):
        return self.__str__()

    def get_folders(self, query=None, order_by=None, limit=100):
        """
        Returns a list of child folders

        :param query: applies a filter to the request such as 'displayName:HelloFolder'
        :param order_by: orders the result set based on this condition
        :param limit: limits the result set.
        """

        if self.root:
            url = self._build_url(self._endpoints.get('root_folders'))
        else:
            url = self._build_url(self._endpoints.get('child_folders').format(id=self.folder_id))

        params = {'$top': limit}
        if query:
            params['$filter'] = query
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

        folders = response.json().get('value', [])

        # Everything received from the cloud must be passed with self._cloud_data_key
        return [self.__class__(parent=self, **{self._cloud_data_key: folder}) for folder in folders]

    def get_messages(self, query=None, order_by=None, limit=10, download_attachments=False):
        """
        Downloads messages from this folder

        :param query: applies a filter to the request such as 'displayName:HelloFolder'
        :param order_by: orders the result set based on this condition
        :param limit: limits the result set.
        :param download_attachments: downloads message attachments
        """

        if self.root:
            url = self._build_url(self._endpoints.get('root_messages'))
        else:
            url = self._build_url(self._endpoints.get('folder_messages').format(id=self.folder_id))

        params = {'$top': limit}

        if query:
            params['$filter'] = query
        if order_by:
            params['$orderby'] = order_by

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error donwloading messages in folder {}. Error {}'.format(self.name, str(e)))
            return []
        log.debug('Getting messages in folder {} Response: {}'.format(self.name, str(response)))

        if response.status_code != 200:
            log.debug('Getting messages Request failed: {}'.format(response.reason))
            return []

        messages = response.json().get('value', [])

        # Everything received from the cloud must be passed with self._cloud_data_key
        return [self.message_constructor(parent=self, download_attachments=download_attachments,
                                         **{self._cloud_data_key: message})
                for message in messages]

    def create_child_folder(self, folder_name):
        """
        Creates a new child folder
        :return the new Folder Object or None
        """

        if not folder_name:
            return None

        if self.root:
            url = self._build_url(self._endpoints.get('root_folders'))
        else:
            url = self._build_url(self._endpoints.get('child_folders').format(id=self.folder_id))

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
        return self.__class__(parent=self, **{self._cloud_data_key: folder})

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
            # get folder by it's id, independet of how the parent of this folder_id
            url = self._build_url(self._endpoints.get('get_folder').format(id=folder_id))
            params = None
        else:
            # get folder by name. Only looks up in child folders.
            if self.root:
                url = self._build_url(self._endpoints.get('root_folders'))
            else:
                url = self._build_url(self._endpoints.get('child_folders').format(id=self.folder_id))
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
        return self.__class__(con=self.con, main_resource=self.main_resource, **{self._cloud_data_key: folder})

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

        url = self._build_url(self._endpoints.get('get_folder').format(id=self.folder_id))

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

        url = self._build_url(self._endpoints.get('get_folder').format(id=self.folder_id))

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

        url = self._build_url(self._endpoints.get('copy_folder').format(id=self.folder_id))

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
        return self.__class__(con=self.con, main_resource=self.main_resource, **{self._cloud_data_key: folder})

    def move_folder(self, to_folder_id, update_parent_if_changed=False):
        """
        Move this folder to another folder
        :param to_folder_id: the destination folder_id
        :param update_parent_if_changed: updates self.parent with the new parent Folder if changed
        """
        if self.root or not self.folder_id or not to_folder_id:
            return False

        url = self._build_url(self._endpoints.get('move_folder').format(id=self.folder_id))

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
        draft_message.folder_id = self.folder_id

        return draft_message


class Inbox(Folder):
    """ Inbox Folder """

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, name='Inbox', folder_id='Inbox', **kwargs)


class Junk(Folder):
    """ JunkEmail Folder """

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, name='JunkEmail', folder_id='v', **kwargs)


class DeletedItems(Folder):
    """ DeletedItems Folder """

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, name='DeletedItems', folder_id='DeletedItems', **kwargs)


class Drafts(Folder):
    """ Drafts Folder """

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, name='Drafts', folder_id='Drafts', **kwargs)


class SentItems(Folder):
    """ SentItems Folder """

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, name='SentItems', folder_id='SentItems', **kwargs)


class Outbox(Folder):
    """ Outbox Folder """

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, name='Outbox', folder_id='Outbox', **kwargs)
