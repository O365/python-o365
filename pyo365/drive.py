import logging
import warnings
from dateutil.parser import parse

from pyo365.address_book import Contact
from pyo365.utils import ApiComponent, Pagination, NEXT_LINK_KEYWORD

log = logging.getLogger(__name__)


class Drive(ApiComponent):
    """ A Drive representation. A Drive is a Container of Folders and Files and act as a root item """

    _endpoints = {
        'list_items': '/drive/root/children',
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con
        self.parent = parent if isinstance(parent, Drive) else None

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get(self._cc('id'))
        self.name = cloud_data.get(self._cc('name'), kwargs.get('name', ''))  # Fallback to manual drive
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

    def get_items(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of drive items """

        url = self.build_url(self._endpoints.get('list_items'))

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

        return data.get('value', [])

        # Everything received from the cloud must be passed with self._cloud_data_key
        # items = [DriveItem(parent=self, **{self._cloud_data_key: item}) for item in data.get('value', [])]
        # if batch:
        #     return Pagination(parent=self, data=items, constructor=self.__class__,
        #                       next_link=data.get(NEXT_LINK_KEYWORD, None), limit=limit)
        # else:
        #     return items


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

    def get_drive(self, drive_id=None, request_drive=False):
        """
        Returns a Drive instance
        :param drive_id: the drive_id to be retrieved.
        :param request_drive: when drive_id is not provided, True will make an api call to retrieve the drive data
        """
        if drive_id is None:
            if request_drive is False:
                return Drive(con=self.con, protocol=self.protocol, main_resource=self.main_resource, name=self.name)
            url = self.build_url(self._endpoints.get('default_drive'))
        else:
            url = self.build_url(self._endpoints.get('get_drive').format(id=drive_id))

        try:
            response = self.con.get(url)
        except Exception as e:
            log.error('Error getting drive {}. Error: {}'.format(drive_id or 'default_drive', str(e)))
            return None

        if response.status_code != 200:
            log.debug('Getting drive Request failed: {}'.format(response.reason))
            return None

        drive = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return Drive(con=self.con, protocol=self.protocol, main_resource=self.main_resource, **{self._cloud_data_key: drive})

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
        if batch:
            return Pagination(parent=self, data=drives, constructor=self.drive_constructor,
                              next_link=data.get(NEXT_LINK_KEYWORD, None), limit=limit)
        else:
            return drives


class DriveItem(ApiComponent):
    """ A DriveItem representation. Groups all funcionality """

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con
        self.parent = parent if isinstance(parent, DriveItem) else None

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

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


class Folder(DriveItem):
    pass


class File(DriveItem):
    pass


class Image(File):
    pass


class Photo(Image):
    pass


class OneDrive(Drive):

    # implement special drive folders access

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, name='OneDrive', **kwargs)


class DocumentLibrary(Storage):
    # returns a sharepoint document library
    pass
