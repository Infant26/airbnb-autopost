# Premium 3D reel recipe

The house style for every new reel, from the Coastal Calm Homes reel (`homes-3d/`, posted 28 Oct 2026, approved).
Copy `homes-3d/` as the starting point for a new reel and change the content, not the machinery.

## Format

- 1080x1920, 30 to 35 s, about 120 BPM, a cut or a move on every beat.
- Dark green night palette (`#0d1715`) that can flip to a cream day palette (`#f6f2ea`); gold accents. Inter for bold words, EB Garamond italic for the soft line.
- Extruded 3D text (`.x3d` stacked text-shadow), a hook visible at frame 0, one idea per beat, six words or fewer per card.
- Keep text between y=230 and y=1440 and out of the right 230 px (Instagram UI).
- End on one ask ("Comment HOME", "Book at thecoastalcalm.com"), the site and +91 88704 67560.

## Building blocks that worked

- A Three.js scene (`three@0.160.0` UMD) as the hero: the house assembling, floors exploding apart, lights switching on, night to day.
- HTML groups over it, one per beat: notification toasts, a calendar or rent grid, a document with a drawn signature and a stamp, a cover-flow of real photos with stars and a guest quote, a counter, chips with stamps, a "Comment X" bar, an end card.
- Real property photos only. No sea-view shots or claims (see voice.md).

## Pipeline

1. **Script:** `/ig-reel` (hooks scored with `hookscore.py`, then `beats.py`), `/ig-human` on the script, `/ig-viral` swipe file at `~/.claude/instagram/swipe.md` for the formula.
2. **Voice:** Kokoro, `npx hyperframes tts -v am_michael` with `HYPERFRAMES_PYTHON=~/.local/share/hyperframes/py/bin/python`. Word timings from `npx hyperframes transcribe`; copy each transcript to its own file so they don't overwrite each other.
3. **Music:** MusicGen on the Apple GPU, `reels/musicgen_mps.py`. SFX from `media-use resolve --local-only` (whoosh, boom, click).
4. **Composition** (`index.html`):
   - One GSAP timeline registered as `window.__timelines['main']`.
   - The 3D scene is driven by a separate paused timeline `st` that tweens a state object `S`; draw it from `window.addEventListener('hf-seek', e => { st.totalTime(e.detail.time); draw(); })`.
   - Renderer `preserveDrawingBuffer: true`; move the house on screen with `camera.setViewOffset(1080, 1920, 0, S.shift, 1080, 1920)` (negative shift moves it down).
   - Show and hide with `tl.set`, not `fromTo` with `opacity: 1` in the from-state. Flash = `set` then `to`. No template-literal selectors.
5. **Check:** `npx hyperframes check --json`, `snapshot --at <t>`, `beats --json` to lock cuts to the track. Set `HYPERFRAMES_NO_TELEMETRY=1`.
6. **Render on the GPU:** `npx hyperframes render --quality delivery --gpu --browser-gpu`, then re-encode to about 9 Mbps with `h264_videotoolbox` so the file stays under 50 MB for GitHub.
7. **Text:** `/ig-caption` (lint with `caption.py --keywords`, 5 hashtags from voice.md), `/ig-story` for a 5-frame story plan with a poll at frame 4 and a link sticker at frame 5.

## Posting

- Show the user the render first. Nothing goes into `posts.json` as "scheduled" until they approve it.
- One reel per evening; if a slot is taken, ask which moves.
- GitHub's cron runs hours late, so at post time also run `gh workflow run post.yml -R Infant26/airbnb-autopost`.
- After it goes live, append to `~/.claude/instagram/log.md`.
