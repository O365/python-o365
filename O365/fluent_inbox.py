import logging

from O365.connection import Connection
from O365.fluent_message import Message

log = logging.getLogger(__name__)


class FluentInbox(object):
	url_dict = {
		'inbox': {
			'1.0': 'https://outlook.office365.com/api/v1.0/me/messages',
			'2.0': 'https://graph.microsoft.com/v1.0/me/messages',
		},
		'folders': {
			'1.0': 'https://outlook.office365.com/api/v1.0/me/Folders',
			'2.0': 'https://graph.microsoft.com/v1.0/me/MailFolders',
		},
		'folder': {
			'1.0': 'https://outlook.office365.com/api/v1.0/me/Folders/{folder_id}/messages',
			'2.0': 'https://graph.microsoft.com/v1.0/me/MailFolders/{folder_id}/messages',
		},
		'child_folders': {
			'1.0': 'https://outlook.office365.com/api/v1.0/me/Folders/{folder_id}/childfolders',
			'2.0': 'https://graph.microsoft.com/v1.0/me/MailFolders/{folder_id}/childfolders',
		},
		'user_folders': {
			'1.0': 'https://outlook.office365.com/api/v1.0/users/{user_id}/Folders',
			'2.0': 'https://graph.microsoft.com/v1.0/users/{user_id}/MailFolders',
		},
		'user_folder': {
			'1.0': 'https://outlook.office365.com/api/v1.0/users/{user_id}/Folders/{folder_id}/messages',
			'2.0': 'https://graph.microsoft.com/v1.0/users/{user_id}/MailFolders/{folder_id}/messages',
		},
		'user_child_folders': {
			'1.0': 'https://outlook.office365.com/api/v1.0/users/{user_id}/Folders/{folder_id}/childfolders',
			'2.0': 'https://graph.microsoft.com/v1.0/users/{user_id}/MailFolders/{folder_id}/childfolders',
		}
	}

	def __init__(self, verify=True):
		""" Creates a new inbox wrapper.

		:param verify: whether or not to verify SSL certificate
		"""
		self.url = FluentInbox._get_url('inbox')
		self.fetched_count = 0
		self._filter = ''
		self._search = ''
		self.verify = verify
		self.messages = []

	def from_folder(self, folder_name, user_id=None):
		""" Configure to use this folder for fetching the mails

		:param folder_name: name of the outlook folder
		:param user_id: user id the folder belongs to (shared mailboxes)
		"""
		self._reset()

		folder_id = self.get_folder(value=folder_name,
									by='DisplayName',
									user_id=user_id)['Id']

		if user_id:
			self.url = FluentInbox._get_url('user_folder').format(
				user_id=user_id, folder_id=folder_id)
		else:
			self.url = FluentInbox._get_url('folder').format(
				folder_id=folder_id)

		return self

	def get_folder(self, value, by='Id', parent_id=None, user_id=None):
		"""
		Return a folder by a given attribute.  If multiple folders exist by
		this attribute, only the first will be returned

		Example:
		   get_folder(by='DisplayName', value='Inbox')

		   or

		   get_folder(by='Id', value='AAKrWFG...')

		   Would both return the requested folder attributes

		:param value: Value that we are searching for
		:param by: Search on this key (default: Id)
		:param user_id: user id the folder belongs to (shared mailboxes)
		:returns: Single folder data
		"""
		if parent_id and user_id:
			folders_url = FluentInbox._get_url('user_child_folders').format(
				folder_id=parent_id, user_id=user_id)
		elif parent_id:
			folders_url = FluentInbox._get_url('child_folders').format(
				folder_id=parent_id)
		elif user_id:
			folders_url = FluentInbox._get_url('user_folders').format(
				user_id=user_id)
		else:
			folders_url = FluentInbox._get_url('folders')

		response = Connection.get_response(folders_url,
										   verify=self.verify,
										   params={'$top': 100})

		folder_id = None
		all_folders = []

		for folder in response:
			if folder[by] == value:
				return(folder)

			all_folders.append(folder['displayName'])

		if not folder_id:
			raise RuntimeError(
				'Folder "{}" is not found by "{}", available folders '
				'are {}'.format(value, by, all_folders))

	def list_folders(self, parent_id=None, user_id=None):
		"""
		:param parent_id: Id of parent folder to list.  Default to top folder
		:return: List of all folder data
		"""
		if parent_id and user_id:
			folders_url = FluentInbox._get_url('user_child_folders').format(
				folder_id=parent_id, user_id=user_id)
		elif parent_id:
			folders_url = FluentInbox._get_url('child_folders').format(
				folder_id=parent_id)
		elif user_id:
			folders_url = FluentInbox._get_url('user_folders').format(
				user_id=user_id)
		else:
			folders_url = FluentInbox._get_url('folders')

		response = Connection.get_response(folders_url,
										   verify=self.verify,
										   params={'$top': 100})

		folders = []
		for folder in response:
			folders.append(folder)

		return folders

	def filter(self, filter_string):
		""" Set the value of a filter. More information on what filters are available can be found here:
		https://msdn.microsoft.com/office/office365/APi/complex-types-for-mail-contacts-calendar#RESTAPIResourcesMessage
		More improvements coming soon

		:param filter_string: The string that represents the filters you want to enact.
				should be something like: (HasAttachments eq true) and (IsRead eq false) or just: IsRead eq false
				test your filter string here: https://outlook.office365.com/api/v1.0/me/messages?$filter=
				if that accepts it then you know it works.
		"""
		self._filter = filter_string
		return self

	def search(self, search_string):
		""" Set the value of a search. More information on what searches are available can be found here:
		https://msdn.microsoft.com/office/office365/APi/complex-types-for-mail-contacts-calendar#RESTAPIResourcesMessage
		More improvements coming soon

		:param search_string: The search string you want to use

		Should be something like: "Category:Action AND Subject:Test" or just: "Subject:Test".

		Test your search string here: "https://outlook.office365.com/api/v1.0/me/messages?$search="
		or directly in your mailbox, if that accepts it then you know it works.
		"""
		self._search = search_string
		return self

	def fetch_first(self, count=10):
		""" Fetch the first n messages, where n is the specified count

		:param count: no.of messages to fetch
		"""
		self.fetched_count = 0
		return self.fetch_next(count=count)

	def skip(self, count):
		""" Skips the first n messages, where n is the specified count

		:param count: no.of messages to skip
		"""
		self.fetched_count = count
		return self

	def fetch(self, count=10):
		""" Fetch n messages from the result, where n is the specified count

		:param count: no.of messages to fetch
		"""
		return self.fetch_next(count=count)

	def fetch_next(self, count=1):
		""" Fetch the next n messages after the previous fetch, where n is the specified count

		:param count: no.of messages to fetch
		"""
		skip_count = self.fetched_count
		if self._search:
			params = {'$filter': self._filter, '$top': count,
					  '$search': '"{}"'.format(self._search)}
		else:
			params = {'$filter': self._filter, '$top': count,
					  '$skip': skip_count}

		response = Connection.get_response(self.url, verify=self.verify,
										   params=params)
		self.fetched_count += count

		connection = Connection()
		messages = []
		for message in response:
			messages.append(Message(message, connection.auth, oauth=connection.oauth))

		return messages

	@staticmethod
	def _get_url(key):
		""" Fetches the url for specified key as per the connection version configured

		:param key: the key for which url is required
		:return: URL to use for requests
		"""
		return FluentInbox.url_dict[key][Connection().api_version]

	def _reset(self):
		""" Resets the current reference """
		self.fetched_count = 0
		self.messages = []
