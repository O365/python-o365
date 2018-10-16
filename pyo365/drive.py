import logging
import warnings
from dateutil.parser import parse
from urllib.parse import urlparse

from pyo365.address_book import Contact
from pyo365.utils import ApiComponent, Pagination, NEXT_LINK_KEYWORD, OneDriveWellKnowFolderNames

log = logging.getLogger(__name__)


class CopyOperation(ApiComponent):
    """
    https://github.com/OneDrive/onedrive-api-docs/issues/762
    """

    _endpoints = {
        # all prefixed with /drives/{drive_id} on main_resource by default
        'item': '/items/{id}',
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con
        self.parent = parent  # parent will be allways a DriveItem

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        self.monitor_url = kwargs.get('monitor_url', None)
        self.item_id = kwargs.get('item_id', None)
        if self.monitor_url is None and self.item_id is None:
            raise ValueError('Must provide a valid monitor_url or item_id')
        if self.monitor_url is not None and self.item_id is not None:
            raise ValueError('Must provide a valid monitor_url or item_id, but not both')

        if self.item_id:
            self.status = 'completed'
            self.completition_percentage = 100.0
        else:
            self.status = 'inProgress'
            self.completition_percentage = 0.0

    def check_status(self):
        """ Checks the api enpoint to """
        if self.item_id:
            return True

        try:
            response = self.con.get(self.monitor_url)
        except Exception as e:
            log.error('Error retrieving monitor url: {}. Error: {}'.format(self.monitor_url, str(e)))
            return False

        if response.status_code != 202:
            log.debug('Retrieving monitor url Request failed: {}'.format(response.reason))
            return False

        data = response.json()

        self.status = data.get('status', 'inProgress')
        self.completition_percentage = data.get(self._cc('percentageComplete'), 0)
        self.item_id = data.get(self._cc('resourceId'), None)

        if self.item_id:
            return True
        else:
            return False

    def get_item(self):
        """ Returns the item copied. Calls the monitor endpoint if the operation is performed async. """
        if not self.item_id:
            while not self.check_status():
                # wait until check_status returns True
                yield None, self.status, self.completition_percentage
        yield self.parent.get_item(self.item_id), self.status, self.completition_percentage


class DriveItem(ApiComponent):
    """ A DriveItem representation. Groups all funcionality """

    _endpoints = {
        # all prefixed with /drives/{drive_id} on main_resource by default
        'list_items': '/items/{id}/children',
        'thumbnails': '/items/{id}/thumbnails',
        'item': '/items/{id}',
        'copy': '/items/{id}/copy'
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con
        self._parent = parent if isinstance(parent, DriveItem) else None
        self.drive = parent if isinstance(parent, Drive) else (parent.drive if isinstance(parent.drive, Drive) else kwargs.get('drive', None))

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None

        protocol = parent.protocol if parent else kwargs.get('protocol')
        if parent and not isinstance(parent, DriveItem):
            # parent is a Drive so append the drive route to the main_resource
            drive_id = (None if parent.object_id == 'root' else parent.object_id) or None

            # prefix with the current known drive or the default one
            resource_prefix = '/drives/{drive_id}'.format(drive_id=drive_id) if drive_id else '/drive'
            main_resource = '{}{}'.format(main_resource or (protocol.default_resource if protocol else ''), resource_prefix)

        super().__init__(protocol=protocol, main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get(self._cc('id'))
        self.name = cloud_data.get(self._cc('name'), '')
        self.web_url = cloud_data.get(self._cc('webUrl'))
        created_by = cloud_data.get(self._cc('createdBy'), {}).get('user', None)
        self.created_by = Contact(con=self.con, protocol=self.protocol, **{self._cloud_data_key: created_by}) if created_by else None
        modified_by = cloud_data.get(self._cc('lastModifiedBy'), {}).get('user', None)
        self.modified_by = Contact(con=self.con, protocol=self.protocol, **{self._cloud_data_key: modified_by}) if modified_by else None

        created = cloud_data.get(self._cc('createdDateTime'), None)
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        self.created = parse(created).astimezone(local_tz) if created else None
        self.modified = parse(modified).astimezone(local_tz) if modified else None

        self.description = cloud_data.get(self._cc('description'), '')
        self.size = cloud_data.get(self._cc('size'), 0)
        self.shared = cloud_data.get(self._cc('shared'), {}).get('scope', None)

        parent_reference = cloud_data.get(self._cc('parentReference'), {})
        self.parent_id = parent_reference.get('id', None)
        self.drive_id = parent_reference.get(self._cc('driveId'), None)

        remote_item = cloud_data.get(self._cc('remoteItem'), None)
        self.remote_item = self._classifier(remote_item)(parent=self, **{self._cloud_data_key: remote_item}) if remote_item else None

        # Thumbnails
        self.thumbnails = cloud_data.get(self._cc('thumbnails'), [])

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '{}: {}'.format(self.__class__.__name__, self.name)

    @staticmethod
    def _classifier(item):
        """ Subclass to change factory clases """
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
        """ Returns a Drive or Folder: the parent of this DriveItem """
        if self._parent and self._parent.object_id == self.parent_id:
            return self._parent
        else:
            if self.parent_id:
                return self.drive.get_item(self.parent_id)
            else:
                # return the drive
                return self.drive

    def get_thumbnails(self, size=None):
        """
        Returns this Item Thumbnails
        Thumbnails are not supported on SharePoint Server 2016.
        :param size: request only the specified size: ej: "small", Custom 300x400 px: "c300x400", Crop: "c300x400_Crop"
        """
        if not self.object_id:
            return []

        url = self.build_url(self._endpoints.get('thumbnails').format(id=self.object_id))

        params = {}
        if size is not None:
            params['select'] = size

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error requesting thumbnails for item {}. Error: {}'.format(self.object_id, str(e)))
            return []

        if response.status_code != 200:
            log.debug('Getting item thumbnails Request failed: {}'.format(response.reason))
            return []

        data = response.json()

        if not self.thumbnails or size is None:
            self.thumbnails = data

        return data

    def update(self, **kwargs):
        """
        Updates this item
        :param kwargs: all the properties to be updated. only name and description are allowed at the moment.
        """
        if not self.object_id:
            return False

        url = self.build_url(self._endpoints.get('item').format(id=self.object_id))

        data = {self._cc(key): value for key, value in kwargs.items() if key in {'name', 'description'}}  # convert keys to protocol casing
        if not data:
            return False

        try:
            response = self.con.patch(url, data=data)
        except Exception as e:
            log.error('Error updating driveitem {}. Error: {}'.format(self.name, str(e)))
            return False

        if response.status_code != 200:
            log.debug('Updating driveitem Request failed: {}'.format(response.reason))
            return False

        new_data = response.json()

        for key in data:
            value = new_data.get(key, None)
            if value:
                setattr(self, self.protocol.to_api_case(key), value)

        return True

    def delete(self):
        """ Moves this item to the Recycle Bin """

        if not self.object_id:
            return False

        url = self.build_url(self._endpoints.get('item').format(id=self.object_id))

        try:
            response = self.con.delete(url)
        except Exception as e:
            log.error('Error deleting driveitem {}. Error: {}'.format(self.name, str(e)))
            return False

        if response.status_code != 204:
            log.debug('Deleting driveitem Request failed: {}'.format(response.reason))
            return False

        self.object_id = None

        return True

    def move(self, target):
        """
        Moves this DriveItem to another Folder. Can't move between different Drives.
        :param target: a Folder, Drive item or Item Id string. If it's a drive the item will be moved to the root folder.
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
            raise ValueError('Both self, and target must have a valid object_id.')

        if target_id == 'root':
            raise ValueError("When moving, target id can't be 'root'")

        url = self.build_url(self._endpoints.get('item').format(id=self.object_id))

        data = {'parentReference': {'id': target_id}}

        try:
            response = self.con.patch(url, data=data)
        except Exception as e:
            log.error('Error moving driveitem {}. Error: {}'.format(self.name, str(e)))
            return False

        if response.status_code != 200:
            log.debug('Moving driveitem Request failed: {}'.format(response.reason))
            return False

        self.parent_id = target_id

        return True

    def copy(self, target=None, name=None):
        """
        Asynchronously creates a copy of this DriveItem and all it's child elements.
        :param target: a Folder or Drive item. If it's a drive the item will be moved to the root folder.
        :param name: a new name for the copy.
        """
        assert target or name, 'Must provide a target or a name (or both)'

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

        url = self.build_url(self._endpoints.get('copy').format(id=self.object_id))

        if target_id and drive_id:
            data = {'parentReference': {'id': target_id, 'driveId': drive_id}}
        else:
            data = {}
        if name:
            data['name'] = name

        try:
            response = self.con.post(url, data=data)
        except Exception as e:
            log.error('Error copying driveitem {}. Error: {}'.format(self.name, str(e)))
            return None

        if response.status_code != 202:
            log.debug('Copying driveitem Request failed: {}'.format(response.reason))
            return None

        # Find out if the server has run a Sync or Async operation
        location = response.headers.get('Location', None)
        print(location)
        if 'monitor' in location:
            # Async operation
            return CopyOperation(parent=self.drive, monitor_url=location)
        else:
            # Sync operation. Item is ready to be retrieved
            path = urlparse(location).path
            item_id = path.split('/')[-1]
            return CopyOperation(parent=self.drive, item_id=item_id)


class File(DriveItem):
    """ A File """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.mime_type = cloud_data.get(self._cc('file'), {}).get(self._cc('mimeType'), None)


class Image(File):
    """ An Image """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        image = cloud_data.get(self._cc('image'), {})
        self.height = image.get(self._cc('height'), 0)
        self.width = image.get(self._cc('width'), 0)

    @property
    def dimenstions(self):
        return '{}x{}'.format(self.width, self.height)


class Photo(Image):
    """ Photo Object. Inherits from Image but has more attributes """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        photo = cloud_data.get(self._cc('photo'), {})

        taken = photo.get(self._cc('takenDateTime'), None)
        local_tz = self.protocol.timezone
        self.taken_datetime = parse(taken).astimezone(local_tz) if taken else None
        self.camera_make = photo.get(self._cc('cameraMake'), None)
        self.camera_model = photo.get(self._cc('cameraModel'), None)
        self.exposure_denominator = photo.get(self._cc('exposureDenominator'), None)
        self.exposure_numerator = photo.get(self._cc('exposureNumerator'), None)
        self.fnumber = photo.get(self._cc('fNumber'), None)
        self.focal_length = photo.get(self._cc('focalLength'), None)
        self.iso = photo.get(self._cc('iso'), None)


class Folder(DriveItem):
    """ A Folder inside a Drive """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.child_count = cloud_data.get(self._cc('folder'), {}).get(self._cc('childCount'), 0)
        self.special_folder = cloud_data.get(self._cc('specialFolder'), {}).get('name', None)

    def get_items(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns all the items inside this folder """

        url = self.build_url(self._endpoints.get('list_items').format(id=self.object_id))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params = {'$top': batch if batch else limit}

        if order_by:
            params['$orderby'] = order_by

        if query:
            if query.has_filters:
                warnings.warn('Filters are not allowed by the Api Provider in this method')
                query.clear_filters()
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

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
        items = [self._classifier(item)(parent=self, **{self._cloud_data_key: item}) for item in data.get('value', [])]
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=items, constructor=self._classifier,
                              next_link=next_link, limit=limit)
        else:
            return items

    def create_child_folder(self, name, description=None):
        """
        Creates a Child Folder
        :param name: the name of the new child folder
        :param description: the description of the new child folder
        """

        if not self.object_id:
            return None

        url = self.build_url(self._endpoints.get('list_items').format(id=self.object_id))

        data = {'name': name}
        if description:
            data['description'] = description

        try:
            response = self.con.post(url, data=data)
        except Exception as e:
            log.error('Error creating folder {}. Error: {}'.format(self.name, str(e)))
            return None

        if response.status_code != 201:
            log.debug('Creating folder Request failed: {}'.format(response.reason))
            return None

        folder = response.json()

        return self._classifier(folder)(parent=self, **{self._cloud_data_key: folder})


class Drive(ApiComponent):
    """ A Drive representation. A Drive is a Container of Folders and Files and act as a root item """

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
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con
        self.parent = parent if isinstance(parent, Drive) else None

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        self._update_data(kwargs)

    def _update_data(self, data):
        cloud_data = data.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get(self._cc('id'))
        self.name = cloud_data.get(self._cc('name'), data.get('name', ''))  # Fallback to manual drive
        self.description = cloud_data.get(self._cc('description'))
        self.drive_type = cloud_data.get(self._cc('driveType'))
        self.web_url = cloud_data.get(self._cc('webUrl'))

        owner = cloud_data.get(self._cc('owner'), {}).get('user', None)
        self.owner = Contact(con=self.con, protocol=self.protocol, **{self._cloud_data_key: owner}) if owner else None
        self.quota = cloud_data.get(self._cc('quota'))  # dict

        created = cloud_data.get(self._cc('createdDateTime'), None)
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        self.created = parse(created).astimezone(local_tz) if created else None
        self.modified = parse(modified).astimezone(local_tz) if modified else None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Drive: {}'.format(self.name or self.object_id)

    def get_root_folder(self):
        """ Returns the Root Folder of this drive """
        if self.object_id:
            # reference the current drive_id
            url = self.build_url(self._endpoints.get('get_root_item').format(id=self.object_id))
        else:
            # we don't know the drive_id so go to the default drive
            url = self.build_url(self._endpoints.get('get_root_item_default'))

        try:
            response = self.con.get(url)
        except Exception as e:
            log.error('Error requesting root folder for drive: {}. Error: {}'.format(self.object_id, str(e)))
            return []

        if response.status_code != 200:
            log.debug('Getting root folder Request failed: {}'.format(response.reason))
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self._classifier(data)(parent=self, **{self._cloud_data_key: data})

    def _base_get_list(self, url, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of drive items """

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params = {'$top': batch if batch else limit}

        if order_by:
            params['$orderby'] = order_by

        if query:
            if query.has_filters:
                warnings.warn('Filters are not allowed by the Api Provider in this method')
                query.clear_filters()
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error requesting child items of {}. Error: {}'.format(self.name, str(e)))
            return []

        if response.status_code != 200:
            log.debug('Getting child items Request failed: {}'.format(response.reason))
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        items = [self._classifier(item)(parent=self, **{self._cloud_data_key: item}) for item in data.get('value', [])]
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=items, constructor=self._classifier,
                              next_link=next_link, limit=limit)
        else:
            return items

    def get_items(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of drive items from the root folder """

        if self.object_id:
            # reference the current drive_id
            url = self.build_url(self._endpoints.get('list_items').format(id=self.object_id))
        else:
            # we don't know the drive_id so go to the default
            url = self.build_url(self._endpoints.get('list_items_default'))

        return self._base_get_list(url, limit=limit, query=query, order_by=order_by, batch=batch)

    def get_recent(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of recently used DriveItems """
        if self.object_id:
            # reference the current drive_id
            url = self.build_url(self._endpoints.get('recent').format(id=self.object_id))
        else:
            # we don't know the drive_id so go to the default
            url = self.build_url(self._endpoints.get('recent_default'))

        return self._base_get_list(url, limit=limit, query=query, order_by=order_by, batch=batch)

    def get_shared_with_me(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of DriveItems shared with me """

        if self.object_id:
            # reference the current drive_id
            url = self.build_url(self._endpoints.get('shared_with_me').format(id=self.object_id))
        else:
            # we don't know the drive_id so go to the default
            url = self.build_url(self._endpoints.get('shared_with_me_default'))

        return self._base_get_list(url, limit=limit, query=query, order_by=order_by, batch=batch)

    def get_item(self, item_id):
        """ Returns a DriveItem by it's Id"""
        if self.object_id:
            # reference the current drive_id
            url = self.build_url(self._endpoints.get('get_item').format(id=self.object_id, item_id=item_id))
        else:
            # we don't know the drive_id so go to the default drive
            url = self.build_url(self._endpoints.get('get_item_default').format(item_id=item_id))

        try:
            response = self.con.get(url)
        except Exception as e:
            log.error('Error requesting item {}. Error: {}'.format(item_id, str(e)))
            return None

        if response.status_code != 200:
            log.debug('Getting item Request failed: {}'.format(response.reason))
            return None

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self._classifier(data)(parent=self, **{self._cloud_data_key: data})

    def get_special_folder(self, name):
        """ Returns the specified Special Folder """

        name = name if isinstance(name, OneDriveWellKnowFolderNames) else OneDriveWellKnowFolderNames(name)

        if self.object_id:
            # reference the current drive_id
            url = self.build_url(self._endpoints.get('get_special').format(id=self.object_id))
        else:
            # we don't know the drive_id so go to the default
            url = self.build_url(self._endpoints.get('get_special_default'))

        try:
            response = self.con.get(url)
        except Exception as e:
            log.error('Error requesting special folder {}. Error: {}'.format(name, str(e)))
            return None

        if response.status_code != 200:
            log.debug('Getting special folder Request failed: {}'.format(response.reason))
            return None

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self._classifier(data)(parent=self, **{self._cloud_data_key: data})

    @staticmethod
    def _classifier(item):
        """ Subclass to change factory clases """
        if 'folder' in item:
            return Folder
        elif 'image' in item:
            return Image
        elif 'photo' in item:
            return Photo
        else:
            return File

    def refresh(self):
        """ Updates this drive with data from the server """

        if self.object_id is None:
            url = self.build_url(self._endpoints.get('default_drive'))
        else:
            url = self.build_url(self._endpoints.get('get_drive').format(id=self.object_id))

        try:
            response = self.con.get(url)
        except Exception as e:
            log.error('Error getting drive {}. Error: {}'.format('default_drive', str(e)))
            return False

        if response.status_code != 200:
            log.debug('Getting drive Request failed: {}'.format(response.reason))
            return False

        drive = response.json()

        self._update_data({self._cloud_data_key: drive})
        return True


class Storage(ApiComponent):
    """ Parent Class that holds drives """

    _endpoints = {
        'default_drive': '/drive',
        'get_drive': '/drives/{id}',
        'list_drives': '/drives',
    }
    drive_constructor = Drive

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.name = cloud_data.get(self._cc('name'), kwargs.get('name', ''))  # Fallback to manual drive

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Storage: {}'.format(self.name)

    def get_default_drive(self, request_drive=False):
        """
        Returns a Drive instance
        :param request_drive: True will make an api call to retrieve the drive data
        """
        if request_drive is False:
            return Drive(con=self.con, protocol=self.protocol, main_resource=self.main_resource, name=self.name)

        url = self.build_url(self._endpoints.get('default_drive'))

        try:
            response = self.con.get(url)
        except Exception as e:
            log.error('Error getting drive {}. Error: {}'.format('default_drive', str(e)))
            return None

        if response.status_code != 200:
            log.debug('Getting drive Request failed: {}'.format(response.reason))
            return None

        drive = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self.drive_constructor(con=self.con, protocol=self.protocol,
                                      main_resource=self.main_resource, **{self._cloud_data_key: drive})

    def get_drive(self, drive_id):
        """
        Returns a Drive instance
        :param drive_id: the drive_id to be retrieved.
        """
        if not drive_id:
            return None

        url = self.build_url(self._endpoints.get('get_drive').format(id=drive_id))

        try:
            response = self.con.get(url)
        except Exception as e:
            log.error('Error getting drive {}. Error: {}'.format(drive_id, str(e)))
            return None

        if response.status_code != 200:
            log.debug('Getting drive Request failed: {}'.format(response.reason))
            return None

        drive = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self.drive_constructor(con=self.con, protocol=self.protocol,
                                      main_resource=self.main_resource, **{self._cloud_data_key: drive})

    def get_drives(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of drives """

        url = self.build_url(self._endpoints.get('list_drives'))

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

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error requesting drives. Error: {}'.format(str(e)))
            return []

        if response.status_code != 200:
            log.debug('Getting drives Request failed: {}'.format(response.reason))
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        drives = [self.drive_constructor(parent=self, **{self._cloud_data_key: drive}) for drive in data.get('value', [])]
        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if batch and next_link:
            return Pagination(parent=self, data=drives, constructor=self.drive_constructor,
                              next_link=next_link, limit=limit)
        else:
            return drives
