import base64
import logging
from pathlib import Path
from io import BytesIO

from .utils import ApiComponent

log = logging.getLogger(__name__)

UPLOAD_SIZE_LIMIT_SIMPLE = 1024 * 1024 * 3  # 3 MB
DEFAULT_UPLOAD_CHUNK_SIZE = 1024 * 1024 * 3


class AttachableMixin:
    def __init__(self, attachment_name_property=None, attachment_type=None):
        """ Defines the functionality for an object to be attachable.
        Any object that inherits from this class will be attachable
        (if the underlying api allows that)

        """
        self.__attachment_name = None
        self.__attachment_name_property = attachment_name_property
        self.__attachment_type = self._gk(attachment_type)

    @property
    def attachment_name(self):
        """ Name of the attachment

        :getter: get attachment name
        :setter: set new name for the attachment
        :type: str
        """
        if self.__attachment_name is not None:
            return self.__attachment_name
        if self.__attachment_name_property:
            return getattr(self, self.__attachment_name_property, '')
        else:
            # property order resolution:
            # 1) try property 'subject'
            # 2) try property 'name'
            try:
                attachment_name = getattr(self, 'subject')
            except AttributeError:
                attachment_name = getattr(self, 'name', '')
            return attachment_name

    @attachment_name.setter
    def attachment_name(self, value):
        self.__attachment_name = value

    @property
    def attachment_type(self):
        """ Type of attachment

        :rtype: str
        """
        return self.__attachment_type

    def to_api_data(self):
        """ Returns a dict to communicate with the server

        :rtype: dict
        """
        raise NotImplementedError()


class UploadSessionRequest(ApiComponent):

    def __init__(self, parent, attachment):
        super().__init__(protocol=parent.protocol,
                         main_resource=parent.main_resource)
        self._attachment = attachment

    def to_api_data(self):
        attachment_item = {
            self._cc('attachmentType'): self._attachment.attachment_type,
            self._cc('name'): self._attachment.name,
            self._cc('size'): self._attachment.size
        }
        if self._attachment.is_inline:
            attachment_item[self._cc('isInline')] = self._attachment.is_inline
        data = {self._cc('AttachmentItem'): attachment_item}
        return data


class BaseAttachment(ApiComponent):
    """ BaseAttachment class is the base object for dealing with attachments """

    _endpoints = {'attach': '/messages/{id}/attachments'}

    def __init__(self, attachment=None, *, parent=None, **kwargs):
        """ Creates a new attachment, optionally from existing cloud data

        :param attachment: attachment data (dict = cloud data,
         other = user data)
        :type attachment: dict or str or Path or list[str] or AttachableMixin
        :param BaseAttachments parent: the parent Attachments
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        kwargs.setdefault('protocol', getattr(parent, 'protocol', None))
        kwargs.setdefault('main_resource',
                          getattr(parent, 'main_resource', None))

        super().__init__(**kwargs)
        self.name = None
        self.attachment_type = 'file'
        self.attachment_id = None
        self.content_id = None
        self.is_inline = False
        self.attachment = None
        self.content = None
        self.on_disk = False
        self.on_cloud = kwargs.get('on_cloud', False)
        self.size = None

        if attachment:
            if isinstance(attachment, dict):
                if self._cloud_data_key in attachment:
                    # data from the cloud
                    attachment = attachment.get(self._cloud_data_key)
                    self.attachment_id = attachment.get(self._cc('id'), None)
                    self.content_id = attachment.get(self._cc('contentId'), None)
                    self.is_inline = attachment.get(self._cc('IsInline'), False)
                    self.name = attachment.get(self._cc('name'), None)
                    self.content = attachment.get(self._cc('contentBytes'),
                                                  None)
                    self.attachment_type = 'item' if 'item' in attachment.get(
                        '@odata.type', '').lower() else 'file'
                    self.on_disk = False
                    self.size = attachment.get(self._cc('size'), None)
                else:
                    file_path = attachment.get('path', attachment.get('name'))
                    if file_path is None:
                        raise ValueError('Must provide a valid "path" or '
                                         '"name" for the attachment')
                    self.content = attachment.get('content')
                    self.on_disk = attachment.get('on_disk')
                    self.attachment_id = attachment.get('attachment_id')
                    self.attachment = Path(file_path) if self.on_disk else None
                    self.name = (self.attachment.name if self.on_disk
                                 else attachment.get('name'))
                    self.size = self.attachment.stat().st_size if self.attachment else None

            elif isinstance(attachment, str):
                self.attachment = Path(attachment)
                self.name = self.attachment.name
            elif isinstance(attachment, Path):
                self.attachment = attachment
                self.name = self.attachment.name
            elif isinstance(attachment, (tuple, list)):
                # files with custom names or Inmemory objects
                file_obj, custom_name = attachment
                if isinstance(file_obj, BytesIO):
                    # in memory objects
                    self.size = file_obj.getbuffer().nbytes
                    self.content = base64.b64encode(file_obj.getvalue()).decode('utf-8')
                else:
                    self.attachment = Path(file_obj)
                self.name = custom_name

            elif isinstance(attachment, AttachableMixin):
                # Object that can be attached (Message for example)
                self.attachment_type = 'item'
                self.attachment = attachment
                self.name = attachment.attachment_name
                self.content = attachment.to_api_data()
                self.content['@odata.type'] = attachment.attachment_type

            if self.content is None and self.attachment and self.attachment.exists():
                with self.attachment.open('rb') as file:
                    self.content = base64.b64encode(file.read()).decode('utf-8')
                self.on_disk = True
                self.size = self.attachment.stat().st_size

    def __len__(self):
        """ Returns the size of this attachment """
        return self.size

    def __eq__(self, other):
        return self.attachment_id == other.attachment_id

    def to_api_data(self):
        """ Returns a dict to communicate with the server

        :rtype: dict
        """
        data = {'@odata.type': self._gk(
            '{}_attachment_type'.format(self.attachment_type)),
            self._cc('name'): self.name}

        if self.is_inline:
            data[self._cc('isInline')] = self.is_inline
        if self.attachment_type == 'file':
            data[self._cc('contentBytes')] = self.content
            if self.content_id is not None:
                data[self._cc('contentId')] = self.content_id
        else:
            data[self._cc('item')] = self.content

        return data

    def save(self, location=None, custom_name=None):
        """  Save the attachment locally to disk

        :param str location: path string to where the file is to be saved.
        :param str custom_name: a custom name to be saved as
        :return: Success / Failure
        :rtype: bool
        """
        if not self.content:
            return False

        location = Path(location or '')
        if not location.exists():
            log.debug('the location provided does not exist')
            return False

        name = custom_name or self.name
        name = name.replace('/', '-').replace('\\', '')
        try:
            path = location / name
            with path.open('wb') as file:
                file.write(base64.b64decode(self.content))
            self.attachment = path
            self.on_disk = True
            self.size = self.attachment.stat().st_size

            log.debug('file saved locally.')
        except Exception as e:
            log.error('file failed to be saved: %s', str(e))
            return False
        return True

    def attach(self, api_object, on_cloud=False):
        """ Attach this attachment to an existing api_object. This
        BaseAttachment object must be an orphan BaseAttachment created for the
        sole purpose of attach it to something and therefore run this method.

        :param api_object: object to attach to
        :param on_cloud: if the attachment is on cloud or not
        :return: Success / Failure
        :rtype: bool
        """

        if self.on_cloud:
            # item is already saved on the cloud.
            return True

        # api_object must exist and if implements attachments
        # then we can attach to it.
        if api_object and getattr(api_object, 'attachments', None):
            if on_cloud:
                if not api_object.object_id:
                    raise RuntimeError(
                        'A valid object id is needed in order to attach a file')
                # api_object builds its own url using its
                # resource and main configuration
                url = api_object.build_url(self._endpoints.get('attach').format(
                    id=api_object.object_id))

                response = api_object.con.post(url, data=self.to_api_data())

                return bool(response)
            else:
                if self.attachment_type == 'file':
                    api_object.attachments.add([{
                        'attachment_id': self.attachment_id,
                        # TODO: copy attachment id? or set to None?
                        'path': str(
                            self.attachment) if self.attachment else None,
                        'name': self.name,
                        'content': self.content,
                        'on_disk': self.on_disk
                    }])
                else:
                    raise RuntimeError('Only file attachments can be attached')

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Attachment: {}'.format(self.name)


class BaseAttachments(ApiComponent):
    """ A Collection of BaseAttachments """

    _endpoints = {
        'attachments': '/messages/{id}/attachments',
        'attachment': '/messages/{id}/attachments/{ida}'
    }
    _attachment_constructor = BaseAttachment

    def __init__(self, parent, attachments=None):
        """ Attachments must be a list of path strings or dictionary elements

        :param Account parent: parent object
        :param attachments: list of attachments
        :type attachments: list[str] or list[Path] or str or Path or dict
        """
        super().__init__(protocol=parent.protocol,
                         main_resource=parent.main_resource)
        self._parent = parent
        self.__attachments = []
        # holds on_cloud attachments removed from the parent object
        self.__removed_attachments = []
        self.untrack = True
        if attachments:
            self.add(attachments)
        self.untrack = False

    def __iter__(self):
        return iter(self.__attachments)

    def __getitem__(self, key):
        return self.__attachments[key]

    def __contains__(self, item):
        return item in {attachment.name for attachment in self.__attachments}

    def __len__(self):
        return len(self.__attachments)

    def __str__(self):
        attachments = len(self.__attachments)
        parent_has_attachments = getattr(self._parent, 'has_attachments', False)
        if parent_has_attachments and attachments == 0:
            return 'Number of Attachments: unknown'
        else:
            return 'Number of Attachments: {}'.format(attachments)

    def __repr__(self):
        return self.__str__()

    def __bool__(self):
        return bool(len(self.__attachments))

    def to_api_data(self):
        """ Returns a dict to communicate with the server

        :rtype: dict
        """
        return [attachment.to_api_data() for attachment in self.__attachments if
                attachment.on_cloud is False]

    def clear(self):
        """ Clear the attachments """
        for attachment in self.__attachments:
            if attachment.on_cloud:
                self.__removed_attachments.append(attachment)
        self.__attachments = []
        self._update_parent_attachments()
        self._track_changes()

    def _track_changes(self):
        """ Update the track_changes on the parent to reflect
        a needed update on this field """
        if getattr(self._parent, '_track_changes',
                   None) is not None and self.untrack is False:
            # noinspection PyProtectedMember
            self._parent._track_changes.add('attachments')

    def _update_parent_attachments(self):
        """ Tries to update the parent property 'has_attachments' """
        try:
            self._parent.has_attachments = bool(len(self.__attachments))
        except AttributeError:
            pass

    def add(self, attachments):
        """ Add more attachments

        :param attachments: list of attachments
        :type attachments: list[str] or list[Path] or str or Path or dict
        """
        if attachments:
            if isinstance(attachments, (str, Path)):
                attachments = [attachments]
            if isinstance(attachments, (list, tuple, set)):
                # User provided attachments
                attachments_temp = [
                    self._attachment_constructor(attachment, parent=self)
                    for attachment in attachments]
            elif isinstance(attachments,
                            dict) and self._cloud_data_key in attachments:
                # Cloud downloaded attachments. We pass on_cloud=True
                # to track if this attachment is saved on the server
                attachments_temp = [self._attachment_constructor(
                    {self._cloud_data_key: attachment}, parent=self,
                    on_cloud=True)
                    for attachment in
                    attachments.get(self._cloud_data_key, [])]
            else:
                raise ValueError('Attachments must be a str or Path or a '
                                 'list, tuple or set of the former')

            self.__attachments.extend(attachments_temp)
            self._update_parent_attachments()
            self._track_changes()

    def remove(self, attachments):
        """ Remove the specified attachments

        :param attachments: list of attachments
        :type attachments: list[str] or list[Path] or str or Path or dict
        """
        if isinstance(attachments, (list, tuple)):
            attachments = ({attachment.name
                            if isinstance(attachment, BaseAttachment)
                            else attachment for attachment in attachments})
        elif isinstance(attachments, str):
            attachments = {attachments}
        elif isinstance(attachments, BaseAttachment):
            attachments = {attachments.name}
        else:
            raise ValueError('Incorrect parameter type for attachments')

        new_attachments = []
        for attachment in self.__attachments:
            if attachment.name not in attachments:
                new_attachments.append(attachment)
            else:
                if attachment.on_cloud:
                    # add to removed_attachments so later we can delete them
                    self.__removed_attachments.append(
                        attachment)
        self.__attachments = new_attachments
        self._update_parent_attachments()
        self._track_changes()

    def download_attachments(self):
        """ Downloads this message attachments into memory.
        Need a call to 'attachment.save' to save them on disk.

        :return: Success / Failure
        :rtype: bool
        """
        if not self._parent.has_attachments:
            log.debug(
                'Parent {} has no attachments, skipping out early.'.format(
                    self._parent.__class__.__name__))
            return False

        if not self._parent.object_id:
            raise RuntimeError(
                'Attempted to download attachments of an unsaved {}'.format(
                    self._parent.__class__.__name__))

        url = self.build_url(self._endpoints.get('attachments').format(
            id=self._parent.object_id))

        response = self._parent.con.get(url)
        if not response:
            return False

        attachments = response.json().get('value', [])

        # Everything received from cloud must be passed as self._cloud_data_key
        self.untrack = True
        self.add({self._cloud_data_key: attachments})
        self.untrack = False

        # TODO: when it's a item attachment the attachment itself
        #  is not downloaded. We must download it...
        # TODO: idea: retrieve the attachments ids' only with
        #  select and then download one by one.
        return True

    def _update_attachments_to_cloud(self, chunk_size=None):
        """ Push new, unsaved attachments to the cloud and remove removed
        attachments. This method should not be called for non draft messages.
        """
        # ! potentially several api requests can be made by this method.
        chunk_size = chunk_size if chunk_size is not None else DEFAULT_UPLOAD_CHUNK_SIZE

        for attachment in self.__attachments:
            if attachment.on_cloud is False:
                file_size = attachment.size
                if file_size <= UPLOAD_SIZE_LIMIT_SIMPLE:
                    url = self.build_url(self._endpoints.get('attachments').format(
                        id=self._parent.object_id))
                    # upload attachment:
                    response = self._parent.con.post(url, data=attachment.to_api_data())
                    if not response:
                        return False

                    data = response.json()

                    # update attachment data
                    attachment.attachment_id = data.get('id')
                    attachment.content = data.get(self._cc('contentBytes'), None)
                else:
                    # Upload with session
                    url = self.build_url(
                        self._endpoints.get('create_upload_session').format(
                            id=self._parent.object_id))

                    request = UploadSessionRequest(parent=self, attachment=attachment)
                    file_data = request.to_api_data()
                    response = self._parent.con.post(url, data=file_data)
                    if not response:
                        return False

                    data = response.json()

                    upload_url = data.get(self._cc('uploadUrl'), None)
                    log.info('Resumable upload on url: {}'.format(upload_url))
                    expiration_date = data.get(self._cc('expirationDateTime'), None)
                    if expiration_date:
                        log.info('Expiration Date for this upload url is: {}'.format(
                            expiration_date))
                    if upload_url is None:
                        log.error('Create upload session response without '
                                  'upload_url for file {}'.format(attachment.name))
                        return False

                    def write_stream(read_byte_chunk):
                        current_bytes = 0
                        while True:
                            data = read_byte_chunk()
                            if not data:
                                break
                            transfer_bytes = len(data)
                            headers = {
                                'Content-type': 'application/octet-stream',
                                'Content-Length': str(len(data)),
                                'Content-Range': 'bytes {}-{}/{}'
                                                 ''.format(current_bytes,
                                                           current_bytes +
                                                           transfer_bytes - 1,
                                                           file_size)
                            }
                            current_bytes += transfer_bytes

                            # this request mut NOT send the authorization header.
                            # so we use a naive simple request.
                            response = self._parent.con.naive_request(upload_url, 'PUT',
                                                              data=data,
                                                              headers=headers)
                            if not response:
                                return False

                            if response.status_code == 201:
                                # file is completed
                                break
                            else:  # Usually 200
                                data = response.json()
                                log.debug('Successfully put {} bytes'.format(
                                    data.get("nextExpectedRanges")))
                        return True

                    if attachment.attachment:
                        with attachment.attachment.open(mode='rb') as file:
                            read_from_file = lambda : file.read(chunk_size)
                            upload_completed = write_stream(read_byte_chunk=read_from_file)
                    else:
                        buffer = BytesIO(base64.b64decode(attachment.content))
                        read_byte_chunk = lambda : buffer.read(chunk_size)
                        upload_completed = write_stream(read_byte_chunk=read_byte_chunk)

                    if not upload_completed:
                        return False

                attachment.on_cloud = True

        for attachment in self.__removed_attachments:
            if attachment.on_cloud and attachment.attachment_id is not None:
                # delete attachment
                url = self.build_url(self._endpoints.get('attachment').format(
                    id=self._parent.object_id, ida=attachment.attachment_id))

                response = self._parent.con.delete(url)
                if not response:
                    return False

        self.__removed_attachments = []  # reset the removed attachments

        log.debug('Successfully updated attachments on {}'.format(
            self._parent.object_id))

        return True

