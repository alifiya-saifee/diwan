# Pictures or video, per post (approved brief, 4 Nov 2026; build after the submission)

**When and where:** after the hackathon submission, on a branch `pictures-or-video`. Nothing to `main` and no deploy
until the owner has seen the screenshots (section 5).

## Why
A picked script usually leads to a video (filmed, AI presenter, or the free video). But many posts work better as a
carousel or one image; video is heavy (Render free: 512 MB, a tenth of a CPU, and the full-size free video peaked at
about 1 GB and restarted the server, which wipes the office); and every script already has a frame-by-frame visual
brief (`visual.py`) that is a carousel waiting to be made.

**Goal:** after a script is picked, the person chooses **Post as pictures** or **Make it a video**; the office suggests a
default from the post's context. Pictures work on every server; video is optional and can be off on light servers.

## Reuse, don't rewrite
`eventpost.py` (`FORMATS`, `shape()`, `slides()`, `render()` with permit, Arabic, logo and the director's review,
`_background(frame=)`), `visual.py` (`frame()`, `shot()`, `sources()`: a listing shows only its own photos),
`studio.py` (`after_pictures()`, `post_text()`, `_to_approval()`, `publish()`), `freevideo.py` (`LIGHT`, `ai_frames()`,
`make()`), `marketing.py` (`check()`, `watch()`, `pause()`), `director.review()`, `platforms.py`, `access.API`,
`web/studio.html` (YOUR TURN → Production).

## Build
1. **The choice** at the top of Production, once a script is picked: "Post as pictures" (a carousel from the script's
   frames, about a minute) or "Make it a video" (today's choices, unchanged). One marked **Suggested** with a one-line
   reason.
2. **`eventpost.from_brief(office, ref, sc)`**:
   - One slide per frame, at most 10. The text is the frame's `words.text`, or that script line.
   - The photo:
     - a listing: its own best-matching photo, each used once;
     - a topic: `None`, so Muse Image draws it;
     - `brand colour`: a designed background.
   - The call to action stays last.
   - Stored as a new script version: `format` carousel or image, `revises: <picked id>`, `via: "pictures from brief"`.
     The original is unchanged.
   - Then the existing `after_pictures()` flow. Nothing posts without the publish approver.
   - Muse Image one call at a time.
   - Slides are 4:5: `shots.prompt` gets an `aspect` argument ("vertical 4:5; keep everything important in the middle
     75% of the height"); the free video stays 9:16.
3. **`studio.suggest_output(office, ref, sc)`**, decided by code, not the model:

   | Post | Suggested |
   |---|---|
   | A listing with 3 or more usable photos | Pictures |
   | A teaching topic, or `shape()` already chose pictures | Pictures |
   | A brand story such as "Meet Diwan Realty" (to camera) | Video |
   | A greeting | Pictures (a designed card) |
   | A strong `taste` lean | Overrides the above |
   | The server can't make video | Pictures, with the video option shown off |

4. **`DIWAN_VIDEO`** = `on` (the default), `light` (as `DIWAN_LIGHT_VIDEO=1`, which keeps working), or `off`.
   - With `off`, free-video, AI-video and captioned-cut rendering return **409** "Video making runs on the full server.
     Post this as pictures, or make the video on the full server."
   - Uploading footage is still allowed.
   - The mode shows in `/api/studio`, and in a header chip if that's easy.
5. **API**, Marketing and the owner only (a broker gets 403), added to `access.API`:
   - `GET /api/studio/output?ref=` returns `{suggest, video, can_pictures}`;
   - `POST /api/studio/as-pictures {ref, script?}` returns the new version id; it is idempotent.

## Rules that still hold
- A listing is only ever shown in its own photos.
- Slide words come from the script only; no amount that isn't on the listing.
- The permit is on listing slides, never on topics or greetings.
- The price-change pause covers the carousel, and it resumes when the price is back.
- No text inside generated pictures.
- Arabic is joined, right to left, with the Arabic thousands separator.
- Platform versions pass `platforms.check()`.
- Nothing posts without the publish approver.
- Every step is an event in the log.

## Tests first
1. A listing with 6 frames gives 6 slides of its own photos, each once, with the call to action last and the permit
   drawn.
2. A topic gives `photo: None`, and Muse Image is called once per slide, never overlapping.
3. Slide words are a subset of the script's words, and an unknown amount is refused.
4. The original script is unchanged; the new version has `revises` and `via`.
5. "As pictures" is idempotent.
6. `suggest_output`:
   - a listing with photos → pictures;
   - Meet Diwan Realty → video;
   - a greeting → pictures;
   - `DIWAN_VIDEO=off` → pictures, with the "full server" reason.
7. With `DIWAN_VIDEO=off`, the three video routes return 409, while pictures and footage upload still work.
8. `DIWAN_LIGHT_VIDEO=1` still means light.
9. After the carousel is made, a price change pauses it and it resumes when the price is back.
10. A broker calling `as-pictures` gets 403.
11. The flow ends in an approval request; nothing is published by itself.
12. An Arabic price draws with no boxes.

## Done means
- The new tests and the full suite pass on exactly what will be pushed.
- A browser check on a local server started like Render (`python -m deploy.start`, a fresh data folder,
  `DIWAN_DEMO_DAY=1`, `DIWAN_VIDEO=off`), as Maya:
  - Marina Crest → "Post as pictures" (suggested) → a 6–8 slide carousel with its own photos, the words, logo, permit
    and the Arabic slide → caption → waiting for Layla;
  - "Meet Diwan Realty": AI backgrounds, with the director's score shown;
  - the video buttons say "Video making runs on the full server".
- Screenshots and scores shown to the owner **before pushing**.
- A README line under Marketing Studio, with nothing beyond what was tested.

## Don'ts
- No push or deploy before the screenshots.
- Don't touch correction, compliance, Nova, Rania or access, beyond the two routes.
- Don't remove the video paths; only gate them.
- No parallel Muse Image calls.
- No features beyond this brief.
