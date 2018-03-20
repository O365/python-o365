# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# Created: Alejandro Casanovas
# Title: TITLE
# Description: DESCRIPTION
# -----------------------------------------------------------------------------

# standard library imports

# framework imports

# app specific imports
from O365.connection import Connection, O365_API_VERSION
from O365.message import Message
from O365.inbox import Inbox


class App(object):

    def __init__(self, username=None, password=None, client_id=None, client_secret=None, api_version=O365_API_VERSION, main_resource='me'):
        self.api_version = api_version
        self.main_resource = main_resource
        self.connection = Connection(username=username, password=password, client_id=client_id, client_secret=client_secret)
        self._inbox = None  # lazy instantiation

    def new_message(self):
        """ Creates a new message to be send or stored"""
        return Message(con=self.connection, api_version=self.api_version, main_resource=self.main_resource)

    def inbox(self):
        if self._inbox is None:
            self._inbox = Inbox(self.connection, api_version=self.api_version, main_resource=self.main_resource)
        return self._inbox
