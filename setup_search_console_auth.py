from __future__ import annotations

import argparse
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create a read-only Google Search Console OAuth refresh token and "
            "show the verified properties visible to the authenticated account."
        )
    )
    parser.add_argument(
        "--client-secrets",
        required=True,
        help="Path to an OAuth Desktop client JSON downloaded from Google Cloud Console.",
    )
    args = parser.parse_args()

    secrets_path = Path(args.client_secrets)
    raw = json.loads(secrets_path.read_text(encoding="utf-8"))
    desktop = raw.get("installed") or raw.get("web")
    if not desktop:
        raise SystemExit(
            "The client secrets file does not contain an installed/web OAuth client."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(secrets_path),
        scopes=SCOPES,
    )
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
            "Google did not return a refresh token. Revoke this app's Search Console "
            "access and run the helper again with consent."
        )

    service = build(
        "searchconsole",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )
    sites = service.sites().list().execute().get("siteEntry", [])

    print("\n=== Save these as GitHub Actions secrets ===")
    print("GSC_CLIENT_ID=" + str(desktop["client_id"]))
    print("GSC_CLIENT_SECRET=" + str(desktop["client_secret"]))
    print("GSC_REFRESH_TOKEN=" + str(credentials.refresh_token))

    print("\n=== Search Console properties visible to this account ===")
    if not sites:
        print("No Search Console properties were found.")
    for site in sites:
        print(
            f'{site.get("siteUrl", "")} | permission={site.get("permissionLevel", "")}'
        )

    print(
        "\nThe automation normally auto-detects worthbuyinguk.co.uk and "
        "worthbuyingusa.com. Only add GSC_UK_SITE_URL or GSC_US_SITE_URL "
        "as GitHub secrets if auto-detection needs an explicit property URL."
    )


if __name__ == "__main__":
    main()
