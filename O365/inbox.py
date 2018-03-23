import logging

from O365.connection import ApiComponent
from O365.message import Message

log = logging.getLogger(__name__)


class Inbox(ApiComponent):
    """ Inbox Class to Handle Messages (filter, update, delete, etc.) """

    _endpoints = {'list': '/messages'}

    def __init__(self, *, parent=None, con=None, **kwargs):

        assert parent or con, 'Need a parent or a connection'
        self.con = parent.con if parent else con

        # get the main_resource passed in kwargs over the parent main_resource
        main_resource = kwargs.pop('main_resource', None)
        if main_resource is None:
            main_resource = getattr(parent, 'main_resource', None) if parent else None
        super().__init__(auth_method=self.con.auth_method, api_version=self.con.api_version,
                         main_resource=main_resource)

        self.filter_templates = {'unread': 'IsRead eq false'}

    def __str__(self):
        return 'Inbox resource: {}'.format(self.main_resource)

    def __repr__(self):
        return self.__str__()

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
            query = [self.filter_templates.get(q, q) for q in query]  # get templated filters
            query_str = ' {} '.format(join_query).join(query)  # convert to query string
            params['$filter'] = query_str

        if order_by:
            params['$orderby'] = order_by

        try:
            response = self.con.get(url, params=params)
        except Exception as e:
            log.error('Error while donwloading messages')
            return False, []

        log.info('Response from O365: %s', str(response))

        if response.status_code != 200:
            return False, []

        messages = response.json().get('value', [])

        # Everything received from the cloud must be passed with self._cloud_data_key
        return True, [Message(parent=self, download_attachments=download_attachments, **{self._cloud_data_key: message})
                      for message in messages]

