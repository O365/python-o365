import logging

from dateutil.parser import parse
from requests.exceptions import HTTPError

from .message import Message, RecipientType
from .utils import ME_RESOURCE, NEXT_LINK_KEYWORD, ApiComponent, Pagination

USERS_RESOURCE = 'users'

log = logging.getLogger(__name__)


class User(ApiComponent):

    _endpoints = {
        'photo': '/photo/$value',
        'photo_size': '/photos/{size}/$value'
    }

    message_constructor = Message

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Represents an Azure AD user account

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

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id')

        if main_resource == USERS_RESOURCE:
            main_resource += f'/{self.object_id}'

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        local_tz = self.protocol.timezone
        cc = self._cc

        self.type = cloud_data.get('@odata.type')
        self.user_principal_name = cloud_data.get(cc('userPrincipalName'))
        self.display_name = cloud_data.get(cc('displayName'))
        self.given_name = cloud_data.get(cc('givenName'), '')
        self.surname = cloud_data.get(cc('surname'), '')
        self.mail = cloud_data.get(cc('mail'))  # read only
        self.business_phones = cloud_data.get(cc('businessPhones'), [])
        self.job_title = cloud_data.get(cc('jobTitle'))
        self.mobile_phone = cloud_data.get(cc('mobilePhone'))
        self.office_location = cloud_data.get(cc('officeLocation'))
        self.preferred_language = cloud_data.get(cc('preferredLanguage'))
        # End of default properties. Next properties must be selected

        self.about_me = cloud_data.get(cc('aboutMe'))
        self.account_enabled = cloud_data.get(cc('accountEnabled'))
        self.age_group = cloud_data.get(cc('ageGroup'))
        self.assigned_licenses = cloud_data.get(cc('assignedLicenses'))
        self.assigned_plans = cloud_data.get(cc('assignedPlans'))  # read only
        birthday = cloud_data.get(cc('birthday'))
        self.birthday = parse(birthday).astimezone(local_tz) if birthday else None
        self.city = cloud_data.get(cc('city'))
        self.company_name = cloud_data.get(cc('companyName'))
        self.consent_provided_for_minor = cloud_data.get(cc('consentProvidedForMinor'))
        self.country = cloud_data.get(cc('country'))
        created = cloud_data.get(cc('createdDateTime'))
        self.created = parse(created).astimezone(
            local_tz) if created else None
        self.department = cloud_data.get(cc('department'))
        self.employee_id = cloud_data.get(cc('employeeId'))
        self.fax_number = cloud_data.get(cc('faxNumber'))
        hire_date = cloud_data.get(cc('hireDate'))
        self.hire_date = parse(hire_date).astimezone(
            local_tz) if hire_date else None
        self.im_addresses = cloud_data.get(cc('imAddresses'))  # read only
        self.interests = cloud_data.get(cc('interests'))
        self.is_resource_account = cloud_data.get(cc('isResourceAccount'))
        last_password_change = cloud_data.get(cc('lastPasswordChangeDateTime'))
        self.last_password_change = parse(last_password_change).astimezone(
            local_tz) if last_password_change else None
        self.legal_age_group_classification = cloud_data.get(cc('legalAgeGroupClassification'))
        self.license_assignment_states = cloud_data.get(cc('licenseAssignmentStates'))  # read only
        self.mailbox_settings = cloud_data.get(cc('mailboxSettings'))
        self.mail_nickname = cloud_data.get(cc('mailNickname'))
        self.my_site = cloud_data.get(cc('mySite'))
        self.other_mails = cloud_data.get(cc('otherMails'))
        self.password_policies = cloud_data.get(cc('passwordPolicies'))
        self.password_profile = cloud_data.get(cc('passwordProfile'))
        self.past_projects = cloud_data.get(cc('pastProjects'))
        self.postal_code = cloud_data.get(cc('postalCode'))
        self.preferred_data_location = cloud_data.get(cc('preferredDataLocation'))
        self.preferred_name = cloud_data.get(cc('preferredName'))
        self.provisioned_plans = cloud_data.get(cc('provisionedPlans'))  # read only
        self.proxy_addresses = cloud_data.get(cc('proxyAddresses'))  # read only
        self.responsibilities = cloud_data.get(cc('responsibilities'))
        self.schools = cloud_data.get(cc('schools'))
        self.show_in_address_list = cloud_data.get(cc('showInAddressList'), True)
        self.skills = cloud_data.get(cc('skills'))
        sign_in_sessions_valid_from = cloud_data.get(cc('signInSessionsValidFromDateTime'))  # read only
        self.sign_in_sessions_valid_from = parse(sign_in_sessions_valid_from).astimezone(
            local_tz) if sign_in_sessions_valid_from else None
        self.state = cloud_data.get(cc('state'))
        self.street_address = cloud_data.get(cc('streetAddress'))
        self.usage_location = cloud_data.get(cc('usageLocation'))
        self.user_type = cloud_data.get(cc('userType'))
        self.on_premises_sam_account_name = cloud_data.get(cc('onPremisesSamAccountName'))

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return self.display_name or self.full_name or self.user_principal_name or 'Unknown Name'

    def __eq__(self, other):
        return self.object_id == other.object_id

    def __hash__(self):
        return self.object_id.__hash__()

    @property
    def full_name(self):
        """ Full Name (Name + Surname)
        :rtype: str
        """
        return f'{self.given_name} {self.surname}'.strip()

    def new_message(self, recipient=None, *, recipient_type=RecipientType.TO):
        """ This method returns a new draft Message instance with this
        user email as a recipient

        :param Recipient recipient: a Recipient instance where to send this
         message. If None the email of this contact will be used
        :param RecipientType recipient_type: section to add recipient into
        :return: newly created message
        :rtype: Message or None
        """

        if isinstance(recipient_type, str):
            recipient_type = RecipientType(recipient_type)

        recipient = recipient or self.mail
        if not recipient:
            return None

        new_message = self.message_constructor(parent=self, is_draft=True)

        target_recipients = getattr(new_message, str(recipient_type.value))
        target_recipients.add(recipient)

        return new_message

    def get_profile_photo(self, size=None):
        """Returns the user profile photo

        :param str size: 48x48, 64x64, 96x96, 120x120, 240x240,
         360x360, 432x432, 504x504, and 648x648
        """
        if size is None:
            url = self.build_url(self._endpoints.get('photo'))
        else:
            url = self.build_url(self._endpoints.get('photo_size').format(size=size))

        try:
            response = self.con.get(url)
        except HTTPError as e:
            log.debug(f'Error while retrieving the user profile photo. Error: {e}')
            return None

        if not response:
            return None

        return response.content

    def update_profile_photo(self, photo):
        """ Updates this user profile photo
        :param bytes photo: the photo data in bytes
        """

        url = self.build_url(self._endpoints.get('photo'))
        response = self.con.patch(url, data=photo, headers={'Content-type': 'image/jpeg'})

        return bool(response)


class Directory(ApiComponent):

    _endpoints = {
        'get_user': '/{email}'
    }
    user_constructor = User

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Represents the Active Directory

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

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

    def __repr__(self):
        return 'Active Directory'

    def get_users(self, limit=100, *, query=None, order_by=None, batch=None):
        """ Gets a list of users from the active directory

        When querying the Active Directory the Users endpoint will be used.
        Only a limited set of information will be available unless you have
        access to scope 'User.Read.All' which requires App Administration
        Consent.

        Also using endpoints has some limitations on the querying capabilities.

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
        :return: list of users
        :rtype: list[User] or Pagination
        """

        url = self.build_url('')  # target the main_resource

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
        users = (self.user_constructor(parent=self, **{self._cloud_data_key: user})
                 for user in data.get('value', []))

        next_link = data.get(NEXT_LINK_KEYWORD, None)

        if batch and next_link:
            return Pagination(parent=self, data=users,
                              constructor=self.user_constructor,
                              next_link=next_link, limit=limit)
        else:
            return users

    def _get_user(self, url, query=None):
        """Helper method so DRY"""

        params = {}
        if query:
            if isinstance(query, str):
                params['$filter'] = query
            else:
                params.update(query.as_params())

        response = self.con.get(url, params=params)
        if not response:
            return None

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.user_constructor(parent=self, **{self._cloud_data_key: data})

    def get_user(self, user, query=None):
        """ Returns a User by it's id or user principal name

        :param str user: the user id or user principal name
        :return: User for specified email
        :rtype: User
        """
        url = self.build_url(self._endpoints.get('get_user').format(email=user))
        return self._get_user(url, query=query)

    def get_current_user(self, query=None):
        """ Returns the current logged-in user"""

        if self.main_resource != ME_RESOURCE:
            raise ValueError(f"Can't get the current user. The main resource must be set to '{ME_RESOURCE}'")

        url = self.build_url('')  # target main_resource
        return self._get_user(url, query=query)

    def get_user_manager(self, user, query=None):
        """ Returns a Users' manager by the users id, or user principal name

        :param str user: the user id or user principal name
        :return: User for specified email
        :rtype: User
        """
        url = self.build_url(self._endpoints.get('get_user').format(email=user))
        return self._get_user(url + '/manager', query=query)

    def get_user_direct_reports(self, user, limit=100, *, query=None, order_by=None, batch=None):
        """ Gets a list of direct reports for the user provided from the active directory

        When querying the Active Directory the Users endpoint will be used.

        Also using endpoints has some limitations on the querying capabilities.

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
        :return: list of users
        :rtype: list[User] or Pagination
        """

        url = self.build_url(self._endpoints.get('get_user').format(email=user))

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

        response = self.con.get(url + '/directReports', params=params)
        if not response:
            return iter(())

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        direct_reports = (self.user_constructor(parent=self, **{self._cloud_data_key: user})
            for user in data.get('value', []))

        next_link = data.get(NEXT_LINK_KEYWORD, None)

        if batch and next_link:
            return Pagination(parent=self, data=direct_reports,
                              constructor=self.user_constructor,
                              next_link=next_link, limit=limit)
        else:
            return direct_reports
