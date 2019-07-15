import datetime as dt
import logging

import pytz
# noinspection PyPep8Naming
from bs4 import BeautifulSoup as bs
from dateutil.parser import parse

from .utils import CaseEnum
from .utils import HandleRecipientsMixin
from .utils import AttachableMixin, ImportanceLevel, TrackerSet
from .utils import BaseAttachments, BaseAttachment
from .utils import Pagination, NEXT_LINK_KEYWORD, ApiComponent
from .utils.windows_tz import get_windows_tz
from .utils.catcolor import MasterCategoryColorDefinition, MasterCategoryColorPreset



class UserSettings(ApiComponent):
    _endpoints = {
        'supported_timezones': '/outlook/supportedTimeZones',
        'master_categories': '/outlook/masterCategories',
        'supported_languages': '/outlook/supportedLanguages',
    }

    def __init__(self, *, parent=None, con=None, **kwargs):

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
        return 'Schedule resource: {}'.format(self.main_resource)



    def get_categories(self):
        '''Returns the Master Categories for the current user
        PS this requires the permission: MailboxSettings.Read
        https://docs.microsoft.com/en-us/graph/api/outlookuser-list-mastercategories
        :return: list of items merged with the standard colour definitions
        :rtype: dictionary list
        '''

        url = self.build_url(self._endpoints.get('master_categories'))
        response = self.con.get(url)
        if not response:
            return None

        data = response.json().get('value')
        if data is None:
            return None

        calcolPreset = MasterCategoryColorPreset()
        for catitem in data:
            catcolitem = calcolPreset.get_item_fromoutlook(catitem.get('color'))
            catitem['color'] = catcolitem.__dict__

        return data



    def get_supportedLanguages(self):
        '''Get the list of locales and languages that are supported for the user,
         as configured on the user's mailbox server.
        https://docs.microsoft.com/en-us/graph/api/outlookuser-supportedlanguages       
        :rtype: dictionary list
        '''

        url = self.build_url(self._endpoints.get('supported_languages'))
        response = self.con.get(url)
        if not response:
            return None

        data = response.json().get('value')
        if data is None:
            return None

        return data



    def get_supportedTimeZones(self):
        '''Get the list of time zones that are supported for the user,
         as configured on the user's mailbox server.
        https://docs.microsoft.com/en-us/graph/api/outlookuser-supportedtimezones       
        :rtype: dictionary list
        '''

        url = self.build_url(self._endpoints.get('supported_timezones'))
        response = self.con.get(url)
        if not response:
            return None

        data = response.json().get('value')
        if data is None:
            return None

        return data
