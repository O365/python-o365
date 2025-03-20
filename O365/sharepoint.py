import logging

from dateutil.parser import parse

from .address_book import Contact
from .drive import Storage
from .utils import NEXT_LINK_KEYWORD, ApiComponent, Pagination, TrackerSet

log = logging.getLogger(__name__)


class SharepointListColumn(ApiComponent):
    """ A Sharepoint List column within a SharepointList """

    _endpoints = {}

    def __init__(self, *, parent=None, con=None, **kwargs):
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: The unique identifier for the column. |br| **Type:** str
        self.object_id = cloud_data.get('id')
        #:For site columns, the name of the group this column belongs to. |br| **Type:** str
        self.column_group = cloud_data.get(self._cc('columnGroup'), None)
        #: The user-facing description of the column. |br| **Type:** str
        self.description = cloud_data.get(self._cc('description'), None)
        #: he user-facing name of the column. |br| **Type:** str
        self.display_name = cloud_data.get(self._cc('displayName'), None)
        #: If true, no two list items may have the same value for this column. |br| **Type:** bool
        self.enforce_unique_values = cloud_data.get(self._cc('enforceUniqueValues'), None)
        #: Specifies whether the column is displayed in the user interface. |br| **Type:** bool
        self.hidden = cloud_data.get(self._cc('hidden'), None)
        #: Specifies whether the column values can be used for sorting and searching.
        #: |br| **Type:** bool
        self.indexed = cloud_data.get(self._cc('indexed'), None)
        #: The API-facing name of the column as it appears in the fields on a listItem.
        #: |br| **Type:** str
        self.internal_name = cloud_data.get(self._cc('name'), None)
        #: Specifies whether the column values can be modified. |br| **Type:** bool
        self.read_only = cloud_data.get(self._cc('readOnly'), None)
        #: Specifies whether the column value isn't optional. |br| **Type:** bool
        self.required = cloud_data.get(self._cc('required'), None)

        # identify the sharepoint column type and set it
        # Graph api doesn't return the type for managed metadata and link column
        if cloud_data.get(self._cc('text'), None) is not None:
            #: Field type of the column. |br| **Type:** str
            self.field_type = 'text'
        elif cloud_data.get(self._cc('choice'), None) is not None:
            self.field_type = 'choice'
        elif cloud_data.get(self._cc('number'), None) is not None:
            self.field_type = 'number'
        elif cloud_data.get(self._cc('currency'), None) is not None:
            self.field_type = 'currency'
        elif cloud_data.get(self._cc('dateTime'), None) is not None:
            self.field_type = 'dateTime'
        elif cloud_data.get(self._cc('lookup'), None) is not None:
            self.field_type = 'lookup'
        elif cloud_data.get(self._cc('boolean'), None) is not None:
            self.field_type = 'boolean'
        elif cloud_data.get(self._cc('calculated'), None) is not None:
            self.field_type = 'calculated'
        elif cloud_data.get(self._cc('personOrGroup'), None) is not None:
            self.field_type = 'personOrGroup'
        else:
            self.field_type = None

    def __repr__(self):
        return 'List Column: {0}-{1}'.format(self.display_name, self.field_type)

    def __eq__(self, other):
        return self.object_id == other.object_id


class SharepointListItem(ApiComponent):
    _endpoints = {'update_list_item': '/items/{item_id}/fields',
                  'delete_list_item': '/items/{item_id}'}

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Sharepoint ListItem within a SharepointList

        :param parent: parent object
        :type parent: SharepointList
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con
        self._parent = parent

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self._track_changes = TrackerSet(casing=self._cc)
        #: The unique identifier of the item. |br| **Type:** str
        self.object_id = cloud_data.get('id')
        created = cloud_data.get(self._cc('createdDateTime'), None)
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        #: The date and time the item was created. |br| **Type:** datetime
        self.created = parse(created).astimezone(local_tz) if created else None
        #: The date and time the item was last modified. |br| **Type:** datetime
        self.modified = parse(modified).astimezone(local_tz) if modified else None

        created_by = cloud_data.get(self._cc('createdBy'), {}).get('user', None)
        #: Identity of the creator of this item. |br| **Type:** contact
        self.created_by = Contact(con=self.con, protocol=self.protocol,
                                  **{self._cloud_data_key: created_by}) if created_by else None
        modified_by = cloud_data.get(self._cc('lastModifiedBy'), {}).get('user', None)
        #: Identity of the last modifier of this item. |br| **Type:** Contact
        self.modified_by = Contact(con=self.con, protocol=self.protocol,
                                   **{self._cloud_data_key: modified_by}) if modified_by else None

        #: URL that displays the item in the browser. |br| **Type:** str
        self.web_url = cloud_data.get(self._cc('webUrl'), None)

        #: The ID of the content type. |br| **Type:** str
        self.content_type_id = cloud_data.get(self._cc('contentType'), {}).get('id', None)

        #: The fields of the item. |br| **Type:** any
        self.fields = cloud_data.get(self._cc('fields'), None)

    def __repr__(self):
        return 'List Item: {}'.format(self.web_url)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def _clear_tracker(self):
        self._track_changes = TrackerSet(casing=self._cc)

    def _valid_field(self, field):
        # Verify the used field names are valid internal field names
        valid_field_names = self.fields if self.fields \
            else self._parent.column_name_cw.values() \
            if self._parent \
            else None
        if valid_field_names:
            return field in valid_field_names

        # If no parent is given, and no internal fields are defined assume correct, API will check
        return True

    def update_fields(self, updates):
        """
        Update the value for a field(s) in the listitem

        :param update: A dict of {'field name': newvalue}
        """

        for field in updates:
            if self._valid_field(field):
                self._track_changes.add(field)
            else:
                raise ValueError('"{}" is not a valid internal field name'.format(field))

        # Update existing instance of fields, or create a fields instance if needed
        if self.fields:
            self.fields.update(updates)
        else:
            self.fields = updates

    def save_updates(self):
        """Save the updated fields to the cloud"""

        if not self._track_changes:
            return True  # there's nothing to update

        url = self.build_url(self._endpoints.get('update_list_item').format(item_id=self.object_id))
        update = {field: value for field, value in self.fields.items()
                  if self._cc(field) in self._track_changes}

        response = self.con.patch(url, update)
        if not response:
            return False
        self._clear_tracker()
        return True

    def delete(self):
        url = self.build_url(self._endpoints.get('delete_list_item').format(item_id=self.object_id))
        response = self.con.delete(url)
        return bool(response)


class SharepointList(ApiComponent):
    _endpoints = {
        'get_items': '/items',
        'get_item_by_id': '/items/{item_id}',
        'get_list_columns': '/columns'
    }
    list_item_constructor = SharepointListItem  #: :meta private:
    list_column_constructor = SharepointListColumn  #: :meta private:

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Sharepoint site List

        :param parent: parent object
        :type parent: Site
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: The ID of the content type. |br| **Type:** str
        self.object_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        # prefix with the current known list
        resource_prefix = '/lists/{list_id}'.format(list_id=self.object_id)
        main_resource = '{}{}'.format(main_resource, resource_prefix)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        #: The name of the item. |br| **Type:** str
        self.name = cloud_data.get(self._cc('name'), '')
        #: The displayable title of the list. |br| **Type:** str
        self.display_name = cloud_data.get(self._cc('displayName'), '')
        if not self.name:
            self.name = self.display_name
        #: The descriptive text for the item.  |br| **Type:** str
        self.description = cloud_data.get(self._cc('description'), '')
        #: URL that displays the item in the browser. |br| **Type:** str
        self.web_url = cloud_data.get(self._cc('webUrl'))

        created = cloud_data.get(self._cc('createdDateTime'), None)
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        #: The date and time when the item was created. |br| **Type:** datetime
        self.created = parse(created).astimezone(local_tz) if created else None
        #: The date and time when the item was last modified. |br| **Type:** datetime
        self.modified = parse(modified).astimezone(
            local_tz) if modified else None

        created_by = cloud_data.get(self._cc('createdBy'), {}).get('user', None)
        #: Identity of the creator of this item. |br| **Type:** Contact
        self.created_by = (Contact(con=self.con, protocol=self.protocol,
                                   **{self._cloud_data_key: created_by})
                           if created_by else None)
        modified_by = cloud_data.get(self._cc('lastModifiedBy'), {}).get('user',
                                                                         None)
        #: Identity of the last modifier of this item. |br| **Type:** Contact
        self.modified_by = (Contact(con=self.con, protocol=self.protocol,
                                    **{self._cloud_data_key: modified_by})
                            if modified_by else None)

        # list info
        lst_info = cloud_data.get('list', {})
        #: If true, indicates that content types are enabled for this list. |br| **Type:** bool
        self.content_types_enabled = lst_info.get(
            self._cc('contentTypesEnabled'), False)
        #: If true, indicates that the list isn't normally visible in the SharePoint
        #: user experience.
        #: |br| **Type:** bool
        self.hidden = lst_info.get(self._cc('hidden'), False)
        #: An enumerated value that represents the base list template used in creating
        #: the list. Possible values include documentLibrary, genericList, task,
        #: survey, announcements, contacts, and more.
        #: |br| **Type:** str
        self.template = lst_info.get(self._cc('template'), False)

        # Crosswalk between display name of user defined columns to internal name
        #: Column names |br| **Type:** dict
        self.column_name_cw = {col.display_name: col.internal_name for
                               col in self.get_list_columns() if not col.read_only}

    def __eq__(self, other):
        return self.object_id == other.object_id
    
    def build_field_filter(self, expand_fields):
        if expand_fields == True:
            return 'fields'
        elif isinstance(expand_fields, list):
            result = ''
            for field in expand_fields:
                if field in self.column_name_cw.values():
                    result += field + ','         
                elif field in self.column_name_cw:
                    result += self.column_name_cw[field] + ','
                else:
                    log.warning('"{}" is not a valid field name - check case'.format(field))
            if result != '':
                return 'fields(select=' + result.rstrip(',') + ')'
            
    def get_items(self, limit=None, *, query=None, order_by=None, batch=None, expand_fields=None):
        """Returns a collection of Sharepoint Items

        :param int limit: max no. of items to get. Over 999 uses batch.
        :param query: applies a filter to the request.
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :param expand_fields: specify user-defined fields to return,
         True will return all fields
        :type expand_fields: list or bool
        :return: list of Sharepoint Items
        :rtype: list[SharepointListItem] or Pagination
        """

        url = self.build_url(self._endpoints.get('get_items'))

        if limit is None or limit > self.protocol.max_top_value:
            batch = self.protocol.max_top_value

        params = {'$top': batch if batch else limit}

        if expand_fields is not None:
            params['expand'] = self.build_field_filter(expand_fields)
            
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
        next_link = data.get(NEXT_LINK_KEYWORD, None)

        items = [self.list_item_constructor(parent=self, **{self._cloud_data_key: item})
                 for item in data.get('value', [])]

        if batch and next_link:
            return Pagination(parent=self, data=items, constructor=self.list_item_constructor,
                              next_link=next_link, limit=limit)
        else:
            return items

    def get_item_by_id(self, item_id, expand_fields=None):
        """Returns a sharepoint list item based on id

        :param int item_id: item id to search for
        :param expand_fields: specify user-defined fields to return,
         True will return all fields
        :type expand_fields: list or bool
        :return: Sharepoint Item
        :rtype: SharepointListItem
        """

        url = self.build_url(self._endpoints.get('get_item_by_id').format(item_id=item_id))
        
        params = {}
        
        if expand_fields is not None:
            params['expand'] = self.build_field_filter(expand_fields)
            
        response = self.con.get(url, params=params)

        if not response:
            return []

        data = response.json()

        return self.list_item_constructor(parent=self, **{self._cloud_data_key: data})

    def get_list_columns(self):
        """ Returns the sharepoint list columns """

        url = self.build_url(self._endpoints.get('get_list_columns'))

        response = self.con.get(url)

        if not response:
            return []

        data = response.json()

        return [self.list_column_constructor(parent=self, **{self._cloud_data_key: column})
                for column in data.get('value', [])]

    def create_list_item(self, new_data):
        """Create new list item

        :param new_data: dictionary of {'col_name': col_value}

        :rtype: SharepointListItem
        """

        url = self.build_url(self._endpoints.get('get_items'))

        response = self.con.post(url, {'fields': new_data})
        if not response:
            return False

        data = response.json()

        return self.list_item_constructor(parent=self, **{self._cloud_data_key: data})

    def delete_list_item(self, item_id):
        """ Delete an existing list item

        :param item_id: Id of the item to be delted
        """

        url = self.build_url(self._endpoints.get('get_item_by_id').format(item_id=item_id))

        response = self.con.delete(url)

        return bool(response)


class Site(ApiComponent):
    """ A Sharepoint Site """

    _endpoints = {
        'get_subsites': '/sites',
        'get_lists': '/lists',
        'get_list_by_name': '/lists/{display_name}'
    }
    list_constructor = SharepointList  #: :meta private:

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Sharepoint site List

        :param parent: parent object
        :type parent: Sharepoint
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        #: The unique identifier of the item. |br| **Type:** str
        self.object_id = cloud_data.get('id')

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        # prefix with the current known site
        resource_prefix = 'sites/{site_id}'.format(site_id=self.object_id)
        main_resource = (resource_prefix if isinstance(parent, Site)
                         else '{}{}'.format(main_resource, resource_prefix))

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        #: Indicates if this is the root site. |br| **Type:** bool
        self.root = 'root' in cloud_data  # True or False
        # Fallback to manual site
        #: The name/title of the item. |br| **Type:** str
        self.name = cloud_data.get(self._cc('name'), kwargs.get('name', ''))
        #: The full title for the site. |br| **Type:** str
        self.display_name = cloud_data.get(self._cc('displayName'), '')
        if not self.name:
            self.name = self.display_name
        #: The descriptive text for the site. |br| **Type:** str
        self.description = cloud_data.get(self._cc('description'), '')
        #: URL that displays the item in the browser. |br| **Type:** str
        self.web_url = cloud_data.get(self._cc('webUrl'))

        created = cloud_data.get(self._cc('createdDateTime'), None)
        modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        local_tz = self.protocol.timezone
        #: The date and time the item was created. |br| **Type:** datetime
        self.created = parse(created).astimezone(local_tz) if created else None
        #: The date and time the item was last modified. |br| **Type:** datttime
        self.modified = parse(modified).astimezone(
            local_tz) if modified else None

        # site storage to access Drives and DriveItems
        #: The storage for the site. |br| **Type:** Storage
        self.site_storage = Storage(parent=self,
                                    main_resource='/sites/{id}'.format(
                                        id=self.object_id))

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Site: {}'.format(self.name)

    def __eq__(self, other):
        return self.object_id == other.object_id

    def get_default_document_library(self, request_drive=False):
        """ Returns the default document library of this site (Drive instance)

        :param request_drive: True will make an api call to retrieve
         the drive data
        :rtype: Drive
        """
        return self.site_storage.get_default_drive(request_drive=request_drive)

    def get_document_library(self, drive_id):
        """ Returns a Document Library (a Drive instance)

        :param drive_id: the drive_id to be retrieved.
        :rtype: Drive
        """
        return self.site_storage.get_drive(drive_id=drive_id)

    def list_document_libraries(self):
        """ Returns a collection of document libraries for this site
        (a collection of Drive instances)
        :return: list of items in this folder
        :rtype: list[Drive] or Pagination
        """
        return self.site_storage.get_drives()

    def get_subsites(self):
        """ Returns a list of subsites defined for this site

        :rtype: list[Site]
        """
        url = self.build_url(
            self._endpoints.get('get_subsites').format(id=self.object_id))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return [self.__class__(parent=self, **{self._cloud_data_key: site}) for
                site in data.get('value', [])]

    def get_lists(self):
        """ Returns a collection of lists within this site

        :rtype: list[SharepointList]
        """
        url = self.build_url(self._endpoints.get('get_lists'))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        return [self.list_constructor(parent=self, **{self._cloud_data_key: lst}) for lst in data.get('value', [])]

    def get_list_by_name(self, display_name):
        """
        Returns a sharepoint list based on the display name of the list
        """

        if not display_name:
            raise ValueError('Must provide a valid list display name')

        url = self.build_url(self._endpoints.get('get_list_by_name').format(display_name=display_name))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        return self.list_constructor(parent=self, **{self._cloud_data_key: data})

    def create_list(self, list_data):
        """
        Creates a SharePoint list.
        :param list_data: Dict representation of list.
        :type list_data: Dict
        :rtype: list[SharepointList]
        """
        url = self.build_url(self._endpoints.get('get_lists'))
        response = self.con.post(url, data=list_data)

        if not response:
            return None

        data = response.json()
        return self.list_constructor(parent=self, **{self._cloud_data_key: data})


class Sharepoint(ApiComponent):
    """ A Sharepoint parent class to group functionality """

    _endpoints = {
        'get_site': '/sites/{id}',
        'search': '/sites?search={keyword}'
    }
    site_constructor = Site  #: :meta private:

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ A Sharepoint site List

        :param parent: parent object
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

        # Choose the main_resource passed in kwargs over the host_name
        main_resource = kwargs.pop('main_resource',
                                   '')  # defaults to blank resource
        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Sharepoint'

    def search_site(self, keyword):
        """ Search a sharepoint host for sites with the provided keyword

        :param keyword: a keyword to search sites
        :rtype: list[Site]
        """
        if not keyword:
            raise ValueError('Must provide a valid keyword')

        next_link = self.build_url(
            self._endpoints.get('search').format(keyword=keyword))

        sites = []
        while next_link:
            response = self.con.get(next_link)
            if not response:
                break

            data = response.json()

            # Everything received from cloud must be passed as self._cloud_data_key
            sites += [
                self.site_constructor(parent=self, **{self._cloud_data_key: site})
                for site in data.get('value', [])
            ]

            next_link = data.get("@odata.nextLink")
        
        return sites

    def get_root_site(self):
        """ Returns the root site

        :rtype: Site
        """
        return self.get_site('root')

    def get_site(self, *args):
        """ Returns a sharepoint site

        :param args: It accepts multiple ways of retrieving a site:

         get_site(host_name): the host_name: host_name ej.
         'contoso.sharepoint.com' or 'root'

         get_site(site_id): the site_id: a comma separated string of
         (host_name, site_collection_id, site_id)

         get_site(host_name, path_to_site): host_name ej. 'contoso.
         sharepoint.com', path_to_site: a url path (with a leading slash)

         get_site(host_name, site_collection_id, site_id):
         host_name ej. 'contoso.sharepoint.com'
        :rtype: Site
        """
        num_args = len(args)
        if num_args == 1:
            site = args[0]
        elif num_args == 2:
            host_name, path_to_site = args
            path_to_site = '/' + path_to_site if not path_to_site.startswith(
                '/') else path_to_site
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

        return self.site_constructor(parent=self,
                                     **{self._cloud_data_key: data})
