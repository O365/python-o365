import datetime as dt
import logging
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.parser import parse
from requests.exceptions import HTTPError

from .utils import ApiComponent, get_iana_tz

log = logging.getLogger(__name__)


class WorkPlanOccurrence(ApiComponent):
    """A work-hours and location occurrence returned by Microsoft Graph."""

    windows_time_zone_fallbacks = {
        # Some Windows mappings resolve to legacy IANA names that are not
        # present in zoneinfo databases (e.g. US/Pacific-New).
        "Pacific Standard Time": "America/Los_Angeles",
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
        """A work-hours and location occurrence

        :param parent: parent object
        :type parent: Account
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )

        cloud_data = kwargs.get(self._cloud_data_key, {})
        cc = self._cc

        #: The unique id of the occurrence. |br| **Type:** str
        self.object_id = cloud_data.get(cc("id"))
        if not self.object_id:
            raise ValueError("Missing occurrence id")
        #: Alias of object_id. |br| **Type:** str
        self.id = self.object_id

        #: The id of the recurrence this occurrence belongs to. |br| **Type:** str
        self.recurrence_id = cloud_data.get(cc("recurrenceId"))
        #: The work location type, e.g. office, remote, timeOff. |br| **Type:** str
        self.work_location_type = cloud_data.get(cc("workLocationType"), "")

        start_payload = cloud_data.get(cc("startDateTime")) or cloud_data.get(
            cc("start")
        )
        end_payload = cloud_data.get(cc("endDateTime")) or cloud_data.get(cc("end"))

        #: The time zone of the occurrence. |br| **Type:** str
        self.time_zone = (
            cloud_data.get(cc("timeZone"))
            or self._extract_time_zone(start_payload)
            or self._extract_time_zone(end_payload)
        )

        #: Start of the occurrence, in the protocol time zone. |br| **Type:** datetime
        self.start = self._parse_occurrence_datetime(start_payload, self.time_zone)
        #: End of the occurrence, in the protocol time zone. |br| **Type:** datetime
        self.end = self._parse_occurrence_datetime(end_payload, self.time_zone)

        #: The location details of the occurrence. |br| **Type:** dict
        self.location = cloud_data.get(cc("location")) or cloud_data.get(
            cc("workLocation")
        )

        #: Valid workLocationType values; populated when include_valid_values is requested. |br| **Type:** list[str]
        self.valid_work_location_types = None

        if self.start is None or self.end is None:
            raise ValueError("Occurrence is missing a valid start or end datetime")

    def _extract_time_zone(self, payload):
        if not isinstance(payload, dict):
            return None
        return payload.get(self._cc("timeZone"))

    def _resolve_time_zone(self, time_zone_name):
        if time_zone_name:
            try:
                return ZoneInfo(time_zone_name)
            except ZoneInfoNotFoundError:
                try:
                    return get_iana_tz(time_zone_name)
                except ZoneInfoNotFoundError:
                    fallback_zone = self.windows_time_zone_fallbacks.get(time_zone_name)
                    if fallback_zone:
                        try:
                            return ZoneInfo(fallback_zone)
                        except ZoneInfoNotFoundError:
                            pass
                    log.debug(
                        "TimeZone not found in IANA or Windows maps: %s. Using protocol timezone.",
                        time_zone_name,
                    )

        return self.protocol.timezone

    def _parse_occurrence_datetime(self, payload, fallback_time_zone):
        if payload is None:
            return None

        cc = self._cc
        date_time_raw = payload
        time_zone_name = fallback_time_zone

        if isinstance(payload, dict):
            date_time_raw = payload.get(cc("dateTime"))
            time_zone_name = payload.get(cc("timeZone")) or fallback_time_zone

        if not date_time_raw:
            return None

        parsed = parse(date_time_raw)

        if parsed.tzinfo is not None:
            date_time = parsed
        else:
            date_time = parsed.replace(tzinfo=self._resolve_time_zone(time_zone_name))

        return date_time.astimezone(self.protocol.timezone)


class WorkHoursAndLocations(ApiComponent):
    """Read work-hours and location occurrences from Microsoft Graph."""

    #: Fallback workLocationType values used when Graph metadata is unavailable. |br| **Type:** tuple[str]
    default_work_location_types = (
        "unspecified",
        "office",
        "remote",
        "timeOff",
        "unknownFutureValue",
    )
    occurrence_constructor = WorkPlanOccurrence  #: :meta private:

    def __init__(self, *, parent=None, con=None, **kwargs):
        """Object to retrieve work-hours and location occurrences

        :param parent: parent object
        :type parent: Account
        :param Connection con: connection to use if no parent specified
        :param Protocol protocol: protocol to use if no parent specified
         (kwargs)
        :param str main_resource: use this resource instead of parent resource
         (kwargs)
        """
        if parent and con:
            raise ValueError("Need a parent or a connection but not both")
        self.con = parent.con if parent else con

        main_resource = kwargs.pop("main_resource", None) or (
            getattr(parent, "main_resource", None) if parent else None
        )

        super().__init__(
            protocol=parent.protocol if parent else kwargs.get("protocol"),
            main_resource=main_resource,
        )
        self._work_location_types_cache = None

    @staticmethod
    def _validate_datetime(value, name):
        if not isinstance(value, dt.datetime):
            raise ValueError(f"'{name}' must be a datetime instance")
        return value

    def _serialize_graph_datetime(self, value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=self.protocol.timezone)
        return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _build_occurrences_view_url(self, start_datetime, end_datetime, user=None):
        resource = "/me" if user is None else f"/users/{user}"
        start_value = self._serialize_graph_datetime(start_datetime)
        end_value = self._serialize_graph_datetime(end_datetime)
        endpoint = (
            "/settings/workHoursAndLocations/occurrencesView"
            f"(startDateTime='{start_value}',endDateTime='{end_value}')"
        )
        return f"{self.protocol.service_url.rstrip('/')}{resource}{endpoint}"

    @staticmethod
    def _extract_work_location_type_members(metadata_xml):
        if not metadata_xml:
            return []

        try:
            root = ET.fromstring(metadata_xml)
        except ET.ParseError:
            return []

        for enum_type in root.findall(".//{*}EnumType"):
            if enum_type.attrib.get("Name") != "workLocationType":
                continue
            return [
                member.attrib.get("Name")
                for member in enum_type.findall("{*}Member")
                if member.attrib.get("Name")
            ]
        return []

    def get_valid_work_location_types(self, force_refresh=False):
        """Return valid workLocationType values from Graph metadata.

        Falls back to known Graph enum defaults when metadata is unavailable.
        """
        if self._work_location_types_cache is not None and not force_refresh:
            return list(self._work_location_types_cache)

        metadata_url = f"{self.protocol.service_url.rstrip('/')}/$metadata"
        resolved_types = []

        try:
            response = self.con.get(metadata_url)
            if response:
                resolved_types = self._extract_work_location_type_members(
                    getattr(response, "text", "")
                )
        except HTTPError as e:
            log.debug(
                "Could not read Graph metadata for workLocationType values. Error: %s",
                e,
            )

        if not resolved_types:
            resolved_types = list(self.default_work_location_types)

        self._work_location_types_cache = tuple(resolved_types)
        return list(self._work_location_types_cache)

    def occurrences_view(
        self,
        start_datetime,
        end_datetime,
        user=None,
        top=None,
        select=None,
        include_valid_values=False,
    ):
        """Return work plan occurrences in a datetime range.

        :param datetime start_datetime: range start datetime
        :param datetime end_datetime: range end datetime
        :param str user: optional user id/upn, defaults to /me when omitted
        :param int top: optional OData $top
        :param list[str] select: optional OData $select fields
        :param bool include_valid_values: include valid workLocationType values on each item
        :rtype: list[WorkPlanOccurrence]
        """
        start_datetime = self._validate_datetime(start_datetime, "start_datetime")
        end_datetime = self._validate_datetime(end_datetime, "end_datetime")

        if end_datetime <= start_datetime:
            raise ValueError("'end_datetime' must be greater than 'start_datetime'")

        if user is not None and not isinstance(user, str):
            raise ValueError("'user' must be a string when provided")

        url = self._build_occurrences_view_url(start_datetime, end_datetime, user=user)

        params = {}
        if top is not None:
            if not isinstance(top, int) or top <= 0:
                raise ValueError("'top' must be a positive integer")
            params["$top"] = top
        if select is not None:
            if not isinstance(select, (list, tuple)) or not all(
                isinstance(field, str) for field in select
            ):
                raise ValueError("'select' must be a list of strings")
            params["$select"] = ",".join(select)
        if not isinstance(include_valid_values, bool):
            raise ValueError("'include_valid_values' must be a boolean")

        try:
            response = self.con.get(url, params=params or None)
        except HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            if status_code in (403, 404):
                message = (
                    "Work-hours endpoint is unavailable for this tenant/user "
                    f"(status: {status_code})"
                )
            else:
                message = (
                    "Failed to fetch work-hours occurrences; this may be transient"
                )
                if status_code:
                    message = f"{message} (status: {status_code})"

            raise HTTPError(f"{message} | Endpoint: {url}", response=e.response) from e

        if not response:
            return []

        payload = response.json()
        values = payload.get(self._cc("value"), payload.get("value"))

        if values is None:
            raise ValueError(
                "Malformed response payload: missing 'value' collection for occurrences view"
            )
        if not isinstance(values, list):
            raise ValueError("Malformed response payload: 'value' must be a list")

        occurrences = []
        valid_values = (
            self.get_valid_work_location_types() if include_valid_values else None
        )
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Malformed response payload: occurrence at index {index} is not an object"
                )

            try:
                occurrence = self.occurrence_constructor(
                    parent=self, **{self._cloud_data_key: item}
                )
                if valid_values is not None:
                    occurrence.valid_work_location_types = list(valid_values)
                occurrences.append(occurrence)
            except Exception as e:
                raise ValueError(
                    f"Malformed occurrence payload at index {index}: {e}"
                ) from e

        return occurrences
