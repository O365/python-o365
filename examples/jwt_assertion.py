import codecs
import uuid
from datetime import datetime, timezone, timedelta

import jwt

_ALGORITHM = "RS256"


def _get_aud(tenant_id):
    return f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def create_jwt_assertion(private_key, tenant_id, thumbprint, client_id):
    """
    Create a JWT assertion, used to obtain an auth token.


    @param private_key: Private key in PEM format from the certificate that was registered as credentials for the
     application.
    @param tenant_id: The directory tenant the application plans to operate against, in GUID or domain-name format.
    @param thumbprint: The X.509 certificate thumbprint.
    @param client_id: The application (client) ID that's assigned to the app.
    @return: JWT assertion to be used to obtain an auth token.
    """
    x5t = codecs.encode(codecs.decode(thumbprint, "hex"), "base64").replace(b"\n", b"").decode()
    aud = _get_aud(tenant_id)

    now = datetime.now(tz=timezone.utc)
    exp = now + timedelta(hours=1)
    jti = str(uuid.uuid4())

    payload = {
        "aud": aud,
        "exp": exp,
        "iss": client_id,
        "jti": jti,
        "nbf": now,
        "sub": client_id,
        "iat": now
    }
    headers = {
        "alg": _ALGORITHM,
        "typ": "JWT",
        "x5t": x5t,
    }
    encoded = jwt.encode(payload, private_key, algorithm=_ALGORITHM, headers=headers)

    return encoded


def decode_jwt_assertion(jwt_assertion, public_key, tenant_id):
    """
    Decode a JWT assertion, the opposite to 'create_jwt_assertion'.

    @param jwt_assertion: The JWT assertion obtained to be decoded.
    @param public_key: Public key in PEM format from the certificate that was registered as credentials for the
     application.
    @param tenant_id: The directory tenant the application plans to operate against, in GUID or domain-name format.
    @return: The decoded assertion.
    """
    aud = _get_aud(tenant_id)
    decoded = jwt.decode(jwt_assertion, public_key, audience=aud, algorithms=[_ALGORITHM])

    return decoded
