import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.config import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

def get_google_credentials() -> Credentials:
    """Gets valid user credentials from disk or initiates the OAuth flow."""
    creds = None
    # We will save token.json in the same directory as the credentials.json
    creds_dir = os.path.dirname(os.path.abspath(config.GOOGLE_OAUTH_CREDENTIALS_PATH))
    token_path = os.path.join(creds_dir, "token.json")

    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            # If the token is corrupted or incompatible, remove it
            os.remove(token_path)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                # If refresh fails, fall back to login flow
                flow = InstalledAppFlow.from_client_secrets_file(
                    config.GOOGLE_OAUTH_CREDENTIALS_PATH, SCOPES
                )
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_OAUTH_CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        os.makedirs(creds_dir, exist_ok=True)
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return creds


def get_gmail_credentials() -> Credentials:
    """Alias for backward compatibility."""
    return get_google_credentials()


def get_gmail_service():
    """Returns an authenticated Gmail service object."""
    creds = get_google_credentials()
    return build("gmail", "v1", credentials=creds)


def get_calendar_service():
    """Returns an authenticated Google Calendar service object."""
    creds = get_google_credentials()
    return build("calendar", "v3", credentials=creds)
