#!/usr/bin/env python3
"""Render each post's "slides" in posts.json into 1080x1350 JPEGs.

Each slide is {"photo": "media/...", "kicker": ..., "title": ..., "sub": ...}.
Output goes to media/ig/<post id>/NN.jpg and the post's "media" list is
rewritten to point at those files. Posts already "posted" are left alone.

Usage:
  python3 build_slides.py            build every unposted post
  python3 build_slides.py ID [ID..]  build only these posts
"""

import html
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(HERE, "posts.json")
OUT = os.path.join(HERE, "media", "ig")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HANDLE = "@the_coastal_calm"

TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 1080px; height: 1350px; overflow: hidden; }}
  body {{ background: #f4eee4; color: #22302e; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; }}
  .photo {{ width: 1080px; height: 810px; background: url("{photo}") center / cover no-repeat; }}
  .text {{ height: 540px; padding: 64px 84px 56px; display: flex; flex-direction: column; }}
  .kicker {{ font-size: 28px; letter-spacing: 6px; text-transform: uppercase; color: #2f6b64; font-weight: 600; }}
  .title {{ font-family: Georgia, "Times New Roman", serif; font-size: {title_size}px; line-height: 1.1; margin-top: 22px; }}
  .sub {{ font-size: 34px; line-height: 1.35; color: #5b6664; margin-top: 22px; }}
  .foot {{ margin-top: auto; display: flex; justify-content: space-between; font-size: 26px; color: #8a8f8b; }}
</style></head><body>
  <div class="photo"></div>
  <div class="text">
    <div class="kicker">{kicker}</div>
    <div class="title">{title}</div>
    <div class="sub">{sub}</div>
    <div class="foot"><span>{handle}</span><span>{counter}</span></div>
  </div>
</body></html>
"""


def render(slide, index, total, out_path, tmp):
    photo = os.path.join(HERE, slide["photo"])
    if not os.path.exists(photo):
        raise SystemExit("missing photo: %s" % slide["photo"])
    page = TEMPLATE.format(
        photo="file://" + photo.replace('"', "%22"),
        kicker=html.escape(slide.get("kicker", "")),
        title=html.escape(slide["title"]),
        sub=html.escape(slide.get("sub", "")),
        handle=HANDLE,
        counter="%d/%d" % (index, total) if total > 1 else "",
        title_size=84 if index == 1 else 68,
    )
    page_path = os.path.join(tmp, "slide.html")
    png_path = os.path.join(tmp, "slide.png")
    with open(page_path, "w") as f:
        f.write(page)
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--allow-file-access-from-files", "--force-device-scale-factor=1",
         "--window-size=1080,1350", "--screenshot=" + png_path, "file://" + page_path],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90", png_path, "--out", out_path],
        check=True, stdout=subprocess.DEVNULL,
    )


def build(post, tmp):
    slides = post.get("slides")
    if not slides:
        return False
    folder = os.path.join(OUT, post["id"])
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    media = []
    for i, slide in enumerate(slides, 1):
        name = "%02d.jpg" % i
        render(slide, i, len(slides), os.path.join(folder, name), tmp)
        media.append("media/ig/%s/%s" % (post["id"], name))
    post["media"] = media
    post["type"] = "carousel" if len(media) > 1 else "image"
    return True


def main():
    with open(QUEUE) as f:
        queue = json.load(f)
    only = set(sys.argv[1:])
    tmp = tempfile.mkdtemp()
    try:
        for post in queue["posts"]:
            if post.get("status") == "posted" or (only and post["id"] not in only):
                continue
            if build(post, tmp):
                print("built %s: %d slide(s)" % (post["id"], len(post["media"])))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with open(QUEUE, "w") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()
