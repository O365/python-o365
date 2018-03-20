import logging
import json
import requests

from O365.connection import BaseApi
from O365.message import Message

log = logging.getLogger(__name__)


class Inbox(BaseApi):
    """
    Wrapper class for an inbox which mostly holds a list of messages.
    Methods:
        getMessages -- downloads messages to local memory.
    """
    _endpoints = {
        'list': '/messages',
    }

    def __init__(self, con, **kwargs):
        """
        Creates a new inbox wrapper.
        """
        super().__init__(**kwargs)
        self.con = con
        self.filters = {'unread': 'IsRead eq false'}

    def get_messages(self, query=None, join_query='or', order_by=None, limit=10, download_attachments=False):
        """
        Downloads messages to local memory.

        You create an inbox to be the container class for messages, this method
        then pulls those messages down to the local disk. This is called in the
        init method, so it's kind of pointless for you. Unless you think new
        messages have come in.

        You can filter only certain emails by setting filters. See the set and
        get filters methods for more information.

                Returns true if there are messages. Returns false if there were no
                messages available that matched the filters specified.
        """

        log.debug('fetching messages.')
        url = self._build_url(self._endpoints.get('list'))

        params = {'$top': limit}

        if query:
            if isinstance(query, str):
                query = [query]  # convert to list
            query = [self.filters.get(q, q) for q in query]  # get templated filters
            query_str = ' {} '.format(join_query).join(query)  # convert to query string
            params['$filter'] = query_str

        if order_by:
            params['$orderby'] = order_by

        response = self.con.get(url, params=params)
        log.info('Response from O365: %s', str(response))

        if response.status_code != 200:
            return False, []

        messages = response.json().get('value', [])

        return True, [Message(self.con, download_attachments=download_attachments, **message) for message in messages]

#     def getFilter(self):
#         '''get the value set for a specific filter, if exists, else None'''
#         return self.filters
#
#     def setFilter(self, f_string):
#         '''
# 		Set the value of a filter. More information on what filters are available
# 		can be found here:
# 		https://msdn.microsoft.com/office/office365/APi/complex-types-for-mail-contacts-calendar#RESTAPIResourcesMessage
# 		I may in the future have the ability to add these in yourself. but right now that is to complicated.
#
# 		Arguments:
# 			f_string -- The string that represents the filters you want to enact.
# 				should be something like: (HasAttachments eq true) and (IsRead eq false)
# 				or just: IsRead eq false
# 				test your filter stirng here: https://outlook.office365.com/api/v1.0/me/messages?$filter=
# 				if that accepts it then you know it works.
# 		'''
#         self.filters = f_string
#         return True
#
# # To the King!
