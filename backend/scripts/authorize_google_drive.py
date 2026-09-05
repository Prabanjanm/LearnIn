"""
One-time setup: authorize LearnIn to upload files to YOUR Google account's
Drive storage (a bare service account has no storage quota of its own).

Prerequisites (Google Cloud Console, project learnin-502810):
  1. APIs & Services -> Library -> enable "Google Drive API".
  2. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID
     -> Application type "Desktop app".
  3. Copy the generated Client ID and Client Secret.

Usage:
    cd backend
    python scripts/authorize_google_drive.py <client_id> <client_secret>

A browser window opens - sign in with the Google account whose Drive
storage should hold LearnIn's files, and approve access. The script then
prints GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET /
GOOGLE_OAUTH_REFRESH_TOKEN for you to paste into backend/.env.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python scripts/authorize_google_drive.py <client_id> <client_secret>")
        raise SystemExit(1)

    client_id, client_secret = sys.argv[1], sys.argv[2]

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    if not credentials.refresh_token:
        print(
            "No refresh token returned. You may have already authorized this "
            "app before - revoke access at https://myaccount.google.com/permissions "
            "and run this script again."
        )
        raise SystemExit(1)

    print("\nAdd these to backend/.env:\n")
    print(f"GOOGLE_OAUTH_CLIENT_ID={client_id}")
    print(f"GOOGLE_OAUTH_CLIENT_SECRET={client_secret}")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={credentials.refresh_token}")


if __name__ == "__main__":
    main()
