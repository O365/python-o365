import logging
from dateutil.parser import parse
from tzlocal import get_localzone

from O365.message import MixinHandleRecipients, Recipients
from O365.utils import Pagination, NEXT_LINK_KEYWORD, ApiComponent

GAL_MAIN_RESOURCE = 'users'

log = logging.getLogger(__name__)


class Contact(ApiComponent, MixinHandleRecipients):
    """ Contact manages lists of events on an associated contact on office365. """

    _mapping = {'display_name': 'displayName', 'name': 'givenName', 'surname': 'surname', 'title': 'title', 'job_title': 'jobTitle',
                'company_name': 'companyName', 'department': 'department', 'office_location': 'officeLocation',
                'business_phones': 'businessPhones', 'mobile_phone': 'mobilePhone', 'home_phones': 'homePhones',
                'emails': 'emailAddresses', 'business_addresses': 'businessAddress', 'home_addresses': 'homesAddress',
                'other_addresses': 'otherAddress', 'categories': 'categories'}

    _endpoints = {
        'root_contact': '/contacts/{id}',
        'child_contact': '/contactFolders/{id}/contacts'
    }

    def __init__(self, *, parent=None, con=None, **kwargs):

        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})
        cc = self._cc  # alias to shorten the code

        self.contact_id = cloud_data.get(cc('id'), None)
        self.created = cloud_data.get(cc('createdDateTime'), None)
        self.modified = cloud_data.get(cc('lastModifiedDateTime'), None)

        local_tz = get_localzone()
        self.created = parse(self.created).astimezone(local_tz) if self.created else None
        self.modified = parse(self.modified).astimezone(local_tz) if self.modified else None

        self.display_name = cloud_data.get(cc('displayName'), '')
        self.name = cloud_data.get(cc('givenName'), '')
        self.surname = cloud_data.get(cc('surname'), '')

        self.title = cloud_data.get(cc('title'), '')
        self.job_title = cloud_data.get(cc('jobTitle'), '')
        self.company_name = cloud_data.get(cc('companyName'), '')
        self.department = cloud_data.get(cc('department'), '')
        self.office_location = cloud_data.get(cc('officeLocation'), '')
        self.business_phones = cloud_data.get(cc('businessPhones'), []) or []
        self.mobile_phone = cloud_data.get(cc('mobilePhone'), '')
        self.home_phones = cloud_data.get(cc('homePhones'), []) or []
        self.emails = self._recipients_from_cloud(cloud_data.get(cc('emailAddresses'), []))
        self.business_addresses = cloud_data.get(cc('businessAddress'), {})
        self.home_addresses = cloud_data.get(cc('homesAddress'), {})
        self.other_addresses = cloud_data.get(cc('otherAddress'), {})
        self.preferred_language = cloud_data.get(cc('preferredLanguage'), None)

        self.categories = cloud_data.get(cc('categories'), [])
        self.folder_id = cloud_data.get(cc('parentFolderId'), None)

        # when using Users endpoints (GAL) : missing keys: ['mail', 'userPrincipalName']
        mail = cloud_data.get(cc('mail'), None)
        user_principal_name = cloud_data.get(cc('userPrincipalName'), None)
        if mail and mail not in self.emails:
            self.emails.add([mail])
        if user_principal_name and user_principal_name not in self.emails:
            self.emails.add([user_principal_name])

    @property
    def full_name(self):
        """ Returns name + surname """
        return '{} {}'.format(self.name, self.surname).strip()

    def __str__(self):
        return self.display_name or self.full_name or 'Unknwon Name'

    def __repr__(self):
        return self.__str__()

    def to_api_data(self):
        """ Returns a dictionary in cloud format """

        data = {
            'displayName': self.display_name,
            'givenName': self.name,
            'surname': self.surname,
            'title': self.title,
            'jobTitle': self.job_title,
            'companyName': self.company_name,
            'department': self.department,
            'officeLocation': self.office_location,
            'businessPhones': self.business_phones,
            'mobilePhone': self.mobile_phone,
            'homePhones': self.home_phones,
            'emailAddresses': self.emails.to_api_data(),
            'businessAddress': self.business_addresses,
            'homesAddress': self.home_addresses,
            'otherAddress': self.other_addresses,
            'categories': self.categories}
        return data

    def delete(self):
        """ Deletes this contact """

        if not self.contact_id:
            raise RuntimeError('Attemping to delete an usaved Contact')

        url = self.build_url(self._endpoints.get('contact').format(id=self.contact_id))

        try:
            response = self.con.delete(url)
        except Exception as e:
            log.error('Error while deleting Contact id: {}'.format(self.contact_id))
            return False
        log.debug('response from delete attempt: {0}'.format(str(response)))

        return response.status_code == 204

    def update(self, fields):
        """ Updates a contact
         :param fields: a dict of fields to update (field: value).
         """

        if not self.contact_id:
            raise RuntimeError('Attemping to update an usaved Contact')

        if fields is None or not isinstance(fields, (list, tuple)):
            raise ValueError('Must provide fields to update as a list or tuple')

        data = {}
        for field in fields:
            mapping = self._mapping.get(field)
            if mapping is None:
                raise ValueError('{} is not a valid updatable field from Contact'.format(field))
            update_value = getattr(self, field)
            if isinstance(update_value, Recipients):
                data[self._cc(mapping)] = [self._recipient_to_cloud(recipient) for recipient in update_value]
            else:
                data[self._cc(mapping)] = update_value

        url = self.build_url(self._endpoints.get('contact'.format(id=self.contact_id)))
        try:
            response = self.con.patch(url, data=data)
            log.debug('sent update request')
        except Exception as e:
            log.error('Error while updating Contact id: {id}. Error: {error}'.format(id=self.contact_id, error=str(e)))
            return False

        log.debug('Response to contact update: {0}'.format(str(response)))

        return response.status_code == 200

    def save(self):
        """ Saves this Contact to the cloud """
        if self.contact_id:
            raise RuntimeError("Can't save an existing Contact. Use Update instead. ")

        if self.folder_id:
            url = self.build_url(self._endpoints.get('child_contact').format(self.folder_id))
        else:
            url = self.build_url(self._endpoints.get('root_contact'))

        try:
            response = self.con.psot(url, data=self.to_api_data())
        except Exception as e:
            log.error('Error while saving contact. Error: {error}'.format(error=str(e)))
            return False

        if response.status_code != 201:
            log.debug('Creating contact Request failed: {}'.format(response.reason))
            return False

        contact = response.json()

        self.contact_id = contact.get(self._cc('id'), None)
        self.created = contact.get(self._cc('createdDateTime'), None)
        self.modified = contact.get(self._cc('lastModifiedDateTime'), None)

        local_tz = get_localzone()
        self.created = parse(self.created).astimezone(local_tz) if self.created else None
        self.modified = parse(self.modified).astimezone(local_tz) if self.modified else None

        return True


class ContactFolder(ApiComponent):
    """ A Contact Folder representation """

    _endpoints = {
        'gal': '',
        'root_contacts': '/contacts',
        'folder_contacts': '/contactFolders/{id}/contacts',
        'get_folder': '/contactFolders/{id}',
        'root_folders': '/contactFolders',
        'child_folders': '/contactFolders/{id}/childFolders'
    }

    contact_constructor = Contact

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent, 'main_resource', None) if parent else None
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

        self.root = kwargs.pop('root', False)  # This folder has no parents if root = True.

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.name = cloud_data.get(self._cc('displayName'), kwargs.get('name', None))  # Fallback to manual folder
        self.folder_id = cloud_data.get(self._cc('id'), None)
        self.parent_id = cloud_data.get(self._cc('parentFolderId'), None)

    def __str__(self):
        return 'Contact Folder: {}'.format(self.name)

    def __repr__(self):
        return self.__str__()

    def get_folder(self, folder_id=None, folder_name=None):
        """
        Returns a ContactFolder by it's id
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
            log.error('Error getting contact folder {}. Error: {}'.format(folder_id, str(e)))
            return None

        if response.status_code != 200:
            log.debug('Getting contact folder Request failed: {}'.format(response.reason))
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
        return ContactFolder(con=self.con, protocol=self.protocol, main_resource=self.main_resource, **{self._cloud_data_key: folder})

    def get_folders(self, limit=25, *, query=None, order_by=None):
        """
        Returns a list of child folders

        :param limit: Number of elements to return.
        :param query: a OData valid filter clause
        :param order_by: OData valid order by clause
        """
        if self.root:
            url = self.build_url(self._endpoints.get('root_folders'))
        else:
            url = self.build_url(self._endpoints.get('child_folders').format(self.folder_id))

        params = {'$top': limit or 25}

        if query:
            params['$filter'] = str(query)
        if order_by:
            params['$orderby'] = order_by

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error getting child contact folders. Error {}'.format(str(e)))
            return []

        if response.status_code != 200:
            log.debug('Getting child contact folders Request failed: {}'.format(response.reason))
            return []

        data = response.json()

        return [ContactFolder(parent=self, **{self._cloud_data_key: folder})
                for folder in data.get('value', [])]

    def get_contacts(self, limit=25, *, query=None, order_by=None, batch=None):
        """
        Gets a list of contacts from this address book

        When quering the Global Address List the Users enpoint will be used.
        Only a limited set of information will be available unless you have acces to
         scope 'User.Read.All' wich requires App Administration Consent.
        Also using the Users enpoint has some limitations on the quering capabilites.

        To use query an order_by check the OData specification here:
        http://docs.oasis-open.org/odata/odata/v4.0/errata03/os/complete/part2-url-conventions/odata-v4.0-errata03-os-part2-url-conventions-complete.html

        :param limit: Number of elements to return. Over 999 uses batch.
        :param query: a OData valid filter clause
        :param order_by: OData valid order by clause
        :param batch: Returns a custom iterator that retrieves items in batches allowing
            to retrieve more items than the limit.
        """

        if self.main_resource == GAL_MAIN_RESOURCE:
            # using Users endpoint to access the Global Address List
            url = self.build_url(self._endpoints.get('gal'))
        else:
            if self.root:
                url = self.build_url(self._endpoints.get('root_contacts'))
            else:
                url = self.build_url(self._endpoints.get('folder_contacts').format(self.folder_id))

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
            log.error('Error getting contacts. Error {}'.format(str(e)))
            return []

        if response.status_code != 200:
            log.debug('Getting contacts Request failed: {}'.format(response.reason))
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        contacts = [self.contact_constructor(parent=self, **{self._cloud_data_key: contact})
                    for contact in data.get('value', [])]

        next_link = data.get(NEXT_LINK_KEYWORD, None)

        if batch and next_link:
            return Pagination(parent=self, data=contacts, constructor=self.contact_constructor,
                              next_link=data.get(NEXT_LINK_KEYWORD, None), limit=limit)
        else:
            return contacts

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
            log.error('Error creating contact folder of {}. Error: {}'.format(self.name, str(e)))
            return None

        if response.status_code != 201:
            log.debug('Creating contact folder Request failed: {}'.format(response.reason))
            return None

        folder = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return ContactFolder(parent=self, **{self._cloud_data_key: folder})

    def update_folder_name(self, name):
        """ Change this folder name """
        if self.root:
            return False
        if not name:
            return False

        url = self.build_url(self._endpoints.get('get_folder').format(id=self.folder_id))

        try:
            response = self.con.patch(url, data={self._cc('displayName'): name})
        except Exception as e:
            log.error('Error updating contact folder {}. Error: {}'.format(self.name, str(e)))
            return False

        if response.status_code != 200:
            log.debug('Updating contact folder Request failed: {}'.format(response.reason))
            return False

        folder = response.json()

        self.name = folder.get(self._cc('displayName'), '')
        self.parent_id = folder.get(self._cc('parentFolderId'), None)

        return True

    def move_folder(self, to_folder):
        """
        Change this folder name
        :param to_folder: a folder_id str or a ContactFolder
        """
        if self.root:
            return False
        if not to_folder:
            return False

        url = self.build_url(self._endpoints.get('get_folder').format(id=self.folder_id))

        if isinstance(to_folder, ContactFolder):
            folder_id = to_folder.folder_id
        elif isinstance(to_folder, str):
            folder_id = to_folder
        else:
            return False

        try:
            response = self.con.patch(url, data={self._cc('parentFolderId'): folder_id})
        except Exception as e:
            log.error('Error moving contact folder {}. Error: {}'.format(self.name, str(e)))
            return False

        if response.status_code != 200:
            log.debug('Moving contact folder Request failed: {}'.format(response.reason))
            return False

        folder = response.json()

        self.name = folder.get(self._cc('displayName'), '')
        self.parent_id = folder.get(self._cc('parentFolderId'), None)

        return True

    def delete(self):
        """ Deletes this folder """

        if self.root or not self.folder_id:
            return False

        url = self.build_url(self._endpoints.get('get_folder').format(id=self.folder_id))

        try:
            response = self.con.delete(url)
        except Exception as e:
            log.error('Error deleting contact folder {}. Error: {}'.format(self.name, str(e)))
            return False

        if response.status_code != 204:
            log.debug('Deleteing contact folder Request failed: {}'.format(response.reason))
            return False

        self.folder_id = None

        return True

    def new_contact(self):
        """ Creates a new contact to be saved into it's parent folder """
        contact = self.contact_constructor(parent=self)
        if not self.root:
            contact.folder_id = self.folder_id


class AddressBook(ContactFolder):
    """ A class representing an address book """

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, root=True, **kwargs)

    def __str__(self):
        return 'Address Book resource: {}'.format(self.main_resource)
