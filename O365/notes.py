import logging

from dateutil.parser import parse

from .utils import ApiComponent
from .utils import Pagination, NEXT_LINK_KEYWORD

log = logging.getLogger(__name__)


class Page(ApiComponent):
    _endpoints = {
        'content': '/onenote/pages/{id}/content'
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        cc = self._cc
        self.object_id = cloud_data.get(cc('id'), kwargs.get('object_id', None))
        self.created = cloud_data.get(cc('createdDateTime'), None)
        self.modified = cloud_data.get(cc('lastModifiedDateTime'), None)

        local_tz = self.protocol.timezone
        self.created = parse(self.created).astimezone(
            local_tz) if self.created else None
        self.modified = parse(self.modified).astimezone(
            local_tz) if self.modified else None

        self.title = cloud_data.get(cc('title'), '')
        self.web_link = cloud_data.get(cc('links'), {}).get(cc('oneNoteWebUrl'), {}).get(cc('href'), '')
        self.onenote_link = cloud_data.get(cc('links'), {}).get(cc('oneNoteClientUrl'), {}).get(cc('href'), '')
        self.__content = None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Page: {}'.format(self.title)

    @property
    def content(self):
        if not self.__content:
            url = self.build_url(self._endpoints.get('content').format(id=self.object_id))
            response = self.con.get(url)
            self.__content = response.content.decode('utf-8')
        return self.__content


class Section(ApiComponent):
    _endpoints = {
        'pages': '/onenote/sections/{id}/pages'
    }
    page_constructor = Page

    def __init__(self, *, parent=None, con=None, **kwargs):
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        cc = self._cc
        self.object_id = cloud_data.get(cc('id'), kwargs.get('object_id', None))
        self.created = cloud_data.get(cc('createdDateTime'), None)
        self.modified = cloud_data.get(cc('lastModifiedDateTime'), None)
        self.display_name = cloud_data.get(self._cc('displayName'), '')

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Section: {}'.format(self.display_name)

    def get_pages(self, limit=25):
        url = self.build_url(self._endpoints.get('pages').format(id=self.object_id))

        response = self.con.get(url)
        
        data = response.json()

        pages = (self.page_constructor(
            parent=self,
            **{self._cloud_data_key: page})
            for page in data.get('value', []))

        next_link = data.get(NEXT_LINK_KEYWORD, None)
        if next_link:
            return Pagination(parent=self, data=pages,
                              constructor=self.page_constructor,
                              next_link=next_link, limit=limit,
                            )
        else:
            return pages


class NoteBook(ApiComponent):
    _endpoints = {
        'sections': '/onenote/notebooks/{id}/sections'
    }
    section_constructor = Section

    def __init__(self, *, parent=None, con=None, **kwargs):
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        cc = self._cc
        self.object_id = cloud_data.get(cc('id'), kwargs.get('object_id', None))
        self.created = cloud_data.get(cc('createdDateTime'), None)
        self.modified = cloud_data.get(cc('lastModifiedDateTime'), None)
        self.display_name = cloud_data.get(self._cc('displayName'), '')
    
    def get_sections(self):
        url = self.build_url(self._endpoints.get('sections').format(id=self.object_id))
        response = self.con.get(url)
        data = response.json()
        sections = (self.section_constructor(
            parent=self,
            **{self._cloud_data_key: section})
            for section in data.get('value', []))
        return sections

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Notebook: {}'.format(self.display_name)


class Notes(ApiComponent):
    """ A Microsoft OneNote"""

    _endpoints = {
        'root_notebooks': '/onenote/notebooks',
        'get_notebook': '/onenote/notebooks/{id}'
    }
    notebook_constructor = NoteBook

    def __init__(self, *, parent=None, con=None, **kwargs):
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

    def list_notebooks(self):
        url = self.build_url(self._endpoints.get('root_notebooks'))

        response = self.con.get(url)

        data = response.json()

        notes = (self.notebook_constructor(
            parent=self,
            **{self._cloud_data_key: notebook})
            for notebook in data.get('value', []))

        return notes

    def get_notebook(self, notebook_id=None):
        """ Returns a notebook by it's id

        :param str notebook_id: the notebook id to be retrieved.
        :return: notebook for the given info
        :rtype: NoteBook
        """

        if not notebook_id:
            raise RuntimeError('Provide notebook id option')

        url = self.build_url(self._endpoints.get('get_notebook').format(id=notebook_id))

        response = self.con.get(url)

        data = response.json()

        notebook = self.notebook_constructor(
            parent=self,
            **{self._cloud_data_key: data}
        )

        return notebook
