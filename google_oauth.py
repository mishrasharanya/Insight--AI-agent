# google_oauth.py = Google OAuth 2.0 flow for connecting Calendar + Drive
#
# Read-only scopes only - this app never writes to or deletes anything in a
# user's real Google account, it only reads Calendar events and Drive file
# contents to index them locally.

import os
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
import requests as http_requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar.readonly",
    # drive.file (not drive.readonly): only grants access to files the user
    # explicitly selects via Google Picker. This is intentional - drive.readonly
    # is a RESTRICTED scope requiring a paid annual third-party security
    # assessment to use at public scale. drive.file is not restricted, so a
    # normal (free) verification review is enough to go fully public.
    "https://www.googleapis.com/auth/drive.file",
]


def _client_config():
    return {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")],
        }
    }


def _build_flow(code_verifier=None):
    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        code_verifier=code_verifier,
        # Only auto-generate a fresh verifier when we don't already have one
        # (i.e. we're starting a new login, not completing an existing one).
        autogenerate_code_verifier=(code_verifier is None),
    )
    flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    return flow


def get_authorization_url():
    """
    Returns (auth_url, state, code_verifier).

    Google now enforces PKCE on the token exchange - the code_verifier used
    here MUST be the exact same one passed into exchange_code() later. Since
    login and callback are two separate HTTP requests (handled by two
    separate Flow objects in api.py), the caller is responsible for
    persisting code_verifier in between (see api.py's short-lived oauth
    cookie) - building a second, unrelated Flow at callback time without it
    is exactly what produces "invalid_grant: Missing code verifier".
    """
    flow = _build_flow()  # code_verifier=None -> autogenerate_code_verifier=True

    auth_url, state = flow.authorization_url(
        access_type="offline",       # required to get a refresh_token back
        include_granted_scopes="true",
        prompt="consent",            # forces a refresh_token even on repeat logins
    )

    return auth_url, state, flow.code_verifier


def exchange_code(code, code_verifier):
    """
    code_verifier: the exact value get_authorization_url() returned for this
    same login attempt - required now that Google enforces PKCE.
    """
    flow = _build_flow(code_verifier=code_verifier)
    flow.fetch_token(code=code)
    return flow.credentials


def credentials_from_refresh_token(refresh_token):
    """Rebuilds usable (short-lived) credentials from a stored long-lived refresh token."""
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=SCOPES,
    )
    credentials.refresh(Request())
    return credentials


def get_user_info(credentials):
    """Returns Google's userinfo payload - includes 'sub' (stable user id) and 'email'."""
    response = http_requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()