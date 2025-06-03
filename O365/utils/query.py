from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import Union, Optional, TYPE_CHECKING, Type, Iterator, TypeAlias

if TYPE_CHECKING:
    from O365.connection import Protocol

FilterWord: TypeAlias = Union[str, bool, None, dt.date, int, float]


class QueryBase(ABC):
    __slots__ = ()

    @abstractmethod
    def as_params(self) -> dict:
        pass

    @abstractmethod
    def render(self) -> str:
        pass

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return self.render()

    @abstractmethod
    def __and__(self, other):
        pass

    @abstractmethod
    def __or__(self, other):
        pass

    def get_filter_by_attribute(self, attribute: str) -> Optional[str]:
        """
        Returns a filter value by attribute name. It will match the attribute to the start of each filter attribute
        and return the first found.
        
        :param attribute: the attribute you want to search
        :return: The value applied to that attribute or None
        """
        search_object: Optional[QueryFilter] = getattr(self, "_filter_instance", None) or getattr(self, "filters", None)
        if search_object is not None:
            # CompositeFilter, IterableFilter, ModifierQueryFilter (negate, group)
            return search_object.get_filter_by_attribute(attribute)

        search_object: Optional[list[QueryFilter]] = getattr(self, "_filter_instances", None)
        if search_object is not None:
            # ChainFilter
            for filter_obj in search_object:
                result = filter_obj.get_filter_by_attribute(attribute)
                if result is not None:
                    return result
            return None

        search_object: Optional[str] = getattr(self, "_attribute", None)
        if search_object is not None:
            # LogicalFilter or FunctionFilter
            if search_object.lower().startswith(attribute.lower()):
                return getattr(self, "_word")
        return None


class QueryFilter(QueryBase, ABC):
    __slots__ = ()

    @abstractmethod
    def render(self, item_name: Optional[str] = None) -> str:
        pass

    def as_params(self) -> dict:
        return {"$filter": self.render()}

    def __and__(self, other: Optional[QueryBase]) -> QueryBase:
        if other is None:
            return self
        if isinstance(other, QueryFilter):
            return ChainFilter("and", [self, other])
        elif isinstance(other, OrderByFilter):
            return CompositeFilter(filters=self, order_by=other)
        elif isinstance(other, SearchFilter):
            raise ValueError("Can't mix search with filters or order by clauses.")
        elif isinstance(other, SelectFilter):
            return CompositeFilter(filters=self, select=other)
        elif isinstance(other, ExpandFilter):
            return CompositeFilter(filters=self, expand=other)
        else:
            raise ValueError(f"Can't mix {type(other)} with {type(self)}")


    def __or__(self, other: QueryFilter) -> ChainFilter:
        if not isinstance(other, QueryFilter):
            raise ValueError("Can't chain a non-query filter with and 'or' operator. Use 'and' instead.")
        return ChainFilter("or", [self, other])


class OperationQueryFilter(QueryFilter, ABC):
    __slots__ = ("_operation",)

    def __init__(self, operation: str):
        self._operation: str = operation


class LogicalFilter(OperationQueryFilter):
    __slots__ = ("_operation", "_attribute", "_word")

    def __init__(self, operation: str, attribute: str, word: str):
        super().__init__(operation)
        self._attribute: str = attribute
        self._word: str = word

    def _prepare_attribute(self, item_name: str = None) -> str:
        if item_name:
            if self._attribute is None:
                # iteration will occur in the item itself
                return f"{item_name}"
            else:
                return f"{item_name}/{self._attribute}"
        else:
            return self._attribute

    def render(self, item_name: Optional[str] = None) -> str:
        return f"{self._prepare_attribute(item_name)} {self._operation} {self._word}"


class FunctionFilter(LogicalFilter):
    __slots__ = ("_operation", "_attribute", "_word")

    def render(self, item_name: Optional[str] = None) -> str:
        return f"{self._operation}({self._prepare_attribute(item_name)}, {self._word})"


class IterableFilter(OperationQueryFilter):
    __slots__ = ("_operation", "_collection", "_item_name", "_filter_instance")

    def __init__(self, operation: str, collection: str, filter_instance: QueryFilter, *, item_name: str = "a"):
        super().__init__(operation)
        self._collection: str = collection
        self._item_name: str = item_name
        self._filter_instance: QueryFilter = filter_instance

    def render(self, item_name: Optional[str] = None) -> str:
        # an iterable filter will always ignore external item names
        filter_instance_render = self._filter_instance.render(item_name=self._item_name)
        return f"{self._collection}/{self._operation}({self._item_name}: {filter_instance_render})"


class ChainFilter(OperationQueryFilter):
    __slots__ = ("_operation", "_filter_instances")

    def __init__(self, operation: str, filter_instances: list[QueryFilter]):
        assert operation in ("and", "or")
        super().__init__(operation)
        self._filter_instances: list[QueryFilter] = filter_instances

    def render(self, item_name: Optional[str] = None) -> str:
        return f" {self._operation} ".join([fi.render(item_name) for fi in self._filter_instances])


class ModifierQueryFilter(QueryFilter, ABC):
    __slots__ = ("_filter_instance",)

    def __init__(self, filter_instance: QueryFilter):
        self._filter_instance: QueryFilter = filter_instance


class NegateFilter(ModifierQueryFilter):
    __slots__ = ("_filter_instance",)

    def render(self, item_name: Optional[str] = None) -> str:
        return f"not {self._filter_instance.render(item_name=item_name)}"


class GroupFilter(ModifierQueryFilter):
    __slots__ = ("_filter_instance",)

    def render(self, item_name: Optional[str] = None) -> str:
        return f"({self._filter_instance.render(item_name=item_name)})"


class SearchFilter(QueryBase):
    __slots__ = ("_search",)

    def __init__(self, word: Optional[Union[str, int, bool]] = None, attribute: Optional[str] = None):
        if word:
            if attribute:
                self._search: str = f"{attribute}:{word}"
            else:
                self._search: str = word
        else:
            self._search: str = ""

    def _combine(self, search_one: str, search_two: str, operator: str = "and"):
        self._search = f"{search_one} {operator} {search_two}"

    def render(self) -> str:
        return f'"{self._search}"'

    def as_params(self) -> dict:
        return {"$search": self.render()}

    def __and__(self, other: Optional[QueryBase]) -> QueryBase:
        if other is None:
            return self
        if isinstance(other, SearchFilter):
            new_search = self.__class__()
            new_search._combine(self._search, other._search, operator="and")
            return new_search
        elif isinstance(other, QueryFilter):
            raise ValueError("Can't mix search with filters clauses.")
        elif isinstance(other, OrderByFilter):
            raise ValueError("Can't mix search with order by clauses.")
        elif isinstance(other, SelectFilter):
            return CompositeFilter(search=self, select=other)
        elif isinstance(other, ExpandFilter):
            return CompositeFilter(search=self, expand=other)
        else:
            raise ValueError(f"Can't mix {type(other)} with {type(self)}")

    def __or__(self, other: QueryBase) -> SearchFilter:
        if not isinstance(other, SearchFilter):
            raise ValueError("Can't chain a non-search filter with and 'or' operator. Use 'and' instead.")
        new_search = self.__class__()
        new_search._combine(self._search, other._search, operator="or")
        return new_search


class OrderByFilter(QueryBase):
    __slots__ = ("_orderby",)

    def __init__(self):
        self._orderby: list[tuple[str, bool]] = []

    def _sorted_attributes(self) -> list[str]:
        return [att for att, asc in self._orderby]

    def add(self, attribute: str, ascending: bool = True) -> None:
        if not attribute:
            raise ValueError("Attribute can't be empty")
        if attribute not in self._sorted_attributes():
            self._orderby.append((attribute, ascending))

    def render(self) -> str:
        return ",".join(f"{att} {'' if asc else 'desc'}".strip() for att, asc in self._orderby)

    def as_params(self) -> dict:
        return {"$orderby": self.render()}

    def __and__(self, other: Optional[QueryBase]) -> QueryBase:
        if other is None:
            return self
        if isinstance(other, OrderByFilter):
            new_order_by = self.__class__()
            for att, asc in self._orderby:
                new_order_by.add(att, asc)
            for att, asc in other._orderby:
                new_order_by.add(att, asc)
            return new_order_by
        elif isinstance(other, SearchFilter):
            raise ValueError("Can't mix order by with search clauses.")
        elif isinstance(other, QueryFilter):
            return CompositeFilter(order_by=self, filters=other)
        elif isinstance(other, SelectFilter):
            return CompositeFilter(order_by=self, select=other)
        elif isinstance(other, ExpandFilter):
            return CompositeFilter(order_by=self, expand=other)
        else:
            raise ValueError(f"Can't mix {type(other)} with {type(self)}")

    def __or__(self, other: QueryBase):
        raise RuntimeError("Orderby clauses are mutually exclusive")


class ContainerQueryFilter(QueryBase):
    __slots__ = ("_container", "_keyword")

    def __init__(self, *args: Union[str, tuple[str, SelectFilter]]):
        self._container: list[Union[str, tuple[str, SelectFilter]]] = list(args)
        self._keyword: str = ''

    def append(self, item: Union[str, tuple[str, SelectFilter]]) -> None:
        self._container.append(item)

    def __iter__(self) -> Iterator[Union[str, tuple[str, SelectFilter]]]:
        return iter(self._container)

    def __contains__(self, attribute: str) -> bool:
        return attribute in [item[0] if isinstance(item, tuple) else item for item in self._container]

    def __and__(self, other: Optional[QueryBase]) -> QueryBase:
        if other is None:
            return self
        if (isinstance(other, SelectFilter) and isinstance(self, SelectFilter)
        ) or (isinstance(other, ExpandFilter) and isinstance(self, ExpandFilter)):
            new_container = self.__class__(*self)
            for item in other:
                if isinstance(item, tuple):
                    attribute = item[0]
                else:
                    attribute = item
                if attribute not in new_container:
                    new_container.append(item)
            return new_container
        elif isinstance(other, QueryFilter):
            return CompositeFilter(**{self._keyword: self, "filters": other})
        elif isinstance(other, SearchFilter):
            return CompositeFilter(**{self._keyword: self, "search": other})
        elif isinstance(other, OrderByFilter):
            return CompositeFilter(**{self._keyword: self, "order_by": other})
        elif isinstance(other, SelectFilter):
            return CompositeFilter(**{self._keyword: self, "select": other})
        elif isinstance(other, ExpandFilter):
            return CompositeFilter(**{self._keyword: self, "expand": other})
        else:
            raise ValueError(f"Can't mix {type(other)} with {type(self)}")

    def __or__(self, other: Optional[QueryBase]):
        raise RuntimeError("Can't combine multiple composite filters with an 'or' statement. Use 'and' instead.")

    def render(self) -> str:
        return ",".join(self._container)

    def as_params(self) -> dict:
        return {f"${self._keyword}": self.render()}


class SelectFilter(ContainerQueryFilter):
    __slots__ = ("_container", "_keyword")

    def __init__(self, *args: str):
        super().__init__(*args)
        self._keyword: str = "select"


class ExpandFilter(ContainerQueryFilter):
    __slots__ = ("_container", "_keyword")

    def __init__(self, *args: Union[str, tuple[str, SelectFilter]]):
        super().__init__(*args)
        self._keyword: str = "expand"

    def render(self) -> str:
        renders = []
        for item in self._container:
            if isinstance(item, tuple):
                renders.append(f"{item[0]}($select={item[1].render()})")
            else:
                renders.append(item)
        return ",".join(renders)


class CompositeFilter(QueryBase):
    """ A Query object that holds all query parameters. """

    __slots__ = ("filters", "search", "order_by", "select", "expand")

    def __init__(self, *, filters: Optional[QueryFilter] = None, search: Optional[SearchFilter] = None,
                 order_by: Optional[OrderByFilter] = None, select: Optional[SelectFilter] = None,
                 expand: Optional[ExpandFilter] = None):
        self.filters: Optional[QueryFilter] = filters
        self.search: Optional[SearchFilter] = search
        self.order_by: Optional[OrderByFilter] = order_by
        self.select: Optional[SelectFilter] = select
        self.expand: Optional[ExpandFilter] = expand

    def render(self) -> str:
        return (
            f"Filters: {self.filters.render() if self.filters else ''}\n"
            f"Search: {self.search.render() if self.search else ''}\n"
            f"OrderBy: {self.order_by.render() if self.order_by else ''}\n"
            f"Select: {self.select.render() if self.select else ''}\n"
            f"Expand: {self.expand.render() if self.expand else ''}"
        )

    @property
    def has_filters(self) -> bool:
        """ Returns if this CompositeFilter has filters"""
        return self.filters is not None

    @property
    def has_selects(self) -> bool:
        """ Returns if this CompositeFilter has selects"""
        return self.select is not None

    @property
    def has_expands(self) -> bool:
        """ Returns if this CompositeFilter has expands"""
        return self.expand is not None

    @property
    def has_search(self) -> bool:
        """ Returns if this CompositeFilter has search"""
        return self.search is not None

    @property
    def has_order_by(self) -> bool:
        """ Returns if this CompositeFilter has order_by"""
        return self.order_by is not None

    def clear_filters(self) -> None:
        """ Removes all filters from the query """
        self.filters = None

    @property
    def has_only_filters(self) -> bool:
        """ Returns true if it only has filters"""
        return (self.filters is not None and self.search is None and
                self.order_by is None and self.select is None and self.expand is None)

    def as_params(self) -> dict:
        params = {}
        if self.filters:
            params.update(self.filters.as_params())
        if self.search:
            params.update(self.search.as_params())
        if self.order_by:
            params.update(self.order_by.as_params())
        if self.expand:
            params.update(self.expand.as_params())
        if self.select:
            params.update(self.select.as_params())
        return params

    def __and__(self, other: Optional[QueryBase]) -> CompositeFilter:
        """ Combine this CompositeFilter with another QueryBase object """
        if other is None:
            return self
        nc = CompositeFilter(filters=self.filters, search=self.search, order_by=self.order_by,
                             select=self.select, expand=self.expand)
        if isinstance(other, QueryFilter):
            if self.search is not None:
                raise ValueError("Can't mix search with filters or order by clauses.")
            nc.filters = nc.filters & other if nc.filters else other
        elif isinstance(other, OrderByFilter):
            if self.search is not None:
                raise ValueError("Can't mix search with filters or order by clauses.")
            nc.order_by = nc.order_by & other if nc.order_by else other
        elif isinstance(other, SearchFilter):
            if self.filters is not None or self.order_by is not None:
                raise ValueError("Can't mix search with filters or order by clauses.")
            nc.search = nc.search & other if nc.search else other
        elif isinstance(other, SelectFilter):
            nc.select = nc.select & other if nc.select else other
        elif isinstance(other, ExpandFilter):
            nc.expand = nc.expand & other if nc.expand else other
        elif isinstance(other, CompositeFilter):
            if (self.search and (other.filters or other.order_by)
            ) or (other.search and (self.filters or self.order_by)):
                raise ValueError("Can't mix search with filters or order by clauses.")
            nc.filters = nc.filters & other.filters if nc.filters else other.filters
            nc.search = nc.search & other.search if nc.search else other.search
            nc.order_by = nc.order_by & other.order_by if nc.order_by else other.order_by
            nc.select = nc.select & other.select if nc.select else other.select
            nc.expand = nc.expand & other.expand if nc.expand else other.expand
        return nc

    def __or__(self, other: Optional[QueryBase]) -> CompositeFilter:
        if isinstance(other, CompositeFilter):
            if self.has_only_filters and other.has_only_filters:
                return CompositeFilter(filters=self.filters | other.filters)
        raise RuntimeError("Can't combine multiple composite filters with an 'or' statement. Use 'and' instead.")


class QueryBuilder:

    _attribute_mapping = {
        "from": "from/emailAddress/address",
        "to": "toRecipients/emailAddress/address",
        "start": "start/DateTime",
        "end": "end/DateTime",
        "due": "duedatetime/DateTime",
        "reminder": "reminderdatetime/DateTime",
        "flag": "flag/flagStatus",
        "body": "body/content"
    }

    def __init__(self, protocol: Union[Protocol, Type[Protocol]]):
        """ Build a query to apply OData filters
        https://docs.microsoft.com/en-us/graph/query-parameters

        :param Protocol protocol: protocol to retrieve the timezone from
        """
        self.protocol = protocol() if isinstance(protocol, type) else protocol

    def _parse_filter_word(self, word: FilterWord) -> str:
        """ Converts the word parameter into a string """
        if isinstance(word, str):
            # string must be enclosed in quotes
            parsed_word = f"'{word}'"
        elif isinstance(word, bool):
            # bools are treated as lower case bools
            parsed_word = str(word).lower()
        elif word is None:
            parsed_word = "null"
        elif isinstance(word, dt.date):
            if isinstance(word, dt.datetime):
                if word.tzinfo is None:
                    # if it's a naive datetime, localize the datetime.
                    word = word.replace(tzinfo=self.protocol.timezone)  # localize datetime into local tz
            # convert datetime to iso format
            parsed_word = f"{word.isoformat()}"
        else:
            # other cases like int or float, return as a string.
            parsed_word = str(word)
        return parsed_word

    def _get_attribute_from_mapping(self, attribute: str) -> str:
        """
        Look up the provided attribute into the query builder mapping
        Applies a conversion to the appropriate casing defined by the protocol.

        :param attribute: attribute to look up
        :return: the attribute itself of if found the corresponding complete attribute in the mapping
        """
        mapping = self._attribute_mapping.get(attribute)
        if mapping:
            attribute = "/".join(
                [self.protocol.convert_case(step) for step in
                 mapping.split("/")])
        else:
            attribute = self.protocol.convert_case(attribute)
        return attribute

    def logical_operation(self, operation: str, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Apply a logical operation like equals, less than, etc.

        :param operation: how to combine with a new one
        :param attribute: attribute to compare word with
        :param word: value to compare the attribute with
        :return: a CompositeFilter instance that can render the OData logical operation
        """
        logical_filter = LogicalFilter(operation,
                                       self._get_attribute_from_mapping(attribute),
                                       self._parse_filter_word(word))
        return CompositeFilter(filters=logical_filter)

    def equals(self, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Return an equals check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a CompositeFilter instance that can render the OData this logical operation
        """
        return self.logical_operation("eq", attribute, word)

    def unequal(self, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Return an unequal check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a CompositeFilter instance that can render the OData this logical operation
        """
        return self.logical_operation("ne", attribute, word)

    def greater(self, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Return a 'greater than' check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a CompositeFilter instance that can render the OData this logical operation
        """
        return self.logical_operation("gt", attribute, word)

    def greater_equal(self, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Return a 'greater than or equal to' check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a CompositeFilter instance that can render the OData this logical operation
        """
        return self.logical_operation("ge", attribute, word)

    def less(self, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Return a 'less than' check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a CompositeFilter instance that can render the OData this logical operation
        """
        return self.logical_operation("lt", attribute, word)

    def less_equal(self, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Return a 'less than or equal to' check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a CompositeFilter instance that can render the OData this logical operation
        """
        return self.logical_operation("le", attribute, word)

    def function_operation(self, operation: str, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Apply a function operation

        :param operation: function name to operate on attribute
        :param attribute: the name of the attribute on which to apply the function
        :param word: value to feed the function
        :return: a CompositeFilter instance that can render the OData function operation
        """
        function_filter = FunctionFilter(operation,
                                         self._get_attribute_from_mapping(attribute),
                                         self._parse_filter_word(word))
        return CompositeFilter(filters=function_filter)

    def contains(self, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Adds a contains word check

        :param attribute: the name of the attribute on which to apply the function
        :param word: value to feed the function
        :return: a CompositeFilter instance that can render the OData function operation
        """
        return self.function_operation("contains", attribute, word)

    def startswith(self, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Adds a startswith word check

        :param attribute: the name of the attribute on which to apply the function
        :param word: value to feed the function
        :return: a CompositeFilter instance that can render the OData function operation
        """
        return self.function_operation("startswith", attribute, word)

    def endswith(self, attribute: str, word: FilterWord) -> CompositeFilter:
        """ Adds a endswith word check

        :param attribute: the name of the attribute on which to apply the function
        :param word: value to feed the function
        :return: a CompositeFilter instance that can render the OData function operation
        """
        return self.function_operation("endswith", attribute, word)

    def iterable_operation(self, operation: str, collection: str, filter_instance: CompositeFilter,
                           *, item_name: str = "a") -> CompositeFilter:
        """ Performs the provided filter operation on a collection by iterating over it.

        For example:

        .. code-block:: python

            q.iterable(
                operation='any',
                collection='email_addresses',
                filter_instance=q.equals('address', 'george@best.com')
            )

        will transform to a filter such as:
        emailAddresses/any(a:a/address eq 'george@best.com')

        :param operation: the iterable operation name
        :param collection: the collection to apply the iterable operation on
        :param filter_instance: a CompositeFilter instance on which you will apply the iterable operation
        :param item_name: the name of the collection item to be used on the filter_instance
        :return: a CompositeFilter instance that can render the OData iterable operation
        """
        iterable_filter = IterableFilter(operation,
                                         self._get_attribute_from_mapping(collection),
                                         filter_instance.filters,
                                         item_name=item_name)
        return CompositeFilter(filters=iterable_filter)


    def any(self, collection: str, filter_instance: CompositeFilter, *, item_name: str = "a") -> CompositeFilter:
        """ Performs a filter with the OData 'any' keyword on the collection

        For example:
        q.any(collection='email_addresses', filter_instance=q.equals('address', 'george@best.com'))

        will transform to a filter such as:

        emailAddresses/any(a:a/address eq 'george@best.com')

        :param collection: the collection to apply the iterable operation on
        :param filter_instance: a CompositeFilter Instance on which you will apply the iterable operation
        :param item_name: the name of the collection item to be used on the filter_instance
        :return: a CompositeFilter instance that can render the OData iterable operation
        """

        return self.iterable_operation("any", collection=collection,
                                       filter_instance=filter_instance, item_name=item_name)


    def all(self, collection: str, filter_instance: CompositeFilter, *, item_name: str = "a") -> CompositeFilter:
        """ Performs a filter with the OData 'all' keyword on the collection

        For example:
        q.all(collection='email_addresses', filter_instance=q.equals('address', 'george@best.com'))

        will transform to a filter such as:

        emailAddresses/all(a:a/address eq 'george@best.com')

        :param collection: the collection to apply the iterable operation on
        :param filter_instance: a CompositeFilter Instance on which you will apply the iterable operation
        :param item_name: the name of the collection item to be used on the filter_instance
        :return: a CompositeFilter instance that can render the OData iterable operation
        """

        return self.iterable_operation("all", collection=collection,
                                       filter_instance=filter_instance, item_name=item_name)

    @staticmethod
    def negate(filter_instance: CompositeFilter) -> CompositeFilter:
        """ Apply a not operator to the provided QueryFilter
        :param filter_instance: a CompositeFilter instance
        :return: a CompositeFilter with its filter negated
        """
        negate_filter = NegateFilter(filter_instance=filter_instance.filters)
        return CompositeFilter(filters=negate_filter)

    def _chain(self, operator: str, *filter_instances: CompositeFilter, group: bool = False) -> CompositeFilter:
        chain = ChainFilter(operation=operator, filter_instances=[fl.filters for fl in filter_instances])
        chain = CompositeFilter(filters=chain)
        if group:
            return self.group(chain)
        else:
            return chain

    def chain_and(self, *filter_instances: CompositeFilter, group: bool = False) -> CompositeFilter:
        """ Start a chain 'and' operation

        :param filter_instances: a list of other CompositeFilter you want to combine with the 'and' operation
        :param group: will group this chain operation if True
        :return: a CompositeFilter with the filter instances combined with an 'and' operation
        """
        return self._chain("and", *filter_instances, group=group)

    def chain_or(self, *filter_instances: CompositeFilter, group: bool = False) -> CompositeFilter:
        """ Start a chain 'or' operation. Will automatically apply a grouping.

        :param filter_instances: a list of other CompositeFilter you want to combine with the 'or' operation
        :param group: will group this chain operation if True
        :return: a CompositeFilter with the filter instances combined with an 'or' operation
        """
        return self._chain("or", *filter_instances, group=group)

    @staticmethod
    def group(filter_instance: CompositeFilter) -> CompositeFilter:
        """ Applies a grouping to the provided filter_instance """
        group_filter = GroupFilter(filter_instance.filters)
        return CompositeFilter(filters=group_filter)

    def search(self, word: Union[str, int, bool], attribute: Optional[str] = None) -> CompositeFilter:
        """
        Perform a search.
        Note from graph docs:

         You can currently search only message and person collections.
         A $search request returns up to 250 results.
         You cannot use $filter or $orderby in a search request.

        :param word: the text to search
        :param attribute: the attribute to search the word on
        :return: a CompositeFilter instance that can render the OData search operation
        """
        word = self._parse_filter_word(word)
        if attribute:
            attribute = self._get_attribute_from_mapping(attribute)
        search = SearchFilter(word=word, attribute=attribute)
        return CompositeFilter(search=search)

    @staticmethod
    def orderby(*attributes: tuple[Union[str, tuple[str, bool]]]) -> CompositeFilter:
        """
        Returns an 'order by' query param
        This is useful to order the result set of query from a resource.
        Note that not all attributes can be sorted and that all resources have different sort capabilities

        :param attributes: the attributes to orderby
        :return: a CompositeFilter instance that can render the OData order by operation
        """
        new_order_by = OrderByFilter()
        for order_by_clause in attributes:
            if isinstance(order_by_clause, str):
                new_order_by.add(order_by_clause)
            elif isinstance(order_by_clause, tuple):
                new_order_by.add(order_by_clause[0], order_by_clause[1])
            else:
                raise ValueError("Arguments must be attribute strings or tuples"
                                 " of attribute strings and ascending booleans")
        return CompositeFilter(order_by=new_order_by)

    def select(self, *attributes: str) -> CompositeFilter:
        """
        Returns a 'select' query param
        This is useful to return a limited set of attributes from a resource or return attributes that are not
        returned by default by the resource.

        :param attributes: a tuple of attribute names to select
        :return: a CompositeFilter instance that can render the OData select operation
        """
        select = SelectFilter()
        for attribute in attributes:
            attribute = self.protocol.convert_case(attribute)
            if attribute.lower() in ["meetingmessagetype"]:
                attribute = f"{self.protocol.keyword_data_store['event_message_type']}/{attribute}"
            select.append(attribute)
        return CompositeFilter(select=select)

    def expand(self, relationship: str, select: Optional[CompositeFilter] = None) -> CompositeFilter:
        """
        Returns an 'expand' query param
        Important: If the 'expand' is a relationship (e.g. "event" or "attachments"), then the ApiComponent using
        this query should know how to handle the relationship (e.g. Message knows how to handle attachments,
        and event (if it's an EventMessage).
        Important: When using expand on multi-value relationships a max of 20 items will be returned.

        :param relationship: a relationship that will be expanded
        :param select: a CompositeFilter instance to select attributes on the expanded relationship
        :return: a CompositeFilter instance that can render the OData expand operation
        """
        expand = ExpandFilter()
        # this will prepend the event message type tag based on the protocol
        if relationship == "event":
            relationship = f"{self.protocol.get_service_keyword('event_message_type')}/event"

        if select is not None:
            expand.append((relationship, select.select))
        else:
            expand.append(relationship)
        return CompositeFilter(expand=expand)
