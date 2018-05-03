import logging

import requests

from O365.message import Message

log = logging.getLogger(__name__)


class Inbox(object):
    '''
    Wrapper class for an inbox which mostly holds a list of messages.

    Methods:
        getMessages -- downloads messages to local memory.

    Variables:
        inbox_url -- url used for fetching emails.
    '''
    # url for fetching emails. Takes a flag for whether they are read or not.
    inbox_url = 'https://outlook.office365.com/api/v1.0/me/messages'

    def __init__(self, auth, getNow=True, verify=True):
        '''
        Creates a new inbox wrapper. Send email and password for authentication.

        set getNow to false if you don't want to immedeatly download new messages.
        '''

        log.debug('creating inbox for the email %s', auth[0])
        self.auth = auth
        self.messages = []
        self.errors = ''

        self.filters = ''
        self.order_by = ''
        self.verify = verify

        if getNow:
            self.filters = 'IsRead eq false'
            self.getMessages()

    def getMessages(self, number=10):
        '''
        Downloads messages to local memory.

        You create an inbox to be the container class for messages, this method
        then pulls those messages down to the local disk. This is called in the
        init method, so it's kind of pointless for you. Unless you think new
        messages have come in.

        You can filter only certain emails by setting filters. See the set and
        get filters methods for more information.

                Returns true if there are messages. Returns false if there were no
                messages available that matched the filters specified.
        '''

        log.debug('fetching messages.')
        response = requests.get(self.inbox_url, auth=self.auth,
                                params={'$orderby': self.order_by, '$filter': self.filters, '$top': number},
                                verify=self.verify)
        if response.status_code in [400, 500]:
            self.errors = response.text
            return False
        elif response.status_code in [401]:
            self.errors = response.reason
            return False

        log.info('Response from O365: %s', str(response))

        # check that there are messages
        try:
            response.json()['value']
        except KeyError as e:
            log.debug('no messages')
            return False

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

    def getErrors(self):
        return self.errors

    def getOrderBy(self):
        return self.order_by

    def setOrderBy(self, f_string):
        '''
        For example 'DateTimeReceived desc'
        '''
        self.order_by = f_string
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
