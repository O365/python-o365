
""" Example on how to use and setup webhooks

Quickstart for this example:
1) Run Flask locally withg the following command:
    - flask --app examples/subscriptions_example.py run --debug
2) Expose HTTPS via a tunnel to your localhost:5000:
    - Free: pinggy (https://pinggy.io/) to get https://<subdomain>.pinggy.link -> http://localhost:5000
    - Paid/free-tier: ngrok (https://ngrok.com/): ngrok http 5000, note the https URL.
3) Use the tunnel HTTPS URL as notification_url pointing to /webhook, URL-encoded. 
4) To create a subscription, follow the example request below:
    - https://<your-tunnel-host>/subscriptions?notification_url=https%3A%2F%2F<your-tunnel-host>%2Fwebhook&client_state=abc123
4) To renew a subscription, follow the example request below: 
    - http://<your-tunnel-host>/subscriptions/<subscription_id>/renew?expiration_minutes=55
5) To delete a subscription, follow the example request below:
    - http://<your-tunnel-host>/subscriptions/<subscription_id>/delete
Graph will call https://<your-tunnel-host>/webhook; this app echoes validationToken and returns 202 for notifications.
"""

from flask import Flask, abort, jsonify, request
from O365 import Account

CLIENT_ID = "YOUR CLIENT ID"
CLIENT_SECRET = "YOUR CLIENT SECRET"
credentials = (CLIENT_ID, CLIENT_SECRET)

account = Account(credentials)
# Pick the scopes that are relevant to you here
account.authenticate(
            scopes=[
                "https://graph.microsoft.com/Mail.ReadWrite",
                "https://graph.microsoft.com/Mail.Send",
                "https://graph.microsoft.com/Calendars.ReadWrite",
                "https://graph.microsoft.com/MailboxSettings.ReadWrite",
                "https://graph.microsoft.com/User.Read",
                "https://graph.microsoft.com/User.ReadBasic.All",
                'offline_access'
            ])

RESOURCE = "/me/mailFolders('inbox')/messages"
DEFAULT_EXPIRATION_MINUTES = 55  # Graph requires renewals before the limit

app = Flask(__name__)


def _int_arg(name: str, default: int) -> int:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        abort(400, description=f"{name} must be an integer")


@app.get("/subscriptions")
def create_subscription():
    notification_url = request.args.get("notification_url")
    if not notification_url:
        abort(400, description="notification_url is required")

    expiration_minutes = _int_arg("expiration_minutes", DEFAULT_EXPIRATION_MINUTES)
    client_state = request.args.get("client_state")
    resource = request.args.get("resource", RESOURCE)

    subscription = account.subscriptions.create_subscription(
        notification_url=notification_url,
        resource=resource,
        change_type="created",
        expiration_minutes=expiration_minutes,
        client_state=client_state,
    )
    return jsonify(subscription), 201


@app.get("/subscriptions/<subscription_id>/renew")
def renew_subscription(subscription_id: str):
    expiration_minutes = _int_arg("expiration_minutes", DEFAULT_EXPIRATION_MINUTES)
    updated = account.subscriptions.renew_subscription(
        subscription_id,
        expiration_minutes=expiration_minutes,
    )
    return jsonify(updated), 200


@app.get("/subscriptions/<subscription_id>/delete")
def delete_subscription(subscription_id: str):
    deleted = account.subscriptions.delete_subscription(subscription_id)
    if not deleted:
        abort(404, description="Subscription not found")
    return ("", 204)


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


if __name__ == "__main__":
    app.run(debug=True, ssl_context=("examples/cert.pem", "examples/key.pem"))
