from O365.message import Message
import logging
import json
import requests

log = logging.getLogger(__name__)

from .connection import Connection


class FluentInbox(object):
    url_dict = {
        'inbox': {
            '1.0': 'https://outlook.office365.com/api/v1.0/me/messages',
            '2.0': 'https://outlook.office365.com/api/v2.0/me/messages',
        },

        'folders': {
            '1.0': 'https://outlook.office365.com/api/v1.0/me/Folders',
            '2.0': 'https://outlook.office365.com/api/v2.0/me/MailFolders',
        },

        'folder': {
            '1.0': 'https://outlook.office365.com/api/v1.0/me/Folders/{folder_id}/messages',
            '2.0': 'https://outlook.office365.com/api/v2.0/me/MailFolders/{folder_id}/messages',
        },
    }

    def __init__(self, verify=True):
        """ Creates a new inbox wrapper.

        :param verify: whether or not to verify SSL certificate
        """
        if not Connection.instance or not Connection.instance.auth:
            raise RuntimeError('Connection is not configured, please use O365.Connection to set username and password')

        self.url = FluentInbox._get_url('inbox')
        self.fetched_count = 0
        self._filter = ''
        self._search = ''
        self.verify = verify
        self.messages = []

    def from_folder(self, folder_name):
        """ Configure to use this folder for fetching the mails

        :param folder_name: name of the outlook folder
        """
        self._reset()
        response = self._get_response(FluentInbox._get_url('folders'), params={'$top': 100})

        folder_id = None
        all_folders = []

        for folder in response.json()['value']:
            if folder['DisplayName'] == folder_name:
                folder_id = folder['Id']
                break

            all_folders.append(folder['DisplayName'])

        if not folder_id:
            raise RuntimeError('Folder "{}" is not found, available folders are {}'.format(folder_name, all_folders))

        self.url = FluentInbox._get_url('folder').format(folder_id=folder_id)

        return self

    def filter(self, filter_string):
        self._filter = filter_string
        return self

    def search(self, search_string):
        self._search = search_string
        return self

    def fetch_first(self, count=10):
        self.fetched_count = 0
        return self.fetch_next(count=count)

    def skip(self, count):
        self.fetched_count = count
        return self

    def fetch(self, count=10):
        return self.fetch_next(count=count)

    def fetch_next(self, count=1):
        skip_count = self.fetched_count
        if self._search:
            params = {'$filter': self._filter, '$top': count, '$search': '"{}"'.format(self._search)}
        else:
            params = {'$filter': self._filter, '$top': count, '$skip': skip_count}

        response = self._get_response(self.url, params=params)
        log.info('Received response from url'.format(response.url))
        self.fetched_count += count

        messages = []
        for message in response.json()['value']:
            messages.append(Message(message, Connection.instance.auth))

        return messages

    @staticmethod
    def _get_url(topic):
        return FluentInbox.url_dict[topic][Connection.instance.api_version]

    def _reset(self):
        self.fetched_count = 0
        self.messages = []

    def _get_response(self, request_url, **kwargs):
        defaults = {
            'auth': Connection.instance.auth,
            'verify': self.verify
        }
        defaults.update(kwargs)
        return requests.get(request_url, **defaults)

    def getMessages(self, number=10):
        '''
        Downloads messages to local memory.

        You create an inbox to be the container class for messages, this method
        then pulls those messages down to the local disk. This is called in the
        init method, so it's kind of pointless for you. Unless you think new
        messages have come in.

        You can filter only certain emails by setting filters. See the set and
        get filters methods for more information.
        '''

        log.debug('fetching messages.')
        response = requests.get(self.inbox_url, auth=self.auth, params={'$filter': self.filters, '$top': number},
                                verify=self.verify)
        log.info('Response from O365: %s', str(response))

        for message in response.json()['value']:
            try:
                duplicate = False
                for i, m in enumerate(self.messages):
                    if message['Id'] == m.json['Id']:
                        self.messages[i] = Message(message, self.auth)
                        duplicate = True
                        break

                if not duplicate:
                    self.messages.append(Message(message, self.auth))

                log.debug('appended message: %s', message['Subject'])
            except Exception as e:
                log.info('failed to append message: %', str(e))

        log.debug('all messages retrieved and put in to the list.')
        return True

    def getFilter(self):
        '''get the value set for a specific filter, if exists, else None'''
        return self.filters

    def setFilter(self, f_string):
        '''
        Set the value of a filter. More information on what filters are available
        can be found here:
        https://msdn.microsoft.com/office/office365/APi/complex-types-for-mail-contacts-calendar#RESTAPIResourcesMessage
        I may in the future have the ability to add these in yourself. but right now that is to complicated.

        Arguments:
            f_string -- The string that represents the filters you want to enact.
                should be something like: (HasAttachments eq true) and (IsRead eq false)
                or just: IsRead eq false
                test your filter stirng here: https://outlook.office365.com/api/v1.0/me/messages?$filter=
                if that accepts it then you know it works.
        '''
        self.filters = f_string
        return True

# To the King!
