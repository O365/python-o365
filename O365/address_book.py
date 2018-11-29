import logging
import datetime as dt
from dateutil.parser import parse
from enum import Enum

from O365.message import Recipients, Message
from O365.utils import Pagination, NEXT_LINK_KEYWORD, ApiComponent
from O365.utils import AttachableMixin, TrackerSet

GAL_MAIN_RESOURCE = 'users'

log = logging.getLogger(__name__)


class RecipientType(Enum):
    TO = 'to'
    CC = 'cc'
    BCC = 'bcc'


class Contact(ApiComponent, AttachableMixin):
    """ Contact manages lists of events on associated contact on office365. """

    _endpoints = {
        'contact': '/contacts',
        'root_contact': '/contacts/{id}',
        'child_contact': '/contactFolders/{folder_id}/contacts'
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

        self._track_changes = TrackerSet(casing=cc)  # internal to know which properties need to be updated on the server

        self.object_id = cloud_data.get(cc('id'), None)
        self.__created = cloud_data.get(cc('createdDateTime'), None)
        self.__modified = cloud_data.get(cc('lastModifiedDateTime'), None)

        local_tz = self.protocol.timezone
        self.__created = parse(self.created).astimezone(
            local_tz) if self.__created else None
        self.__modified = parse(self.modified).astimezone(
            local_tz) if self.__modified else None

        self.__display_name = cloud_data.get(cc('displayName'), '')
        self.__name = cloud_data.get(cc('givenName'), '')
        self.__surname = cloud_data.get(cc('surname'), '')

        self.__title = cloud_data.get(cc('title'), '')
        self.__job_title = cloud_data.get(cc('jobTitle'), '')
        self.__company_name = cloud_data.get(cc('companyName'), '')
        self.__department = cloud_data.get(cc('department'), '')
        self.__office_location = cloud_data.get(cc('officeLocation'), '')
        self.__business_phones = cloud_data.get(cc('businessPhones'), []) or []
        self.__mobile_phone = cloud_data.get(cc('mobilePhone'), '')
        self.__home_phones = cloud_data.get(cc('homePhones'), []) or []

        emails = cloud_data.get(cc('emailAddresses'), [])
        self.__emails = Recipients(recipients=[(rcp.get(cc('name'), ''), rcp.get(cc('address'), ''))
                                               for rcp in emails],
                                   parent=self, field=cc('emailAddresses'))
        email = cloud_data.get(cc('email'))
        self.__emails.untrack = True
        if email and email not in self.__emails:
            # a Contact from OneDrive?
            self.__emails.add(email)
        self.__business_address = cloud_data.get(cc('businessAddress'), {})
        self.__home_address = cloud_data.get(cc('homesAddress'), {})
        self.__other_address = cloud_data.get(cc('otherAddress'), {})
        self.__preferred_language = cloud_data.get(cc('preferredLanguage'), None)

        self.__categories = cloud_data.get(cc('categories'), [])
        self.__folder_id = cloud_data.get(cc('parentFolderId'), None)

        # when using Users endpoints (GAL) : missing keys: ['mail', 'userPrincipalName']
        mail = cloud_data.get(cc('mail'), None)
        user_principal_name = cloud_data.get(cc('userPrincipalName'), None)
        if mail and mail not in self.emails:
            self.emails.add(mail)
        if user_principal_name and user_principal_name not in self.emails:
            self.emails.add(user_principal_name)
        self.__emails.untrack = False

    @property
    def created(self):
        return self.__created

    @property
    def modified(self):
        return self.__modified

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self, value):
        self.__name = value
        self._track_changes.add(self._cc('givenName'))

    @property
    def surname(self):
        return self.__surname

    @surname.setter
    def surname(self, value):
        self.__surname = value
        self._track_changes.add(self._cc('surname'))

    @property
    def full_name(self):
        """ Returns name + surname """
        return '{} {}'.format(self.name, self.surname).strip()

    @property
    def title(self):
        return self.__title

    @title.setter
    def title(self, value):
        self.__title = value
        self._track_changes.add(self._cc('title'))

    @property
    def job_title(self):
        return self.__job_title

    @job_title.setter
    def job_title(self, value):
        self.__job_title = value
        self._track_changes.add(self._cc('jobTitle'))

    @property
    def company_name(self):
        return self.__company_name

    @company_name.setter
    def company_name(self, value):
        self.__company_name = value
        self._track_changes.add(self._cc('companyName'))

    @property
    def department(self):
        return self.__department

    @department.setter
    def department(self, value):
        self.__department = value
        self._track_changes.add(self._cc('department'))

    @property
    def office_location(self):
        return self.__office_location

    @office_location.setter
    def office_location(self, value):
        self.__office_location = value
        self._track_changes.add(self._cc('officeLocation'))

    @property
    def business_phones(self):
        return self.__business_phones

    @business_phones.setter
    def business_phones(self, value):
        if isinstance(value, tuple):
            value = list(value)
        if not isinstance(value, list):
            value = [value]
        self.__business_phones = value
        self._track_changes.add(self._cc('businessPhones'))

    @property
    def mobile_phone(self):
        return self.__mobile_phone

    @mobile_phone.setter
    def mobile_phone(self, value):
        self.__mobile_phone = value
        self._track_changes.add(self._cc('mobilePhone'))

    @property
    def home_phones(self):
        return self.__home_phones

    @home_phones.setter
    def home_phones(self, value):
        if isinstance(value, list):
            self.__home_phones = value
        elif isinstance(value, str):
            self.__home_phones = [value]
        elif isinstance(value, tuple):
            self.__home_phones = list(value)
        else:
            raise ValueError('home_phones must be a list')
        self._track_changes.add(self._cc('homePhones'))

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
    def business_address(self):
        return self.__business_address

    @business_address.setter
    def business_address(self, value):
        if not isinstance(value, dict):
            raise ValueError('"business_address" must be dict')
        self.__business_address = value
        self._track_changes.add(self._cc('businessAddress'))

    @property
    def home_address(self):
        return self.__home_address

    @home_address.setter
    def home_address(self, value):
        if not isinstance(value, dict):
            raise ValueError('"home_address" must be dict')
        self.__home_address = value
        self._track_changes.add(self._cc('homesAddress'))

    @property
    def other_address(self):
        return self.__other_address

    @other_address.setter
    def other_address(self, value):
        if not isinstance(value, dict):
            raise ValueError('"other_address" must be dict')
        self.__other_address = value
        self._track_changes.add(self._cc('otherAddress'))

    @property
    def preferred_language(self):
        return self.__preferred_language

    @preferred_language.setter
    def preferred_language(self, value):
        self.__preferred_language = value
        self._track_changes.add(self._cc('preferredLanguage'))

    @property
    def categories(self):
        return self.__categories

    @categories.setter
    def categories(self, value):
        if isinstance(value, list):
            self.__categories = value
        elif isinstance(value, str):
            self.__categories = [value]
        elif isinstance(value, tuple):
            self.__categories = list(value)
        else:
            raise ValueError('categories must be a list')
        self._track_changes.add(self._cc('categories'))

    @property
    def folder_id(self):
        return self.__folder_id

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return self.display_name or self.full_name or 'Unknwon Name'

    def to_api_data(self, restrict_keys=None):
        """ Returns a dictionary in cloud format

        :param restrict_keys: a set of keys to restrict the returned data to.
        """
        cc = self._cc  # alias

        data = {
            cc('displayName'): self.__display_name,
            cc('givenName'): self.__name,
            cc('surname'): self.__surname,
            cc('title'): self.__title,
            cc('jobTitle'): self.__job_title,
            cc('companyName'): self.__company_name,
            cc('department'): self.__department,
            cc('officeLocation'): self.__office_location,
            cc('businessPhones'): self.__business_phones,
            cc('mobilePhone'): self.__mobile_phone,
            cc('homePhones'): self.__home_phones,
            cc('emailAddresses'): [{self._cc('name'): recipient.name, self._cc('address'): recipient.address}
                                   if recipient.name else
                                   {self._cc('address'): recipient.address}
                                   for recipient in self.emails],
            cc('businessAddress'): self.__business_address,
            cc('homesAddress'): self.__home_address,
            cc('otherAddress'): self.__other_address,
            cc('categories'): self.__categories
        }

        if restrict_keys:
            for key in list(data.keys()):
                if key not in restrict_keys:
                    del data[key]
        return data

    def delete(self):
        """ Deletes this contact """

        if not self.object_id:
            raise RuntimeError('Attemping to delete an usaved Contact')

        url = self.build_url(
            self._endpoints.get('root_contact').format(id=self.object_id))

        response = self.con.delete(url)

        return bool(response)

    def save(self):
        """ Create a new Contact or update an existing one by checking what
        values have changed and update them on the server
        """
        if self.object_id:
            # Update Contact
            if not self._track_changes:
                return True  # there's nothing to update
            url = self.build_url(self._endpoints.get('root_contact').format(id=self.object_id))
            method = self.con.patch
            data = self.to_api_data(restrict_keys=self._track_changes)
        else:
            # Save new Contact
            if self.__folder_id:
                url = self.build_url(
                    self._endpoints.get('child_contact').format(folder_id=self.__folder_id))
            else:
                url = self.build_url(self._endpoints.get('contact'))
            method = self.con.post
            data = self.to_api_data(restrict_keys=self._track_changes)

        response = method(url, data=data)

        if not response:
            return False

        if not self.object_id:
            # New Contact
            contact = response.json()

            self.object_id = contact.get(self._cc('id'), None)

            self.__created = contact.get(self._cc('createdDateTime'), None)
            self.__modified = contact.get(self._cc('lastModifiedDateTime'), None)

            local_tz = self.protocol.timezone
            self.__created = parse(self.created).astimezone(
                local_tz) if self.__created else None
            self.__modified = parse(self.modified).astimezone(
                local_tz) if self.__modified else None
        else:
            self.__modified = self.protocol.timezone.localize(dt.datetime.now())

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

    def get_contact_by_email(self, email):
        """ Returns a Contact by it's email """

        if not email:
            return None

        email = email.strip()

        query = self.q().any(collection='email_addresses', attribute='address', word=email, operation='eq')

        contacts = self.get_contacts(limit=1, query=query)

        return contacts[0] if contacts else None


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
                self._endpoints.get('child_folders').format(id=self.folder_id))

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
            contact.__folder_id = self.folder_id
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
