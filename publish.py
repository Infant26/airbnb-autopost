#!/usr/bin/env python3
"""Publish due posts from posts.json to Instagram via the official Graph API.

Only posts with "status": "scheduled" and a "publish_at" in the past are sent,
at most one per run, oldest first. After a successful publish the post is
marked "posted" and posts.json is rewritten.

Env:
  IG_ACCESS_TOKEN   Page access token (Facebook Login) or Instagram Login token
  IG_USER_ID        Instagram professional account id
  MEDIA_BASE_URL    Public base URL that relative media paths are joined to
  IG_API_HOST       graph.facebook.com (default) or graph.instagram.com
  IG_API_VERSION    default v26.0

Usage:
  python3 publish.py              publish the next due post
  python3 publish.py --dry-run    show what would be published, send nothing
  python3 publish.py --check      validate posts.json and the token
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(HERE, "posts.json")

IMAGE_EXT = (".jpg", ".jpeg")
VIDEO_EXT = (".mp4", ".mov")
MAX_CAPTION = 2200
MAX_HASHTAGS = 30


def api_base():
    host = os.environ.get("IG_API_HOST", "graph.facebook.com")
    version = os.environ.get("IG_API_VERSION", "v26.0")
    return "https://%s/%s" % (host, version)


def call(method, path, params):
    params = dict(params, access_token=os.environ["IG_ACCESS_TOKEN"])
    data = urllib.parse.urlencode(params).encode()
    url = "%s/%s" % (api_base(), path)
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            body = json.loads(body).get("error", {}).get("message", body)
        except ValueError:
            pass
        raise RuntimeError("%s %s failed (%s): %s" % (method, path, e.code, body))


def parse_time(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("publish_at needs a timezone offset, e.g. +05:30: %s" % value)
    return dt


def media_url(path):
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = os.environ.get("MEDIA_BASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("MEDIA_BASE_URL is not set, cannot build a public URL for %s" % path)
    return base + "/" + urllib.parse.quote(path)


def validate(post):
    """Return a list of problems with one post."""
    problems = []
    kind = post.get("type")
    media = post.get("media") or []
    caption = post.get("caption", "")
    if kind not in ("image", "carousel", "reel"):
        problems.append("type must be image, carousel or reel")
    if not media:
        problems.append("media is empty")
    if kind == "image" and len(media) != 1:
        problems.append("image posts take exactly one file")
    if kind == "reel" and (len(media) != 1 or not media[0].lower().endswith(VIDEO_EXT)):
        problems.append("reel posts take exactly one .mp4/.mov file")
    if kind == "carousel" and not 2 <= len(media) <= 10:
        problems.append("carousels take 2 to 10 files")
    for m in media:
        if kind != "reel" and not m.lower().endswith(IMAGE_EXT + VIDEO_EXT):
            problems.append("%s: Instagram only accepts JPEG images or MP4/MOV video" % m)
        local = os.path.join(HERE, m)
        if not m.startswith("http") and not os.path.exists(local):
            problems.append("%s: file not found in repo" % m)
    if len(caption) > MAX_CAPTION:
        problems.append("caption is %d chars, limit is %d" % (len(caption), MAX_CAPTION))
    if caption.count("#") > MAX_HASHTAGS:
        problems.append("more than %d hashtags" % MAX_HASHTAGS)
    try:
        parse_time(post.get("publish_at", ""))
    except ValueError as e:
        problems.append(str(e))
    return problems


def wait_ready(container_id, timeout=600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = call("GET", container_id, {"fields": "status_code,status"})
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError("media container %s: %s" % (container_id, status.get("status")))
        time.sleep(10)
    raise RuntimeError("media container %s not ready after %ds" % (container_id, timeout))


def item_params(path, in_carousel):
    url = media_url(path)
    if path.lower().endswith(VIDEO_EXT):
        params = {"media_type": "VIDEO" if in_carousel else "REELS", "video_url": url}
    else:
        params = {"image_url": url}
    if in_carousel:
        params["is_carousel_item"] = "true"
    return params


def publish(post):
    user = os.environ["IG_USER_ID"]
    caption = post.get("caption", "")
    if post["type"] == "carousel":
        children = []
        for m in post["media"]:
            child = call("POST", "%s/media" % user, item_params(m, True))["id"]
            wait_ready(child)
            children.append(child)
        params = {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption}
    else:
        params = dict(item_params(post["media"][0], False), caption=caption)
        if post["type"] == "reel":
            params["share_to_feed"] = "true"
    container = call("POST", "%s/media" % user, params)["id"]
    wait_ready(container)
    return call("POST", "%s/media_publish" % user, {"creation_id": container})["id"]


def load():
    with open(QUEUE) as f:
        return json.load(f)


def save(queue):
    with open(QUEUE, "w") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)
        f.write("\n")


def due_posts(queue, now):
    due = [p for p in queue["posts"]
           if p.get("status") == "scheduled" and parse_time(p["publish_at"]) <= now]
    return sorted(due, key=lambda p: parse_time(p["publish_at"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="show the next due post, send nothing")
    ap.add_argument("--check", action="store_true", help="validate the queue and the token")
    args = ap.parse_args()

    queue = load()
    bad = 0
    for p in queue["posts"]:
        if p.get("status") in ("scheduled", "draft"):
            for problem in validate(p):
                print("[%s] %s" % (p.get("id", "?"), problem))
                bad += 1
    if bad:
        print("%d problem(s) in posts.json" % bad)
        return 1

    if args.check:
        if not os.environ.get("IG_ACCESS_TOKEN"):
            print("posts.json OK. IG_ACCESS_TOKEN not set, token not checked.")
            return 0
        me = call("GET", os.environ["IG_USER_ID"], {"fields": "username,media_count"})
        print("posts.json OK. Token works for @%s (%s posts)." % (me["username"], me.get("media_count")))
        return 0

    now = datetime.now(timezone.utc)
    due = due_posts(queue, now)
    upcoming = [p for p in queue["posts"] if p.get("status") == "scheduled" and p not in due]
    if not due:
        nxt = min(upcoming, key=lambda p: parse_time(p["publish_at"]), default=None)
        print("Nothing due." + (" Next: %s at %s" % (nxt["id"], nxt["publish_at"]) if nxt else ""))
        return 0

    post = due[0]
    if args.dry_run:
        print("Would publish %s (%s, %d file(s)):" % (post["id"], post["type"], len(post["media"])))
        for m in post["media"]:
            try:
                print("  " + media_url(m))
            except RuntimeError:
                print("  %s (MEDIA_BASE_URL not set)" % m)
        print("---\n" + post["caption"] + "\n---")
        if len(due) > 1:
            print("%d more due after this one." % (len(due) - 1))
        return 0

    try:
        media_id = publish(post)
    except RuntimeError as e:
        post["last_error"] = str(e)
        save(queue)
        print("Failed to publish %s: %s" % (post["id"], e))
        return 1
    post["status"] = "posted"
    post["media_id"] = media_id
    post["posted_at"] = now.isoformat(timespec="seconds")
    post.pop("last_error", None)
    save(queue)
    print("Published %s as media %s" % (post["id"], media_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
