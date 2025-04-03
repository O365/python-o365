from __future__ import annotations

import datetime as dt
from typing import Union, Optional


# class OldQuery:
#     """ Helper to conform OData filters """
#     _mapping = {
#         'from': 'from/emailAddress/address',
#         'to': 'toRecipients/emailAddress/address',
#         'start': 'start/DateTime',
#         'end': 'end/DateTime',
#         'due': 'duedatetime/DateTime',
#         'reminder': 'reminderdatetime/DateTime',
#         'flag': 'flag/flagStatus',
#         'body': 'body/content'
#     }
#
#     def __str__(self):
#         return 'Filter: {}\nOrder: {}\nSelect: {}\nExpand: {}\nSearch: {}'.format(self.get_filters(),
#                                                                                   self.get_order(),
#                                                                                   self.get_selects(),
#                                                                                   self.get_expands(),
#                                                                                   self._search)
#
#     def select(self, *attributes):
#         """ Adds the attribute to the $select parameter
#
#         :param str attributes: the attributes tuple to select.
#          If empty, the on_attribute previously set is added.
#         :rtype: Query
#         """
#         if attributes:
#             for attribute in attributes:
#                 attribute = self.protocol.convert_case(
#                     attribute) if attribute and isinstance(attribute,
#                                                            str) else None
#                 if attribute:
#                     if '/' in attribute:
#                         # only parent attribute can be selected
#                         attribute = attribute.split('/')[0]
#                     self._selects.add(attribute)
#         else:
#             if self._attribute:
#                 self._selects.add(self._attribute)
#
#         return self
#
#     def expand(self, *relationships):
#         """
#         Adds the relationships (e.g. "event" or "attachments")
#         that should be expanded with the $expand parameter
#         Important: The ApiComponent using this should know how to handle this relationships.
#
#             eg: Message knows how to handle attachments, and event (if it's an EventMessage)
#
#         Important: When using expand on multi-value relationships a max of 20 items will be returned.
#
#         :param str relationships: the relationships tuple to expand.
#         :rtype: Query
#         """
#
#         for relationship in relationships:
#             if relationship == "event":
#                 relationship = "{}/event".format(
#                     self.protocol.get_service_keyword("event_message_type")
#                 )
#             self._expands.add(relationship)
#
#         return self
#
#     def as_params(self):
#         """ Returns the filters, orders, select, expands and search as query parameters
#
#         :rtype: dict
#         """
#         params = {}
#         if self.has_filters:
#             params['$filter'] = self.get_filters()
#         if self.has_order:
#             params['$orderby'] = self.get_order()
#         if self.has_expands and not self.has_selects:
#             params['$expand'] = self.get_expands()
#         if self.has_selects and not self.has_expands:
#             params['$select'] = self.get_selects()
#         if self.has_expands and self.has_selects:
#             params['$expand'] = '{}($select={})'.format(self.get_expands(), self.get_selects())
#         if self._search:
#             params['$search'] = self._search
#             params.pop('$filter', None)
#             params.pop('$orderby', None)
#         return params
#
#
#     def get_order(self):
#         """ Returns the result order by clauses
#
#         :rtype: str or None
#         """
#         # first get the filtered attributes in order as they must appear
#         # in the order_by first
#         if not self.has_order:
#             return None
#
#         return ','.join(['{} {}'.format(attribute, direction or '').strip()
#                          for attribute, direction in self._order_by.items()])
#
#     def get_selects(self):
#         """ Returns the result select clause
#
#         :rtype: str or None
#         """
#         if self._selects:
#             return ','.join(self._selects)
#         else:
#             return None
#
#     def get_expands(self):
#         """ Returns the result expand clause
#
#          :rtype: str or None
#         """
#         if self._expands:
#             return ','.join(self._expands)
#         else:
#             return None
#
#     def _get_mapping(self, attribute):
#         if attribute:
#             mapping = self._mapping.get(attribute)
#             if mapping:
#                 attribute = '/'.join(
#                     [self.protocol.convert_case(step) for step in
#                      mapping.split('/')])
#             else:
#                 attribute = self.protocol.convert_case(attribute)
#             return attribute
#         return None
#
#     def on_list_field(self, field):
#         """ Apply query on a list field, to be used along with chain()
#
#         :param str field: field name (note: name is case sensitive)
#         :rtype: Query
#         """
#         self._attribute = 'fields/' + field
#         return self
#
#
#     def order_by(self, attribute=None, *, ascending=True):
#         """ Applies a order_by clause
#
#         :param str attribute: attribute to apply on
#         :param bool ascending: should it apply ascending order or descending
#         :rtype: Query
#         """
#         attribute = self._get_mapping(attribute) or self._attribute
#         if attribute:
#             self._order_by[attribute] = None if ascending else 'desc'
#         else:
#             raise ValueError(
#                 'Attribute property needed. call on_attribute(attribute) '
#                 'or new(attribute)')
#         return self


FilterWord = Union[str, bool, None, dt.date, int, float]


class QueryFilter:
    __slots__ = ()

    def render(self, item_name: Optional[str] = None) -> str:
        raise NotImplementedError()

    def __repr__(self):
        return self.render()

    def __and__(self, other: QueryFilter):
        return ChainFilter('and', [self, other])

    def __or__(self, other: QueryFilter):
        return ChainFilter('or', [self, other])


class OperationQueryFilter(QueryFilter):
    __slots__ = ("_operation")

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
    __slots__ = ()

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
        assert operation in ('and', 'or')
        assert len(filter_instances) > 1
        super().__init__(operation)
        self._filter_instances: list[QueryFilter] = filter_instances

    def render(self, item_name: Optional[str] = None) -> str:
        return f" {self._operation} ".join([fi.render(item_name) for fi in self._filter_instances])


class ModifierQueryFilter(QueryFilter):
    __slots__ = ("_filter_instance")

    def __init__(self, filter_instance: QueryFilter):
        self._filter_instance: QueryFilter = filter_instance

    def render(self, item_name: Optional[str] = None) -> str:
        raise NotImplementedError()


class NegateFilter(ModifierQueryFilter):
    __slots__ = ("_filter_instance")

    def render(self, item_name: Optional[str] = None) -> str:
        return f"not {self._filter_instance.render(item_name=item_name)}"


class GroupFilter(ModifierQueryFilter):
    __slots__ = ("_filter_instance")

    def render(self, item_name: Optional[str] = None) -> str:
        return f"({self._filter_instance.render(item_name=item_name)})"


class SearchFilter(QueryFilter):
    __slots__ = ("_text")

    def __init__(self, text: str):
        self._text: str = text

    def render(self) -> str:
        return f'"{self._text}"'


class Query:

    def __init__(self, protocol):
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
            parsed_word = 'null'
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

    def logical_operation(self, operation: str, attribute: str, word: FilterWord) -> LogicalFilter:
        """ Apply a logical operation like equals, less than, etc.

        :param operation: how to combine with a new one
        :param attribute: attribute to compare word with
        :param word: value to compare the attribute with
        :return: a QueryFilter instance that can render the OData logical operation
        """
        return LogicalFilter(operation, attribute, self._parse_filter_word(word))

    def equals(self, attribute: str, word: FilterWord) -> LogicalFilter:
        """ Return an equals check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a QueryFilter instance that can render the OData this logical operation
        """
        return self.logical_operation('eq', attribute, word)

    def unequal(self, attribute: str, word: FilterWord) -> LogicalFilter:
        """ Return an unequal check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a QueryFilter instance that can render the OData this logical operation
        """
        return self.logical_operation('ne', attribute, word)

    def greater(self, attribute: str, word: FilterWord) -> LogicalFilter:
        """ Return a 'greater than' check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a QueryFilter instance that can render the OData this logical operation
        """
        return self.logical_operation('gt', attribute, word)

    def greater_equal(self, attribute: str, word: FilterWord) -> LogicalFilter:
        """ Return a 'greater than or equal to' check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a QueryFilter instance that can render the OData this logical operation
        """
        return self.logical_operation('ge', attribute, word)

    def less(self, attribute: str, word: FilterWord) -> LogicalFilter:
        """ Return a 'less than' check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a QueryFilter instance that can render the OData this logical operation
        """
        return self.logical_operation('lt', attribute, word)

    def less_equal(self, attribute: str, word: FilterWord) -> LogicalFilter:
        """ Return a 'less than or equal to' check

        :param attribute: attribute to compare word with
        :param word: word to compare with
        :return: a QueryFilter instance that can render the OData this logical operation
        """
        return self.logical_operation('le', attribute, word)

    def function_operation(self, operation: str, attribute: str, word: FilterWord) -> FunctionFilter:
        """ Apply a function operation

        :param operation: function name to operate on attribute
        :param attribute: the name of the attribute on which to apply the function
        :param word: value to feed the function
        :return: a QueryFilter instance that can render the OData function operation
        """
        return FunctionFilter(operation, attribute, self._parse_filter_word(word))

    def contains(self, attribute: str, word: FilterWord) -> FunctionFilter:
        """ Adds a contains word check

        :param attribute: the name of the attribute on which to apply the function
        :param word: value to feed the function
        :return: a QueryFilter instance that can render the OData function operation
        """
        return self.function_operation('contains', attribute, word)

    def startswith(self, attribute: str, word: FilterWord) -> FunctionFilter:
        """ Adds a startswith word check

        :param attribute: the name of the attribute on which to apply the function
        :param word: value to feed the function
        :return: a QueryFilter instance that can render the OData function operation
        """
        return self.function_operation('startswith', attribute, word)

    def endswith(self, attribute: str, word: FilterWord) -> FunctionFilter:
        """ Adds a endswith word check

        :param attribute: the name of the attribute on which to apply the function
        :param word: value to feed the function
        :return: a QueryFilter instance that can render the OData function operation
        """
        return self.function_operation('endswith', attribute, word)

    @staticmethod
    def iterable_operation(operation: str, collection: str, filter_instance: QueryFilter,
                           *, item_name: str = "a") -> IterableFilter:
        """ Performs the provided filter operation on a collection by iterating over it.

        For example:
        q.iterable(
            operation='any',
            collection='email_addresses',
            filter_instance=q.equals('address', 'george@best.com')
        )

        will transform to a filter such as:
        emailAddresses/any(a:a/address eq 'george@best.com')

        :param operation: the iterable operation name
        :param collection: the collection to apply the iterable operation on
        :param filter_instance: a QueryFilter Instance on which you will apply the iterable operation
        :param item_name: the name of the collection item to be used on the filter_instance
        :return: a QueryFilter instance that can render the OData iterable operation
        """
        return IterableFilter(operation, collection, filter_instance, item_name=item_name)


    def any(self, collection: str, filter_instance: QueryFilter, *, item_name: str = "a") -> IterableFilter:
        """ Performs a filter with the OData 'any' keyword on the collection

        For example:
        q.any(collection='email_addresses', filter_instance=q.equals('address', 'george@best.com'))

        will transform to a filter such as:

        emailAddresses/any(a:a/address eq 'george@best.com')

        :param collection: the collection to apply the iterable operation on
        :param filter_instance: a QueryFilter Instance on which you will apply the iterable operation
        :param item_name: the name of the collection item to be used on the filter_instance
        :return: a QueryFilter instance that can render the OData iterable operation
        """

        return self.iterable_operation('any', collection=collection,
                                       filter_instance=filter_instance, item_name=item_name)


    def all(self, collection: str, filter_instance: QueryFilter, *, item_name: str = "a") -> IterableFilter:
        """ Performs a filter with the OData 'all' keyword on the collection

        For example:
        q.all(collection='email_addresses', filter_instance=q.equals('address', 'george@best.com'))

        will transform to a filter such as:

        emailAddresses/all(a:a/address eq 'george@best.com')

        :param collection: the collection to apply the iterable operation on
        :param filter_instance: a QueryFilter Instance on which you will apply the iterable operation
        :param item_name: the name of the collection item to be used on the filter_instance
        :return: a QueryFilter instance that can render the OData iterable operation
        """

        return self.iterable_operation('any', collection=collection,
                                       filter_instance=filter_instance, item_name=item_name)

    @staticmethod
    def negate(filter_instance: QueryFilter) -> NegateFilter:
        """ Apply a not operator to the provided QueryFilter """
        return NegateFilter(filter_instance=filter_instance)

    def chain_and(self, *filter_instances: QueryFilter, group: bool = False) -> QueryFilter:
        """ Start a chain 'and' operation

        :param filter_instances: a list of other QueryFilters you want to combine with the 'and' operation
        :param group: will group this chain operation if True
        :return: a QueryFilter with the filter instances combined with an 'and' operation
        """
        chain = ChainFilter(operation='and', filter_instances=list(filter_instances))
        if group:
            return self.group(chain)
        else:
            return chain

    def chain_or(self, *filter_instances: QueryFilter, group: bool = False) -> QueryFilter:
        """ Start a chain 'or' operation. Will automatically apply a grouping.

        :param filter_instances: a list of other QueryFilters you want to combine with the 'or' operation
        :param group: will group this chain operation if True
        :return: a QueryFilter with the filter instances combined with an 'or' operation
        """
        chain = ChainFilter(operation='or', filter_instances=list(filter_instances))
        if group:
            return self.group(chain)
        else:
            return chain

    @staticmethod
    def group(filter_instance: QueryFilter) -> GroupFilter:
        """ Applies a grouping to the provided filter_instance """
        return GroupFilter(filter_instance)

    @staticmethod
    def search(text: str):
        """
        Perform a search.
        Note from graph docs:

         You can currently search only message and person collections.
         A $search request returns up to 250 results.
         You cannot use $filter or $orderby in a search request.

        :param str text: the text to search
        :return: a QueryFilter instance that can render the OData search operation
        """
        return SearchFilter(text=text)


# TODO mapping attributes?
# TODO: orderby
# TODO: selects
# TODO: expands

