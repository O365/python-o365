Subscriptions
=============

Subscriptions provides the ability to create and manage webhook subscriptions for change notifications against Microsoft Graph. Read here for more details on MS Graph subscriptions

- https://learn.microsoft.com/en-us/graph/api/resources/subscription?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks?tabs=http

Create a Subscription
^^^^^^^^^^^^^^^^^^^^^

Assuming a web host (example uses `flask`) and an authenticated account, create a subscription to be notified about new emails.

.. code-block:: python

    from flask import Flask, abort, jsonify, request

    RESOURCE = "/me/mailFolders('inbox')/messages"
    DEFAULT_EXPIRATION_MINUTES = 10069  # Maximum expiration is 10,070 in the future for Outlook message.

    app = Flask(__name__)

    @app.get("/subscriptions")
    def create_subscription():
        """Create a subscription."""
        notification_url = request.args.get("notification_url")
        if not notification_url:
            abort(400, description="notification_url is required")

        expiration_minutes = int(request.args.get("expiration_minutes", DEFAULT_EXPIRATION_MINUTES))
        client_state = request.args.get("client_state")
        resource = request.args.get("resource", RESOURCE)

        subscription = account.subscriptions().create_subscription(
            notification_url=notification_url,
            resource=resource,
            change_type="created",
            expiration_minutes=expiration_minutes,
            client_state=client_state,
        )
        return jsonify(subscription), 201

    @app.post("/webhook")
    def webhook_handler():
        """Handle Microsoft Graph webhook calls.

        - During subscription validation, Graph sends POST with ?validationToken=... .
        We must echo the token as plain text within 10 seconds.
        - For change notifications, Graph posts JSON; we just log/ack.
        """
        validation_token = request.args.get("validationToken")
        if validation_token:
            # Echo back token exactly as plain text with HTTP 200.
            return validation_token, 200, {"Content-Type": "text/plain"}

        # Change notifications: inspect or log as needed.
        payload = request.get_json(silent=True) or {}
        print("Received notification payload:", payload)
        return ("", 202)

Use this url:

    ``https://<your-tunnel-host>/subscriptions?notification_url=https%3A%2F%2F<your-tunnel-host>%2Fwebhook&client_state=abc123``

HTTP status 201 and the following should be returned:

.. code-block:: JSON

    {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#subscriptions/$entity",
        "applicationId": "12345678-bad9-4c34-94d6-f9a1388522f8",
        "changeType": "created",
        "clientState": "abc123",
        "creatorId": "12345678-a5c7-46da-8107-b25090a1ed66",
        "encryptionCertificate": null,
        "encryptionCertificateId": null,
        "expirationDateTime": "2026-01-07T11:20:42.305776Z",
        "id": "548355f8-c2c0-47ae-aac7-3ad02b2dfdb1",
        "includeResourceData": null,
        "latestSupportedTlsVersion": "v1_2",
        "lifecycleNotificationUrl": null,
        "notificationQueryOptions": null,
        "notificationUrl": "https://<your-tunnel-host>/webhook",
        "notificationUrlAppId": null,
        "resource": "/me/mailFolders('inbox')/messages"
    }

List Subscriptions
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    @app.get("/subscriptions/list")
    def list_subscriptions():
        """List all subscriptions."""
        limit = int(request.args.get("limit"))
        subscriptions = account.subscriptions().list_subscriptions(limit=limit)
        return jsonify(list(subscriptions)), 200

Use this url:

    ``https://<your-tunnel-host>/subscriptions/list``

HTTP status 200 and the following should be returned:

.. code-block:: JSON

    [
        {
            "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#subscriptions/$entity",
            "applicationId": "12345678-bad9-4c34-94d6-f9a1388522f8",
            "changeType": "created",
            "clientState": "abc123",
            "creatorId": "12345678-a5c7-46da-8107-b25090a1ed66",
            "encryptionCertificate": null,
            "encryptionCertificateId": null,
            "expirationDateTime": "2026-01-07T11:20:42.305776Z",
            "id": "548355f8-c2c0-47ae-aac7-3ad02b2dfdb1",
            "includeResourceData": null,
            "latestSupportedTlsVersion": "v1_2",
            "lifecycleNotificationUrl": null,
            "notificationQueryOptions": null,
            "notificationUrl": "https://<your-tunnel-host>/webhook",
            "notificationUrlAppId": null,
            "resource": "/me/mailFolders('inbox')/messages"
        }
    ]

Renew a Subscription
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    @app.get("/subscriptions/<subscription_id>/renew")
    def renew_subscription(subscription_id: str):
        """Renew a subscription."""
        expiration_minutes = int(request.args.get("expiration_minutes", DEFAULT_EXPIRATION_MINUTES))
        updated = account.subscriptions().renew_subscription(
            subscription_id,
            expiration_minutes=expiration_minutes,
        )
        return jsonify(updated), 200

Use this url:

    ``http://<your-tunnel-host>/subscriptions/548355f8-c2c0-47ae-aac7-3ad02b2dfdb1/renew?expiration_minutes=10069``

HTTP status 200 and the following should be returned:

.. code-block:: JSON

    {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#subscriptions/$entity",
        "applicationId": "12345678-bad9-4c34-94d6-f9a1388522f8",
        "changeType": "created",
        "clientState": "abc123",
        "creatorId": "12345678-a5c7-46da-8107-b25090a1ed66",
        "encryptionCertificate": null,
        "encryptionCertificateId": null,
        "expirationDateTime": "2026-01-07T11:35:40.301594Z",
        "id": "548355f8-c2c0-47ae-aac7-3ad02b2dfdb1",
        "includeResourceData": null,
        "latestSupportedTlsVersion": "v1_2",
        "lifecycleNotificationUrl": null,
        "notificationQueryOptions": null,
        "notificationUrl": "https://<your-tunnel-host>/webhook",
        "notificationUrlAppId": null,
        "resource": "/me/mailFolders('inbox')/messages"
    }

Delete a Subscription
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    @app.get("/subscriptions/<subscription_id>/delete")
    def delete_subscription(subscription_id: str):
        """Delete a subscription."""
        deleted = account.subscriptions().delete_subscription(subscription_id)
        if not deleted:
            abort(404, description="Subscription not found")
        return ("", 204)

Use this url:

    ``http://<your-tunnel-host>/subscriptions/548355f8-c2c0-47ae-aac7-3ad02b2dfdb1/delete``

HTTP status 204 should be returned.

Webhook
^^^^^^^

With a subscription as described above and an email sent to the inbox, a webhook will be received as below:

.. code-block:: python

    {
        'value': [
            {
                'subscriptionId': '548355f8-c2c0-47ae-aac7-3ad02b2dfdb12', 
                'subscriptionExpirationDateTime': '2026-01-07T11:35:40.301594+00:00', 
                'changeType': 'created', 
                'resource': 'Users/12345678-a5c7-46da-8107-b25090a1ed66/Messages/<long_guid>=', 
                'resourceData': {
                    '@odata.type': '#Microsoft.Graph.Message', 
                    '@odata.id': 'Users/12345678-a5c7-46da-8107-b25090a1ed66/Messages/<long_guid>=', 
                    '@odata.etag': 'W/"CQAAABYACCCoiRErLbiNRJDCFyMjq4khBBnH4N7A"', 
                    'id': '<long_guid>='
                }, 
                'clientState': 'abc123', 
                'tenantId': '12345678-abcd-1234-abcd-1234567890ab'
            }
        ]
    }

The client state should be validated for accuracy and if correct, the message can be acted upon as approriate for the type of subscription.

An example application can be found in the examples directory here - https://github.com/O365/python-o365/blob/master/examples/subscriptions_example.py