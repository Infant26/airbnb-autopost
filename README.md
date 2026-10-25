# Airbnb Instagram autopost

Posts to Instagram on a schedule, for free, using Instagram's official
Graph API and GitHub Actions. Nothing logs in with your password.

```
media/           photos (JPEG) and videos (MP4) for the posts
posts.json       the queue: what to post, when, with which caption
publish.py       sends the next due post to Instagram
.github/workflows/post.yml   runs publish.py every hour in GitHub's cloud
```

## How a post goes out

1. Photos go in `media/`.
2. Claude writes the posts into `posts.json` with `"status": "draft"`.
3. You read them. For each one you approve, change `"draft"` to `"scheduled"`.
4. Push to GitHub. Every hour, GitHub checks for a scheduled post whose
   `publish_at` time has passed, posts it, and marks it `"posted"`.

One post per hourly run at most, so a backlog can't flood the account.

Post types: `image` (one JPEG), `carousel` (2-10 JPEG/MP4), `reel` (one MP4).
`publish_at` needs a timezone, e.g. `2026-11-01T18:00:00+05:30`.

## One-time setup (about 30 minutes)

### 1. Make the Instagram account professional
Instagram app → Settings → Account type and tools → Switch to professional
account → Business.

### 2. Link it to a Facebook Page
Create a Facebook Page for the property if you don't have one, then link it:
Facebook Page → Settings → Linked accounts → Instagram → Connect.

### 3. Create a Meta app
[developers.facebook.com](https://developers.facebook.com) → My Apps →
Create App → pick the Business type (or the "Instagram" / "manage
content" use case if offered). The app can stay in development mode: you
are posting to your own account, so no App Review is needed.

### 4. Get a token that never expires
1. Open the [Graph API Explorer](https://developers.facebook.com/tools/explorer/),
   select your app, click **Generate Access Token** and grant:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `pages_read_engagement`, `business_management`.
2. Paste that token into the
   [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)
   and click **Extend Access Token**. Copy the long-lived token.
3. Back in the Explorer, paste the long-lived token and run `GET me/accounts`.
   Copy your Page's `access_token` and `id`.
4. Check the Page token in the debugger: it should say **Expires: Never**.
   This is `IG_ACCESS_TOKEN`.
5. In the Explorer run `GET <page-id>?fields=instagram_business_account`.
   The `id` inside is `IG_USER_ID`.

Keep the token private. Anyone who has it can post to the account.

### 5. Add the secrets to GitHub
In this folder, run each command and paste the value when it asks:

```bash
gh secret set IG_ACCESS_TOKEN
```

```bash
gh secret set IG_USER_ID
```

### 6. Test
GitHub → the repo → Actions → Post to Instagram → Run workflow. With no
scheduled posts due, it should end with "Nothing due."

Locally, without sending anything:

```bash
python3 publish.py --dry-run
```

## Notes

- The repo is public so Instagram can download the photos from
  `raw.githubusercontent.com`. Only put in it what you'd post anyway.
- GitHub may run the hourly job a few minutes to an hour late.
- If a post fails, the run goes red, GitHub emails you, and the error is
  saved as `last_error` on that post. It retries on the next run.
- GitHub pauses scheduled jobs in repos with no activity for 60 days. Adding
  posts regularly keeps it running.
