import logging
import json
import copy
import O365

log = logging.getLogger(__name__)

class O365Handler(logging.Handler):
	'''
	Logging handler for sending O365 emails
	'''

	def __init__(self, *args, **kwargs):
		'''
		Creates a new logging handler for sending O365 messages

		The parameters for initialization are the same for O365.Message.

		If the handler is initialized with a JSON parameter, that will be used
		as a default message structure.

		If a new record has a message that can be deserialized by JSON.loads(),
		its message will be used to create a new O365 message. If the message
		can't be deserialized, the message will be appended to the body of the
		handler's default O365 message.

		If a new record is received and the handler was initialized with a
		default JSON format, the record's message will be appended to the end
		of the default messsage's body prior to being sent.
		'''

		super(O365Handler, self).__init__()

		self._defaultMessage = O365.Message(*args, **kwargs)

	def emit(self, record):
		'''
		Handles emitting a record

		Arguments
		record -- the record to handle
		'''

		# We'll need to try to use our default message to send this, so start
		# by making a copy
		message = copy.deepcopy(self._defaultMessage)

		# If we can deserialize this record's message, use that to try to send
		# the message
		try:
			message.json = json.loads(record.getMessage())
			message.sendMessage()
			return
		except Exception as e:
			pass

		# There could be a few things missing from the various dictionaries,
		# and the dictionary layout might change, so just be cheap and wrap
		# this in a dictionary try/catch.
		try:
			defaultMessageBody = self._defaultMessage.getBody()

			# We already have a body, so append to the end
			message.setBody("{}{}".format(defaultMessageBody, record.getMessage()))

		except KeyError:
			# We don't have a body yet, so just set the record's message as the
			# body
			message.setBody(record.getMessage())

		# Send!
		try:
			message.sendMessage()
		except Exception as e:
			log.info('Could not send message: {}'.format(str(e)))
