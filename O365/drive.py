import logging
import warnings
from pathlib import Path
from time import sleep
from typing import Union, Optional
from urllib.parse import quote, urlparse
from io import BytesIO

from dateutil.parser import parse

from .address_book import Contact
from .utils import (
    NEXT_LINK_KEYWORD,
    ApiComponent,
    OneDriveWellKnowFolderNames,
    Pagination,
    ExperimentalQuery,
    CompositeFilter
)

log = logging.getLogger(__name__)

SIZE_THERSHOLD = 1024 * 1024 * 2  # 2 MB
UPLOAD_SIZE_LIMIT_SIMPLE = 1024 * 1024 * 4  # 4 MB
UPLOAD_SIZE_LIMIT_SESSION = 1024 * 1024 * 60  # 60 MB
CHUNK_SIZE_BASE = 1024 * 320  # 320 Kb

# 5 MB --> Must be a multiple of CHUNK_SIZE_BASE
DEFAULT_UPLOAD_CHUNK_SIZE = 1024 * 1024 * 5
ALLOWED_PDF_EXTENSIONS = {".csv", ".doc", ".docx", ".odp", ".ods", ".odt",
                          ".pot", ".potm", ".potx",
                          ".pps", ".ppsx", ".ppsxm", ".ppt", ".pptm", ".pptx",
                          ".rtf", ".xls", ".xlsx"}


class DownloadableMixin:

    def download(self, to_path: Union[None, str, Path] = None, name: str = None,
                 chunk_size: Union[str, int] = "auto", convert_to_pdf: bool = False,
                 output: Optional[BytesIO] = None):
        """ Downloads this file to the local drive. Can download the
        file in chunks with multiple requests to the server.

        :param to_path: a path to store the downloaded file
        :type to_path: str or Path
        :param str name: the name you want the stored file to have.
        :param int chunk_size: number of bytes to retrieve from
         each api call to the server. if auto, files bigger than
         SIZE_THERSHOLD will be chunked (into memory, will be
         however only 1 request)
        :param bool convert_to_pdf: will try to download the converted pdf
         if file extension in ALLOWED_PDF_EXTENSIONS
        :param BytesIO output: (optional) an opened io object to write to.
         if set, the to_path and name will be ignored
        :return: Success / Failure
        :rtype: bool
        """
        # TODO: Add download with more than one request (chunk_requests) with
        #  header 'Range'. For example: 'Range': 'bytes=0-1024'

        if not output:
            if to_path is None:
                to_path = Path()
            else:
                if not isinstance(to_path, Path):
                    to_path = Path(to_path)

            if not to_path.exists():
                raise FileNotFoundError("{} does not exist".format(to_path))

            if name and not Path(name).suffix and self.name:
                name = name + Path(self.name).suffix

            name = name or self.name
            if convert_to_pdf:
                to_path = to_path / Path(name).with_suffix(".pdf")
            else:
                to_path = to_path / name

        url = self.build_url(
            self._endpoints.get("download").format(id=self.object_id))

        try:
            if chunk_size is None:
                stream = False
            elif chunk_size == "auto":
                if self.size and self.size > SIZE_THERSHOLD:
                    stream = True
                else:
                    stream = False
                chunk_size = None
            elif isinstance(chunk_size, int):
                stream = True
            else:
                raise ValueError("Argument chunk_size must be either 'auto' "
                                 "or any integer number representing bytes")

            params = {}
            if convert_to_pdf:
                if not output:
                    if Path(name).suffix in ALLOWED_PDF_EXTENSIONS:
                        params["format"] = "pdf"
                else:
                    params["format"] = "pdf"

            with self.con.get(url, stream=stream, params=params) as response:
                if not response:
                    log.debug("Downloading driveitem Request failed: {}".format(
                        response.reason))
                    return False

                def write_output(out):
                    if stream:
                        for chunk in response.iter_content(
                                chunk_size=chunk_size):
                            if chunk:
                                out.write(chunk)
                    else:
                        out.write(response.content)

                if output:
                    write_output(output)
                else:
                    with to_path.open(mode="wb") as output:
                        write_output(output)

        except Exception as e:
            log.error(
                "Error downloading driveitem {}. Error: {}".format(self.name,
                                                                   str(e)))
            return False

        return True


class CopyOperation(ApiComponent):
    """ https://github.com/OneDrive/onedrive-api-docs/issues/762 """

    _endpoints = {
        # all prefixed with /drives/{drive_id} on main_resource by default
        'item': '/items/{id}',
    }

    def __init__(self, *, parent=None, con=None, target=None, **kwargs):
        """

        :param parent: parent for this operation i.e. the source of the copied item
        :type parent: Drive
        :param Connection con: connection to use if no parent specified
        :param target: The target drive for the copy operation
        :type target: Drive
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        :param str monitor_url:
        :param str item_id:
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con
        #: Parent drive of the copy operation. |br| **Type:** Drive
        self.parent = parent  # parent will be always a Drive
        #: Target drive of the copy operation. |br| **Type:** Drive
        self.target = target or parent

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        #: Monitor url of the copy operation. |br| **Type:** str
        self.monitor_url = kwargs.get('monitor_url', None)
        #: item_id of the copy operation. |br| **Type:** str
        self.item_id = kwargs.get('item_id', None)
        if self.monitor_url is None and self.item_id is None:
            raise ValueError('Must provide a valid monitor_url or item_id')
        if self.monitor_url is not None and self.item_id is not None:
            raise ValueError(
                'Must provide a valid monitor_url or item_id, but not both')

        if self.item_id:
            #: Status of the copy operation. |br| **Type:** str
            self.status = 'completed'
            #: Percentage complete of the copy operation. |br| **Type:** float
            self.completion_percentage = 100.0
        else:
            self.status = 'inProgress'
            self.completion_percentage = 0.0

    def _request_status(self):
        """ Checks the api endpoint to check if the async job progress """
        if self.item_id:
            return True

        response = self.con.naive_request(self.monitor_url, method="get")
        if not response:
            return False

        data = response.json()

        self.status = data.get('status', 'inProgress')
        self.completion_percentage = data.get(self._cc('percentageComplete'),
                                              0)
        self.item_id = data.get(self._cc('resourceId'), None)

        return self.item_id is not None

    def check_status(self, delay=0):
        """ Checks the api endpoint in a loop

        :param delay: number of seconds to wait between api calls.
         Note Connection 'requests_delay' also apply.
        :return: tuple of status and percentage complete
        :rtype: tuple(str, float)
        """
        if not self.item_id:
            while not self._request_status():
                # wait until _request_status returns True
                yield self.status, self.completion_percentage
                if self.item_id is None:
                    sleep(delay)
        else:
            yield self.status, self.completion_percentage

    def get_item(self):
        """ Returns the item copied

        :return: Copied Item
        :rtype: DriveItem
        """
        return self.target.get_item(
            self.item_id) if self.item_id is not None else None


class DriveItemVersion(ApiComponent, DownloadableMixin):
    """ A version of a DriveItem """

    _endpoints = {
        'download': '/versions/{id}/content',
        'restore': '/versions/{id}/restoreVersion'
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Version of DriveItem

        :param parent: parent for this operation
        :type parent: DriveItem
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con
        self._parent = parent if isinstance(parent, DriveItem) else None

        protocol = parent.protocol if parent else kwargs.get('protocol')
        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        resource_prefix = '/items/{item_id}'.format(
            item_id=self._parent.object_id)
        main_resource = '{}{}'.format(
            main_resource or (protocol.default_resource if protocol else ''),
            resource_prefix)
        super().__init__(protocol=protocol, main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: The unique identifier of the item within the Drive. |br| **Type:** str
        self.driveitem_id = self._parent.object_id
        #: The ID of the version. |br| **Type:** str
        self.object_id = cloud_data.get('id', '1.0')
        #: The name (ID) of the version. |br| **Type:** str
        self.name = self.object_id
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        #: Date and time the version was last modified. |br| **Type:** datetime
        self.modified = parse(modified).astimezone(
            local_tz) if modified else None
        #: Indicates the size of the content stream for this version of the item.
        #: |br| **Type:** int
        self.size = cloud_data.get('size', 0)
        modified_by = cloud_data.get(self._cc('lastModifiedBy'), {}).get('user',
                                                                         None)
        #: Identity of the user which last modified the version. |br| **Type:** Contact
        self.modified_by = Contact(con=self.con, protocol=self.protocol, **{
            self._cloud_data_key: modified_by}) if modified_by else None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return ('Version Id: {} | Modified on: {} | by: {}'
                ''.format(self.name,
                          self.modified,
                          self.modified_by.display_name
                          if self.modified_by else None))

    def restore(self):
        """ Restores this DriveItem Version.
        You can not restore the current version (last one).

        :return: Success / Failure
        :rtype: bool
        """
        url = self.build_url(
            self._endpoints.get('restore').format(id=self.object_id))

        response = self.con.post(url)

        return bool(response)

    def download(self, to_path: Union[None, str, Path] = None, name: str = None,
                 chunk_size: Union[str, int] = 'auto', convert_to_pdf: bool = False,
                 output: Optional[BytesIO] = None):
        """ Downloads this version.
        You can not download the current version (last one).

        :return: Success / Failure
        :rtype: bool
        """
        return super().download(to_path=to_path, name=name, chunk_size=chunk_size,
                                convert_to_pdf=convert_to_pdf, output=output)


class DriveItemPermission(ApiComponent):
    """ A Permission representation for a DriveItem """
    _endpoints = {
        'permission': '/items/{driveitem_id}/permissions/{id}'
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Permissions for DriveItem

        :param parent: parent for this operation
        :type parent: DriveItem
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con
        self._parent = parent if isinstance(parent, DriveItem) else None
        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        protocol = parent.protocol if parent else kwargs.get('protocol')
        super().__init__(protocol=protocol, main_resource=main_resource)

        #: The unique identifier of the item within the Drive. |br| **Type:** str
        self.driveitem_id = self._parent.object_id
        cloud_data = kwargs.get(self._cloud_data_key, {})
        #: The unique identifier of the permission among all permissions on the item. |br| **Type:** str
        self.object_id = cloud_data.get(self._cc('id'))
        #: Provides a reference to the ancestor of the current permission,
        #: if it's inherited from an ancestor. |br| **Type:** ItemReference
        self.inherited_from = cloud_data.get(self._cc('inheritedFrom'), None)

        link = cloud_data.get(self._cc('link'), None)
        #: The unique identifier of the permission among all permissions on the item. |br| **Type:** str
        self.permission_type = 'owner'
        if link:
            #: The permission type. |br| **Type:** str
            self.permission_type = 'link'
            #: The share type. |br| **Type:** str
            self.share_type = link.get('type', 'view')
            #: The share scope. |br| **Type:** str
            self.share_scope = link.get('scope', 'anonymous')
            #: The share link. |br| **Type:** str
            self.share_link = link.get('webUrl', None)

        invitation = cloud_data.get(self._cc('invitation'), None)
        if invitation:
            self.permission_type = 'invitation'
            #: The share email. |br| **Type:** str
            self.share_email = invitation.get('email', '')
            invited_by = invitation.get('invitedBy', {})
            #: The invited by user. |br| **Type:** str
            self.invited_by = invited_by.get('user', {}).get(
                self._cc('displayName'), None) or invited_by.get('application',
                                                                 {}).get(
                self._cc('displayName'), None)
            #: Is sign in required. |br| **Type:** bool
            self.require_sign_in = invitation.get(self._cc('signInRequired'),
                                                  True)

        #: The type of permission, for example, read. |br| **Type:** list[str]
        self.roles = cloud_data.get(self._cc('roles'), [])
        granted_to = cloud_data.get(self._cc('grantedTo'), {})
        #: For user type permissions, the details of the users and applications
        #: for this permission. |br| **Type:** IdentitySet
        self.granted_to = granted_to.get('user', {}).get(
            self._cc('displayName')) or granted_to.get('application', {}).get(
            self._cc('displayName'))
        #: A unique token that can be used to access this shared item via the shares API
        #: |br| **Type:** str
        self.share_id = cloud_data.get(self._cc('shareId'), None)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Permission for {} of type: {}'.format(self._parent.name,
                                                      self.permission_type)

    def update_roles(self, roles='view'):
        """ Updates the roles of this permission

        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            return False

        url = self.build_url(self._endpoints.get('permission').format(
            driveitem_id=self.driveitem_id, id=self.object_id))

        if roles in {'view', 'read'}:
            data = {'roles': ['read']}
        elif roles in {'edit', 'write'}:
            data = {'roles': ['write']}
        else:
            raise ValueError('"{}" is not a valid share_type'.format(roles))

        response = self.con.patch(url, data=data)
        if not response:
            return False

        self.roles = data.get('roles', [])
        return True

    def delete(self):
        """ Deletes this permission. Only permissions that are not
        inherited can be deleted.

        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            return False

        url = self.build_url(self._endpoints.get('permission').format(
            driveitem_id=self.driveitem_id, id=self.object_id))

        response = self.con.delete(url)
        if not response:
            return False

        self.object_id = None
        return True


class DriveItem(ApiComponent):
    """ A DriveItem representation. Groups all functionality """

    _endpoints = {
        # all prefixed with /drives/{drive_id} on main_resource by default
        'list_items': '/items/{id}/children',
        'thumbnails': '/items/{id}/thumbnails',
        'item': '/items/{id}',
        'copy': '/items/{id}/copy',
        'download': '/items/{id}/content',
        'search': "/items/{id}/search(q='{search_text}')",
        'versions': '/items/{id}/versions',
        'version': '/items/{id}/versions/{version_id}',
        'simple_upload': '/items/{id}:/{filename}:/content',
        'create_upload_session': '/items/{id}:/{filename}:/createUploadSession',
        'share_link': '/items/{id}/createLink',
        'share_invite': '/items/{id}/invite',
        'permissions': '/items/{id}/permissions',
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Create a DriveItem

        :param parent: parent for this operation
        :type parent: Drive or drive.Folder
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con
        self._parent = parent if isinstance(parent, DriveItem) else None

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        protocol = parent.protocol if parent else kwargs.get('protocol')
        if parent and not isinstance(parent, DriveItem):
            # parent is a Drive so append the drive route to the main_resource
            drive_id = (None if parent.object_id == 'root'
                        else parent.object_id) or None

            # prefix with the current known drive or the default one
            resource_prefix = '/drives/{drive_id}'.format(
                drive_id=drive_id) if drive_id else '/drive'
            main_resource = '{}{}'.format(main_resource or (
                protocol.default_resource if protocol else ''), resource_prefix)

        super().__init__(protocol=protocol, main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: The unique identifier of the item within the Drive. |br| **Type:** str
        self.object_id = cloud_data.get(self._cc('id'))

        parent_reference = cloud_data.get(self._cc('parentReference'), {})
        #: The id of the parent. |br| **Type:** str
        self.parent_id = parent_reference.get('id', None)
        #: Identifier of the drive instance that contains the item. |br| **Type:** str
        self.drive_id = parent_reference.get(self._cc('driveId'), None)
        #: Path that can be used to navigate to the item. |br| **Type:** str
        self.parent_path = parent_reference.get(self._cc("path"), None)

        remote_item = cloud_data.get(self._cc('remoteItem'), None)
        if remote_item is not None:
            #: The drive |br| **Type:** Drive
            self.drive = None  # drive is unknown?
            #: Remote item data, if the item is shared from a drive other than the one being accessed.
            #: |br| **Type:** remoteItem
            self.remote_item = self._classifier(remote_item)(parent=self, **{
                self._cloud_data_key: remote_item})
            self.parent_id = self.remote_item.parent_id
            self.drive_id = self.remote_item.drive_id
            self.set_base_url('drives/{}'.format(self.drive_id))  # changes main_resource and _base_url
        else:
            self.drive = parent if isinstance(parent, Drive) else (
                parent.drive if isinstance(parent.drive, Drive) else kwargs.get(
                    'drive', None))
            self.remote_item = None

        #: The name of the item (filename and extension). |br| **Type:** str
        self.name = cloud_data.get(self._cc('name'), '')
        #: URL that displays the resource in the browser.  |br| **Type:** str
        self.web_url = cloud_data.get(self._cc('webUrl'))
        created_by = cloud_data.get(self._cc('createdBy'), {}).get('user', None)
        #: Identity of the user, device, and application which created the item. |br| **Type:** Contact
        self.created_by = Contact(con=self.con, protocol=self.protocol, **{
            self._cloud_data_key: created_by}) if created_by else None
        modified_by = cloud_data.get(self._cc('lastModifiedBy'), {}).get('user',
                                                                         None)
        #: Identity of the user, device, and application which last modified the item
        #: |br| **Type:** Contact
        self.modified_by = Contact(con=self.con, protocol=self.protocol, **{
            self._cloud_data_key: modified_by}) if modified_by else None

        created = cloud_data.get(self._cc('createdDateTime'), None)
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        #: Date and time of item creation. |br| **Type:** datetime
        self.created = parse(created).astimezone(local_tz) if created else None
        #: Date and time the item was last modified. |br| **Type:** datetime
        self.modified = parse(modified).astimezone(
            local_tz) if modified else None

        #: Provides a user-visible description of the item. |br| **Type:** str
        self.description = cloud_data.get(self._cc('description'), '')
        #: Size of the item in bytes. |br| **Type:** int
        self.size = cloud_data.get(self._cc('size'), 0)
        #: Indicates that the item has been shared with others and
        #: provides information about the shared state of the item. |br| **Type:** str
        self.shared = cloud_data.get(self._cc('shared'), {}).get('scope', None)

        # Thumbnails
        #: The thumbnails. |br| **Type:** any
        self.thumbnails = cloud_data.get(self._cc('thumbnails'), [])

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '{}: {}'.format(self.__class__.__name__, self.name)

    def __eq__(self, other):
        obj_id = getattr(other, 'object_id', None)
        if obj_id is not None:
            return self.object_id == obj_id
        return False

    @staticmethod
    def _classifier(item):
        """ Subclass to change factory classes """
        if 'folder' in item:
            return Folder
        elif 'image' in item:
            return Image
        elif 'photo' in item:
            return Photo
        else:
            return File

    @property
    def is_folder(self):
        """ Returns if this DriveItem is a Folder """
        return isinstance(self, Folder)

    @property
    def is_file(self):
        """ Returns if this DriveItem is a File """
        return isinstance(self, File)

    @property
    def is_image(self):
        """ Returns if this DriveItem is a Image """
        return isinstance(self, Image)

    @property
    def is_photo(self):
        """ Returns if this DriveItem is a Photo """
        return isinstance(self, Photo)

    def get_parent(self):
        """ the parent of this DriveItem

        :return: Parent of this item
        :rtype: Drive or drive.Folder
        """
        if self._parent and self._parent.object_id == self.parent_id:
            return self._parent
        else:
            if self.parent_id:
                return self.drive.get_item(self.parent_id)
            else:
                # return the drive
                return self.drive

    def get_drive(self):
        """
        Returns this item drive
        :return: Drive of this item
        :rtype: Drive or None
        """
        if not self.drive_id:
            return None

        url = self.build_url('')
        response = self.con.get(url)
        if not response:
            return None

        drive = response.json()

        return Drive(parent=self, main_resource='', **{self._cloud_data_key: drive})

    def get_thumbnails(self, size=None):
        """ Returns this Item Thumbnails. Thumbnails are not supported on
        SharePoint Server 2016.

        :param size: request only the specified size: ej: "small",
         Custom 300x400 px: "c300x400", Crop: "c300x400_Crop"
        :return: Thumbnail Data
        :rtype: dict
        """
        if not self.object_id:
            return []

        url = self.build_url(
            self._endpoints.get('thumbnails').format(id=self.object_id))

        params = {}
        if size is not None:
            params['select'] = size

        response = self.con.get(url, params=params)
        if not response:
            return []

        data = response.json()

        if not self.thumbnails or size is None:
            self.thumbnails = data

        return data

    def update(self, **kwargs):
        """ Updates this item

        :param kwargs: all the properties to be updated.
         only name and description are allowed at the moment.
        :return: Success / Failure
        :rtype: bool
        """
        if not self.object_id:
            return False

        url = self.build_url(
            self._endpoints.get('item').format(id=self.object_id))

        data = {self._cc(key): value for key, value in kwargs.items() if
                key in {'name',
                        'description'}}  # convert keys to protocol casing
        if not data:
            return False

        response = self.con.patch(url, data=data)
        if not response:
            return False

        new_data = response.json()

        for key in data:
            value = new_data.get(key, None)
            if value:
                setattr(self, self.protocol.to_api_case(key), value)

        return True

    def delete(self):
        """ Moves this item to the Recycle Bin

        :return: Success / Failure
        :rtype: bool
        """

        if not self.object_id:
            return False

        url = self.build_url(
            self._endpoints.get('item').format(id=self.object_id))

        response = self.con.delete(url)
        if not response:
            return False

        self.object_id = None

        return True

    def move(self, target):
        """ Moves this DriveItem to another Folder.
        Can't move between different Drives.

        :param target: a Folder, Drive item or Item Id string.
         If it's a drive the item will be moved to the root folder.
        :type target: drive.Folder or DriveItem or str
        :return: Success / Failure
        :rtype: bool
        """

        if isinstance(target, Folder):
            target_id = target.object_id
        elif isinstance(target, Drive):
            # we need the root folder id
            root_folder = target.get_root_folder()
            if not root_folder:
                return False
            target_id = root_folder.object_id
        elif isinstance(target, str):
            target_id = target
        else:
            raise ValueError('Target must be a Folder or Drive')

        if not self.object_id or not target_id:
            raise ValueError(
                'Both self, and target must have a valid object_id.')

        if target_id == 'root':
            raise ValueError("When moving, target id can't be 'root'")

        url = self.build_url(
            self._endpoints.get('item').format(id=self.object_id))

        data = {'parentReference': {'id': target_id}}

        response = self.con.patch(url, data=data)
        if not response:
            return False

        self.parent_id = target_id

        return True

    def copy(self, target=None, name=None):
        """Asynchronously creates a copy of this DriveItem and all it's
        child elements.

        :param target: target location to move to.
            If it's a drive the item will be moved to the root folder.
            If it's None, the target is the parent of the item being copied i.e. item will be copied
            into the same location.
        :type target: drive.Folder or Drive
        :param name: a new name for the copy.
        :rtype: CopyOperation
        """

        if target is None and name is None:
            raise ValueError('Must provide a target or a name (or both)')

        if isinstance(target, Folder):
            target_id = target.object_id
            drive_id = target.drive_id
            target_drive = target.drive
        elif isinstance(target, Drive):
            # we need the root folder
            root_folder = target.get_root_folder()
            if not root_folder:
                return None
            target_id = root_folder.object_id
            drive_id = root_folder.drive_id
            target_drive = root_folder.drive
        elif target is None:
            target_id = None
            drive_id = None
            target_drive = None
        else:
            raise ValueError('Target, if provided, must be a Folder or Drive')

        if not self.object_id:
            return None

        if target_id == 'root':
            raise ValueError("When copying, target id can't be 'root'")

        url = self.build_url(
            self._endpoints.get('copy').format(id=self.object_id))

        if target_id and drive_id:
            data = {'parentReference': {'id': target_id, 'driveId': drive_id}}
        else:
            data = {}
        if name:
            # incorporate the extension if the name provided has none.
            if not Path(name).suffix and self.name:
                name = name + Path(self.name).suffix
            data['name'] = name

        response = self.con.post(url, data=data)
        if not response:
            return None

        # Find out if the server has run a Sync or Async operation
        location = response.headers.get('Location', None)

        parent = self.drive or self.remote_item
        if response.status_code == 202:
            # Async operation
            return CopyOperation(parent=parent, monitor_url=location, target=target_drive)
        else:
            # Sync operation. Item is ready to be retrieved
            path = urlparse(location).path
            item_id = path.split('/')[-1]
            return CopyOperation(parent=parent, item_id=item_id, target=target_drive)

    def get_versions(self):
        """ Returns a list of available versions for this item

        :return: list of versions
        :rtype: list[DriveItemVersion]
        """

        if not self.object_id:
            return []
        url = self.build_url(
            self._endpoints.get('versions').format(id=self.object_id))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return [DriveItemVersion(parent=self, **{self._cloud_data_key: item})
                for item in data.get('value', [])]

    def get_version(self, version_id):
        """ Returns a version for specified id

        :return: a version object of specified id
        :rtype: DriveItemVersion
        """
        if not self.object_id:
            return None

        url = self.build_url(
            self._endpoints.get('version').format(id=self.object_id,
                                                  version_id=version_id))

        response = self.con.get(url)
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return DriveItemVersion(parent=self, **{self._cloud_data_key: data})

    def share_with_link(self, share_type='view', share_scope='anonymous', share_password=None, share_expiration_date=None):
        """ Creates or returns a link you can share with others

        :param str share_type: 'view' to allow only view access,
         'edit' to allow editions, and
         'embed' to allow the DriveItem to be embedded
        :param str share_scope: 'anonymous': anyone with the link can access.
         'organization' Only organization members can access
        :param str share_password: sharing link password that is set by the creator. Optional.
        :param str share_expiration_date: format of yyyy-MM-dd (e.g., 2022-02-14) that indicates the expiration date of the permission. Optional.
        :return: link to share
        :rtype: DriveItemPermission
        """

        if not self.object_id:
            return None

        url = self.build_url(
            self._endpoints.get('share_link').format(id=self.object_id))

        data = {
            'type': share_type,
            'scope': share_scope
        }
        if share_password is not None:
            data['password'] = share_password
        if share_expiration_date is not None:
            data['expirationDateTime'] = share_expiration_date

        response = self.con.post(url, data=data)
        if not response:
            return None

        data = response.json()

        # return data.get('link', {}).get('webUrl')
        return DriveItemPermission(parent=self, **{self._cloud_data_key: data})

    def share_with_invite(self, recipients, require_sign_in=True,
                          send_email=True, message=None, share_type='view'):
        """ Sends an invitation to access or edit this DriveItem

        :param recipients: a string or Contact or a list of the former
         representing recipients of this invitation
        :type recipients: list[str] or list[Contact] or str or Contact
        :param bool require_sign_in: if True the recipients
         invited will need to log in to view the contents
        :param bool send_email: if True an email will be send to the recipients
        :param str message: the body text of the message emailed
        :param str share_type: 'view': will allow to read the contents.
         'edit' will allow to modify the contents
        :return: link to share
        :rtype: DriveItemPermission
        """
        if not self.object_id:
            return None

        to = []
        if recipients is None:
            raise ValueError('Provide a valid to parameter')
        elif isinstance(recipients, (list, tuple)):
            for x in recipients:
                if isinstance(x, str):
                    to.append({'email': x})
                elif isinstance(x, Contact):
                    to.append({'email': x.main_email})
                else:
                    raise ValueError(
                        'All the recipients must be either strings or Contacts')
        elif isinstance(recipients, str):
            to.append({'email': recipients})
        elif isinstance(recipients, Contact):
            to.append({'email': recipients.main_email})
        else:
            raise ValueError(
                'All the recipients must be either strings or Contacts')

        url = self.build_url(
            self._endpoints.get('share_invite').format(id=self.object_id))

        data = {
            'recipients': to,
            self._cc('requireSignIn'): require_sign_in,
            self._cc('sendInvitation'): send_email,
        }
        if share_type in {'view', 'read'}:
            data['roles'] = ['read']
        elif share_type in {'edit', 'write'}:
            data['roles'] = ['write']
        else:
            raise ValueError(
                '"{}" is not a valid share_type'.format(share_type))
        if send_email and message:
            data['message'] = message

        response = self.con.post(url, data=data)
        if not response:
            return None

        data = response.json()

        return DriveItemPermission(parent=self, **{self._cloud_data_key: data})

    def get_permissions(self):
        """ Returns a list of DriveItemPermissions with the
        permissions granted for this DriveItem.

        :return: List of Permissions
        :rtype: list[DriveItemPermission]
        """
        if not self.object_id:
            return []

        url = self.build_url(
            self._endpoints.get('permissions').format(id=self.object_id))

        response = self.con.get(url)
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return [DriveItemPermission(parent=self, **{self._cloud_data_key: item})
                for item in data.get('value', [])]


class File(DriveItem, DownloadableMixin):
    """ A File """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: The MIME type for the file. |br| **Type:** str
        self.mime_type = cloud_data.get(self._cc('file'), {}).get(
            self._cc('mimeType'), None)

        #: Hashes of the file's binary content, if available. |br| **Type:** Hashes
        self.hashes = cloud_data.get(self._cc('file'), {}).get(
            self._cc('hashes'), None)

    @property
    def extension(self):
        """The suffix of the file name.

        :getter: get the suffix
        :type: str
        """
        return Path(self.name).suffix


class Image(File):
    """ An Image """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        image = cloud_data.get(self._cc('image'), {})
        #: Height of the image, in pixels. |br| **Type:** int
        self.height = image.get(self._cc('height'), 0)
        #: Width of the image, in pixels. |br| **Type:** int
        self.width = image.get(self._cc('width'), 0)

    @property
    def dimensions(self):
        """ Dimension of the Image

        :return: width x height
        :rtype: str
        """
        return '{}x{}'.format(self.width, self.height)


class Photo(Image):
    """ Photo Object. Inherits from Image but has more attributes """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        photo = cloud_data.get(self._cc('photo'), {})

        taken = photo.get(self._cc('takenDateTime'), None)
        local_tz = self.protocol.timezone
        #: Represents the date and time the photo was taken. |br| **Type:** datetime
        self.taken_datetime = parse(taken).astimezone(
            local_tz) if taken else None
        #: Camera manufacturer. |br| **Type:** str
        self.camera_make = photo.get(self._cc('cameraMake'), None)
        #: Camera model. |br| **Type:** str
        self.camera_model = photo.get(self._cc('cameraModel'), None)
        #: The denominator for the exposure time fraction from the camera. |br| **Type:** float
        self.exposure_denominator = photo.get(self._cc('exposureDenominator'),
                                              None)
        #: The numerator for the exposure time fraction from the camera. |br| **Type:** float
        self.exposure_numerator = photo.get(self._cc('exposureNumerator'), None)
        #: The F-stop value from the camera |br| **Type:** float
        self.fnumber = photo.get(self._cc('fNumber'), None)
        #: The focal length from the camera. |br| **Type:** float
        self.focal_length = photo.get(self._cc('focalLength'), None)
        #: The ISO value from the camera. |br| **Type:** int
        self.iso = photo.get(self._cc('iso'), None)


class Folder(DriveItem):
    """ A Folder inside a Drive """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: Number of children contained immediately within this container. |br| **Type:** int
        self.child_count = cloud_data.get(self._cc('folder'), {}).get(
            self._cc('childCount'), 0)
        #: The unique identifier for this item in the /drive/special collection. |br| **Type:** str
        self.special_folder = cloud_data.get(self._cc('specialFolder'), {}).get(
            'name', None)

    def get_items(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns generator all the items inside this folder

        :param int limit: max no. of folders to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: items in this folder
        :rtype: generator of DriveItem or Pagination
        """

        url = self.build_url(
            self._endpoints.get('list_items').format(id=self.object_id))

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
        items = (
            self._classifier(item)(parent=self, **{self._cloud_data_key: item})
            for item in data.get('value', []))
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=items,
                              constructor=self._classifier,
                              next_link=next_link, limit=limit)
        else:
            return items

    def get_child_folders(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns all the folders inside this folder

        :param int limit: max no. of folders to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: folder items in this folder
        :rtype: generator of DriveItem or Pagination
        """

        if query:
            if not isinstance(query, str):
                if isinstance(query, CompositeFilter):
                    q = ExperimentalQuery(protocol=self.protocol)
                    query = query & q.unequal('folder', None)
                else:
                    query = query.on_attribute('folder').unequal(None)
        else:
            q = ExperimentalQuery(protocol=self.protocol)
            query = q.unequal('folder', None)

        return self.get_items(limit=limit, query=query, order_by=order_by, batch=batch)

    def create_child_folder(self, name, description=None):
        """ Creates a Child Folder

        :param str name: the name of the new child folder
        :param str description: the description of the new child folder
        :return: newly created folder
        :rtype: drive.Folder
        """

        if not self.object_id:
            return None

        url = self.build_url(
            self._endpoints.get('list_items').format(id=self.object_id))

        data = {'name': name, 'folder': {}}
        if description:
            data['description'] = description

        response = self.con.post(url, data=data)
        if not response:
            return None

        folder = response.json()

        return self._classifier(folder)(parent=self,
                                        **{self._cloud_data_key: folder})

    def download_contents(self, to_folder=None):
        """ This will download each file and folder sequentially.
        Caution when downloading big folder structures
        :param drive.Folder to_folder: folder where to store the contents
        """
        if to_folder is None:
            try:
                to_folder = Path() / self.name
            except Exception as e:
                log.error('Could not create folder with name: {}. Error: {}'.format(self.name, e))
                to_folder = Path()  # fallback to the same folder
        else:
            to_folder = Path() / to_folder
            if not to_folder.exists():
                to_folder.mkdir()
        if not isinstance(to_folder, str):
            if not to_folder.exists():
                to_folder.mkdir()
        else:
            to_folder = Path() / self.name

        for item in self.get_items(query=self.new_query().select('id', 'size', 'folder', 'name')):
            if item.is_folder and item.child_count > 0:
                item.download_contents(to_folder=to_folder / item.name)
            elif item.is_folder and item.child_count == 0:
                # Create child folder without contents.
                child_folder = to_folder / item.name
                if not child_folder.exists():
                    child_folder.mkdir()
            else:
                item.download(to_folder)

    def search(self, search_text, limit=None, *, query=None, order_by=None,
               batch=None):
        """ Search for DriveItems under this folder
        The search API uses a search service under the covers,
        which requires indexing of content.

        As a result, there will be some time between creation of an item
        and when it will appear in search results.

        :param str search_text: The query text used to search for items.
         Values may be matched across several fields including filename,
         metadata, and file content.
        :param int limit: max no. of folders to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: items in this folder matching search
        :rtype: generator of DriveItem or Pagination
        """
        if not isinstance(search_text, str) or not search_text:
            raise ValueError('Provide a valid search_text')

        url = self.build_url(
            self._endpoints.get('search').format(id=self.object_id,
                                                 search_text=search_text))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params = {'$top': batch if batch else limit}

        if order_by:
            params['$orderby'] = order_by

        if query:
            if isinstance(query, str):
                params['$filter'] = query
            else:
                if query.has_filters:
                    warnings.warn(
                        'Filters are not allowed by the Api '
                        'Provider in this method')
                    query.clear_filters()
                params.update(query.as_params())

        response = self.con.get(url, params=params)
        if not response:
            return iter(())

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        items = (
            self._classifier(item)(parent=self, **{self._cloud_data_key: item})
            for item in data.get('value', []))
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=items,
                              constructor=self._classifier,
                              next_link=next_link, limit=limit)
        else:
            return items

    def upload_file(
            self,
            item,
            item_name=None,
            chunk_size=DEFAULT_UPLOAD_CHUNK_SIZE,
            upload_in_chunks=False,
            stream=None,
            stream_size=None,
            conflict_handling=None,
            file_created_date_time: str = None,
            file_last_modified_date_time: str= None
    ):
        """ Uploads a file

        :param item: path to the item you want to upload
        :type item: str or Path
        :param item_name: name of the item on the server. None to use original name
        :type item_name: str or Path
        :param chunk_size: Only applies if file is bigger than 4MB or upload_in_chunks is True.
         Chunk size for uploads. Must be a multiple of 327.680 bytes
        :param upload_in_chunks: force the method to upload the file in chunks
        :param io.BufferedIOBase stream: (optional) an opened io object to read into.
         if set, the to_path and name will be ignored
        :param int stream_size: size of stream, required if using stream
        :param conflict_handling: How to handle conflicts.
         NOTE: works for chunk upload only (>4MB or upload_in_chunks is True)
         None to use default (overwrite). Options: fail | replace | rename
        :param file_created_date_time: allow to force file created date time while uploading
        :param file_last_modified_date_time: allow to force file last modified date time while uploading
        :type conflict_handling: str
        :return: uploaded file
        :rtype: DriveItem
        """

        if not stream:
            if item is None:
                raise ValueError('Item must be a valid path to file')
            item = Path(item) if not isinstance(item, Path) else item

            if not item.exists():
                raise ValueError('Item must exist')
            if not item.is_file():
                raise ValueError('Item must be a file')

        file_size = (stream_size if stream_size is not None else item.stat().st_size)

        if not upload_in_chunks and file_size <= UPLOAD_SIZE_LIMIT_SIMPLE:
            # Simple Upload
            url = self.build_url(
                self._endpoints.get('simple_upload').format(id=self.object_id,
                                                            filename=quote(item.name if item_name is None else item_name)))
            # headers = {'Content-type': 'text/plain'}
            headers = {'Content-type': 'application/octet-stream'}
            # headers = None
            if stream:
                data = stream.read()
            else:
                with item.open(mode='rb') as file:
                    data = file.read()

            response = self.con.put(url, headers=headers, data=data)
            if not response:
                return None

            data = response.json()

            return self._classifier(data)(parent=self,
                                          **{self._cloud_data_key: data})
        else:
            # Resumable Upload
            url = self.build_url(
                self._endpoints.get('create_upload_session').format(
                    id=self.object_id, filename=quote(item.name if item_name is None else item_name)))

            # WARNING : order matters in the dict, first we need to set conflictBehavior (if any) and then createdDateTime, otherwise microsoft refuses the api
            # call...
            file_data = {}
            if conflict_handling:
                file_data.setdefault("item", dict())["@microsoft.graph.conflictBehavior"] = conflict_handling
            if file_created_date_time:
                file_data.setdefault("item", dict()).setdefault("fileSystemInfo", dict())["createdDateTime"] = file_created_date_time
            if file_last_modified_date_time:
                file_data.setdefault("item", dict()).setdefault("fileSystemInfo", dict())["lastModifiedDateTime"] = file_last_modified_date_time
               
            log.info(f'Uploading file with {file_data=}')

            response = self.con.post(url, data=file_data)
            if not response:
                return None

            data = response.json()

            upload_url = data.get(self._cc('uploadUrl'), None)
            log.info('Resumable upload on url: {}'.format(upload_url))
            expiration_date = data.get(self._cc('expirationDateTime'), None)
            if expiration_date:
                log.info('Expiration Date for this upload url is: {}'.format(expiration_date))
            if upload_url is None:
                log.error('Create upload session response without '
                          'upload_url for file {}'.format(item.name))
                return None

            def write_stream(file):
                current_bytes = 0
                while True:
                    data = file.read(chunk_size)
                    if not data:
                        break
                    transfer_bytes = len(data)
                    headers = {
                        'Content-type': 'application/octet-stream',
                        'Content-Length': str(len(data)),
                        'Content-Range': 'bytes {}-{}/{}'
                                         ''.format(current_bytes,
                                                   current_bytes +
                                                   transfer_bytes - 1,
                                                   file_size)
                    }
                    current_bytes += transfer_bytes

                    # this request mut NOT send the authorization header.
                    # so we use a naive simple request.
                    response = self.con.naive_request(upload_url, 'PUT',
                                                      data=data,
                                                      headers=headers)
                    if not response:
                        return None

                    if response.status_code != 202:
                        # file is completed
                        data = response.json()
                        return self._classifier(data)(parent=self, **{
                            self._cloud_data_key: data})

            if stream:
                return write_stream(stream)
            else:
                with item.open(mode='rb') as file:
                    return write_stream(file)


class Drive(ApiComponent):
    """ A Drive representation.
    A Drive is a Container of Folders and Files and act as a root item """

    _endpoints = {
        'default_drive': '/drive',
        'get_drive': '/drives/{id}',
        'get_root_item_default': '/drive/root',
        'get_root_item': '/drives/{id}/root',
        'list_items_default': '/drive/root/children',
        'list_items': '/drives/{id}/root/children',
        'get_item_default': '/drive/items/{item_id}',
        'get_item': '/drives/{id}/items/{item_id}',
        'get_item_by_path_default': '/drive/root:{item_path}',
        'get_item_by_path': '/drives/{id}/root:{item_path}',
        'recent_default': '/drive/recent',
        'recent': '/drives/{id}/recent',
        'shared_with_me_default': '/drive/sharedWithMe',
        'shared_with_me': '/drives/{id}/sharedWithMe',
        'get_special_default': '/drive/special/{name}',
        'get_special': '/drives/{id}/special/{name}',
        'search_default': "/drive/search(q='{search_text}')",
        'search': "/drives/{id}/search(q='{search_text}')",
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Create a drive representation

        :param parent: parent for this operation
        :type parent: Drive or Storage
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con
        #: The parent of the Drive. |br| **Type:** Drive
        self.parent = parent if isinstance(parent, Drive) else None

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None)
        if main_resource is None:
            main_resource = getattr(parent, 'main_resource', None) if parent else None
        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self._update_data(kwargs)

    def _update_data(self, data):
        cloud_data = data.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get(self._cc('id'))
        # Fallback to manual drive
        self.name = cloud_data.get(self._cc('name'), data.get('name',
                                                              ''))
        self.description = cloud_data.get(self._cc('description'))
        self.drive_type = cloud_data.get(self._cc('driveType'))
        self.web_url = cloud_data.get(self._cc('webUrl'))

        owner = cloud_data.get(self._cc('owner'), {}).get('user', None)
        self.owner = Contact(con=self.con, protocol=self.protocol,
                             **{self._cloud_data_key: owner}) if owner else None
        self.quota = cloud_data.get(self._cc('quota'))  # dict

        created = cloud_data.get(self._cc('createdDateTime'), None)
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        self.created = parse(created).astimezone(local_tz) if created else None
        self.modified = parse(modified).astimezone(
            local_tz) if modified else None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        owner = str(self.owner) if self.owner else ''
        name = self.name or self.object_id or 'Default Drive'
        if owner:
            return 'Drive: {} (Owned by: {})'.format(name, owner)
        else:
            return 'Drive: {}'.format(name)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def get_root_folder(self):
        """ Returns the Root Folder of this drive

        :return: Root Folder
        :rtype: DriveItem
        """
        if self.object_id:
            # reference the current drive_id
            url = self.build_url(
                self._endpoints.get('get_root_item').format(id=self.object_id))
        else:
            # we don't know the drive_id so go to the default drive
            url = self.build_url(self._endpoints.get('get_root_item_default'))

        response = self.con.get(url)
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self._classifier(data)(parent=self,
                                      **{self._cloud_data_key: data})

    def _base_get_list(self, url, limit=None, *, query=None, order_by=None,
                       batch=None, params={}):
        """ Returns a collection of drive items """

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params['$top'] = batch if batch else limit

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
        items = (
            self._classifier(item)(parent=self, **{self._cloud_data_key: item})
            for item in data.get('value', []))
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=items,
                              constructor=self._classifier,
                              next_link=next_link, limit=limit)
        else:
            return items

    def get_items(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of drive items from the root folder

        :param int limit: max no. of items to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: items in this folder
        :rtype: generator of DriveItem or Pagination
        """

        if self.object_id:
            # reference the current drive_id
            url = self.build_url(
                self._endpoints.get('list_items').format(id=self.object_id))
        else:
            # we don't know the drive_id so go to the default
            url = self.build_url(self._endpoints.get('list_items_default'))

        return self._base_get_list(url, limit=limit, query=query,
                                   order_by=order_by, batch=batch)

    def get_child_folders(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns all the folders inside this folder

        :param int limit: max no. of folders to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: folder items in this folder
        :rtype: generator of DriveItem or Pagination
        """
        if query:
            if not isinstance(query, str):
                if isinstance(query, CompositeFilter):
                    q = ExperimentalQuery(protocol=self.protocol)
                    query = query & q.unequal('folder', None)
                else:
                    query = query.on_attribute('folder').unequal(None)
        else:
            q = ExperimentalQuery(protocol=self.protocol)
            query = q.unequal('folder', None)

        return self.get_items(limit=limit, query=query, order_by=order_by, batch=batch)

    def get_recent(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of recently used DriveItems

        :param int limit: max no. of items to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: items in this folder
        :rtype: generator of DriveItem or Pagination
        """
        if self.object_id:
            # reference the current drive_id
            url = self.build_url(
                self._endpoints.get('recent').format(id=self.object_id))
        else:
            # we don't know the drive_id so go to the default
            url = self.build_url(self._endpoints.get('recent_default'))

        return self._base_get_list(url, limit=limit, query=query,
                                   order_by=order_by, batch=batch)

    def get_shared_with_me(self, limit=None, allow_external=False, *, query=None, order_by=None,
                           batch=None):
        """ Returns a collection of DriveItems shared with me

        :param int limit: max no. of items to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :param allow_external: includes items shared from external tenants
        :type allow_external: bool
        :return: items in this folder
        :rtype: generator of DriveItem or Pagination
        """

        if self.object_id:
            # reference the current drive_id
            url = self.build_url(
                self._endpoints.get('shared_with_me').format(id=self.object_id))
        else:
            # we don't know the drive_id so go to the default
            url = self.build_url(self._endpoints.get('shared_with_me_default'))

        # whether to include driveitems external to tenant
        params = {"allowexternal": allow_external}

        return self._base_get_list(url, limit=limit, query=query,
                                   order_by=order_by, batch=batch, params=params)

    def get_item(self, item_id):
        """ Returns a DriveItem by it's Id

        :return: one item
        :rtype: DriveItem
        """
        if self.object_id:
            # reference the current drive_id
            url = self.build_url(
                self._endpoints.get('get_item').format(id=self.object_id,
                                                       item_id=item_id))
        else:
            # we don't know the drive_id so go to the default drive
            url = self.build_url(
                self._endpoints.get('get_item_default').format(item_id=item_id))

        response = self.con.get(url)
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self._classifier(data)(parent=self,
                                      **{self._cloud_data_key: data})

    def get_item_by_path(self, item_path):
        """ Returns a DriveItem by it's absolute path: /path/to/file
        :return: one item
        :rtype: DriveItem
        """

        if not item_path.startswith("/"):
            item_path = "/" + item_path

        if self.object_id:
            # reference the current drive_id
            url = self.build_url(
                self._endpoints.get('get_item_by_path').format(id=self.object_id,
                                                               item_path=item_path))
        else:
            # we don't know the drive_id so go to the default drive
            url = self.build_url(
                self._endpoints.get('get_item_by_path_default').format(item_path=item_path))

        response = self.con.get(url)
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self._classifier(data)(parent=self,
                                      **{self._cloud_data_key: data})

    def get_special_folder(self, name):
        """ Returns the specified Special Folder

        :return: a special Folder
        :rtype: drive.Folder
        """

        name = name if \
            isinstance(name, OneDriveWellKnowFolderNames) \
            else OneDriveWellKnowFolderNames(name.lower())
        name = name.value

        if self.object_id:
            # reference the current drive_id
            url = self.build_url(
                self._endpoints.get('get_special').format(id=self.object_id,
                                                          name=name))
        else:
            # we don't know the drive_id so go to the default
            url = self.build_url(
                self._endpoints.get('get_special_default').format(name=name))

        response = self.con.get(url)
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self._classifier(data)(parent=self,
                                      **{self._cloud_data_key: data})

    @staticmethod
    def _classifier(item):
        """ Subclass to change factory classes """
        if 'folder' in item:
            return Folder
        elif 'image' in item:
            return Image
        elif 'photo' in item:
            return Photo
        else:
            return File

    def refresh(self):
        """ Updates this drive with data from the server

        :return: Success / Failure
        :rtype: bool
        """

        if self.object_id is None:
            url = self.build_url(self._endpoints.get('default_drive'))
        else:
            url = self.build_url(
                self._endpoints.get('get_drive').format(id=self.object_id))

        response = self.con.get(url)
        if not response:
            return False

        drive = response.json()

        self._update_data({self._cloud_data_key: drive})
        return True

    def search(self, search_text, limit=None, *, query=None, order_by=None,
               batch=None):
        """ Search for DriveItems under this drive.
        Your app can search more broadly to include items shared with the
        current user.

        To broaden the search scope, use this search instead the Folder Search.

        The search API uses a search service under the covers, which requires
        indexing of content.

        As a result, there will be some time between creation of an
        item and when it will appear in search results.

        :param str search_text: The query text used to search for items.
         Values may be matched across several fields including filename,
         metadata, and file content.
        :param int limit: max no. of items to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: items in this folder matching search
        :rtype: generator of DriveItem or Pagination
        """
        if not isinstance(search_text, str) or not search_text:
            raise ValueError('Provide a valid search_text')

        if self.object_id is None:
            url = self.build_url(self._endpoints.get('search_default').format(
                search_text=search_text))
        else:
            url = self.build_url(
                self._endpoints.get('search').format(id=self.object_id,
                                                     search_text=search_text))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params = {'$top': batch if batch else limit}

        if order_by:
            params['$orderby'] = order_by

        if query:
            if query.has_filters:
                warnings.warn(
                    'Filters are not allowed by the Api Provider '
                    'in this method')
                query.clear_filters()
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

        response = self.con.get(url, params=params)
        if not response:
            return iter(())

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        items = (
            self._classifier(item)(parent=self, **{self._cloud_data_key: item})
            for item in data.get('value', []))
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=items,
                              constructor=self._classifier,
                              next_link=next_link, limit=limit)
        else:
            return items


class Storage(ApiComponent):
    """ Parent Class that holds drives """

    _endpoints = {
        'default_drive': '/drive',
        'get_drive': '/drives/{id}',
        'list_drives': '/drives',
    }
    drive_constructor = Drive  #: :meta private:

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Create a storage representation

        :param parent: parent for this operation
        :type parent: Account
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)
        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Storage for resource: {}'.format(self.main_resource)

    def get_default_drive(self, request_drive=False):
        """ Returns a Drive instance

        :param request_drive: True will make an api call to retrieve the drive
         data
        :return: default One Drive
        :rtype: Drive
        """
        if request_drive is False:
            return Drive(con=self.con, protocol=self.protocol,
                         main_resource=self.main_resource, name='Default Drive')

        url = self.build_url(self._endpoints.get('default_drive'))

        response = self.con.get(url)
        if not response:
            return None

        drive = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.drive_constructor(con=self.con, protocol=self.protocol,
                                      main_resource=self.main_resource,
                                      **{self._cloud_data_key: drive})

    def get_drive(self, drive_id):
        """ Returns a Drive instance

        :param drive_id: the drive_id to be retrieved
        :return: Drive for the id
        :rtype: Drive
        """
        if not drive_id:
            return None

        url = self.build_url(
            self._endpoints.get('get_drive').format(id=drive_id))

        response = self.con.get(url)
        if not response:
            return None

        drive = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.drive_constructor(con=self.con, protocol=self.protocol,
                                      main_resource=self.main_resource,
                                      **{self._cloud_data_key: drive})

    def get_drives(self):
        """ Returns a collection of drives"""

        url = self.build_url(self._endpoints.get('list_drives'))

        response = self.con.get(url)

        if not response:
            return []

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        drives = [self.drive_constructor(parent=self, **{self._cloud_data_key: drive}) for
                  drive in data.get('value', [])]

        return drives
