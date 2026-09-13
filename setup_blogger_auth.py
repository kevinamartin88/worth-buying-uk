from __future__ import annotations

import argparse
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/blogger"]


def main():
    parser = argparse.ArgumentParser(
        description="Create a Blogger OAuth refresh token and show your Blogger blog IDs."
    )
    parser.add_argument(
        "--client-secrets",
        required=True,
        help="Path to the OAuth Desktop client JSON downloaded from Google Cloud Console.",
    )
    args = parser.parse_args()

    secrets_path = Path(args.client_secrets)
    raw = json.loads(secrets_path.read_text(encoding="utf-8"))
    desktop = raw.get("installed") or raw.get("web")
    if not desktop:
        raise SystemExit("The client secrets file does not contain an installed/web OAuth client.")

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), scopes=SCOPES)
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        authorization_prompt_message="Open this URL in your browser:\n{url}",
        success_message="Authorization completed. You can close this browser tab.",
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )

    if not credentials.refresh_token:
        raise SystemExit(
            "Google did not return a refresh token. Revoke the app's access in your Google "
            "account and run this helper again with consent."
        )

    service = build("blogger", "v3", credentials=credentials, cache_discovery=False)
    blogs = service.blogs().listByUser(userId="self").execute().get("items", [])

    print("\n=== Save these as GitHub Actions secrets ===")
    print("BLOGGER_CLIENT_ID=" + str(desktop["client_id"]))
    print("BLOGGER_CLIENT_SECRET=" + str(desktop["client_secret"]))
    print("BLOGGER_REFRESH_TOKEN=" + str(credentials.refresh_token))

    print("\n=== Your Blogger blogs ===")
    if not blogs:
        print("No Blogger blogs were found for this Google account.")
    for blog in blogs:
        print(f'BLOGGER_BLOG_ID={blog["id"]}  |  {blog.get("name")}  |  {blog.get("url")}')


if __name__ == "__main__":
    main()
