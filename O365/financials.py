from O365.connection import MSBusinessCentral365Protocol
from dateutil.parser import parse
import inflection
import re
import sys

from .utils import ApiComponent, TrackerSet


def replacenth(string, sub, wanted, n):
    pattern = re.compile(sub)
    where = [m for m in pattern.finditer(string)][n - 1]
    before = string[:where.start()]
    after = string[where.end():]
    newString = before + wanted + after

    return newString


class FinancialsApiComponent(ApiComponent):

    def __init__(self, *, parent=None, con=None, **kwargs):
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        cc = self._cc  # alias
        # internal to know which properties need to be updated on the server
        self._track_changes = TrackerSet(casing=cc)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        # Choose the main_resource passed in kwargs over parent main_resource
        if kwargs.pop('main_resource', None):
            main_resource = kwargs.pop('main_resource', None)
        elif parent:
            if type(parent.protocol) == MSBusinessCentral365Protocol:
                main_resource = ('/companies/{id}').format(id=getattr(parent, 'id', None))
            else:
                main_resource = ('financials/companies/{id}').format(id=getattr(parent, 'id', None))
        else:
            main_resource = ''

        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), con=con, main_resource=main_resource)

        self.__parent_id = getattr(parent, 'id', None)
        self.__etag = cloud_data.get('@odata.etag', None)
        self.object_id = cloud_data.get('id', None)

    def build_url(self, endpoint):
        """ Returns a url for a given endpoint using the protocol
        service url

        :param str endpoint: endpoint to build the url for
        :return: final url
        :rtype: str
        """
        if type(self.protocol) == MSBusinessCentral365Protocol:
            endpoint = replacenth(endpoint, "/", ")/", 2)
            endpoint = replacenth(endpoint, "/", "(", 1)

        if type(self) == Company:
            return '{}{}'.format(self._base_url, "/financials/companies" + endpoint)
        else:
            return '{}{}'.format(self._base_url, endpoint)

    def _get_entity(self, entity_id=None, constructor=None):
        if not constructor or not entity_id:
            raise RuntimeError('Provide one of the options')

        # No id is represented as 00000000-0000-0000-0000-000000000000
        if entity_id == "00000000-0000-0000-0000-000000000000":
            return None

        cid = self.__parent_id if self.__parent_id else self.object_id

        if entity_id:
            if type(self) == Company:
                url = self.build_url("/{cid}/{entity}/{id}".format(cid=cid, entity=constructor._ENTITY, id=entity_id))
            else:
                url = self.build_url("/{entity}/{id}".format(cid=cid, entity=constructor._ENTITY, id=entity_id))
            params = None

        response = self.con.get(url, params=params)
        if not response:
            return None

        if entity_id:
            data = response.json()
        else:
            data = response.json().get('value')
            data = data[0] if data else None
            if data is None:
                return None

        if not entity_id:
            raise RuntimeError('Provide one of the options')

        # Everything received from cloud must be passed as self._cloud_data_key
        return constructor(parent=self, **{self._cloud_data_key: data})

    def _get_entities(self, constructor=None, limit=None, query=None, order_by=None, parent=None):
        if not constructor:
            raise RuntimeError('Provide one of the options')

        cid = self.__parent_id if self.__parent_id else self.object_id

        if constructor:
            if parent:
                url = self.build_url("/{entity}/{id}/{navigationEntity}".format(entity=self._ENTITY, id=self.object_id, navigationEntity=constructor._ENTITY))
            else:
                url = self.build_url("/{cid}/{entity}".format(cid=cid, entity=constructor._ENTITY))
            params = None

        params = {}
        if limit:
            params['$top'] = limit
        if query:
            params['$filter'] = str(query)
        if order_by:
            params['$orderby'] = order_by

        response = self.con.get(url, params=params)
        if not response:
            return []

        data = response.json()

        if not id:
            raise RuntimeError('Provide one of the options')

        # Everything received from cloud must be passed as self._cloud_data_key
        return [constructor(parent=self, **{self._cloud_data_key: x}) for x in data.get('value', [])]

    def _update(self):
        if not self.object_id:
            return False
        else:
            if not self._track_changes:
                return True  # there's nothing to update

            url = self.build_url(("/" + type(self)._ENTITY + "/{id}").format(id=self.object_id))

            method = self.con.patch
            data = self.to_api_data(restrict_keys=self._track_changes)
            headers = {"If-Match": self.__etag}

            response = method(url, data=data, headers=headers)

            if not response:
                return False

            if not response.ok:
                return False

            self.__modified = self.protocol.timezone.localize(datetime.now())

            return True

    def _delete(self):
        if not self.object_id:
            return False

        url = self.build_url(("/" + type(self)._ENTITY + "/{id}").format(id=self.object_id))

        response = self.con.delete(url)
        if response.status_code != 204:
            return False

        self.object_id = None
        return True

    def _create(self):
        if not self._track_changes:
            return True  # there's nothing to update

        url = self.build_url("/" + type(self)._ENTITY)

        method = self.con.post
        data = self.to_api_data(restrict_keys=self._track_changes)

        response = method(url, data=data)

        if not response.status_code == 201:
            return False

        object_created = response.json()

        for key, value in object_created.items():
            if not key.startswith("@"):
                if hasattr(self, inflection.underscore(key)):

                    if "datetime" in key.lower():
                        setattr(self, inflection.underscore(key), parse(value).astimezone(self.protocol.timezone))
                    elif "date" in key.lower():
                        if value != "0001-01-01":
                            setattr(self, inflection.underscore(key), parse(value).astimezone(self.protocol.timezone))
                        else:
                            setattr(self, inflection.underscore(key), None)
                    else:
                        setattr(self, inflection.underscore(key), value)

        if "lastModifiedDateTime" in object_created:
            self.__modified = parse(object_created["lastModifiedDateTime"]).astimezone(self.protocol.timezone)

        self.__etag = object_created.get("@odata.etag", None)
        self.object_id = object_created['id']

        return True

    def _save(self):
        if self.object_id:
            _update()
        else:
            _create()

    def to_api_data(self, restrict_keys=None):
        cc = self._cc  # alias

        data = dict((cc(attr), attr) for attr, value in vars(type(self)).items() if isinstance(value, property) and value.fset is not None)

        for cloud_key, var_name in data.items():
            data[cloud_key] = getattr(self, var_name)

        if restrict_keys:
            for key in list(data.keys()):
                if key not in restrict_keys:
                    del data[key]
        return data

    def to_dict(self):
        cc = self._cc  # alias

        data = dict((cc(attr), attr) for attr, value in vars(type(self)).items() if isinstance(value, property) and value.fset is not None)

        return data


class Item(FinancialsApiComponent):
    _ENTITY = "items"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__number = cloud_data.get('number')
        self.__display_name = cloud_data.get('displayName')
        self.__type = cloud_data.get('type')
        self.__item_category_id = cloud_data.get('itemCategoryId')
        self.__blocked = cloud_data.get('blocked')
        self.__base_unit_of_measure_id = cloud_data.get('baseUnitOfMeasureId')
        self.__gtin = cloud_data.get('gtin')
        self.__unit_price = cloud_data.get('unitPrice')
        self.__price_includes_tax = cloud_data.get('unitPrice')
        self.__unit_cost = cloud_data.get('unitPrice')
        self.__tax_group_code = cloud_data.get('taxGroupCode')
        self.__tax_group_id = cloud_data.get('taxGroupId')
        self.__inventory = cloud_data.get('inventory')
        self.__item_category_code = cloud_data.get('itemCategoryCode')

        self.__item_category = super()._get_entity(entity_id=cloud_data.get('itemCategoryId'), constructor=ItemCategory)
        self.__tax_group = super()._get_entity(entity_id=cloud_data.get('taxGroupId'), constructor=TaxGroup)
        self.__base_unit_of_measure = super()._get_entity(entity_id=cloud_data.get('baseUnitOfMeasureId'), constructor=UnitOfMeasure)

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'Item: {}'.format(self.display_name)

    @property
    def number(self):
        return self.__number

    @number.setter
    def number(self, value):
        self.__number = value
        self._track_changes.add(self._cc('number'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def type(self):
        return self.__type

    @type.setter
    def type(self, value):
        self.__type = value
        self._track_changes.add(self._cc('type'))

    @property
    def item_category_id(self):
        return self.__item_category_id

    @item_category_id.setter
    def item_category_id(self, value):
        self.__item_category_id = value
        self._track_changes.add(self._cc('itemCategoryId'))

    @property
    def item_category_code(self):
        return self.__item_category_code

    @property
    def blocked(self):
        return self.__blocked

    @blocked.setter
    def blocked(self, value):
        self.__blocked = value
        self._track_changes.add(self._cc('blocked'))

    @property
    def base_unit_of_measure_id(self):
        return self.__base_unit_of_measure_id

    @base_unit_of_measure_id.setter
    def base_unit_of_measure_id(self, value):
        self.__base_unit_of_measure_id = value
        self._track_changes.add(self._cc('baseUnitOfMeasureId'))

    @property
    def gtin(self):
        return self.__gtin

    @gtin.setter
    def gtin(self, value):
        self.__gtin = value
        self._track_changes.add(self._cc('gtin'))

    @property
    def inventory(self):
        return self.__inventory

    @property
    def unit_price(self):
        return self.__unit_price

    @unit_price.setter
    def unit_price(self, value):
        self.__unit_price = value
        self._track_changes.add(self._cc('unitPrice'))

    @property
    def price_includes_tax(self):
        return self.__price_includes_tax

    @price_includes_tax.setter
    def price_includes_tax(self, value):
        self.__price_includes_tax = value
        self._track_changes.add(self._cc('priceIncludesTax'))

    @property
    def unit_cost(self):
        return self.__unit_cost

    @unit_cost.setter
    def unit_cost(self, value):
        self.__unit_cost = value
        self._track_changes.add(self._cc('unitCost'))

    @property
    def tax_group_id(self):
        return self.__tax_group_id

    @tax_group_id.setter
    def tax_group_id(self, value):
        self.__tax_group_id = value
        self._track_changes.add(self._cc('taxGroupId'))

    @property
    def tax_group_code(self):
        return self.__tax_group_code

    @tax_group_code.setter
    def tax_group_code(self, value):
        self.__tax_group_code = value
        self._track_changes.add(self._cc('taxGroupCode'))

    @property
    def modified(self):
        return self.__modified

    @property
    def item_category(self):
        return self.__item_category

    @property
    def tax_group(self):
        return self.__tax_group

    @property
    def base_unit_of_measure(self):
        return self.__base_unit_of_measure

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class Customer(FinancialsApiComponent):
    _ENTITY = "customers"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__number = cloud_data.get('number')
        self.__display_name = cloud_data.get('displayName')
        self.__type = cloud_data.get('type')
        self.__address = cloud_data.get('address')
        self.__phone_number = cloud_data.get('phoneNumber')
        self.__email = cloud_data.get('email')
        self.__website = cloud_data.get('website')
        self.__tax_liable = cloud_data.get('taxLiable')
        self.__tax_area_id = cloud_data.get('taxAreaId')
        self.__tax_area_display_name = cloud_data.get('taxAreaDisplayName')
        self.__tax_registration_number = cloud_data.get('taxRegistrationNumber')
        self.__currency_id = cloud_data.get('currencyId')
        self.__currency_code = cloud_data.get('currencyCode')
        self.__payment_terms_id = cloud_data.get('paymentTermsId')
        self.__payment_method_id = cloud_data.get('paymentMethodId')
        self.__shipment_method_id = cloud_data.get('shipmentMethodId')
        self.__blocked = cloud_data.get('blocked', False)
        self.__balance = cloud_data.get('balance', 0)
        self.__overdue_amount = cloud_data.get('overdueAmount', 0)
        self.__total_sales_excluding_tax = cloud_data.get('totalSalesExcludingTax', 0)

        self.__currency = super()._get_entity(entity_id=cloud_data.get('currencyId'), constructor=Currency)
        self.__payment_terms = super()._get_entity(entity_id=cloud_data.get('paymentTermsId'), constructor=PaymentTerm)
        self.__payment_method = super()._get_entity(entity_id=cloud_data.get('paymentMethodId'), constructor=PaymentMethod)
        self.__shipment_method = super()._get_entity(entity_id=cloud_data.get('shipmentMethodId'), constructor=ShipmentMethod)
        self.__tax_area = super()._get_entity(entity_id=cloud_data.get('taxAreaId'), constructor=TaxArea)

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'Item: {}'.format(self.display_name)

    @property
    def number(self):
        return self.__number

    @number.setter
    def number(self, value):
        self.__number = value
        self._track_changes.add(self._cc('number'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def type(self):
        return self.__type

    @type.setter
    def type(self, value):
        self.__type = value
        self._track_changes.add(self._cc('type'))

    @property
    def address(self):
        return self.__address

    @address.setter
    def address(self, value):
        self.__address = value
        self._track_changes.add(self._cc('address'))

    @property
    def phone_number(self):
        return self.__phone_number

    @phone_number.setter
    def phone_number(self, value):
        self.__phone_number = value
        self._track_changes.add(self._cc('phoneNumber'))

    @property
    def email(self):
        return self.__email

    @email.setter
    def email(self, value):
        self.__email = value
        self._track_changes.add(self._cc('email'))

    @property
    def website(self):
        return self.__website

    @website.setter
    def website(self, value):
        self.__website = value
        self._track_changes.add(self._cc('website'))

    @property
    def tax_liable(self):
        return self.__tax_liable

    @tax_liable.setter
    def tax_liable(self, value):
        self.__tax_liable = value
        self._track_changes.add(self._cc('taxLiable'))

    @property
    def tax_area_id(self):
        return self.__tax_area_id

    @tax_area_id.setter
    def tax_area_id(self, value):
        self.__tax_area_id = value
        self._track_changes.add(self._cc('taxAreaId'))

    @property
    def tax_area_display_name(self):
        return self.__tax_area_display_name

    @tax_area_display_name.setter
    def tax_area_display_name(self, value):
        self.__tax_area_display_name = value
        self._track_changes.add(self._cc('taxAreaDisplayName'))

    @property
    def tax_registration_number(self):
        return self.__tax_registration_number

    @tax_registration_number.setter
    def tax_registration_number(self, value):
        self.__tax_registration_number = value
        self._track_changes.add(self._cc('taxRegistrationNumber'))

    @property
    def currency_id(self):
        return self.__currency_id

    @currency_id.setter
    def currency_id(self, value):
        self.__currency_id = value
        self._track_changes.add(self._cc('currencyId'))

    @property
    def currency_code(self):
        return self.__currency_code

    @currency_code.setter
    def currency_code(self, value):
        self.__currency_code = value
        self._track_changes.add(self._cc('currencyCode'))

    @property
    def payment_terms_id(self):
        return self.__payment_terms_id

    @payment_terms_id.setter
    def payment_terms_id(self, value):
        self.__payment_terms_id = value
        self._track_changes.add(self._cc('paymentTermsId'))

    @property
    def shipment_method_id(self):
        return self.__shipment_method_id

    @shipment_method_id.setter
    def shipment_method_id(self, value):
        self.__shipment_method_id = value
        self._track_changes.add(self._cc('shipmentMethodId'))

    @property
    def payment_method_id(self):
        return self.__payment_method_id

    @payment_method_id.setter
    def payment_method_id(self, value):
        self.__payment_method_id = value
        self._track_changes.add(self._cc('paymentMethodId'))

    @property
    def blocked(self):
        return self.__blocked

    @blocked.setter
    def blocked(self, value):
        self.__blocked = value
        self._track_changes.add(self._cc('blocked'))

    @property
    def modified(self):
        return self.__modified

    @property
    def currency(self):
        return self.__currency

    @property
    def payment_term(self):
        return self.__payment_term

    @property
    def shipment_method(self):
        return self.__shipment_method

    @property
    def payment_method(self):
        return self.__payment_method

    @property
    def tax_area(self):
        return self.__tax_area

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class Vendor(FinancialsApiComponent):
    _ENTITY = "vendors"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__number = cloud_data.get('number')
        self.__display_name = cloud_data.get('displayName')
        self.__address = cloud_data.get('address')
        self.__phone_number = cloud_data.get('phoneNumber')
        self.__email = cloud_data.get('email')
        self.__website = cloud_data.get('website')
        self.__tax_registration_number = cloud_data.get('taxRegistrationNumber')
        self.__currency_id = cloud_data.get('currencyId')
        self.__currency_code = cloud_data.get('currencyCode')
        self.__irs_1099_code = cloud_data.get('irs1099Code', None)
        self.__payment_terms_id = cloud_data.get('paymentTermsId')
        self.__payment_method_id = cloud_data.get('paymentMethodId')
        self.__tax_liable = cloud_data.get('taxLiable')
        self.__blocked = cloud_data.get('blocked')
        self.__balance = cloud_data.get('balance')

        self.__currency = super()._get_entity(entity_id=cloud_data.get('currencyId'), constructor=Currency)
        self.__payment_term = super()._get_entity(entity_id=cloud_data.get('paymentTermsId'), constructor=PaymentTerm)
        self.__payment_method = super()._get_entity(entity_id=cloud_data.get('paymentMethodId'), constructor=PaymentMethod)

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'Vendor: {}'.format(self.display_name)

    @property
    def number(self):
        return self.__number

    @number.setter
    def number(self, value):
        self.__number = value
        self._track_changes.add(self._cc('number'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def address(self):
        return self.__address

    @address.setter
    def address(self, value):
        self.__address = value
        self._track_changes.add(self._cc('address'))

    @property
    def phone_number(self):
        return self.__phone_number

    @phone_number.setter
    def phone_number(self, value):
        self.__phone_number = value
        self._track_changes.add(self._cc('phoneNumber'))

    @property
    def email(self):
        return self.__email

    @email.setter
    def email(self, value):
        self.__email = value
        self._track_changes.add(self._cc('email'))

    @property
    def website(self):
        return self.__website

    @website.setter
    def website(self, value):
        self.__website = value
        self._track_changes.add(self._cc('website'))

    @property
    def tax_registration_number(self):
        return self.__tax_registration_number

    @tax_registration_number.setter
    def tax_registration_number(self, value):
        self.__tax_registration_number = value
        self._track_changes.add(self._cc('taxRegistrationNumber'))

    @property
    def currency_id(self):
        return self.__currency_id

    @currency_id.setter
    def currency_id(self, value):
        self.__currency_id = value
        self._track_changes.add(self._cc('currencyId'))

    @property
    def currency_code(self):
        return self.__currency_code

    @currency_code.setter
    def currency_code(self, value):
        self.__currency_code = value
        self._track_changes.add(self._cc('currencyCode'))

    @property
    def irs_1099_code(self):
        return self.__irs_1099_code

    @irs_1099_code.setter
    def irs_1099_code(self, value):
        self.__irs_1099_code = value
        self._track_changes.add(self._cc('irs1099Code'))

    @property
    def payment_terms_id(self):
        return self.__payment_terms_id

    @payment_terms_id.setter
    def payment_terms_id(self, value):
        self.__payment_terms_id = value
        self._track_changes.add(self._cc('paymentTermsId'))

    @property
    def payment_method_id(self):
        return self.__payment_method_id

    @payment_method_id.setter
    def payment_method_id(self, value):
        self.__payment_method_id = value
        self._track_changes.add(self._cc('paymentMethodId'))

    @property
    def tax_liable(self):
        return self.__tax_liable

    @tax_liable.setter
    def tax_liable(self, value):
        self.__tax_liable = value
        self._track_changes.add(self._cc('taxLiable'))

    @property
    def blocked(self):
        return self.__blocked

    @blocked.setter
    def blocked(self, value):
        self.__blocked = value
        self._track_changes.add(self._cc('blocked'))

    @property
    def balance(self):
        return self.__balance

    @property
    def modified(self):
        return self.__modified

    @property
    def currency(self):
        return self.__currency

    @property
    def payment_term(self):
        return self.__payment_term

    @property
    def payment_method(self):
        return self.__payment_method

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class SalesInvoice(FinancialsApiComponent):
    _ENTITY = "salesInvoices"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__number = cloud_data.get('number')
        self.__due_date = cloud_data.get('dueDate')
        self.__customer_number = cloud_data.get('customerNumber')
        self.__contact_id = cloud_data.get('contactId')
        self.__customer_id = cloud_data.get('customerId')
        self.__currency_id = cloud_data.get('currencyId')
        self.__currency_code = cloud_data.get('currencyCode')

        self.__order_id = cloud_data.get('orderId')
        self.__order_number = cloud_data.get('orderNumber')
        self.__status = cloud_data.get('status')

        self.__payment_terms_id = cloud_data.get('paymentTermsId')
        self.__payment_method_id = cloud_data.get('paymentMethodId')
        self.__tax_liable = cloud_data.get('taxLiable')
        self.__blocked = cloud_data.get('blocked')
        self.__balance = cloud_data.get('balance')

        self.__currency = super()._get_entity(entity_id=cloud_data.get('currencyId'), constructor=Currency)
        self.__payment_terms = super()._get_entity(entity_id=cloud_data.get('paymentTermsId'), constructor=PaymentTerm)
        self.__payment_method = super()._get_entity(entity_id=cloud_data.get('paymentMethodId'), constructor=PaymentMethod)

        self.__sales_invoice_lines = self._get_entities(SalesInvoiceLine)

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'SalesInvoice: {}'.format(self.number)

    @property
    def number(self):
        return self.__number

    @property
    def external_document_number(self):
        return self.__external_document_number

    @property
    def invoice_date(self):
        return self.__invoice_date

    @property
    def due_date(self):
        return self.__due_date

    @property
    def customer_purchase_order_reference(self):
        return self.__customer_purchase_order_reference

    @property
    def customer_id(self):
        return self.__customer_id

    @property
    def customer_number(self):
        return self.__customer_number

    @property
    def customer_name(self):
        return self.__customer_name

    @property
    def bill_to_name(self):
        return self.__bill_to_name

    @property
    def bill_to_customer_id(self):
        return self.__bill_to_customer_id

    @property
    def bill_to_customer_number(self):
        return self.__bill_to_customer_number

    @property
    def ship_to_name(self):
        return self.__ship_to_name

    @property
    def ship_to_contact(self):
        return self.__ship_to_contact

    @property
    def selling_postal_address(self):
        return self.__selling_postal_address

    @property
    def billing_postal_address(self):
        return self.__billing_postal_address

    @property
    def shipping_postal_address(self):
        return self.__shipping_postal_address

    @property
    def currency_id(self):
        return self.__currency_id

    @property
    def currency_code(self):
        return self.__currency_code

    @property
    def orderId(self):
        return self.__orderId

    @property
    def orderNumber(self):
        return self.__orderNumber

    @property
    def payment_terms_id(self):
        return self.__payment_terms_id

    @property
    def shipment_method_id(self):
        return self.__shipment_method_id

    @property
    def salesperson(self):
        return self.__salesperson

    @property
    def prices_include_tax(self):
        return self.__prices_include_tax

    @property
    def discount_amount(self):
        return self.__discount_amount

    @property
    def discount_applied_before_tax(self):
        return self.__discount_applied_before_tax

    @property
    def total_amount_excluding_tax(self):
        return self.__total_amount_excluding_tax

    @property
    def total_tax_amount(self):
        return self.__total_tax_amount

    @property
    def total_amount_including_tax(self):
        return self.__total_amount_including_tax

    @property
    def status(self):
        return self.__status

    @property
    def modified(self):
        return self.__modified

    @property
    def phone(self):
        return self.__phone

    @property
    def email(self):
        return self.__email

    @property
    def sales_invoice_lines(self):
        return self.__sales_invoice_lines

    @property
    def customer(self):
        return self.__customer

    @property
    def currency(self):
        return self.__currency

    @property
    def payment_term(self):
        return self.__payment_term

    @property
    def shipment_method(self):
        return self.__shipment_method

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class SalesInvoiceLine(FinancialsApiComponent):
    _ENTITY = "salesInvoiceLines"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__document_id = cloud_data.get('documentId')
        self.__sequence = cloud_data.get('sequence')
        self.__item_id = cloud_data.get('itemId')
        self.__account_id = cloud_data.get('accountId')
        self.__line_type = cloud_data.get('lineType')
        self.__line_details = cloud_data.get('lineDetails')
        self.__description = cloud_data.get('description')
        self.__unit_of_measure_id = cloud_data.get('unitOfMeasureId')
        self.__quantity = cloud_data.get('quantity', 0)
        self.__unit_price = cloud_data.get('unitPrice', 0)
        self.__discount_amount = cloud_data.get('discountAmount', 0)
        self.__discount_percent = cloud_data.get('discountPercent', 0)
        self.__discount_applied_before_tax = cloud_data.get('discountAppliedBeforeTax')
        self.__amount_excluding_tax = cloud_data.get('amountExcludingTax', 0)
        self.__tax_code = cloud_data.get('taxCode')
        self.__tax_percent = cloud_data.get('taxPercent', 0)
        self.__total_tax_amount = cloud_data.get('totalTaxAmount', 0)
        self.__amount_including_tax = cloud_data.get('amountIncludingTax', 0)
        self.__invoice_discount_allocation = cloud_data.get('invoiceDiscountAllocation')
        self.__net_amount = cloud_data.get('netAmount', 0)
        self.__net_tax_amount = cloud_data.get('netTaxAmount', 0)
        self.__net_amount_including_tax = cloud_data.get('netAmountIncludingTax', 0)

        self.__shipment_date = cloud_data.get(self._cc('shipmentDate'), None)
        self.__shipment_date = parse(self.__shipment_date) if self.__shipment_date else None

        self.__unit_of_measure = super()._get_entity(entity_id=cloud_data.get('unitOfMeasureId'), constructor=UnitOfMeasure)
        self.__account = super()._get_entity(entity_id=cloud_data.get('accountId'), constructor=Account)
        self.__item = super()._get_entity(entity_id=cloud_data.get('itemId'), constructor=Item)

    def __repr__(self):
        return 'SalesInvoiceLine: {}'.format(self.item_id)

    @property
    def document_id(self):
        return self.__document_id

    @document_id.setter
    def document_id(self, value):
        self.__document_id = value
        self._track_changes.add(self._cc('documentId'))

    @property
    def sequence(self):
        return self.__sequence

    @sequence.setter
    def sequence(self, value):
        self.__sequence = value
        self._track_changes.add(self._cc('sequence'))

    @property
    def item_id(self):
        return self.__item_id

    @item_id.setter
    def item_id(self, value):
        self.__item_id = value
        self._track_changes.add(self._cc('itemId'))
        self.__item = super()._get_entity(entity_id=self.__item_id, constructor=Item)

    @property
    def account_id(self):
        return self.__account_id

    @account_id.setter
    def account_id(self, value):
        self.__account_id = value
        self._track_changes.add(self._cc('accountId'))
        self.__account = super()._get_entity(entity_id=self.__account_id, constructor=Account)

    @property
    def line_type(self):
        return self.__line_type

    @line_type.setter
    def line_type(self, value):
        self.__line_type = value
        self._track_changes.add(self._cc('lineType'))

    @property
    def description(self):
        return self.__description

    @description.setter
    def description(self, value):
        self.__description = value
        self._track_changes.add(self._cc('description'))

    @property
    def unit_of_measure_id(self):
        return self.__unit_of_measure_id

    @unit_of_measure_id.setter
    def unit_of_measure_id(self, value):
        self.__unit_of_measure_id = value
        self._track_changes.add(self._cc('unitOfMeasureId'))
        self.__unit_of_measure = super()._get_entity(entity_id=self.__unit_of_measure_id, constructor=UnitOfMeasure)

    @property
    def unit_price(self):
        return self.__unit_price

    @unit_price.setter
    def unit_price(self, value):
        self.__unit_price = value
        self._track_changes.add(self._cc('unitPrice'))

    @property
    def quantity(self):
        return self.__quantity

    @quantity.setter
    def quantity(self, value):
        self.__quantity = value
        self._track_changes.add(self._cc('quantity'))

    @property
    def discount_amount(self):
        return self.__discount_amount

    @discount_amount.setter
    def discount_amount(self, value):
        self.__discount_amount = value
        self._track_changes.add(self._cc('discountAmount'))

    @property
    def discount_percent(self):
        return self.__discount_percent

    @discount_percent.setter
    def discount_percent(self, value):
        self.__discount_percent = value
        self._track_changes.add(self._cc('discountPercent'))

    @property
    def discount_applied_before_tax(self):
        return self.__discount_applied_before_tax

    @property
    def amount_excluding_tax(self):
        return self.__amount_excluding_tax

    @property
    def tax_code(self):
        return self.__tax_code

    @tax_code.setter
    def tax_code(self, value):
        self.__tax_code = value
        self._track_changes.add(self._cc('taxCode'))

    @property
    def tax_percent(self):
        return self.__tax_percent

    @property
    def total_tax_amount(self):
        return self.__total_tax_amount

    @property
    def amount_including_tax(self):
        return self.__amount_including_tax

    @property
    def invoice_discount_allocation(self):
        return self.__invoice_discount_allocation

    @property
    def net_amount(self):
        return self.__net_amount

    @property
    def net_tax_amount(self):
        return self.__net_tax_amount

    @property
    def net_amountIncludingTax(self):
        return self.__net_amountIncludingTax

    @property
    def shipment_date(self):
        return self.__shipment_date

    @shipment_date.setter
    def shipment_date(self, value):
        self.__shipment_date = parse(value)
        self._track_changes.add(self._cc('shipmentDate'))

    @property
    def item(self):
        return self.__item

    @property
    def account(self):
        return self.__account

    @property
    def unit_of_measure(self):
        return self.__unit_of_measure

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class CustomerPaymentJournal(FinancialsApiComponent):
    _ENTITY = "customerPaymentJournals"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')
        self.__balancing_account_id = cloud_data.get('balancingAccountId')
        self.__balancing_account_number = cloud_data.get('balancingAccountNumber')

        self.__account = super()._get_entity(entity_id=cloud_data.get('balancingAccountId'), constructor=Account)
        self.__customer_payments = super()._get_entities(constructor=CustomerPayment, parent=self)

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'CustomerPaymentJournal: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def modified(self):
        return self.__modified

    @property
    def balancing_account_id(self):
        return self.__balancing_account_id

    @balancing_account_id.setter
    def balancing_account_id(self, value):
        self.__balancing_account_id = value
        self._track_changes.add(self._cc('displayName'))
        self.__account = super()._get_entity(entity_id=self.__balancing_account_id, constructor=Account)

    @property
    def balancing_account_number(self):
        return self.__balancing_account_number

    @property
    def customer_payments(self):
        return self.__customer_payments

    @property
    def account(self):
        return self.__account

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class CustomerPayment(FinancialsApiComponent):
    _ENTITY = "customerPayments"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__journal_display_name = cloud_data.get('journalDisplayName')
        self.__line_number = cloud_data.get('lineNumber')
        self.__customer_id = cloud_data.get('customerId')
        self.__customer_number = cloud_data.get('customerNumber')
        self.__contact_id = cloud_data.get('contactId')
        self.__document_number = cloud_data.get('documentNumber')
        self.__external_document_number = cloud_data.get('externalDocumentNumber')
        self.__amount = cloud_data.get('amount', 0)
        self.__applies_to_invoice_id = cloud_data.get('appliesToInvoiceId')
        self.__applies_to_invoice_number = cloud_data.get('appliesToInvoiceNumber')
        self.__description = cloud_data.get('description')
        self.__comment = cloud_data.get('comment')

        self.__invoice = super()._get_entity(entity_id=cloud_data.get('appliesToInvoiceId'), constructor=Invoice)
        self.__customer = super()._get_entity(entity_id=cloud_data.get('customerId'), constructor=Customer)

        self.__posting_date = cloud_data.get('postingDate', None)
        self.__posting_date = parse(self.__posting_date) if self.__posting_date else None
        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'CustomerPayment: {}'.format(self.description)

    @property
    def journal_display_name(self):
        return self.__journal_display_name

    @property
    def line_number(self):
        return self.__line_number

    @property
    def customer_id(self):
        return self.__customer_id

    @property
    def customer_number(self):
        return self.__customer_number

    @property
    def contact_id(self):
        return self.__contact_id

    @property
    def posting_date(self):
        return self.__posting_date

    @posting_date.setter
    def posting_date(self, value):
        self.__posting_date = parse(value)
        self._track_changes.add(self._cc('postingDate'))

    @property
    def document_number(self):
        return self.__document_number

    @property
    def external_document_number(self):
        return self.__external_document_number

    @property
    def amount(self):
        return self.__amount

    @amount.setter
    def amount(self, value):
        self.__amount = value
        self._track_changes.add(self._cc('amount'))

    @property
    def applies_to_invoice_id(self):
        return self.__applies_to_invoice_id

    @property
    def applies_to_invoice_number(self):
        return self.__applies_to_invoice_number

    @property
    def description(self):
        return self.__description

    @description.setter
    def description(self, value):
        self.__description = value
        self._track_changes.add(self._cc('description'))

    @property
    def comment(self):
        return self.__comment

    @comment.setter
    def comment(self, value):
        self.__comment = value
        self._track_changes.add(self._cc('comment'))

    @property
    def modified(self):
        return self.__modified

    @property
    def customer(self):
        return self.__customer

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class TaxGroup(FinancialsApiComponent):
    _ENTITY = "taxGroups"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')
        self.__tax_type = cloud_data.get('taxType')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'TaxGroup: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def tax_type(self):
        return self.__tax_type

    @tax_type.setter
    def tax_type(self, value):
        self.__tax_type = value
        self._track_changes.add(self._cc('taxTyp'))

    @property
    def modified(self):
        return self.__modified

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class Journal(FinancialsApiComponent):
    _ENTITY = "journals"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

        self.__balancing_account_id = cloud_data.get('balancingAccountId')
        self.__balancing_account_number = cloud_data.get('balancingAccountNumber')

        self.__account = super()._get_entity(entity_id=cloud_data.get('balancingAccountId'), constructor=Account)
        self.__journal_lines = super()._get_entities(constructor=JournalLine, parent=self)

    def __repr__(self):
        return 'Journal: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def modified(self):
        return self.__modified

    @property
    def balancing_account_id(self):
        return self.__balancing_account_id

    @balancing_account_id.setter
    def balancing_account_id(self, value):
        self.__balancing_account_id = value
        self._track_changes.add(self._cc('displayName'))
        self.__account = super()._get_entity(entity_id=self.__balancing_account_id, constructor=Account)

    @property
    def balancing_account_number(self):
        return self.__balancing_account_number

    @property
    def account(self):
        return self.__account

    @property
    def journal_lines(self):
        return self.__journal_lines

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class JournalLine(FinancialsApiComponent):
    _ENTITY = "journalLines"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__journal_display_name = cloud_data.get('journalDisplayName')
        self.__line_number = cloud_data.get('lineNumber')
        self.__account_id = cloud_data.get('accountId')
        self.__account_number = cloud_data.get('accountNumber')
        self.__document_number = cloud_data.get('documentNumber')
        self.__external_document_number = cloud_data.get('externalDocumentNumber')
        self.__amount = cloud_data.get('amount', 0)
        self.__description = cloud_data.get('description')
        self.__comment = cloud_data.get('comment')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None
        self.__posting_date = cloud_data.get(self._cc('postingDate'), None)
        self.__posting_date = parse(self.__posting_date) if self.__posting_date else None

        self.__account = super()._get_entity(entity_id=cloud_data.get('accountId'), constructor=Account)

    def __repr__(self):
        return 'JournalLine: {}'.format(self.description)

    @property
    def journal_display_name(self):
        return self.__journal_display_name

    @property
    def line_number(self):
        return self.__line_number

    @line_number.setter
    def line_number(self, value):
        self.__line_number = value
        self._track_changes.add(self._cc('lineNumber'))

    @property
    def account_id(self):
        return self.__account_id

    @account_id.setter
    def account_id(self, value):
        self.__account_id = value
        self._track_changes.add(self._cc('accountId'))
        self.__account = super()._get_entity(entity_id=self.__account_id, constructor=Account)
        self.account_number = self.account.number

    @property
    def account_number(self):
        return self.__account_number

    @property
    def posting_date(self):
        return self.__posting_date

    @posting_date.setter
    def posting_date(self, value):
        self.__posting_date = parse(value)
        self._track_changes.add(self._cc('postingDate'))

    @property
    def document_number(self):
        return self.__document_number

    @document_number.setter
    def document_number(self, value):
        self.__document_number = value
        self._track_changes.add(self._cc('documentNumber'))

    @property
    def external_document_number(self):
        return self.__external_document_number

    @external_document_number.setter
    def external_document_number(self, value):
        self.__external_document_number = value
        self._track_changes.add(self._cc('externalDocumentNumber'))

    @property
    def amount(self):
        return self.__amount

    @amount.setter
    def amount(self, value):
        self.__amount = value
        self._track_changes.add(self._cc('amount'))

    @property
    def description(self):
        return self.__description

    @description.setter
    def description(self, value):
        self.__description = value
        self._track_changes.add(self._cc('description'))

    @property
    def comment(self):
        return self.__comment

    @comment.setter
    def comment(self, value):
        self.__comment = value
        self._track_changes.add(self._cc('comment'))

    @property
    def modified(self):
        return self.__modified

    @property
    def account(self):
        return self.__account

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class Employee(FinancialsApiComponent):
    _ENTITY = "employees"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__number = cloud_data.get('number')
        self.__display_name = cloud_data.get('displayName')
        self.__given_name = cloud_data.get('givenName')
        self.__middle_name = cloud_data.get('middleName')
        self.__surname = cloud_data.get('surname')
        self.__address = cloud_data.get('address', {})
        self.__phone_number = cloud_data.get('phoneNumber')
        self.__mobile_phone = cloud_data.get('mobilePhone')
        self.__email = cloud_data.get('email')
        self.__personal_email = cloud_data.get('personalEmail')
        self.__status = cloud_data.get('status')
        self.__job_title = cloud_data.get('jobTitle')
        self.__picture = cloud_data.get('picture')
        self.__statistics_group_code = cloud_data.get('statisticsGroupCode')

        self.__employment_date = cloud_data.get('employmentDate', None)
        self.__employment_date = parse(self.__employment_date) if self.__employment_date else None
        self.__termination_date = cloud_data.get('terminationDate', None)
        self.__termination_date = parse(self.__termination_date) if self.__termination_date else None
        self.__birth_date = cloud_data.get('birthDate', None)
        self.__birth_date = parse(self.__birth_date) if self.__birth_date else None
        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'Employee: {}'.format(self.display_name)

    @property
    def number(self):
        return self.__number

    @number.setter
    def number(self, value):
        self.__number = value
        self._track_changes.add(self._cc('number'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def given_name(self):
        return self.__given_name

    @given_name.setter
    def given_name(self, value):
        self.__given_name = value
        self._track_changes.add(self._cc('givenName'))

    @property
    def middle_name(self):
        return self.__middle_name

    @middle_name.setter
    def middle_name(self, value):
        self.__middle_name = value
        self._track_changes.add(self._cc('middleName'))

    @property
    def surname(self):
        return self.__surname

    @surname.setter
    def surname(self, value):
        self.__surname = value
        self._track_changes.add(self._cc('surname'))

    @property
    def job_title(self):
        return self.__job_title

    @job_title.setter
    def job_title(self, value):
        self.__job_title = value
        self._track_changes.add(self._cc('jobTitle'))

    @property
    def address(self):
        return self.__address

    @address.setter
    def address(self, value):
        self.__address = value
        self._track_changes.add(self._cc('address'))

    @property
    def phone_number(self):
        return self.__phone_number

    @phone_number.setter
    def phone_number(self, value):
        self.__phone_number = value
        self._track_changes.add(self._cc('phoneNumber'))

    @property
    def mobile_phone(self):
        return self.__mobile_phone

    @mobile_phone.setter
    def mobile_phone(self, value):
        self.__mobile_phone = value
        self._track_changes.add(self._cc('mobilePhone'))

    @property
    def email(self):
        return self.__email

    @email.setter
    def email(self, value):
        self.__email = value
        self._track_changes.add(self._cc('email'))

    @property
    def personal_email(self):
        return self.__personal_email

    @personal_email.setter
    def personal_email(self, value):
        self.__personal_email = value
        self._track_changes.add(self._cc('personalEmail'))

    @property
    def employment_date(self):
        return self.__employment_date

    @employment_date.setter
    def employment_date(self, value):
        self.__employment_date = value
        self._track_changes.add(self._cc('employmentDate'))

    @property
    def termination_date(self):
        return self.__termination_date

    @termination_date.setter
    def termination_date(self, value):
        self.__termination_date = value
        self._track_changes.add(self._cc('terminationDate'))

    @property
    def status(self):
        return self.__status

    @status.setter
    def status(self, value):
        self.__status = value
        self._track_changes.add(self._cc('status'))

    @property
    def birth_date(self):
        return self.__birth_date

    @birth_date.setter
    def birth_date(self, value):
        self.__birth_date = value
        self._track_changes.add(self._cc('birthDate'))

    @property
    def statistics_group_code(self):
        return self.__statistics_group_code

    @statistics_group_code.setter
    def statistics_group_code(self, value):
        self.__statistics_group_code = value
        self._track_changes.add(self._cc('statisticsGroupCode'))

    @property
    def modified(self):
        return self.__modified

    @property
    def picture(self):
        return self.__picture

    @picture.setter
    def picture(self, value):
        self.__picture = value
        self._track_changes.add(self._cc('picture'))

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class GeneralLedgerEntry(FinancialsApiComponent):
    _ENTITY = "generalLedgerEntries"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__document_number = cloud_data.get('documentNumber')
        self.__document_type = cloud_data.get('documentType')
        self.__account_id = cloud_data.get('accountId')
        self.__account_number = cloud_data.get('accountNumber')
        self.__description = cloud_data.get('description')
        self.__debit_amount = cloud_data.get('debitAmount', 0)
        self.__credit_amount = cloud_data.get('creditAmount', 0)

        self.__posting_date = cloud_data.get('postingDate', None)
        self.__posting_date = parse(self.__posting_date) if self.__posting_date else None
        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'GeneralLedgerEntry: {}'.format(self.document_number)

    @property
    def posting_date(self):
        return self.__posting_date

    @property
    def document_number(self):
        return self.__document_number

    @property
    def document_type(self):
        return self.__document_type

    @property
    def account_id(self):
        return self.__account_id

    @property
    def account_number(self):
        return self.__account_number

    @property
    def description(self):
        return self.__description

    @property
    def debit_amount(self):
        return self.__debit_amount

    @property
    def credit_amount(self):
        return self.__credit_amount

    @property
    def modified(self):
        return self.__modified

    @property
    def account(self):
        return self.__account


class Currency(FinancialsApiComponent):
    _ENTITY = "currencies"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')
        self.__symbol = cloud_data.get('symbol')
        self.__amount_decimal_places = cloud_data.get('amountDecimalPlaces')
        self.__amount_rounding_precision = cloud_data.get('amountRoundingPrecision')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'Currency: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def symbol(self):
        return self.__symbol

    @symbol.setter
    def symbol(self, value):
        self.__symbol = value
        self._track_changes.add(self._cc('symbol'))

    @property
    def amount_decimal_places(self):
        return self.__amount_decimal_places

    @amount_decimal_places.setter
    def amount_decimal_places(self, value):
        self.__amount_decimal_places = value
        self._track_changes.add(self._cc('amountDecimalPlaces'))

    @property
    def amount_rounding_precision(self):
        return self.__amount_rounding_precision

    @amount_rounding_precision.setter
    def amount_rounding_precision(self, value):
        self.__amount_rounding_precision = value
        self._track_changes.add(self._cc('amountRoundingPrecision'))

    @property
    def modified(self):
        return self.__modified

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class PaymentMethod(FinancialsApiComponent):
    _ENTITY = "paymentMethods"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'PaymentMethod: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def modified(self):
        return self.__modified

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class Dimension(FinancialsApiComponent):
    _ENTITY = "dimensions"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

        self.__dimension_values = self._get_entities(constructor=DimensionValue, parent=self)

    @property
    def code(self):
        return self.__code

    @property
    def display_name(self):
        return self.__display_name

    @property
    def modified(self):
        return self.__modified

    @property
    def dimension_values(self):
        return self.__dimension_values


class DimensionValue(FinancialsApiComponent):
    _ENTITY = "dimensionValues"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    @property
    def code(self):
        return self.__code

    @property
    def display_name(self):
        return self.__display_name

    @property
    def modified(self):
        return self.__modified


class PaymentTerm(FinancialsApiComponent):
    _ENTITY = "paymentTerms"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')
        self.__due_date_calculation = cloud_data.get('dueDateCalculation')
        self.__discount_date_calculation = cloud_data.get('discountDateCalculation')
        self.__discount_percent = cloud_data.get('discountPercent')
        self.__calculate_discount_on_credit_memos = cloud_data.get('calculateDiscountOnCreditMemos')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'PaymentTerm: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def due_date_calculation(self):
        return self.__due_date_calculation

    @due_date_calculation.setter
    def due_date_calculation(self, value):
        self.__due_date_calculation = value
        self._track_changes.add(self._cc('dueDateCalculation'))

    @property
    def discount_date_calculation(self):
        return self.__discount_date_calculation

    @discount_date_calculation.setter
    def discount_date_calculation(self, value):
        self.__discount_date_calculation = value
        self._track_changes.add(self._cc('discountDateCalculation'))

    @property
    def discount_percent(self):
        return self.__discount_percent

    @discount_percent.setter
    def discount_percent(self, value):
        self.__discount_percent = value
        self._track_changes.add(self._cc('discountPercent'))

    @property
    def calculate_discount_on_credit_memos(self):
        return self.__calculate_discount_on_credit_memos

    @calculate_discount_on_credit_memos.setter
    def calculate_discount_on_credit_memos(self, value):
        self.__calculate_discount_on_credit_memos = value
        self._track_changes.add(self._cc('calculateDiscountOnCreditMemos'))

    @property
    def modified(self):
        return self.__modified

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class ShipmentMethod(FinancialsApiComponent):
    _ENTITY = "shipmentMethods"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'ShipmentMethod: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def modified(self):
        return self.__modified

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class ItemCategory(FinancialsApiComponent):
    _ENTITY = "itemCategories"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'ItemCategory: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def modified(self):
        return self.__modified

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class CountryRegion(FinancialsApiComponent):
    _ENTITY = "countriesRegions"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')
        self.__address_format = cloud_data.get('addressFormat')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'Country/Region: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def address_format(self):
        return self.__address_format

    @address_format.setter
    def address_format(self, value):
        self.__address_format = value
        self._track_changes.add(self._cc('addressFormat'))

    @property
    def modified(self):
        return self.__modified

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class SalesOrder(FinancialsApiComponent):
    _ENTITY = "salesOrders"

    @property
    def number(self):
        return self.__number

    @property
    def external_document_number(self):
        return self.__external_document_number

    @property
    def order_date(self):
        return self.__order_date

    @property
    def customer_id(self):
        return self.__customer_id

    @property
    def customer_number(self):
        return self.__customer_number

    @property
    def customer_name(self):
        return self.__customer_name

    @property
    def bill_to_name(self):
        return self.__bill_to_name

    @property
    def bill_to_customer_id(self):
        return self.__bill_to_customer_id

    @property
    def bill_to_customer_number(self):
        return self.__bill_to_customer_number

    @property
    def ship_to_name(self):
        return self.__ship_to_name

    @property
    def ship_to_contact(self):
        return self.__ship_to_contact

    @property
    def selling_postal_address(self):
        return self.__selling_postal_address

    @property
    def billing_postal_address(self):
        return self.__billing_postal_address

    @property
    def shipping_postal_address(self):
        return self.__shipping_postal_address

    @property
    def currency_id(self):
        return self.__currency_id

    @property
    def currency_code(self):
        return self.__currency_code

    @property
    def prices_include_tax(self):
        return self.__prices_include_tax

    @property
    def payment_terms_id(self):
        return self.__payment_terms_id

    @property
    def salesperson(self):
        return self.__salesperson

    @property
    def partial_shipping(self):
        return self.__partial_shipping

    @property
    def requested_delivery_date(self):
        return self.__requested_delivery_date

    @property
    def discount_amount(self):
        return self.__discount_amount

    @property
    def discount_applied_before_tax(self):
        return self.__discount_applied_before_tax

    @property
    def total_amount_excluding_tax(self):
        return self.__total_amount_excluding_tax

    @property
    def total_tax_amount(self):
        return self.__total_tax_amount

    @property
    def total_amount_including_tax(self):
        return self.__

    @property
    def fully_shipped(self):
        return self.__fully_shipped

    @property
    def status(self):
        return self.__status

    @property
    def modified(self):
        return self.__modified

    @property
    def phone(self):
        return self.__phone

    @property
    def email(self):
        return self.__email

    @property
    def sales_order_lines(self):
        return self.__sales_order_lines

    @property
    def customer(self):
        return self.__customer

    @property
    def currency(self):
        return self.__currency

    @property
    def payment_term(self):
        return self.__payment_term


class SalesOrderLine(FinancialsApiComponent):
    _ENTITY = "salesOrderLines"

    @property
    def document_id(self):
        return self.__document_id

    @property
    def sequence(self):
        return self.__sequence

    @property
    def item_id(self):
        return self.__item_id

    @property
    def account_id(self):
        return self.__account_id

    @property
    def line_type(self):
        return self.__line_type

    @property
    def description(self):
        return self.__description

    @property
    def unit_of_measure_id(self):
        return self.__unit_of_measure_id

    @property
    def quantity(self):
        return self.__quantity

    @property
    def unit_price(self):
        return self.__unit_price

    @property
    def discount_amount(self):
        return self.__discount_amount

    @property
    def discount_percent(self):
        return self.__discount_percent

    @property
    def discount_applied_before_tax(self):
        return self.__discount_applied_before_tax

    @property
    def amount_excluding_tax(self):
        return self.__amount_excluding_tax

    @property
    def tax_code(self):
        return self.__tax_code

    @property
    def tax_percent(self):
        return self.__tax_percent

    @property
    def total_tax_amount(self):
        return self.__total_tax_amount

    @property
    def amount_including_tax(self):
        return self.__amount_including_tax

    @property
    def invoice_discount_allocation(self):
        return self.__invoice_discount_allocation

    @property
    def net_amount(self):
        return self.__net_amount

    @property
    def net_tax_amount(self):
        return self.__net_tax_amount

    @property
    def net_amount_including_tax(self):
        return self.__net_amount_including_tax

    @property
    def shipment_date(self):
        return self.__shipment_date

    @property
    def shipped_quantity(self):
        return self.__shipped_quantity

    @property
    def invoiced_quantity(self):
        return self.__invoiced_quantity

    @property
    def invoice_quantity(self):
        return self.__invoice_quantity

    @property
    def ship_quantity(self):
        return self.__ship_quantity

    @property
    def item(self):
        return self.__item

    @property
    def account(self):
        return self.__account


class UnitOfMeasure(FinancialsApiComponent):
    _ENTITY = "unitsOfMeasure"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')
        self.__international_standard_code = cloud_data.get('internationalStandardCode')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'UnitOfMeasure: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def international_standard_code(self):
        return self.__international_standard_code

    @international_standard_code.setter
    def international_standard_code(self, value):
        self.__international_standard_code = value
        self._track_changes.add(self._cc('internationalStandardCode'))

    @property
    def modified(self):
        return self.__modified

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class AgedAccountsReceivable(FinancialsApiComponent):
    _ENTITY = "agedAccountsReceivable"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__customer_id = cloud_data.get('customerId')
        self.__customer_number = cloud_data.get('customerNumber')
        self.__name = cloud_data.get('name')
        self.__currency_code = cloud_data.get('currencyCode')
        self.__balance_due = cloud_data.get('balanceDue')
        self.__current_amount = cloud_data.get('currentAmount')
        self.__period1_amount = cloud_data.get('period1Amount')
        self.__period2_amount = cloud_data.get('period2Amount')
        self.__period3_amount = cloud_data.get('period3Amount')

        self.__aged_as_of_date = cloud_data.get(self._cc('agedAsOfDate'), None)
        self.__aged_as_of_date = parse(self.__aged_as_of_date).astimezone(self.protocol.timezone) if self.__aged_as_of_date else None

        self.__period_length_filter = cloud_data.get('periodLengthFilter')

        if self.customer_id:
            self.__customer = super()._get_entity(entity_id=cloud_data.get('customerId'), constructor=Customer)

    @property
    def customer_id(self):
        return self.__customer_id

    @property
    def customer_number(self):
        return self.__customer_number

    @property
    def name(self):
        return self.__name

    @property
    def currency_code(self):
        return self.__currency_code

    @property
    def balance_due(self):
        return self.__balance_due

    @property
    def current_amount(self):
        return self.__current_amount

    @property
    def period1_amount(self):
        return self.__period1_amount

    @property
    def period2_amount(self):
        return self.__period2_amount

    @property
    def period3_amount(self):
        return self.__period3_amount

    @property
    def aged_as_of_date(self):
        return self.__aged_as_of_date

    @property
    def period_length_filter(self):
        return self.__period_length_filter

    @property
    def customer(self):
        return self.__customer

    def __repr__(self):
        return 'Aged Accounts Receivable: {}'.format(self.name)


class AgedAccountsPayable(FinancialsApiComponent):
    _ENTITY = "agedAccountsPayable"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__vendor_id = cloud_data.get('vendorId')
        self.__vendor_number = cloud_data.get('vendorNumber')
        self.__name = cloud_data.get('name')
        self.__currency_code = cloud_data.get('currencyCode')
        self.__balance_due = cloud_data.get('balanceDue')
        self.__current_amount = cloud_data.get('currentAmount')
        self.__period1_amount = cloud_data.get('period1Amount')
        self.__period2_amount = cloud_data.get('period2Amount')
        self.__period3_amount = cloud_data.get('period3Amount')

        self.__aged_as_of_date = cloud_data.get(self._cc('agedAsOfDate'), None)
        self.__aged_as_of_date = parse(self.__aged_as_of_date).astimezone(self.protocol.timezone) if self.__aged_as_of_date else None

        self.__period_length_filter = cloud_data.get('periodLengthFilter')

        if self.vendor_id:
            self.__vendor = super()._get_entity(entity_id=self.vendor_id, constructor=Customer)

    @property
    def vendor_id(self):
        return self.__vendor_id

    @property
    def vendor_number(self):
        return self.__vendor_number

    @property
    def name(self):
        return self.__name

    @property
    def currency_code(self):
        return self.__currency_code

    @property
    def balance_due(self):
        return self.__balance_due

    @property
    def current_amount(self):
        return self.__current_amount

    @property
    def period1_amount(self):
        return self.__period1_amount

    @property
    def period2_amount(self):
        return self.__period2_amount

    @property
    def period3_amount(self):
        return self.__period3_amount

    @property
    def aged_as_of_date(self):
        return self.__aged_as_of_date

    @property
    def period_length_filter(self):
        return self.__period_length_filter

    @property
    def vendor(self):
        return self.__vendor

    def __repr__(self):
        return 'Aged Accounts Payable: {}'.format(self.name)


class TaxArea(FinancialsApiComponent):
    _ENTITY = "taxAreas"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__code = cloud_data.get('code')
        self.__display_name = cloud_data.get('displayName')
        self.__tax_type = cloud_data.get('faxNumber')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'TaxArea: {}'.format(self.display_name)

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, value):
        self.__code = value
        self._track_changes.add(self._cc('code'))

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def tax_type(self):
        return self.__tax_type

    @tax_type.setter
    def tax_type(self, value):
        self.__tax_type = value
        self._track_changes.add(self._cc('taxType'))

    @property
    def modified(self):
        return self.__modified

    def update(self):
        return super()._update()

    def delete(self):
        return super()._delete()

    def create(self):
        return super()._create()


class SalesQuote(FinancialsApiComponent):
    _ENTITY = "salesQuotes"

    @property
    def number(self):
        return self.__number

    @property
    def external_document_number(self):
        return self.__external_document_number

    @property
    def document_date(self):
        return self.__document_date

    @property
    def due_date(self):
        return self.__due_date

    @property
    def customer_id(self):
        return self.__customer_id

    @property
    def customer_number(self):
        return self.__customer_number

    @property
    def customer_name(self):
        return self.__customer_name

    @property
    def bill_to_name(self):
        return self.__bill_to_name

    @property
    def bill_to_customer_id(self):
        return self.__bill_to_customer_id

    @property
    def bill_to_customer_number(self):
        return self.__bill_to_customer_number

    @property
    def ship_to_name(self):
        return self.__ship_to_name

    @property
    def ship_to_contact(self):
        return self.__ship_to_contact

    @property
    def selling_postal_address(self):
        return self.__selling_postal_address

    @property
    def billing_postal_address(self):
        return self.__billing_postal_address

    @property
    def shipping_postal_address(self):
        return self.__shipping_postal_address

    @property
    def currency_id(self):
        return self.__currency_id

    @property
    def currency_code(self):
        return self.__currency_code

    @property
    def payment_terms_id(self):
        return self.__payment_terms_id

    @property
    def shipment_method_id(self):
        return self.__shipment_method_id

    @property
    def salesperson(self):
        return self.__salesperson

    @property
    def discount_amount(self):
        return self.__discount_amount

    @property
    def total_amount_excluding_tax(self):
        return self.__total_amount_excluding_tax

    @property
    def total_tax_amount(self):
        return self.__total_tax_amount

    @property
    def total_amount_including_tax(self):
        return self.__total_amount_including_tax

    @property
    def status(self):
        return self.__status

    @property
    def sent_date(self):
        return self.__sent_date

    @property
    def valid_until_date(self):
        return self.__valid_until_date

    @property
    def accepted(self):
        return self.__accepted

    @property
    def modified(self):
        return self.__modified

    @property
    def phone(self):
        return self.__phone

    @property
    def email(self):
        return self.__email

    @property
    def sales_quote_lines(self):
        return self.__sales_quote_lines

    @property
    def customer(self):
        return self.__customer

    @property
    def currency(self):
        return self.__currency

    @property
    def payment_term(self):
        return self.__payment_term

    @property
    def shipment_method(self):
        return self.__shipment_method


class SalesQuoteLine(FinancialsApiComponent):
    _ENTITY = "salesQuoteLines"

    @property
    def document_id(self):
        return self.__document_id

    @property
    def sequence(self):
        return self.__sequence

    @property
    def item_id(self):
        return self.__item_id

    @property
    def account_id(self):
        return self.__account_id

    @property
    def line_type(self):
        return self.__line_type

    @property
    def description(self):
        return self.__description

    @property
    def unit_of_measure_id(self):
        return self.__unit_of_measure_id

    @property
    def unit_price(self):
        return self.__unit_price

    @property
    def quantity(self):
        return self.__quantity

    @property
    def discount_amount(self):
        return self.__discount_amount

    @property
    def discount_percent(self):
        return self.__discount_percent

    @property
    def discount_applied_before_tax(self):
        return self.__discount_applied_before_tax

    @property
    def amount_excluding_tax(self):
        return self.__amount_excluding_tax

    @property
    def tax_code(self):
        return self.__tax_code

    @property
    def tax_percent(self):
        return self.__tax_percent

    @property
    def total_tax_amount(self):
        return self.__total_tax_amount

    @property
    def amount_including_tax(self):
        return self.__amount_including_tax

    @property
    def net_amount(self):
        return self.__net_amount

    @property
    def net_tax_amount(self):
        return self.__net_tax_amount

    @property
    def net_amount_including_tax(self):
        return self.__net_amount_including_tax

    @property
    def item(self):
        return self.__item

    @property
    def account(self):
        return self.__account


class SalesCreditMemo(FinancialsApiComponent):
    _ENTITY = "salesCreditMemos"

    @property
    def number(self):
        return self.__number

    @property
    def external_document_number(self):
        return self.__external_document_number

    @property
    def credit_memo_date(self):
        return self.__credit_memo_date

    @property
    def due_date(self):
        return self.__due_date

    @property
    def customer_id(self):
        return self.__customer_id

    @property
    def customer_number(self):
        return self.__customer_number

    @property
    def customer_name(self):
        return self.__customer_name

    @property
    def bill_to_name(self):
        return self.__bill_to_name

    @property
    def bill_to_customer_id(self):
        return self.__bill_to_customer_id

    @property
    def bill_to_customer_number(self):
        return self.__bill_to_customer_number

    @property
    def selling_postal_address(self):
        return self.__selling_postal_address

    @property
    def billing_postal_address(self):
        return self.__billing_postal_address

    @property
    def currency_id(self):
        return self.__currency_id

    @property
    def currency_code(self):
        return self.__currency_code

    @property
    def payment_terms_id(self):
        return self.__payment_terms_id

    @property
    def salesperson(self):
        return self.__salesperson

    @property
    def prices_include_tax(self):
        return self.__prices_include_tax

    @property
    def discount_amount(self):
        return self.__discount_amount

    @property
    def discount_applied_before_tax(self):
        return self.__discount_applied_before_tax

    @property
    def total_amount_excluding_tax(self):
        return self.__total_amount_excluding_tax

    @property
    def total_tax_amount(self):
        return self.__total_tax_amount

    @property
    def total_amount_including_tax(self):
        return self.__total_amount_including_tax

    @property
    def status(self):
        return self.__status

    @property
    def modified(self):
        return self.__modified

    @property
    def invoice_id(self):
        return self.__invoice_id

    @property
    def invoice_number(self):
        return self.__invoice_number

    @property
    def phone(self):
        return self.__phone

    @property
    def email(self):
        return self.__email

    @property
    def sales_credit_memo_lines(self):
        return self.__sales_credit_memo_lines

    @property
    def customer(self):
        return self.__customer

    @property
    def currency(self):
        return self.__currency

    @property
    def payment_term(self):
        return self.__payment_term


class SalesCreditMemoLine(FinancialsApiComponent):
    _ENTITY = "salesCreditMemoLines"

    @property
    def document_id(self):
        return self.__document_id

    @property
    def sequence(self):
        return self.__sequence

    @property
    def item_id(self):
        return self.__item_id

    @property
    def account_id(self):
        return self.__account_id

    @property
    def line_type(self):
        return self.__line_type

    @property
    def description(self):
        return self.__description

    @property
    def unit_of_measure_id(self):
        return self.__unit_of_measure_id

    @property
    def unit_price(self):
        return self.__unit_price

    @property
    def quantity(self):
        return self.__quantity

    @property
    def discount_amount(self):
        return self.__discount_amount

    @property
    def discount_percent(self):
        return self.__discount_percent

    @property
    def discount_applied_before_tax(self):
        return self.__discount_applied_before_tax

    @property
    def amount_excluding_tax(self):
        return self.__amount_excluding_tax

    @property
    def tax_code(self):
        return self.__tax_code

    @property
    def tax_percent(self):
        return self.__tax_percent

    @property
    def total_tax_amount(self):
        return self.__total_tax_amount

    @property
    def amount_including_tax(self):
        return self.__amount_including_tax

    @property
    def invoice_discount_allocation(self):
        return self.__invoice_discount_allocation

    @property
    def net_amount(self):
        return self.__net_amount

    @property
    def net_tax_amount(self):
        return self.__net_tax_amount

    @property
    def net_amount_including_tax(self):
        return self.__net_amount_including_tax

    @property
    def shipment_date(self):
        return self.__shipment_date

    @property
    def item(self):
        return self.__item

    @property
    def account(self):
        return self.__account


class PurchaseInvoice(FinancialsApiComponent):
    _ENTITY = "purchaseInvoices"

    @property
    def number(self):
        return self.__number

    @property
    def invoice_date(self):
        return self.__invoice_date

    @property
    def due_date(self):
        return self.__due_date

    @property
    def vendor_invoice_number(self):
        return self.__vendor_invoice_number

    @property
    def vendor_id(self):
        return self.__vendor_id

    @property
    def vendor_number(self):
        return self.__vendor_number

    @property
    def vendor_name(self):
        return self.__vendor_name

    @property
    def pay_to_name(self):
        return self.__pay_to_name

    @property
    def pay_to_contact(self):
        return self.__pay_to_contact

    @property
    def pay_to_vendor_id(self):
        return self.__pay_to_vendor_id

    @property
    def pay_to_vendor_number(self):
        return self.__pay_to_vendor_number

    @property
    def ship_to_name(self):
        return self.__ship_to_name

    @property
    def ship_to_contact(self):
        return self.__ship_to_contact

    @property
    def buy_from_address(self):
        return self.__buy_from_address

    @property
    def pay_to_address(self):
        return self.__pay_to_address

    @property
    def ship_to_address(self):
        return self.__ship_to_address

    @property
    def currency_id(self):
        return self.__currency_id

    @property
    def currency_code(self):
        return self.__currency_code

    @property
    def prices_include_tax(self):
        return self.__prices_include_tax

    @property
    def discount_amount(self):
        return self.__discount_amount

    @property
    def discount_applied_before_tax(self):
        return self.__discount_applied_before_tax

    @property
    def total_amount_excluding_tax(self):
        return self.__total_amount_excluding_tax

    @property
    def total_tax_amount(self):
        return self.__total_tax_amount

    @property
    def total_amount_including_tax(self):
        return self.__total_amount_including_tax

    @property
    def status(self):
        return self.__status

    @property
    def modified(self):
        return self.__modified

    @property
    def purchase_invoice_lines(self):
        return self.__purchase_invoice_lines

    @property
    def vendor(self):
        return self.__vendor

    @property
    def currency(self):
        return self.__currency


class PurchaseInvoiceLine(FinancialsApiComponent):
    _ENTITY = "purchaseInvoiceLines"

    @property
    def document_id(self):
        return self.__document_id

    @property
    def sequence(self):
        return self.__sequence

    @property
    def item_id(self):
        return self.__item_id

    @property
    def account_id(self):
        return self.__account_id

    @property
    def line_type(self):
        return self.__line_type

    @property
    def description(self):
        return self.__description

    @property
    def unit_cost(self):
        return self.__unit_cost

    @property
    def quantity(self):
        return self.__quantity

    @property
    def discount_amount(self):
        return self.__discount_amount

    @property
    def discount_percent(self):
        return self.__discount_percent

    @property
    def discount_applied_before_tax(self):
        return self.__discount_applied_before_tax

    @property
    def amount_excluding_tax(self):
        return self.__amount_excluding_tax

    @property
    def tax_code(self):
        return self.__tax_code

    @property
    def tax_percent(self):
        return self.__tax_percent

    @property
    def total_tax_amount(self):
        return self.__total_tax_amount

    @property
    def amount_including_tax(self):
        return self.__amount_including_tax

    @property
    def invoice_discount_allocation(self):
        return self.__invoice_discount_allocation

    @property
    def net_amount(self):
        return self.__net_amount

    @property
    def net_tax_amount(self):
        return self.__net_tax_amount

    @property
    def net_amount_including_tax(self):
        return self.__net_amount_including_tax

    @property
    def expected_receipt_date(self):
        return self.__expected_receipt_date

    @property
    def item(self):
        return self.__item

    @property
    def account(self):
        return self.__account


class CompanyInformation(FinancialsApiComponent):
    _ENTITY = "companyInformation"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__display_name = cloud_data.get('displayName')
        self.__phone = cloud_data.get('phoneNumber')
        self.__fax = cloud_data.get('faxNumber')
        self.__email = cloud_data.get('email')
        self.__website = cloud_data.get('website')
        self.__tax_registration_number = cloud_data.get('taxRegistrationNumber')
        self.__currency_code = cloud_data.get('currencyCode')
        self.__industry = cloud_data.get('industry')
        self.__address = cloud_data.get('address', {})

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None
        self.__current_fiscal_year_start_date = cloud_data.get('currentFiscalYearStartDate', None)
        self.__current_fiscal_year_start_date = parse(self.__current_fiscal_year_start_date) if self.__current_fiscal_year_start_date else None

    def __repr__(self):
        return 'CompanyInformation: {}'.format(self.display_name)

    @property
    def id(self):
        return self.object_id

    @property
    def display_name(self):
        return self.__display_name

    @display_name.setter
    def display_name(self, value):
        self.__display_name = value
        self._track_changes.add(self._cc('displayName'))

    @property
    def currency_code(self):
        return self.__currency_code

    @property
    def modified(self):
        return self.__modified

    @property
    def website(self):
        return self.__website

    @website.setter
    def website(self, value):
        self.__website = value
        self._track_changes.add(self._cc('website'))

    @property
    def email(self):
        return self.__email

    @email.setter
    def email(self, value):
        self.__email = value
        self._track_changes.add(self._cc('email'))

    @property
    def phone(self):
        return self.__phone

    @phone.setter
    def phone(self, value):
        self.__phone = value
        self._track_changes.add(self._cc('phoneNumber'))

    @property
    def fax(self):
        return self.__fax

    @fax.setter
    def fax(self, value):
        self.__fax = value
        self._track_changes.add(self._cc('faxNumber'))

    @property
    def tax_registration_number(self):
        return self.__tax_registration_number

    @tax_registration_number.setter
    def tax_registration_number(self, value):
        self.__tax_registration_number = value
        self._track_changes.add(self._cc('taxRegistrationNumber'))

    @property
    def address(self):
        return self.__address

    @address.setter
    def address(self, value):
        self.__address = value
        self._track_changes.add(self._cc('address'))

    @property
    def industry(self):
        return self.__industry

    @industry.setter
    def industry(self, value):
        self.__industry = value
        self._track_changes.add(self._cc('industry'))

    @property
    def current_fiscal_year_start_date(self):
        return self.__current_fiscal_year_start_date

    @property
    def picture(self):
        return self.__picture

    def update(self):
        super()._update()


class Account(FinancialsApiComponent):
    _ENTITY = "accounts"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(parent=parent, con=con, **kwargs)

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.__number = cloud_data.get('number')
        self.__display_name = cloud_data.get('displayName')
        self.__category = cloud_data.get('category')
        self.__sub_category = cloud_data.get('subCategory')
        self.__blocked = cloud_data.get('blocked')

        self.__modified = cloud_data.get(self._cc('lastModifiedDateTime'), None)
        self.__modified = parse(self.__modified).astimezone(self.protocol.timezone) if self.__modified else None

    def __repr__(self):
        return 'Account: {}'.format(self.display_name)

    @property
    def number(self):
        return self.__number

    @property
    def display_name(self):
        return self.__display_name

    @property
    def category(self):
        return self.__category

    @property
    def sub_category(self):
        return self.__sub_category

    @property
    def blocked(self):
        return self.__blocked

    @property
    def modified(self):
        return self.__modified


class Company(FinancialsApiComponent):
    _ENTITY = "companies"

    def __init__(self, *, parent=None, con=None, **kwargs):
        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'))

        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        cloud_data = kwargs.get(self._cloud_data_key, {})

        self.object_id = cloud_data.get('id')

        self.__name = cloud_data.get('name')
        self.__display_name = cloud_data.get('displayName')
        self.__system_version = cloud_data.get('systemVersion')
        self.__business_profile_id = cloud_data.get('businessProfileId')

    def __repr__(self):
        return 'Company: {}'.format(self.display_name)

    @property
    def id(self):
        return self.object_id

    @property
    def name(self):
        return self.__name

    @property
    def display_name(self):
        return self.__display_name

    @property
    def system_version(self):
        return self.__system_version

    @property
    def business_profile_id(self):
        return self.__business_profile_id

    def get_company_information(self):
        return super()._get_entities(constructor=CompanyInformation)

    def get_accounts(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=Account, limit=limit, query=query, order_by=order_by)

    def get_account(self, id=None):
        return super()._get_entity(entity_id=id, constructor=Account)

    def get_aged_accounts_payables(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=AgedAccountsPayable, limit=limit, query=query, order_by=order_by)

    def get_aged_accounts_receivables(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=AgedAccountsReceivable, limit=limit, query=query, order_by=order_by)

    def get_countries_regions(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=CountryRegion, limit=limit, query=query, order_by=order_by)

    def get_country_region(self, id=None):
        return super()._get_entity(entity_id=id, constructor=CountryRegion)

    def get_currencies(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=Currency, limit=limit, query=query, order_by=order_by)

    def get_currency(self, id=None):
        return super()._get_entity(entity_id=id, constructor=Currency)

    def get_customers(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=Customer, limit=limit, query=query, order_by=order_by)

    def get_customer(self, id=None):
        return super()._get_entity(entity_id=id, constructor=Customer)

    def get_customer_payments(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=CustomerPayment, limit=limit, query=query, order_by=order_by)

    def get_customer_payment(self, id=None):
        return super()._get_entity(entity_id=id, constructor=CustomerPayment)

    def get_customer_payment_journals(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=CustomerPaymentJournal, limit=limit, query=query, order_by=order_by)

    def get_customer_payment_journal(self, id=None):
        return super()._get_entity(entity_id=id, constructor=CustomerPaymentJournal)

    def get_dimensions(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=Dimension, limit=limit, query=query, order_by=order_by)

    def get_dimension(self, id=None):
        return super()._get_entity(entity_id=id, constructor=Dimension)

    def get_dimension_values(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=DimensionValue, limit=limit, query=query, order_by=order_by)

    def get_dimension_value(self, id=None):
        return super()._get_entity(entity_id=id, constructor=DimensionValue)

    def get_employees(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=Employee, limit=limit, query=query, order_by=order_by)

    def get_employee(self, id=None):
        return super()._get_entity(entity_id=id, constructor=Employee)

    def get_gl_entries(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=GeneralLedgerEntry, limit=limit, query=query, order_by=order_by)

    def get_gl_entry(self, id=None):
        return super()._get_entity(entity_id=id, constructor=GeneralLedgerEntry)

    def get_items(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=Item, limit=limit, query=query, order_by=order_by)

    def get_item(self, id=None):
        return super()._get_entity(entity_id=id, constructor=Item)

    def get_item_categories(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=ItemCategory, limit=limit, query=query, order_by=order_by)

    def get_item_category(self, id=None):
        return super()._get_entity(entity_id=id, constructor=ItemCategory)

    def get_journals(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=Journal, limit=limit, query=query, order_by=order_by)

    def get_journal(self, id=None):
        return super()._get_entity(entity_id=id, constructor=Journal)

    def get_payment_methods(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=PaymentMethod, limit=limit, query=query, order_by=order_by)

    def get_payment_method(self, id=None):
        return super()._get_entity(entity_id=id, constructor=PaymentMethod)

    def get_payment_terms(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=PaymentTerm, limit=limit, query=query, order_by=order_by)

    def get_payment_term(self, id=None):
        return super()._get_entity(entity_id=id, constructor=PaymentTerm)

    def get_shipment_methods(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=ShipmentMethod, limit=limit, query=query, order_by=order_by)

    def get_shipment_method(self, id=None):
        return super()._get_entity(entity_id=id, constructor=ShipmentMethod)

    def get_tax_areas(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=TaxArea, limit=limit, query=query, order_by=order_by)

    def get_tax_area(self, id=None):
        return super()._get_entity(entity_id=id, constructor=TaxArea)

    def get_tax_groups(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=TaxGroup, limit=limit, query=query, order_by=order_by)

    def get_tax_group(self, id=None):
        return super()._get_entity(entity_id=id, constructor=TaxGroup)

    def get_units_of_measures(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=UnitOfMeasure, limit=limit, query=query, order_by=order_by)

    def get_units_of_measure(self, id=None):
        return super()._get_entity(entity_id=id, constructor=UnitOfMeasure)

    def get_vendors(self, limit=None, *, query=None, order_by=None):
        return super()._get_entities(constructor=Vendor, limit=limit, query=query, order_by=order_by)

    def get_vendor(self, id=None):
        return super()._get_entity(entity_id=id, constructor=Vendor)


class Financials(ApiComponent):
    _endpoints = {
        'get_companies': '/companies',
        'get_company': '/companies/{id}',
        'get_company_bc': '/companies({id})'
    }

    company_constructor = Company

    def __init__(self, *, parent=None, con=None, **kwargs):
        if parent and con:
            raise ValueError('Need a parent or a connection but not both')
        self.con = parent.con if parent else con

        # Choose the main_resource passed in kwargs over parent main_resource
        if type(parent.protocol) == MSBusinessCentral365Protocol:
            main_resource = ''
        else:
            main_resource = 'financials'

        super().__init__(protocol=parent.protocol if parent else kwargs.get('protocol'), main_resource=main_resource)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return 'Financials resource: {}'.format(self.main_resource)

    def get_companies(self, limit=None, *, query=None, order_by=None):
        url = self.build_url(self._endpoints.get('get_companies'))

        params = {}
        if limit:
            params['$top'] = limit
        if query:
            params['$filter'] = str(query)
        if order_by:
            params['$orderby'] = order_by

        response = self.con.get(url, params=params or None)
        if not response:
            return []

        data = response.json()

        # Everything received from cloud must be passed as self._cloud_data_key
        objects = [self.company_constructor(parent=self, **{
            self._cloud_data_key: x}) for x in data.get('value', [])]

        return objects

    def get_company(self, company_id=None):
        if not company_id:
            raise RuntimeError('Provide one of the options')

        if company_id:
            # get calendar by it's id
            if type(self.protocol) == MSBusinessCentral365Protocol:
                url = self.build_url(self._endpoints.get('get_company_bc').format(id=company_id))
            else:
                url = self.build_url(self._endpoints.get('get_company').format(id=company_id))
            params = None

        response = self.con.get(url, params=params)
        if not response:
            return None

        if company_id:
            data = response.json()
        else:
            data = response.json().get('value')
            data = data[0] if data else None
            if data is None:
                return None

        # Everything received from cloud must be passed as self._cloud_data_key
        return self.company_constructor(parent=self, **{self._cloud_data_key: data})
