import logging
import warnings
from pathlib import Path
from time import sleep
from urllib.parse import urlparse

from dateutil.parser import parse

from .address_book import Contact
from .utils import ApiComponent, Pagination, NEXT_LINK_KEYWORD, \
    OneDriveWellKnowFolderNames

log = logging.getLogger(__name__)

SIZE_THERSHOLD = 1024 * 1024 * 2  # 2 MB
UPLOAD_SIZE_LIMIT_SIMPLE = 1024 * 1024 * 4  # 4 MB
UPLOAD_SIZE_LIMIT_SESSION = 1024 * 1024 * 60  # 60 MB
CHUNK_SIZE_BASE = 1024 * 320  # 320 Kb

# 5 MB --> Must be a multiple of CHUNK_SIZE_BASE
DEFAULT_UPLOAD_CHUNK_SIZE = 1024 * 1024 * 5
ALLOWED_PDF_EXTENSIONS = {'.csv', '.doc', '.docx', '.odp', '.ods', '.odt',
                          '.pot', '.potm', '.potx',
                          '.pps', '.ppsx', '.ppsxm', '.ppt', '.pptm', '.pptx',
                          '.rtf', '.xls', '.xlsx'}


class DownloadableMixin:

    def download(self, to_path=None, name=None, chunk_size='auto',
                 convert_to_pdf=False):
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
        :return: Success / Failure
        :rtype: bool
        """
        # TODO: Add download with more than one request (chunk_requests) with
        # header 'Range'. For example: 'Range': 'bytes=0-1024'

        if to_path is None:
            to_path = Path()
        else:
            if not isinstance(to_path, Path):
                to_path = Path(to_path)

        if not to_path.exists():
            raise FileNotFoundError('{} does not exist'.format(to_path))

        if name and not Path(name).suffix and self.name:
            name = name + Path(self.name).suffix

        name = name or self.name
        to_path = to_path / name

        url = self.build_url(
            self._endpoints.get('download').format(id=self.object_id))

        try:
            if chunk_size is None:
                stream = False
            elif chunk_size == 'auto':
                if self.size and self.size > SIZE_THERSHOLD:
                    stream = True
                else:
                    stream = False
            elif isinstance(chunk_size, int):
                stream = True
            else:
                raise ValueError("Argument chunk_size must be either 'auto' "
                                 "or any integer number representing bytes")

            params = {}
            if convert_to_pdf and Path(name).suffix in ALLOWED_PDF_EXTENSIONS:
                params['format'] = 'pdf'

            with self.con.get(url, stream=stream, params=params) as response:
                if not response:
                    log.debug('Downloading driveitem Request failed: {}'.format(
                        response.reason))
                    return False
                with to_path.open(mode='wb') as output:
                    if stream:
                        for chunk in response.iter_content(
                                chunk_size=chunk_size):
                            if chunk:
                                output.write(chunk)
                    else:
                        output.write(response.content)
        except Exception as e:
            log.error(
                'Error downloading driveitem {}. Error: {}'.format(self.name,
                                                                   str(e)))
            return False

        return True


class CopyOperation(ApiComponent):
    """ https://github.com/OneDrive/onedrive-api-docs/issues/762 """

    _endpoints = {
        # all prefixed with /drives/{drive_id} on main_resource by default
        'item': '/items/{id}',
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """

        :param parent: parent for this operation
        :type parent: Drive
        :param Connection con: connection to use if no parent specified
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
        self.parent = parent  # parent will be always a DriveItem

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.monitor_url = kwargs.get('monitor_url', None)
        self.item_id = kwargs.get('item_id', None)
        if self.monitor_url is None and self.item_id is None:
            raise ValueError('Must provide a valid monitor_url or item_id')
        if self.monitor_url is not None and self.item_id is not None:
            raise ValueError(
                'Must provide a valid monitor_url or item_id, but not both')

        if self.item_id:
            self.status = 'completed'
            self.completion_percentage = 100.0
        else:
            self.status = 'inProgress'
            self.completion_percentage = 0.0

    def _request_status(self):
        """ Checks the api endpoint to check if the async job progress """
        if self.item_id:
            return True

        response = self.con.get(self.monitor_url)
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
        return self.parent.get_item(
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

        self.driveitem_id = self._parent.object_id
        self.object_id = cloud_data.get('id', '1.0')
        self.name = self.object_id
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        self.modified = parse(modified).astimezone(
            local_tz) if modified else None
        self.size = cloud_data.get('size', 0)
        modified_by = cloud_data.get(self._cc('lastModifiedBy'), {}).get('user',
                                                                         None)
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

    def download(self, to_path=None, name=None, chunk_size='auto',
                 convert_to_pdf=False):
        """ Downloads this version.
        You can not download the current version (last one).

        :return: Success / Failure
        :rtype: bool
        """
        return super().download(to_path=to_path, name=name,
                                chunk_size=chunk_size,
                                convert_to_pdf=convert_to_pdf)


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

        self.driveitem_id = self._parent.object_id
        cloud_data = kwargs.get(self._cloud_data_key, {})
        self.object_id = cloud_data.get(self._cc('id'))
        self.inherited_from = cloud_data.get(self._cc('inheritedFrom'), None)

        link = cloud_data.get(self._cc('link'), None)
        self.permission_type = 'owner'
        if link:
            self.permission_type = 'link'
            self.share_type = link.get('type', 'view')
            self.share_scope = link.get('scope', 'anonymous')
            self.share_link = link.get('webUrl', None)

        invitation = cloud_data.get(self._cc('invitation'), None)
        if invitation:
            self.permission_type = 'invitation'
            self.share_email = invitation.get('email', '')
            invited_by = invitation.get('invitedBy', {})
            self.invited_by = invited_by.get('user', {}).get(
                self._cc('displayName'), None) or invited_by.get('application',
                                                                 {}).get(
                self._cc('displayName'), None)
            self.require_sign_in = invitation.get(self._cc('signInRequired'),
                                                  True)

        self.roles = cloud_data.get(self._cc('roles'), [])
        granted_to = cloud_data.get(self._cc('grantedTo'), {})
        self.granted_to = granted_to.get('user', {}).get(
            self._cc('displayName')) or granted_to.get('application', {}).get(
            self._cc('displayName'))
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
        elif roles == {'edit', 'write'}:
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
        self.drive = parent if isinstance(parent, Drive) else (
            parent.drive if isinstance(parent.drive, Drive) else kwargs.get(
                'drive', None))

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

        self.object_id = cloud_data.get(self._cc('id'))
        self.name = cloud_data.get(self._cc('name'), '')
        self.web_url = cloud_data.get(self._cc('webUrl'))
        created_by = cloud_data.get(self._cc('createdBy'), {}).get('user', None)
        self.created_by = Contact(con=self.con, protocol=self.protocol, **{
            self._cloud_data_key: created_by}) if created_by else None
        modified_by = cloud_data.get(self._cc('lastModifiedBy'), {}).get('user',
                                                                         None)
        self.modified_by = Contact(con=self.con, protocol=self.protocol, **{
            self._cloud_data_key: modified_by}) if modified_by else None

        created = cloud_data.get(self._cc('createdDateTime'), None)
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        self.created = parse(created).astimezone(local_tz) if created else None
        self.modified = parse(modified).astimezone(
            local_tz) if modified else None

        self.description = cloud_data.get(self._cc('description'), '')
        self.size = cloud_data.get(self._cc('size'), 0)
        self.shared = cloud_data.get(self._cc('shared'), {}).get('scope', None)

        parent_reference = cloud_data.get(self._cc('parentReference'), {})
        self.parent_id = parent_reference.get('id', None)
        self.drive_id = parent_reference.get(self._cc('driveId'), None)

        remote_item = cloud_data.get(self._cc('remoteItem'), None)
        self.remote_item = self._classifier(remote_item)(parent=self, **{
            self._cloud_data_key: remote_item}) if remote_item else None

        # Thumbnails
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
        """ Asynchronously creates a copy of this DriveItem and all it's
        child elements.

        :param target: target location to move to.
         If it's a drive the item will be moved to the root folder.
        :type target: drive.Folder or Drive
        :param name: a new name for the copy.
        :rtype: CopyOperation
        """
        if target is None and name is None:
            raise ValueError('Must provide a target or a name (or both)')

        if isinstance(target, Folder):
            target_id = target.object_id
            drive_id = target.drive_id
        elif isinstance(target, Drive):
            # we need the root folder
            root_folder = target.get_root_folder()
            if not root_folder:
                return None
            target_id = root_folder.object_id
            drive_id = root_folder.drive_id
        elif target is None:
            target_id = None
            drive_id = None
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

        if 'monitor' in location:
            # Async operation
            return CopyOperation(parent=self.drive, monitor_url=location)
        else:
            # Sync operation. Item is ready to be retrieved
            path = urlparse(location).path
            item_id = path.split('/')[-1]
            return CopyOperation(parent=self.drive, item_id=item_id)

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

    def share_with_link(self, share_type='view', share_scope='anonymous'):
        """ Creates or returns a link you can share with others

        :param str share_type: 'view' to allow only view access,
         'edit' to allow editions, and
         'embed' to allow the DriveItem to be embedded
        :param str share_scope: 'anonymous': anyone with the link can access.
         'organization' Only organization members can access
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
        elif share_type == {'edit', 'write'}:
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

        self.mime_type = cloud_data.get(self._cc('file'), {}).get(
            self._cc('mimeType'), None)

    @property
    def extension(self):
        return Path(self.name).suffix


class Image(File):
    """ An Image """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        image = cloud_data.get(self._cc('image'), {})
        self.height = image.get(self._cc('height'), 0)
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
        self.taken_datetime = parse(taken).astimezone(
            local_tz) if taken else None
        self.camera_make = photo.get(self._cc('cameraMake'), None)
        self.camera_model = photo.get(self._cc('cameraModel'), None)
        self.exposure_denominator = photo.get(self._cc('exposureDenominator'),
                                              None)
        self.exposure_numerator = photo.get(self._cc('exposureNumerator'), None)
        self.fnumber = photo.get(self._cc('fNumber'), None)
        self.focal_length = photo.get(self._cc('focalLength'), None)
        self.iso = photo.get(self._cc('iso'), None)


class Folder(DriveItem):
    """ A Folder inside a Drive """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.child_count = cloud_data.get(self._cc('folder'), {}).get(
            self._cc('childCount'), 0)
        self.special_folder = cloud_data.get(self._cc('specialFolder'), {}).get(
            'name', None)

    def get_items(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns all the items inside this folder

        :param int limit: max no. of folders to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: list of items in this folder
        :rtype: list[DriveItem] or Pagination
        """

        url = self.build_url(
            self._endpoints.get('list_items').format(id=self.object_id))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params = {'$top': batch if batch else limit}

        if order_by:
            params['$orderby'] = order_by

        if query:
            if query.has_filters:
                warnings.warn('Filters are not allowed by the '
                              'Api Provider in this method')
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
        to_folder = to_folder or Path()
        if not to_folder.exists():
            to_folder.mkdir()

        for item in self.get_items(query=self.new_query().select('id', 'size')):
            if item.is_folder and item.child_count > 0:
                item.download_contents(to_folder=to_folder / item.name)
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
        :return: list of items in this folder
        :rtype: list[DriveItem] or Pagination
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
            if query.has_filters:
                warnings.warn(
                    'Filters are not allowed by the Api '
                    'Provider in this method')
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

    def upload_file(self, item, chunk_size=DEFAULT_UPLOAD_CHUNK_SIZE):
        """ Uploads a file

        :param item: path to the item you want to upload
        :type item: str or Path
        :param chunk_size: Only applies if file is bigger than 4MB.
         Chunk size for uploads. Must be a multiple of 327.680 bytes
        :return: uploaded file
        :rtype: DriveItem
        """

        if item is None:
            raise ValueError('Item must be a valid path to file')
        item = Path(item) if not isinstance(item, Path) else item

        if not item.exists():
            raise ValueError('Item must exist')
        if not item.is_file():
            raise ValueError('Item must be a file')

        file_size = item.stat().st_size

        if file_size <= UPLOAD_SIZE_LIMIT_SIMPLE:
            # Simple Upload
            url = self.build_url(
                self._endpoints.get('simple_upload').format(id=self.object_id,
                                                            filename=item.name))
            # headers = {'Content-type': 'text/plain'}
            headers = {'Content-type': 'application/octet-stream'}
            # headers = None
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
                    id=self.object_id, filename=item.name))

            response = self.con.post(url)
            if not response:
                return None

            data = response.json()

            upload_url = data.get(self._cc('uploadUrl'), None)
            if upload_url is None:
                log.error('Create upload session response without '
                          'upload_url for file {}'.format(item.name))
                return None

            current_bytes = 0
            with item.open(mode='rb') as file:
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
        self.parent = parent if isinstance(parent, Drive) else None

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)
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
        return 'Drive: {}'.format(
            self.name or self.object_id or 'Default Drive')

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
                       batch=None):
        """ Returns a collection of drive items """

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

    def get_items(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of drive items from the root folder

        :param int limit: max no. of items to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: list of items in this folder
        :rtype: list[DriveItem] or Pagination
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

    def get_recent(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of recently used DriveItems

        :param int limit: max no. of items to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: list of items in this folder
        :rtype: list[DriveItem] or Pagination
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

    def get_shared_with_me(self, limit=None, *, query=None, order_by=None,
                           batch=None):
        """ Returns a collection of DriveItems shared with me

        :param int limit: max no. of items to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: list of items in this folder
        :rtype: list[DriveItem] or Pagination
        """

        if self.object_id:
            # reference the current drive_id
            url = self.build_url(
                self._endpoints.get('shared_with_me').format(id=self.object_id))
        else:
            # we don't know the drive_id so go to the default
            url = self.build_url(self._endpoints.get('shared_with_me_default'))

        return self._base_get_list(url, limit=limit, query=query,
                                   order_by=order_by, batch=batch)

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
        :return: list of items in this folder
        :rtype: list[DriveItem] or Pagination
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
    drive_constructor = Drive

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
        return [self.drive_constructor(parent=self, **{self._cloud_data_key: drive})
                for drive in data.get('value', [])]
