from enum import Enum, auto

from .utils import ApiComponent


class CategoryColor(Enum):
    def _generate_next_value_(name, start, count, last_values):
        return 'preset{}'.format(count)
    RED = auto()  # 0
    ORANGE = auto()  # 1
    BROWN = auto()  # 2
    YELLOW = auto()  # 3
    GREEN = auto()  # 4
    TEAL = auto()  # 5
    OLIVE = auto()  # 6
    BLUE = auto()  # 7
    PURPLE = auto()  # 8
    CRANBERRY = auto()  # 9
    STEEL = auto()  # 10
    DARKSTEEL = auto()  # 11
    GRAY = auto()  # 12
    DARKGREY = auto()  # 13
    BLACK = auto()  # 14
    DARKRED = auto()  # 15
    DARKORANGE = auto()  # 16
    DARKBROWN = auto()  # 17
    DARKYELLOW = auto()  # 18
    DARKGREEN = auto()  # 19
    DARKTEAL = auto()  # 20
    DARKOLIVE = auto()  # 21
    DARKBLUE = auto()  # 22
    DARKPURPLE = auto()  # 23
    DARKCRANBERRY = auto()  # 24

    @classmethod
    def get(cls, color):
        """
        Gets a color by name or value.
        Raises ValueError if not found whithin the collection of colors.
        """
        try:
            return cls(color.capitalize())  # 'preset0' to 'Preset0'
        except ValueError:
            pass
        try:
            return cls[color.upper()]  # 'red' to 'RED'
        except KeyError:
            raise ValueError('color is not a valid color from CategoryColor') from None


class Category(ApiComponent):

    _endpoints = {
        'update': '/outlook/masterCategories/{id}'
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """
        Represents a category by which a user can group Outlook
         items such as messages and events.
        It can be used in conjunction with Event, Message, Contact and Post.

        :param parent: parent object
        :type parent: Account
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """

        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id')
        self.name = cloud_data.get(self._cc('displayName'))
        color = cloud_data.get(self._cc('color'))
        self.color = CategoryColor(color) if color else None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '{} (color: {})'.format(self.name, self.color.name if self.color else None)

    def update_color(self, color):
        """
        Updates this Category color
        :param None or str or CategoryColor color: the category color
        """
        url = self.build_url(self._endpoints.get('update').format(id=self.object_id))
        if color is not None and not isinstance(color, CategoryColor):
            color = CategoryColor.get(color)

        response = self.con.patch(url, data={'color': color.value if color else None})
        if not response:
            return False

        self.color = color
        return True

    def delete(self):
        """ Deletes this Category """
        url = self.build_url(self._endpoints.get('update').format(id=self.object_id))

        response = self.con.delete(url)

        return bool(response)


class Categories(ApiComponent):

    _endpoints = {
        'list': '/outlook/masterCategories',
        'get': '/outlook/masterCategories/{id}',
    }

    category_constructor = Category

    def __init__(self, *, parent=None, con=None, **kwargs):
        """ Object to retrive categories

        :param parent: parent object
        :type parent: Account
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """

        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over parent main_resource
        main_resource = kwargs.pop('main_resource', None) or (
            getattr(parent, 'main_resource', None) if parent else None)

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get('protocol'),
            main_resource=main_resource)

    def get_categories(self):
        """ Returns a list of categories"""
        url = self.build_url(self._endpoints.get('list'))

        response = self.con.get(url)
        if not response:
            return []

        data = response.json()

        return [
            self.category_constructor(parent=self, **{self._cloud_data_key: category})
            for category in data.get('value', [])
        ]

    def get_category(self, category_id):
        """ Returns a category by id"""
        url = self.build_url(self._endpoints.get('get').format(id=category_id))

        response = self.con.get(url)
        if not response:
            return None

        data = response.json()

        return self.category_constructor(parent=self, **{self._cloud_data_key: data})

    def create_category(self, name, color='auto'):
        """
        Creates a category.
        If the color is not provided it will be choosed from the pool of unused colors.

        :param str name: The name of this outlook category. Must be unique.
        :param str or CategoryColor color: optional color. If not provided will be assigned automatically.
        :return: bool
        """
        if color == 'auto':
            used_colors = {category.color for category in self.get_categories()}
            all_colors = {color for color in CategoryColor}
            available_colors = all_colors - used_colors
            try:
                color = available_colors.pop()
            except KeyError:
                # re-use a color
                color = all_colors.pop()
        else:
            if color is not None and not isinstance(color, CategoryColor):
                color = CategoryColor.get(color)

        url = self.build_url(self._endpoints.get('list'))
        data = {self._cc('displayName'): name, 'color': color.value if color else None}
        response = self.con.post(url, data=data)
        if not response:
            return None

        category = response.json()

        return self.category_constructor(parent=self, **{self._cloud_data_key: category})
