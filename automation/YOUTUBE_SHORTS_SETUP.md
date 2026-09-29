# YouTube Shorts automation

Each confirmed live Blogger article can create one 1080x1920, 25-second companion
Short for the matching regional channel. The video uses the existing article hero,
the exact regional Worth Buying logo, three article-derived comparison points and a
call to read the full guide.

## Required GitHub Actions secrets

Add these at **Repository settings > Secrets and variables > Actions**:

- `YOUTUBE_CLIENT_ID` - OAuth desktop client ID from a Google Cloud project with
  YouTube Data API v3 enabled.
- `YOUTUBE_CLIENT_SECRET` - secret for that OAuth client.
- `YOUTUBE_UK_REFRESH_TOKEN` - refresh token granted with the
  `youtube.upload` scope while the Worth Buying UK Brand Account is selected.
- `YOUTUBE_US_REFRESH_TOKEN` - a separate refresh token granted with the same scope
  while the Worth Buying USA Brand Account is selected.

Do not reuse or replace the Blogger refresh tokens. The YouTube tokens have a
different scope and are validated against the expected public channel IDs before
any upload starts.

`YOUTUBE_PRIVACY_STATUS` is optional. If omitted, new Shorts are public. Set it as a
repository variable or environment variable to `private` or `unlisted` while testing.

## Safe activation

The first configured run records all existing published articles as a baseline and
does not upload the archive. Future new or changed articles upload once. A live test
can be run without uploading:

```bash
python publish_youtube_shorts.py --market uk --article ARTICLE_SLUG --dry-run
```

OAuth can be checked without uploading a video:

```bash
python scripts/test_youtube_live.py --market uk
python scripts/test_youtube_live.py --market us
```

The workflow marks the Short step as non-blocking, so YouTube can never interrupt
Blogger, X, Bluesky or Pinterest publishing.
