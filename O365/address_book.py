import datetime as dt
import logging

from dateutil.parser import parse
from requests.exceptions import HTTPError

from .category import Category
from .message import Message, RecipientType
from .utils import (
    NEXT_LINK_KEYWORD,
    ApiComponent,
    AttachableMixin,
    Pagination,
    Recipients,
    TrackerSet,
)

log = logging.getLogger(__name__)


class Contact(ApiComponent, AttachableMixin):
    """ Contact manages lists of events on associated contact on office365. """

    _endpoints = {
        'contact': '/contacts',
        'root_contact': '/contacts/{id}',
        'child_contact': '/contactFolders/{folder_id}/contacts',
        'photo': '/contacts/{id}/photo/$value',
        'photo_size': '/contacts/{id}/photos/{size}/$value',
    }

    message_constructor = Message

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Create a contact API component

        :param parent: parent account for this folder
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

        cloud_data = kwargs.get(self._cloud_data_key, {})
        cc = self._cc  # alias to shorten the code

        # internal to know which properties need to be updated on the server
        self._track_changes = TrackerSet(casing=cc)

        self.object_id = cloud_data.get(cc('id'), None)
        self.__created = cloud_data.get(cc('createdDateTime'), None)
        self.__modified = cloud_data.get(cc('lastModifiedDateTime'), None)

        local_tz = self.protocol.timezone
        self.__created = parse(self.__created).astimezone(
            local_tz) if self.__created else None
        self.__modified = parse(self.__modified).astimezone(
            local_tz) if self.__modified else None

        self.__display_name = cloud_data.get(cc('displayName'), '')
        self.__fileAs = cloud_data.get(cc('fileAs'), '')
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
        self.__emails = Recipients(
            recipients=[(rcp.get(cc('name'), ''), rcp.get(cc('address'), ''))
                        for rcp in emails],
            parent=self, field=cc('emailAddresses'))
        email = cloud_data.get(cc('email'))
        self.__emails.untrack = True
        if email and email not in self.__emails:
            # a Contact from OneDrive?
            self.__emails.add(email)
        self.__business_address = cloud_data.get(cc('businessAddress'), {})
        self.__home_address = cloud_data.get(cc('homeAddress'), {})
        self.__other_address = cloud_data.get(cc('otherAddress'), {})
        self.__preferred_language = cloud_data.get(cc('preferredLanguage'),
                                                   None)

        self.__categories = cloud_data.get(cc('categories'), [])
        self.__folder_id = cloud_data.get(cc('parentFolderId'), None)

        self.__personal_notes = cloud_data.get(cc('personalNotes'), '')

        # When using Users endpoints (GAL)
        # Missing keys: ['mail', 'userPrincipalName']
        mail = cloud_data.get(cc('mail'), None)
        user_principal_name = cloud_data.get(cc('userPrincipalName'), None)
        if mail and mail not in self.emails:
            self.emails.add(mail)
        if user_principal_name and user_principal_name not in self.emails:
            self.emails.add(user_principal_name)
        self.__emails.untrack = False

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return self.display_name or self.full_name or 'Unknown Name'

    def __eq__(self, other):
        return self.object_id == other.object_id

    @property
    def created(self):
        """ Created Time

        :rtype: datetime
        """
        return self.__created

    @property
    def modified(self):
        """ Last Modified Time

        :rtype: datetime
        """
        return self.__modified

    @property
    def display_name(self):
        """ Display Name

        :getter: Get the display name of the contact
        :setter: Update the display name
        :type: str
        """
        return self.__display_name
        
    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))
    
    @property
    def fileAs(self):
        """ File As

        :getter: Get the fileAs of the contact
        :setter: Update the fileAs
        :type: str
        """
        return self.__fileAs
        
    @fileAs.setter
    def fileAs(self, value):
        self.__fileAs = value
        self._track_changes.add(self._cc('fileAs'))
        
    @property
    def name(self):
        """ First Name

        :getter: Get the name of the contact
        :setter: Update the name
        :type: str
        """
        return self.__name

    @name.setter
    def name(self, value):
        self.__name = value
        self._track_changes.add(self._cc('givenName'))

    @property
    def surname(self):
        """ Surname of Contact

        :getter: Get the surname of the contact
        :setter: Update the surname
        :type: str
        """
        return self.__surname

    @surname.setter
    def surname(self, value):
        self.__surname = value
        self._track_changes.add(self._cc('surname'))

    @property
    def full_name(self):
        """ Full Name (Name + Surname)

        :rtype: str
        """
        return '{} {}'.format(self.name, self.surname).strip()

    @property
    def title(self):
        """ Title (Mr., Ms., etc..)

        :getter: Get the title of the contact
        :setter: Update the title
        :type: str
        """
        return self.__title

    @title.setter
    def title(self, value):
        self.__title = value
        self._track_changes.add(self._cc('title'))

    @property
    def job_title(self):
        """ Job Title

        :getter: Get the job title of contact
        :setter: Update the job title
        :type: str
        """
        return self.__job_title

    @job_title.setter
    def job_title(self, value):
        self.__job_title = value
        self._track_changes.add(self._cc('jobTitle'))

    @property
    def company_name(self):
        """ Name of the company

        :getter: Get the company name of contact
        :setter: Update the company name
        :type: str
        """
        return self.__company_name

    @company_name.setter
    def company_name(self, value):
        self.__company_name = value
        self._track_changes.add(self._cc('companyName'))

    @property
    def department(self):
        """ Department

        :getter: Get the department of contact
        :setter: Update the department
        :type: str
        """
        return self.__department

    @department.setter
    def department(self, value):
        self.__department = value
        self._track_changes.add(self._cc('department'))

    @property
    def office_location(self):
        """ Office Location

        :getter: Get the office location of contact
        :setter: Update the office location
        :type: str
        """
        return self.__office_location

    @office_location.setter
    def office_location(self, value):
        self.__office_location = value
        self._track_changes.add(self._cc('officeLocation'))

    @property
    def business_phones(self):
        """ Business Contact numbers

        :getter: Get the contact numbers of contact
        :setter: Update the contact numbers
        :type: list[str]
        """
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
        """ Personal Contact numbers

        :getter: Get the contact numbers of contact
        :setter: Update the contact numbers
        :type: list[str]
        """
        return self.__mobile_phone

    @mobile_phone.setter
    def mobile_phone(self, value):
        self.__mobile_phone = value
        self._track_changes.add(self._cc('mobilePhone'))

    @property
    def home_phones(self):
        """ Home Contact numbers

        :getter: Get the contact numbers of contact
        :setter: Update the contact numbers
        :type: list[str]
        """
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
        """ List of email ids of the Contact

        :rtype: Recipients
        """
        return self.__emails

    @property
    def main_email(self):
        """ Primary(First) email id of the Contact

        :rtype: str
        """
        if not self.emails:
            return None
        return self.emails[0].address

    @property
    def business_address(self):
        """ Business Address

        :getter: Get the address of contact
        :setter: Update the address
        :type: dict
        """
        return self.__business_address

    @business_address.setter
    def business_address(self, value):
        if not isinstance(value, dict):
            raise ValueError('"business_address" must be dict')
        self.__business_address = value
        self._track_changes.add(self._cc('businessAddress'))

    @property
    def home_address(self):
        """ Home Address

        :getter: Get the address of contact
        :setter: Update the address
        :type: dict
        """
        return self.__home_address

    @home_address.setter
    def home_address(self, value):
        if not isinstance(value, dict):
            raise ValueError('"home_address" must be dict')
        self.__home_address = value
        self._track_changes.add(self._cc('homeAddress'))

    @property
    def other_address(self):
        """ Other Address

        :getter: Get the address of contact
        :setter: Update the address
        :type: dict
        """
        return self.__other_address

    @other_address.setter
    def other_address(self, value):
        if not isinstance(value, dict):
            raise ValueError('"other_address" must be dict')
        self.__other_address = value
        self._track_changes.add(self._cc('otherAddress'))

    @property
    def preferred_language(self):
        """ Preferred Language

        :getter: Get the language of contact
        :setter: Update the language
        :type: str
        """
        return self.__preferred_language

    @preferred_language.setter
    def preferred_language(self, value):
        self.__preferred_language = value
        self._track_changes.add(self._cc('preferredLanguage'))

    @property
    def categories(self):
        """ Assigned Categories

        :getter: Get the categories
        :setter: Update the categories
        :type: list[str]
        """
        return self.__categories

    @categories.setter
    def categories(self, value):
        if isinstance(value, list):
            self.__categories = []
            for val in value:
                if isinstance(val, Category):
                    self.__categories.append(val.name)
                else:
                    self.__categories.append(val)
        elif isinstance(value, str):
            self.__categories = [value]
        elif isinstance(value, Category):
            self.__categories = [value.name]
        else:
            raise ValueError('categories must be a list')
        self._track_changes.add(self._cc('categories'))

    @property
    def personal_notes(self):
        return self.__personal_notes

    @personal_notes.setter
    def personal_notes(self, value):
        self.__personal_notes = value
        self._track_changes.add(self._cc('personalNotes'))

    @property
    def folder_id(self):
        """ ID of the folder

        :rtype: str
        """
        return self.__folder_id

    def to_api_data(self, restrict_keys=None):
        """ Returns a dictionary in cloud format

        :param restrict_keys: a set of keys to restrict the returned data to.
        """
        cc = self._cc  # alias

        data = {
            cc('displayName'): self.__display_name,
            cc('fileAs'): self.__fileAs,
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
            cc('emailAddresses'): [{self._cc('name'): recipient.name or '',
                                    self._cc('address'): recipient.address}
                                   for recipient in self.emails],
            cc('businessAddress'): self.__business_address,
            cc('homeAddress'): self.__home_address,
            cc('otherAddress'): self.__other_address,
            cc('categories'): self.__categories,
            cc('personalNotes'): self.__personal_notes,
        }

        if restrict_keys:
            restrict_keys.add(cc(
                'givenName'))  # GivenName is required by the api all the time.
            for key in list(data.keys()):
                if key not in restrict_keys:
                    del data[key]
        return data

    def delete(self):
        """ Deletes this contact

        :return: Success or Failure
        :rtype: bool
        :raises RuntimeError: if contact is not yet saved to cloud
        """
        if not self.object_id:
            raise RuntimeError('Attempting to delete an unsaved Contact')

        url = self.build_url(
            self._endpoints.get('root_contact').format(id=self.object_id))

        response = self.con.delete(url)

        return bool(response)

    def save(self):
        """ Saves this contact to the cloud (create or update existing one
        based on what values have changed)

        :return: Saved or Not
        :rtype: bool
        """
        if self.object_id:
            # Update Contact
            if not self._track_changes:
                return True  # there's nothing to update
            url = self.build_url(
                self._endpoints.get('root_contact').format(id=self.object_id))
            method = self.con.patch
            data = self.to_api_data(restrict_keys=self._track_changes)
        else:
            # Save new Contact
            if self.__folder_id:
                url = self.build_url(
                    self._endpoints.get('child_contact').format(
                        folder_id=self.__folder_id))
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
            self.__modified = contact.get(self._cc('lastModifiedDateTime'),
                                          None)

            local_tz = self.protocol.timezone
            self.__created = parse(self.created).astimezone(
                local_tz) if self.__created else None
            self.__modified = parse(self.modified).astimezone(
                local_tz) if self.__modified else None
        else:
            self.__modified = dt.datetime.now().replace(tzinfo=self.protocol.timezone)

        return True

    def new_message(self, recipient=None, *, recipient_type=RecipientType.TO):
        """ This method returns a new draft Message instance with
        contacts first email as a recipient

        :param Recipient recipient: a Recipient instance where to send this
         message. If None first email of this contact will be used
        :param RecipientType recipient_type: section to add recipient into
        :return: newly created message
        :rtype: Message or None
        """

        if isinstance(recipient_type, str):
            recipient_type = RecipientType(recipient_type)

        recipient = recipient or self.emails.get_first_recipient_with_address()
        if not recipient:
            return None

        new_message = self.message_constructor(parent=self, is_draft=True)

        target_recipients = getattr(new_message, str(recipient_type.value))
        target_recipients.add(recipient)

        return new_message

    def get_profile_photo(self, size=None):
        """Returns this contact profile photo

        :param str size: 48x48, 64x64, 96x96, 120x120, 240x240,
         360x360, 432x432, 504x504, and 648x648
        """
        if size is None:
            url = self.build_url(self._endpoints.get('photo').format(id=self.object_id))
        else:
            url = self.build_url(self._endpoints.get('photo_size').format(id=self.object_id, size=size))

        try:
            response = self.con.get(url)
        except HTTPError as e:
            log.debug('Error while retrieving the contact profile photo. Error: {}'.format(e))
            return None

        if not response:
            return None

        return response.content

    def update_profile_photo(self, photo):
        """ Updates this contact profile photo
        :param bytes photo: the photo data in bytes
        """

        url = self.build_url(self._endpoints.get('photo').format(id=self.object_id))
        response = self.con.patch(url, data=photo, headers={'Content-type': 'image/jpeg'})

        return bool(response)


class BaseContactFolder(ApiComponent):
    """ Base Contact Folder Grouping Functionality """

    _endpoints = {
        'root_contacts': '/contacts',
        'folder_contacts': '/contactFolders/{id}/contacts',
        'get_folder': '/contactFolders/{id}',
        'root_folders': '/contactFolders',
        'child_folders': '/contactFolders/{id}/childFolders'
    }

    contact_constructor = Contact
    message_constructor = Message

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Create a contact folder component

        :param parent: parent folder/account for this folder
        :type parent: BaseContactFolder or Account
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

        # This folder has no parents if root = True.
        self.root = kwargs.pop('root', False)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        # Fallback to manual folder if nothing available on cloud data
        self.name = cloud_data.get(self._cc('displayName'),
                                   kwargs.get('name',
                                              ''))
        # TODO: Most of above code is same as mailbox.Folder __init__

        self.folder_id = cloud_data.get(self._cc('id'), None)
        self.parent_id = cloud_data.get(self._cc('parentFolderId'), None)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Contact Folder: {}'.format(self.name)

    def __eq__(self, other):
        return self.folder_id == other.folder_id

    def get_contacts(self, limit=100, *, query=None, order_by=None, batch=None):
        """ Gets a list of contacts from this address book

        To use query an order_by check the OData specification here:
        http://docs.oasis-open.org/odata/odata/v4.0/errata03/os/complete/
        part2-url-conventions/odata-v4.0-errata03-os-part2-url-conventions
        -complete.html

        :param limit: max no. of contacts to get. Over 999 uses batch.
        :type limit: int or None
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :param int batch: batch size, retrieves items in
         batches allowing to retrieve more items than the limit.
        :return: list of contacts
        :rtype: list[Contact] or Pagination
        """

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
            return iter(())

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        contacts = (self.contact_constructor(parent=self,
                                             **{self._cloud_data_key: contact})
                    for contact in data.get('value', []))

        next_link = data.get(NEXT_LINK_KEYWORD, None)

        if batch and next_link:
            return Pagination(parent=self, data=contacts,
                              constructor=self.contact_constructor,
                              next_link=next_link, limit=limit)
        else:
            return contacts

    def get_contact_by_email(self, email):
        """ Returns a Contact by it's email

        :param email: email to get contact for
        :return: Contact for specified email
        :rtype: Contact
        """
        if not email:
            return None

        query = self.q().any(collection='email_addresses', attribute='address',
                             word=email.strip(), operation='eq')
        contacts = list(self.get_contacts(limit=1, query=query))
        return contacts[0] if contacts else None


class ContactFolder(BaseContactFolder):
    """ A Contact Folder representation """

    def get_folder(self, folder_id=None, folder_name=None):
        """ Returns a Contact Folder by it's id or child folders by name

        :param folder_id: the folder_id to be retrieved.
         Can be any folder Id (child or not)
        :param folder_name: the folder name to be retrieved.
         Must be a child of this folder
        :return: a single contact folder
        :rtype: ContactFolder
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

        # Everything received from cloud must be passed as self._cloud_data_key
        # we don't pass parent, as this folder may not be a child of self.
        return self.__class__(con=self.con, protocol=self.protocol,
                              main_resource=self.main_resource,
                              **{self._cloud_data_key: folder})

    def get_folders(self, limit=None, *, query=None, order_by=None):
        """ Returns a list of child folders

        :param int limit: max no. of folders to get. Over 999 uses batch.
        :param query: applies a OData filter to the request
        :type query: Query or str
        :param order_by: orders the result set based on this condition
        :type order_by: Query or str
        :return: list of folders
        :rtype: list[ContactFolder]
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

        return [self.__class__(parent=self, **{self._cloud_data_key: folder})
                for folder in data.get('value', [])]

    def create_child_folder(self, folder_name):
        """ Creates a new child folder

        :param str folder_name: name of the new folder to create
        :return: newly created folder
        :rtype: ContactFolder or None
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

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.__class__(parent=self, **{self._cloud_data_key: folder})

    def update_folder_name(self, name):
        """ Change this folder name

        :param str name: new name to change to
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

        folder = response.json()

        self.name = folder.get(self._cc('displayName'), '')
        self.parent_id = folder.get(self._cc('parentFolderId'), None)

        return True

    def move_folder(self, to_folder):
        """ Change this folder name

        :param to_folder: folder_id/ContactFolder to move into
        :type to_folder: str or ContactFolder
        :return: Moved or Not
        :rtype: bool
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

    def new_contact(self):
        """ Creates a new contact to be saved into it's parent folder

        :return: newly created contact
        :rtype: Contact
        """
        contact = self.contact_constructor(parent=self)
        if not self.root:
            contact.__folder_id = self.folder_id
        return contact

    def new_message(self, recipient_type=RecipientType.TO, *, query=None):
        """ This method returns a new draft Message instance with all the
        contacts first email as a recipient

        :param RecipientType recipient_type: section to add recipient into
        :param query: applies a OData filter to the request
        :type query: Query or str
        :return: newly created message
        :rtype: Message or None
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
        # Set instance to be a root instance
        super().__init__(parent=parent, con=con, root=True, **kwargs)

    def __repr__(self):
        return 'Address Book resource: {}'.format(self.main_resource)
