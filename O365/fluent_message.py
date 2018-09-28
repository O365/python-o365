import logging

from .message import Message
from .utils import fluent, action

log = logging.getLogger(__name__)


class FluentMessage(object):
    """ Makes a wrapper for message object
    to make fluent api calls for sending

    :param message: Message object to wrap in fluent api
    :param json_data: Takes json if you have a pre-existing message to
     create from. this is mostly used inside the library for
     when new messages are downloaded.
    :param verify: whether or not to verify SSL certificate
    """

    def __init__(self, message=None, json_data=None, verify=True):
        """ Makes a wrapper for message object
        to make fluent api calls for sending

        :param message: Message object to wrap in fluent api
        :param json_data: Takes json if you have a pre-existing message to
         create from. this is mostly used inside the library for
         when new messages are downloaded.
        :param verify: whether or not to verify SSL certificate
        """
        if message:
            self._real_message = message

        else:
            self._real_message = Message(json_data=json_data, verify=verify)

        self._success = None
        self._error_message = None

    @property
    def is_success(self):
        """ Returns if the previous action is success or not

        :return: True or False
        :rtype: bool
        """
        return self._success

    @property
    def error_message(self):
        """ Returns the error message if any for the previous action

        :return: Error Message
        :rtype: str
        """
        return self._error_message

    def extract(self):
        """ Unwraps the message object from fluent api for general usage

        :return: Underlying message object
        :rtype: Message
        """
        return self._real_message

    @fluent
    def to(self, *recipients):
        """ Set the `TO` recipients list.

            Each recipient can be either of the below:

            :type: dict - this must to be a dictionary formatted as such

                .. code-block:: json

                    {
                        "EmailAddress": {
                            "Address":"user@domain.com"
                        }
                    }

                with other options such as "Name" with address. but at minimum
                it must have this.
            :type: str - simple email address in form of "user@domain.com"
            :type: Contact - Contact object (Contact is part of this library)
            :type: Group - Group object, which is a list of contacts
             (Group is part of this library)

        :param recipients: List of recipients
        :return: copy of this object
        :rtype: FluentMessage
        """
        self._real_message._set_recipients(*recipients, 'to')
        return self

    @fluent
    def cc(self, *recipients):
        """ Set the `CC` recipients list.

            Each recipient can be either of the below:

            :type: dict - this must to be a dictionary formatted as such

                .. code-block:: json

                    {
                        "EmailAddress": {
                            "Address":"user@domain.com"
                        }
                    }

                with other options such as "Name" with address. but at minimum
                it must have this.
            :type: str - simple email address in form of "user@domain.com"
            :type: Contact - Contact object (Contact is part of this library)
            :type: Group - Group object, which is a list of contacts
             (Group is part of this library)

        :param recipients: List of recipients
        :return: copy of this object
        :rtype: FluentMessage
        """
        self._real_message._set_recipients(*recipients, 'cc')
        return self

    @fluent
    def bcc(self, *recipients):
        """ Set the `BCC` recipients list.

            Each recipient can be either of the below:

            :type: dict - this must to be a dictionary formatted as such

                .. code-block:: json

                    {
                        "EmailAddress": {
                            "Address":"user@domain.com"
                        }
                    }

                with other options such as "Name" with address. but at minimum
                it must have this.
            :type: str - simple email address in form of "user@domain.com"
            :type: Contact - Contact object (Contact is part of this library)
            :type: Group - Group object, which is a list of contacts
             (Group is part of this library)

        :param recipients: List of recipients
        :return: copy of this object
        :rtype: FluentMessage
        """
        self._real_message._set_recipients(*recipients, 'bcc')
        return self

    @fluent
    def subject(self, text):
        """ Set the subject of the message

        :param text: text to set as subject
        :return: copy of this object
        :rtype: FluentMessage
        """
        self._real_message.subject = text
        return self

    @fluent
    def body(self, text):
        """ Set the body of the message

        :param text: text content to set as body
        :return: copy of this object
        :rtype: FluentMessage
        """
        self._real_message.body = text
        return self

    @fluent
    def html_body(self, text):
        """ Set the body of the message using a html

        :param text: html text to set as body
        :return: copy of this object
        :rtype: FluentMessage
        """
        self._real_message.set_html_body(text)
        return self

    @action
    @fluent
    def send(self, user_id=None, **kwargs):
        """ Send the email

        :param user_id: User id (email) if sending as other user
        :return: copy of this object
        :rtype: FluentMessage
        """
        self._success, self._error_message = \
            self._real_message.send(user_id=user_id,
                                    return_status=True,
                                    **kwargs)
        return self
