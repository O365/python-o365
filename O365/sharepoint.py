import logging
from dateutil.parser import parse

from O365.address_book import Contact
from O365.drive import Storage
from O365.utils import ApiComponent


log = logging.getLogger(__name__)


class SharepointListItem(ApiComponent):
    """ A Sharepoint ListItem within a SharepointList """

    _endpoints = {}

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None

        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id')


class SharepointList(ApiComponent):
    """ A Sharepoint site List """

    _endpoints = {
        'get_items': '/items'
    }
    list_item_constructor = SharepointListItem

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None

        # prefix with the current known list
        resource_prefix = 'lists/{list_id}'.format(list_id=self.object_id)
        main_resource = '{}{}'.format(main_resource, resource_prefix)

        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        self.name = cloud_data.get(self._cc('name'), '')
        self.display_name = cloud_data.get(self._cc('displayName'), '')
        if not self.name:
            self.name = self.display_name
        self.description = cloud_data.get(self._cc('description'), '')
        self.web_url = cloud_data.get(self._cc('webUrl'))

        created = cloud_data.get(self._cc('createdDateTime'), None)
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        self.created = parse(created).astimezone(local_tz) if created else None
        self.modified = parse(modified).astimezone(local_tz) if modified else None

        created_by = cloud_data.get(self._cc('createdBy'), {}).get('user', None)
        self.created_by = Contact(con=self.con, protocol=self.protocol,
                                  **{self._cloud_data_key: created_by}) if created_by else None
        modified_by = cloud_data.get(self._cc('lastModifiedBy'), {}).get('user', None)
        self.modified_by = Contact(con=self.con, protocol=self.protocol,
                                   **{self._cloud_data_key: modified_by}) if modified_by else None

        # list info
        lst_info = cloud_data.get('list', {})
        self.content_types_enabled = lst_info.get(self._cc('contentTypesEnabled'), False)
        self.hidden = lst_info.get(self._cc('hidden'), False)
        self.template = lst_info.get(self._cc('template'), False)

    def get_items(self):
        """ Returns a collection of Sharepoint Items """
        url = self.build_url(self._endpoints.get('get_items'))

        response = self.con.get(url)

        if not response:
            return []

        data = response.json()

        return [self.list_item_constructor(parent=self, **{self._cloud_data_key: item})
                for item in data.get('value', [])]


class Site(ApiComponent):
    """ A Sharepoint Site """

    _endpoints = {
        'get_subsites': '/sites',
        'get_lists': '/lists'
    }
    list_constructor = SharepointList

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None

        # prefix with the current known site
        resource_prefix = 'sites/{site_id}'.format(site_id=self.object_id)
        main_resource = '{}{}'.format(main_resource, resource_prefix)

        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        self.root = 'root' in cloud_data  # True or False
        self.name = cloud_data.get(self._cc('name'), kwargs.get('name', ''))  # Fallback to manual site
        self.display_name = cloud_data.get(self._cc('displayName'), '')
        if not self.name:
            self.name = self.display_name
        self.description = cloud_data.get(self._cc('description'), '')
        self.web_url = cloud_data.get(self._cc('webUrl'))

        created = cloud_data.get(self._cc('createdDateTime'), None)
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        self.created = parse(created).astimezone(local_tz) if created else None
        self.modified = parse(modified).astimezone(local_tz) if modified else None

        # site storage to access Drives and DriveItems
        self.site_storage = Storage(parent=self, main_resource='/sites/{id}'.format(id=self.object_id))

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Site: {}'.format(self.name)

    def get_default_document_library(self, request_drive=False):
        """
        Returns the default document library of this site (a Drive instance)
        :param request_drive: True will make an api call to retrieve the drive data
        """
        return self.site_storage.get_default_drive(request_drive=request_drive)

    def get_document_library(self, drive_id):
        """
        Returns a Document Library (a Drive instance)
        :param drive_id: the drive_id to be retrieved.
        """
        return self.site_storage.get_drive(drive_id=drive_id)

    def list_document_libraries(self, limit=None, *, query=None, order_by=None, batch=None):
        """ Returns a collection of document libraries for this site (a collection of Drive instances) """
        return self.site_storage.get_drives(limit=limit, query=query, order_by=order_by, batch=batch)

    def get_subsites(self):
        """ Returns a list of subsites defined for this site """
        url = self.build_url(self._endpoints.get('get_subsites').format(id=self.object_id))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return [self.__class__(parent=self, **{self._cloud_data_key: site}) for site in data.get('value', [])]

    def get_lists(self):
        """ Returns a collection of lists within this site """
        url = self.build_url(self._endpoints.get('get_lists'))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        return [self.list_constructor(parent=self, **{self._cloud_data_key: lst}) for lst in data.get('value', [])]


class Sharepoint(ApiComponent):
    """ A Sharepoint parent class to group functionality """

    _endpoints = {
        'get_site': '/sites/{id}',
        'search': '/sites?search={keyword}'
    }
    site_constructor = Site

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the host_name
        main_resource = kwargs.pop('main_resource', '')  # defaults to blank resource
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Sharepoint'

    def search_site(self, keyword):
        """
        Search a sharepoint host for sites with the provided keyword
        :param keyword: a keyword to search sites
        """
        if not keyword:
            raise ValueError('Must provide a valid keyword')

        url = self.build_url(self._endpoints.get('search').format(keyword=keyword))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return [self.site_constructor(parent=self, **{self._cloud_data_key: site}) for site in data.get('value', [])]

    def get_root_site(self):
        """ Returns the root site """
        return self.get_site('root')

    def get_site(self, *args):
        """ Returns a sharepoint site
        :param args: It accepts multiple ways of retrieving a site:
            - get_site(host_name): the host_name: host_name ej. 'contoso.sharepoint.com' or 'root'
            - get_site(site_id): the site_id: a comma separated string of (host_name, site_collection_id, site_id)
            - get_site(host_name, path_to_site): host_name ej. 'contoso.sharepoint.com', path_to_site: a url path (with a leading slash)
            - get_site(host_name, site_collection_id, site_id): host_name ej. 'contoso.sharepoint.com'
        """
        num_args = len(args)
        if num_args == 1:
            site = args[0]
        elif num_args == 2:
            host_name, path_to_site = args
            path_to_site = '/' + path_to_site if not path_to_site.startswith('/') else path_to_site
            site = '{}:{}:'.format(host_name, path_to_site)
        elif num_args == 3:
            site = ','.join(args)
        else:
            raise ValueError('Incorrect number of arguments')

        url = self.build_url(self._endpoints.get('get_site').format(id=site))

        response = self.con.get(url)
        if not response:
            return None

        data = response.json()

        return self.site_constructor(parent=self, **{self._cloud_data_key: data})
