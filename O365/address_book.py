import logging
from dateutil.parser import parse
from enum import Enum

from O365.message import HandleRecipientsMixin, Recipients, Message
from O365.utils import Pagination, NEXT_LINK_KEYWORD, ApiComponent
from O365.utils import AttachableMixin

GAL_MAIN_RESOURCE = 'users'

log = logging.getLogger(__name__)


class RecipientType(Enum):
    TO = 'to'
    CC = 'cc'
    BCC = 'bcc'


class Contact(ApiComponent, AttachableMixin, HandleRecipientsMixin):
    """ Contact manages lists of events on associated contact on office365. """

    _mapping = {
        'display_name': 'displayName',
        'name': 'givenName',
        'surname': 'surname',
        'title': 'title',
        'job_title': 'jobTitle',
        'company_name': 'companyName',
        'department': 'department',
        'office_location': 'officeLocation',
        'business_phones': 'businessPhones',
        'mobile_phone': 'mobilePhone',
        'home_phones': 'homePhones',
        'emails': 'emailAddresses',
        'business_addresses': 'businessAddress',
        'home_addresses': 'homesAddress',
        'other_addresses': 'otherAddress',
        'categories': 'categories'
    }

    _endpoints = {
        'root_contact': '/contacts/{id}',
        'child_contact': '/contactFolders/{id}/contacts'
    }

    message_constructor = Message

    def __init__(self, *, parent=None, con=None, **kwargs):
        """

        :param parent:
        :param con:
        :param kwargs:
        """
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent,
                                                                     'main_resource',
                                                                     None) if parent else None
        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})
        cc = self._cc  # alias to shorten the code

        self.object_id = cloud_data.get(cc('id'), None)
        self.created = cloud_data.get(cc('createdDateTime'), None)
        self.modified = cloud_data.get(cc('lastModifiedDateTime'), None)

        local_tz = self.protocol.timezone
        self.created = parse(self.created).astimezone(
            local_tz) if self.created else None
        self.modified = parse(self.modified).astimezone(
            local_tz) if self.modified else None

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
        self.__emails = self._recipients_from_cloud(
            cloud_data.get(cc('emailAddresses'), []))
        email = cloud_data.get(cc('email'))
        if email and email not in self.__emails:
            # a Contact from OneDrive?
            self.__emails.add(email)
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
            self.emails.add(mail)
        if user_principal_name and user_principal_name not in self.emails:
            self.emails.add(user_principal_name)

    @property
    def emails(self):
        return self.__emails

    @property
    def main_email(self):
        """ Returns the first email on the emails"""
        if not self.emails:
            return None
        return self.emails[0].address

    @property
    def full_name(self):
        """ Returns name + surname """
        return '{} {}'.format(self.name, self.surname).strip()

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return self.display_name or self.full_name or 'Unknwon Name'

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
            'emailAddresses': [self._recipient_to_cloud(recipient) for recipient in self.emails],
            'businessAddress': self.business_addresses,
            'homesAddress': self.home_addresses,
            'otherAddress': self.other_addresses,
            'categories': self.categories}
        return data

    def delete(self):
        """ Deletes this contact """

        if not self.object_id:
            raise RuntimeError('Attemping to delete an usaved Contact')

        url = self.build_url(
            self._endpoints.get('contact').format(id=self.object_id))

        response = self.con.delete(url)

        return bool(response)

    def update(self, fields):
        """ Updates a contact
         :param fields: a dict of fields to update (field: value).
         """

        if not self.object_id:
            raise RuntimeError('Attemping to update an usaved Contact')

        if fields is None or not isinstance(fields, (list, tuple)):
            raise ValueError('Must provide fields to update as a list or tuple')

        data = {}
        for field in fields:
            mapping = self._mapping.get(field)
            if mapping is None:
                raise ValueError(
                    '{} is not a valid updatable field from Contact'.format(
                        field))
            update_value = getattr(self, field)
            if isinstance(update_value, Recipients):
                data[self._cc(mapping)] = [self._recipient_to_cloud(recipient)
                                           for recipient in update_value]
            else:
                data[self._cc(mapping)] = update_value

        url = self.build_url(
            self._endpoints.get('contact'.format(id=self.object_id)))

        response = self.con.patch(url, data=data)

        return bool(response)

    def save(self):
        """ Saves this Contact to the cloud """
        if self.object_id:
            raise RuntimeError(
                "Can't save an existing Contact. Use Update instead. ")

        if self.folder_id:
            url = self.build_url(
                self._endpoints.get('child_contact').format(self.folder_id))
        else:
            url = self.build_url(self._endpoints.get('root_contact'))

        response = self.con.post(url, data=self.to_api_data())
        if not response:
            return False

        contact = response.json()

        self.object_id = contact.get(self._cc('id'), None)
        self.created = contact.get(self._cc('createdDateTime'), None)
        self.modified = contact.get(self._cc('lastModifiedDateTime'), None)

        local_tz = self.protocol.timezone
        self.created = parse(self.created).astimezone(
            local_tz) if self.created else None
        self.modified = parse(self.modified).astimezone(
            local_tz) if self.modified else None

        return True

    def new_message(self, recipient=None, *, recipient_type=RecipientType.TO):
        """
        This method returns a new draft Message instance with this contact first email as a recipient
        :param recipient: a Recipient instance where to send this message. If None, first recipient with address.
        :param recipient_type: a RecipientType Enum.
        :return: a new draft Message or None if recipient has no addresses
        """
        if self.main_resource == GAL_MAIN_RESOURCE:
            # preventing the contact lookup to explode for big organizations..
            raise RuntimeError(
                'Sending a message to all users within an Organization is not allowed')

        if isinstance(recipient_type, str):
            recipient_type = RecipientType(recipient_type)

        recipient = recipient or self.emails.get_first_recipient_with_address()
        if not recipient:
            return None

        new_message = self.message_constructor(parent=self, is_draft=True)

        target_recipients = getattr(new_message, str(recipient_type.value))
        target_recipients.add(recipient)

        return new_message


class BaseContactFolder(ApiComponent):
    """ Base Contact Folder Grouping Functionality """

    _endpoints = {
        'gal': '',
        'root_contacts': '/contacts',
        'folder_contacts': '/contactFolders/{id}/contacts',
        'get_folder': '/contactFolders/{id}',
        'root_folders': '/contactFolders',
        'child_folders': '/contactFolders/{id}/childFolders'
    }

    contact_constructor = Contact
    message_constructor = Message

    def __init__(self, *, parent=None, con=None, **kwargs):
        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None) or getattr(parent,
                                                                     'main_resource',
                                                                     None) if parent else None
        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        self.root = kwargs.pop('root',
                               False)  # This folder has no parents if root = True.

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.name = cloud_data.get(self._cc('displayName'), kwargs.get('name',
                                                                       None))  # Fallback to manual folder
        self.folder_id = cloud_data.get(self._cc('id'), None)
        self.parent_id = cloud_data.get(self._cc('parentFolderId'), None)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Contact Folder: {}'.format(self.name)

    def get_contacts(self, limit=100, *, query=None, order_by=None, batch=None):
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
                url = self.build_url(
                    self._endpoints.get('folder_contacts').format(
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
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        contacts = [self.contact_constructor(parent=self,
                                             **{self._cloud_data_key: contact})
                    for contact in data.get('value', [])]

        next_link = data.get(NEXT_LINK_KEYWORD, None)

        if batch and next_link:
            return Pagination(parent=self, data=contacts,
                              constructor=self.contact_constructor,
                              next_link=next_link, limit=limit)
        else:
            return contacts


class ContactFolder(BaseContactFolder):
    """ A Contact Folder representation """

    def get_folder(self, folder_id=None, folder_name=None):
        """
        Returns a ContactFolder by it's id or name
        :param folder_id: the folder_id to be retrieved. Can be any folder Id (child or not)
        :param folder_name: the folder name to be retrieved. Must be a child of this folder.
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

        # Everything received from the cloud must be passed with self._cloud_data_key
        # we don't pass parent, as this folder may not be a child of self.
        return ContactFolder(con=self.con, protocol=self.protocol,
                             main_resource=self.main_resource,
                             **{self._cloud_data_key: folder})

    def get_folders(self, limit=None, *, query=None, order_by=None):
        """
        Returns a list of child folders

        :param limit: Number of elements to return.
        :param query: a OData valid filter clause
        :param order_by: OData valid order by clause
        """
        if self.root:
            url = self.build_url(self._endpoints.get('root_folders'))
        else:
            url = self.build_url(
                self._endpoints.get('child_folders').format(self.folder_id))

        params = {}

        if limit:
            params['$top'] = limit

        if order_by:
            params['$orderby'] = order_by

        if query:
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

        response = self.con.get(url, params=params or None)
        if not response:
            return []

        data = response.json()

        return [ContactFolder(parent=self, **{self._cloud_data_key: folder})
                for folder in data.get('value', [])]

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
            url = self.build_url(
                self._endpoints.get('child_folders').format(id=self.folder_id))

        response = self.con.post(url,
                                 data={self._cc('displayName'): folder_name})
        if not response:
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

        url = self.build_url(
            self._endpoints.get('get_folder').format(id=self.folder_id))

        response = self.con.patch(url, data={self._cc('displayName'): name})
        if not response:
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

        url = self.build_url(
            self._endpoints.get('get_folder').format(id=self.folder_id))

        if isinstance(to_folder, ContactFolder):
            folder_id = to_folder.folder_id
        elif isinstance(to_folder, str):
            folder_id = to_folder
        else:
            return False

        response = self.con.patch(url,
                                  data={self._cc('parentFolderId'): folder_id})
        if not response:
            return False

        folder = response.json()

        self.name = folder.get(self._cc('displayName'), '')
        self.parent_id = folder.get(self._cc('parentFolderId'), None)

        return True

    def delete(self):
        """ Deletes this folder """

        if self.root or not self.folder_id:
            return False

        url = self.build_url(
            self._endpoints.get('get_folder').format(id=self.folder_id))

        response = self.con.delete(url)
        if not response:
            return False

        self.folder_id = None

        return True

    def new_contact(self):
        """ Creates a new contact to be saved into it's parent folder """
        contact = self.contact_constructor(parent=self)
        if not self.root:
            contact.folder_id = self.folder_id

        return contact

    def new_message(self, recipient_type=RecipientType.TO, *, query=None):
        """
        This method returns a new draft Message instance with all the contacts first email as a recipient
        :param recipient_type: a RecipientType Enum.
        :param query: a query to filter the contacts (passed to get_contacts)
        :return: a draft Message or None if no contacts could be retrieved
        """

        if isinstance(recipient_type, str):
            recipient_type = RecipientType(recipient_type)

        recipients = [contact.emails[0]
                      for contact in self.get_contacts(limit=None, query=query)
                      if contact.emails and contact.emails[0].address]

        if not recipients:
            return None

        new_message = self.message_constructor(parent=self, is_draft=True)
        target_recipients = getattr(new_message, str(recipient_type.value))
        target_recipients.add(recipients)

        return new_message


class AddressBook(ContactFolder):
    """ A class representing an address book """

    def __init__(self, *, parent=None, con=None, **kwargs):
        # set instance to be a root instance
        super().__init__(parent=parent, con=con, root=True, **kwargs)

    def __repr__(self):
        return 'Address Book resource: {}'.format(self.main_resource)


class GlobalAddressList(BaseContactFolder):
    """ A class representing the Global Address List (Users API) """

    def __init__(self, *, parent=None, con=None, **kwargs):
        # set instance to be a root instance and the main_resource to be the GAL_MAIN_RESOURCE
        super().__init__(parent=parent, con=con, root=True,
                         main_resource=GAL_MAIN_RESOURCE,
                         name='Global Address List', **kwargs)

    def __repr__(self):
        return 'Global Address List'

    def get_contact_by_email(self, email):
        """ Returns a Contact by it's email """

        if not email:
            return None

        email = email.strip()

        url = self.build_url('{}/{}'.format(self._endpoints.get('gal'), email))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        # Everything received from the cloud must be passed with self._cloud_data_key
        return self.contact_constructor(parent=self,
                                        **{self._cloud_data_key: data})
