import datetime as dt
from typing import Iterable, Mapping, Optional, Union

from .utils import ApiComponent, NEXT_LINK_KEYWORD, Pagination


class Subscriptions(ApiComponent):
    """Subscription operations for Microsoft Graph webhooks."""

    _endpoints = {
        "subscriptions": "/subscriptions",
    }

    def __init__(self, *, parent=None, con=None, **kwargs):
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

    def _build_subscription_url(self, subscription_id: Optional[str] = None) -> str:
        """Build the Microsoft Graph subscriptions endpoint."""
        endpoint = self._endpoints.get("subscriptions")
        if endpoint is None:
            raise ValueError("Subscriptions endpoint is not configured.")
        base_url = self.protocol.service_url.rstrip("/")
        if subscription_id:
            return f"{base_url}{endpoint}/{subscription_id}"
        return f"{base_url}{endpoint}"

    @staticmethod
    def _format_subscription_expiration(
        expiration_datetime: Optional[dt.datetime] = None,
        expiration_minutes: Optional[int] = None,
    ) -> str:
        """Return an ISO 8601 UTC expiration string as required by Graph webhooks."""
        if expiration_datetime and expiration_minutes is not None:
            raise ValueError(
                "Provide either expiration_datetime or expiration_minutes, not both."
            )
        if expiration_datetime is None:
            minutes = expiration_minutes if expiration_minutes is not None else 60
            if minutes <= 0:
                raise ValueError("expiration_minutes must be a positive integer.")
            expiration_datetime = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
                minutes=minutes
            )
        else:
            if expiration_datetime.tzinfo is None:
                expiration_datetime = expiration_datetime.replace(tzinfo=dt.timezone.utc)
            else:
                expiration_datetime = expiration_datetime.astimezone(dt.timezone.utc)
        return expiration_datetime.isoformat(timespec="microseconds").replace("+00:00", "Z")

    @staticmethod
    def _stringify_change_type(change_type: Union[str, Iterable[str]]) -> str:
        """Normalize changeType into the comma-separated string Graph expects."""
        if isinstance(change_type, str):
            value = change_type.strip()
        else:
            try:
                parts = [str(part).strip() for part in change_type]
            except TypeError as exc:
                raise ValueError(
                    "change_type must be a string or an iterable of strings."
                ) from exc
            value = ",".join(part for part in parts if part)
        if not value:
            raise ValueError("change_type must contain at least one value.")
        return value

    def get_subscription(
        self,
        subscription_id: str,
        *,
        params: Optional[Mapping[str, object]] = None,
        **request_kwargs,
    ) -> Optional[dict]:
        """Retrieve a single webhook subscription by id."""
        if not subscription_id:
            raise ValueError("subscription_id must be provided.")
        if params is not None and not isinstance(params, Mapping):
            raise ValueError("params must be a mapping if provided.")

        url = self._build_subscription_url(subscription_id)
        response = self.con.get(url, params=params, **request_kwargs)

        if not response:
            return None

        return response.json()

    def create_subscription(
        self,
        notification_url: str,
        resource: Optional[str] = None,
        change_type: Union[str, Iterable[str]] = "created",
        *,
        expiration_datetime: Optional[dt.datetime] = None,
        expiration_minutes: Optional[int] = None,
        client_state: Optional[str] = None,
        include_resource_data: Optional[bool] = None,
        encryption_certificate: Optional[str] = None,
        encryption_certificate_id: Optional[str] = None,
        lifecycle_notification_url: Optional[str] = None,
        latest_supported_tls_version: Optional[str] = None,
        additional_data: Optional[Mapping[str, object]] = None,
        **request_kwargs,
    ) -> Optional[dict]:
        """Create a Microsoft Graph webhook subscription.

        See subscriptions usage documentation for webhook setup requirements.
        """
        if not notification_url:
            raise ValueError("notification_url must be provided.")

        resource = resource or self.main_resource
        if not resource:
            raise ValueError("resource must be provided.")
        if not resource.startswith("/"):
            resource = f"/{resource}"

        expiration_value = self._format_subscription_expiration(
            expiration_datetime=expiration_datetime,
            expiration_minutes=expiration_minutes,
        )
        change_type_value = self._stringify_change_type(change_type)

        payload = {
            self._cc("change_type"): change_type_value,
            self._cc("notification_url"): notification_url,
            self._cc("resource"): resource,
            self._cc("expiration_date_time"): expiration_value,
        }

        if client_state is not None:
            payload[self._cc("client_state")] = client_state
        if include_resource_data is not None:
            payload[self._cc("include_resource_data")] = include_resource_data
        if encryption_certificate is not None:
            payload[self._cc("encryption_certificate")] = encryption_certificate
        if encryption_certificate_id is not None:
            payload[self._cc("encryption_certificate_id")] = encryption_certificate_id
        if lifecycle_notification_url is not None:
            payload[self._cc("lifecycle_notification_url")] = lifecycle_notification_url
        if latest_supported_tls_version is not None:
            payload[
                self._cc("latest_supported_tls_version")
            ] = latest_supported_tls_version
        if additional_data:
            if not isinstance(additional_data, Mapping):
                raise ValueError("additional_data must be a mapping if provided.")
            payload.update({str(key): value for key, value in additional_data.items()})

        url = self._build_subscription_url()
        response = self.con.post(url, data=payload, **request_kwargs)

        if not response:
            return None

        return response.json()

    def list_subscriptions(
        self,
        *,
        limit: Optional[int] = None,
        **request_kwargs,
    ) -> Union[Iterable[dict], Pagination]:
        """List webhook subscriptions visible to the current app/context."""
        if limit is not None and limit <= 0:
            raise ValueError("limit must be a positive integer.")

        url = self._build_subscription_url()
        response = self.con.get(url, **request_kwargs)
        if not response:
            return iter(())

        data = response.json()
        subscriptions = data.get("value", [])
        next_link = data.get(NEXT_LINK_KEYWORD)

        if next_link:
            return Pagination(
                parent=self,
                data=subscriptions,
                next_link=next_link,
                limit=limit,
            )

        if limit is not None:
            return subscriptions[:limit]

        return subscriptions

    def renew_subscription(
        self,
        subscription_id: str,
        *,
        expiration_datetime: Optional[dt.datetime] = None,
        expiration_minutes: Optional[int] = None,
        **request_kwargs,
    ) -> Optional[dict]:
        """Renew an existing webhook subscription."""
        if not subscription_id:
            raise ValueError("subscription_id must be provided.")

        expiration_value = self._format_subscription_expiration(
            expiration_datetime=expiration_datetime,
            expiration_minutes=expiration_minutes,
        )

        payload = {
            self._cc("expiration_date_time"): expiration_value,
        }

        url = self._build_subscription_url(subscription_id)
        response = self.con.patch(url, data=payload, **request_kwargs)

        if not response:
            return None

        return response.json()

    def update_subscription(
        self,
        subscription_id: str,
        *,
        notification_url: Optional[str] = None,
        expiration_datetime: Optional[dt.datetime] = None,
        expiration_minutes: Optional[int] = None,
        **request_kwargs,
    ) -> Optional[dict]:
        """Update subscription fields (expiration and/or notification URL)."""
        if not subscription_id:
            raise ValueError("subscription_id must be provided.")

        payload = {}

        if expiration_datetime is not None or expiration_minutes is not None:
            payload[self._cc("expiration_date_time")] = self._format_subscription_expiration(
                expiration_datetime=expiration_datetime,
                expiration_minutes=expiration_minutes,
            )

        if notification_url is not None:
            if not notification_url:
                raise ValueError("notification_url, if provided, cannot be empty.")
            payload[self._cc("notification_url")] = notification_url

        if not payload:
            raise ValueError("At least one of expiration or notification_url must be provided.")

        url = self._build_subscription_url(subscription_id)
        response = self.con.patch(url, data=payload, **request_kwargs)

        if not response:
            return None

        return response.json()

    def delete_subscription(
        self,
        subscription_id: str,
        **request_kwargs,
    ) -> bool:
        """Delete an existing webhook subscription."""
        if not subscription_id:
            raise ValueError("subscription_id must be provided.")

        url = self._build_subscription_url(subscription_id)
        response = self.con.delete(url, **request_kwargs)

        return bool(response)
