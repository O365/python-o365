import datetime as dt
import logging

from .message import Message
from .utils import Pagination, NEXT_LINK_KEYWORD, \
    OutlookWellKnowFolderNames, ApiComponent

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
        'move_folder': '/mailFolders/{id}/move',
        'message': '/messages/{id}',
    }
    message_constructor = Message

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Create an instance to represent the specified folder un given
        parent folder

        :param parent: parent folder/account for this folder
        :type parent: mailbox.Folder or Account
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        :param str name: name of the folder to get under the parent (kwargs)
        :param str folder_id: id of the folder to get under the parent (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con
        self.parent = parent if isinstance(parent, Folder) else None

        # This folder has no parents if root = True.
        self.root = kwargs.pop('root', False)

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        # Fallback to manual folder if nothing available on cloud data
        self.name = cloud_data.get(self._cc('displayName'),
                                   kwargs.get('name',
                                              ''))
        if self.root is False:
            # Fallback to manual folder if nothing available on cloud data
            self.folder_id = cloud_data.get(self._cc('id'),
                                            kwargs.get('folder_id',
                                                       None))
            self.parent_id = cloud_data.get(self._cc('parentFolderId'), None)
            self.child_folders_count = cloud_data.get(
                self._cc('childFolderCount'), 0)
            self.unread_items_count = cloud_data.get(
                self._cc('unreadItemCount'), 0)
            self.total_items_count = cloud_data.get(self._cc('totalItemCount'),
                                                    0)
            self.updated_at = dt.datetime.now()

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '{} from resource: {}'.format(self.name, self.main_resource)

    def get_folders(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a list of child folders matching the query

        :param int limit: max no. of folders to get. Over 999 uses batch.
        :param query: applies a filter to the request such as
         "displayName eq 'HelloFolder'"
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: list of folders
        :rtype: list[mailbox.Folder] or Pagination
        """

        if self.root:
            url = self.build_url(self._endpoints.get('root_folders'))
        else:
            url = self.build_url(
                self._endpoints.get('child_folders').format(id=self.folder_id))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params = {'$top': batch if batch else limit}

        if order_by:
            params['$orderby'] = order_by

        if query:
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

        response = self.con.get(url, params=params)
        if not response:
            return []

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        self_class = getattr(self, 'folder_constructor', type(self))
        folders = [self_class(parent=self, **{self._cloud_data_key: folder}) for
                   folder in data.get('value', [])]
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=folders, constructor=self_class,
                              next_link=next_link, limit=limit)
        else:
            return folders

    def get_message(self, object_id=None, query=None, *, download_attachments=False):
        """ Get one message from the query result.
         A shortcut to get_messages with limit=1
        :param object_id: the message id to be retrieved.
        :param query: applies a filter to the request such as
         "displayName eq 'HelloFolder'"
        :type query: Query or str
        :param bool download_attachments: whether or not to download attachments
        :return: one Message
        :rtype: Message or None
        """
        if object_id is not None and query is not None:
            raise ValueError('Must provide object id or query but not both.')

        if object_id is not None:
            url = self.build_url(self._endpoints.get('message').format(id=object_id))
            response = self.con.get(url)
            if not response:
                return None

            message = response.json()

            return self.message_constructor(parent=self,
                                            download_attachments=download_attachments,
                                            **{self._cloud_data_key: message})

        else:
            messages = list(self.get_messages(limit=1, query=query,
                                              download_attachments=download_attachments))

            return messages[0] if messages else None

    def get_messages(self, limit=25, *, query=None, order_by=None, batch=None,
                     download_attachments=False):
        """
        Downloads messages from this folder

        :param int limit: limits the result set. Over 999 uses batch.
        :param query: applies a filter to the request such as
         "displayName eq 'HelloFolder'"
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :param bool download_attachments: whether or not to download attachments
        :return: list of messages
        :rtype: list[Message] or Pagination
        """

        if self.root:
            url = self.build_url(self._endpoints.get('root_messages'))
        else:
            url = self.build_url(self._endpoints.get('folder_messages').format(
                id=self.folder_id))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params = {'$top': batch if batch else limit}

        if order_by:
            params['$orderby'] = order_by

        if query:
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

        response = self.con.get(url, params=params)
        if not response:
            return iter(())

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        messages = (self.message_constructor(
            parent=self,
            download_attachments=download_attachments,
            **{self._cloud_data_key: message})
            for message in data.get('value', []))

        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=messages,
                              constructor=self.message_constructor,
                              next_link=next_link, limit=limit,
                              download_attachments=download_attachments)
        else:
            return messages

    def create_child_folder(self, folder_name):
        """ Creates a new child folder under this folder

        :param str folder_name: name of the folder to add
        :return: newly created folder
        :rtype: mailbox.Folder or None
        """
        if not folder_name:
            return None

        if self.root:
            url = self.build_url(self._endpoints.get('root_folders'))
        else:
            url = self.build_url(
                self._endpoints.get('child_folders').format(id=self.folder_id))

        response = self.con.post(url,
                                 data={self._cc('displayName'): folder_name})
        if not response:
            return None

        folder = response.json()

        self_class = getattr(self, 'folder_constructor', type(self))
        # Everything received from cloud must be passed as self._cloud_data_key
        return self_class(parent=self, **{self._cloud_data_key: folder})

    def get_folder(self, *, folder_id=None, folder_name=None):
        """ Get a folder by it's id or name

        :param str folder_id: the folder_id to be retrieved.
         Can be any folder Id (child or not)
        :param str folder_name: the folder name to be retrieved.
         Must be a child of this folder.
        :return: a single folder
        :rtype: mailbox.Folder or None
        """
        if folder_id and folder_name:
            raise RuntimeError('Provide only one of the options')

        if not folder_id and not folder_name:
            raise RuntimeError('Provide one of the options')

        if folder_id:
            # get folder by it's id, independent of the parent of this folder_id
            url = self.build_url(
                self._endpoints.get('get_folder').format(id=folder_id))
            params = None
        else:
            # get folder by name. Only looks up in child folders.
            if self.root:
                url = self.build_url(self._endpoints.get('root_folders'))
            else:
                url = self.build_url(
                    self._endpoints.get('child_folders').format(
                        id=self.folder_id))
            params = {'$filter': "{} eq '{}'".format(self._cc('displayName'),
                                                     folder_name), '$top': 1}

        response = self.con.get(url, params=params)
        if not response:
            return None

        if folder_id:
            folder = response.json()
        else:
            folder = response.json().get('value')
            folder = folder[0] if folder else None
            if folder is None:
                return None

        self_class = getattr(self, 'folder_constructor', type(self))
        # Everything received from cloud must be passed as self._cloud_data_key
        # We don't pass parent, as this folder may not be a child of self.
        return self_class(con=self.con, protocol=self.protocol,
                          main_resource=self.main_resource,
                          **{self._cloud_data_key: folder})

    def refresh_folder(self, update_parent_if_changed=False):
        """ Re-download folder data
        Inbox Folder will be unable to download its own data (no folder_id)

        :param bool update_parent_if_changed: updates self.parent with new
         parent Folder if changed
        :return: Refreshed or Not
        :rtype: bool
        """
        folder_id = getattr(self, 'folder_id', None)
        if self.root or folder_id is None:
            return False

        folder = self.get_folder(folder_id=folder_id)
        if folder is None:
            return False

        self.name = folder.name
        if folder.parent_id and self.parent_id:
            if folder.parent_id != self.parent_id:
                self.parent_id = folder.parent_id
                self.parent = (self.get_parent_folder()
                               if update_parent_if_changed else None)
        self.child_folders_count = folder.child_folders_count
        self.unread_items_count = folder.unread_items_count
        self.total_items_count = folder.total_items_count
        self.updated_at = folder.updated_at

        return True

    def get_parent_folder(self):
        """ Get the parent folder from attribute self.parent or
        getting it from the cloud

        :return: Parent Folder
        :rtype: mailbox.Folder or None
        """
        if self.root:
            return None
        if self.parent:
            return self.parent

        if self.parent_id:
            self.parent = self.get_folder(folder_id=self.parent_id)
        return self.parent

    def update_folder_name(self, name, update_folder_data=True):
        """ Change this folder name

        :param str name: new name to change to
        :param bool update_folder_data: whether or not to re-fetch the data
        :return: Updated or Not
        :rtype: bool
        """
        if self.root:
            return False
        if not name:
            return False

        url = self.build_url(
            self._endpoints.get('get_folder').format(id=self.folder_id))

        response = self.con.patch(url, data={self._cc('displayName'): name})
        if not response:
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
        """ Deletes this folder

        :return: Deleted or Not
        :rtype: bool
        """

        if self.root or not self.folder_id:
            return False

        url = self.build_url(
            self._endpoints.get('get_folder').format(id=self.folder_id))

        response = self.con.delete(url)
        if not response:
            return False

        self.folder_id = None
        return True

    def copy_folder(self, to_folder):
        """ Copy this folder and it's contents to into another folder

        :param to_folder: the destination Folder/folder_id to copy into
        :type to_folder: mailbox.Folder or str
        :return: The new folder after copying
        :rtype: mailbox.Folder or None
        """
        to_folder_id = to_folder.folder_id if isinstance(to_folder,
                                                         Folder) else to_folder

        if self.root or not self.folder_id or not to_folder_id:
            return None

        url = self.build_url(
            self._endpoints.get('copy_folder').format(id=self.folder_id))

        response = self.con.post(url,
                                 data={self._cc('destinationId'): to_folder_id})
        if not response:
            return None

        folder = response.json()

        self_class = getattr(self, 'folder_constructor', type(self))
        # Everything received from cloud must be passed as self._cloud_data_key
        return self_class(con=self.con, main_resource=self.main_resource,
                          **{self._cloud_data_key: folder})

    def move_folder(self, to_folder, *, update_parent_if_changed=True):
        """ Move this folder to another folder

        :param to_folder: the destination Folder/folder_id to move into
        :type to_folder: mailbox.Folder or str
        :param bool update_parent_if_changed: updates self.parent with the
         new parent Folder if changed
        :return: The new folder after copying
        :rtype: mailbox.Folder or None
        """
        to_folder_id = to_folder.folder_id if isinstance(to_folder,
                                                         Folder) else to_folder

        if self.root or not self.folder_id or not to_folder_id:
            return False

        url = self.build_url(
            self._endpoints.get('move_folder').format(id=self.folder_id))

        response = self.con.post(url,
                                 data={self._cc('destinationId'): to_folder_id})
        if not response:
            return False

        folder = response.json()

        parent_id = folder.get(self._cc('parentFolderId'), None)

        if parent_id and self.parent_id:
            if parent_id != self.parent_id:
                self.parent_id = parent_id
                self.parent = (self.get_parent_folder()
                               if update_parent_if_changed else None)

        return True

    def new_message(self):
        """ Creates a new draft message under this folder

        :return: new Message
        :rtype: Message
        """

        draft_message = self.message_constructor(parent=self, is_draft=True)

        if self.root:
            draft_message.folder_id = OutlookWellKnowFolderNames.DRAFTS.value
        else:
            draft_message.folder_id = self.folder_id

        return draft_message

    def delete_message(self, message):
        """ Deletes a stored message

        :param message: message/message_id to delete
        :type message: Message or str
        :return: Success / Failure
        :rtype: bool
        """

        message_id = message.object_id if isinstance(message,
                                                     Message) else message

        if message_id is None:
            raise RuntimeError('Provide a valid Message or a message id')

        url = self.build_url(
            self._endpoints.get('message').format(id=message_id))

        response = self.con.delete(url)

        return bool(response)


class MailBox(Folder):
    folder_constructor = Folder

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, root=True, **kwargs)

    def inbox_folder(self):
        """ Shortcut to get Inbox Folder instance

        :rtype: mailbox.Folder
        """
        return self.folder_constructor(parent=self, name='Inbox',
                                       folder_id=OutlookWellKnowFolderNames
                                       .INBOX.value)

    def junk_folder(self):
        """ Shortcut to get Junk Folder instance

        :rtype: mailbox.Folder
        """
        return self.folder_constructor(parent=self, name='Junk',
                                       folder_id=OutlookWellKnowFolderNames
                                       .JUNK.value)

    def deleted_folder(self):
        """ Shortcut to get DeletedItems Folder instance

        :rtype: mailbox.Folder
        """
        return self.folder_constructor(parent=self, name='DeletedItems',
                                       folder_id=OutlookWellKnowFolderNames
                                       .DELETED.value)

    def drafts_folder(self):
        """ Shortcut to get Drafts Folder instance

        :rtype: mailbox.Folder
        """
        return self.folder_constructor(parent=self, name='Drafts',
                                       folder_id=OutlookWellKnowFolderNames
                                       .DRAFTS.value)

    def sent_folder(self):
        """ Shortcut to get SentItems Folder instance

        :rtype: mailbox.Folder
        """
        return self.folder_constructor(parent=self, name='SentItems',
                                       folder_id=OutlookWellKnowFolderNames
                                       .SENT.value)

    def outbox_folder(self):
        """ Shortcut to get Outbox Folder instance

        :rtype: mailbox.Folder
        """
        return self.folder_constructor(parent=self, name='Outbox',
                                       folder_id=OutlookWellKnowFolderNames
                                       .OUTBOX.value)
