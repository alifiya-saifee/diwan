"""The pictures for a post about a place or a topic (never a listing: a listing shows its own photos).

Two steps, because a script line is not a picture. "I'm with Diwan Realty, 13 years working here in Dubai" handed
straight to an image model comes back as a desk, a map or a painting. So:

1. The photo director (Muse Spark) turns each moment of the script into one concrete shot a photographer could take:
   which real place, what is in the frame, from where, with which lens and light. It knows what the named areas look
   like (PLACES below, plus its own knowledge), so a line about the Marina shows the Marina.
2. Muse Image gets that shot as a structured brief (subject, place, camera, light, style, never), with its own
   planning turned up, so it works out the scene before it draws it.

What never changes: no words or logos in the picture (the video adds captions), no recognisable faces, and no picture
of a home presented as one that is for sale.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from diwan.office import Office

# What a place looks like, so the picture is that place and not "a city". Dubai first: where this office works.
PLACES = {
    "dubai marina": "a deep-blue canal lined with tall glass residential towers, yachts moored along the Marina Walk promenade, palms and cafe terraces",
    "jbr": "Jumeirah Beach Residence: a row of sand-coloured high-rise towers right behind a wide white beach and calm turquoise Gulf water",
    "palm jumeirah": "the palm-shaped island: fronds of private beach villas with pools, a crescent of resort hotels, turquoise lagoons",
    "downtown": "Downtown Dubai: the Burj Khalifa above the Dubai Fountain lake, Opera district, low-rise Arabesque Old Town and boulevard",
    "business bay": "glass office and residential towers along the Dubai Canal, waterfront promenade and footbridges, Burj Khalifa in the distance",
    "jvc": "Jumeirah Village Circle: quiet low- and mid-rise apartment blocks and townhouses around green parks, cycle paths and community streets",
    "jlt": "Jumeirah Lake Towers: clusters of towers around man-made lakes with walking paths and lakeside cafes",
    "dubai hills": "Dubai Hills Estate: modern villas and low-rise apartments around a green golf course and a large park, skyline far off",
    "arabian ranches": "Arabian Ranches: Spanish- and Arabic-style family villas, shaded streets, community pools, desert-edge greenery",
    "creek": "Dubai Creek Harbour: new waterfront towers across the creek, wooden abra boats, mangroves and the Ras Al Khor wetlands",
    "deira": "old Dubai Creek: wooden dhows and abras, souks, low traditional buildings and wind towers along the water",
    "difc": "DIFC: sleek financial towers, the Gate building, art galleries and terraces in a polished business district",
    "city walk": "City Walk: low-rise outdoor shopping streets with cafes, murals, palm trees and the downtown skyline behind",
    "dubai south": "Dubai South: new wide boulevards and fresh communities near Al Maktoum airport, open desert sky",
    "abu dhabi": "Abu Dhabi: the Corniche, waterfront towers, Saadiyat and Yas islands, white beaches and calm sea",
}

ALIASES = {"marina": "dubai marina", "burj khalifa": "downtown", "the palm": "palm jumeirah", "jumeirah village circle": "jvc",
           "jumeirah lake towers": "jlt", "jumeirah beach residence": "jbr", "creek harbour": "creek", "dubai creek": "creek"}  # how people say them

SYSTEM = """You are a top real estate and architectural photographer and photo director. You plan the stills for one short vertical
social video by a property business. Each moment of the script gets ONE photograph a real photographer could take on a real day.

Rules for every shot:
- Concrete and visual. Name what is in the frame, where the camera is, and what the light is. Never an abstract idea, a metaphor,
  a map, a scale model, a desk with plans, a collage, an icon, a chart or anything with words on it.
- If the line names a place (an area, a community, a city), the shot shows THAT place as it really looks today, from a spot where
  someone could actually stand: a promenade, a balcony, a rooftop, a street, a beach, a park, a drone height above it.
  Use the visual description given for the place when there is one. Never invent a landmark or put one in the wrong city.
- If the line names no place, show the real life behind it in the business's own city: bright modern interiors with a view,
  terraces at golden hour, family life in a community park, keys on a kitchen counter, a viewing seen from behind.
- People only as small figures, from behind or at a distance: never a recognisable face.
- Never a picture that pretends to be a specific home for sale.
- Vary the shots across the video: mix wide establishing views, mid shots and close details; mix day, golden hour and blue hour.
- Name the materials and textures in the frame (travertine, oak, brushed brass, linen, matte black steel, glass), so it reads as a real place."""

SCHEMA = {"name": "shots", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["shots"], "properties": {
    "shots": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                         "required": ["n", "place", "subject", "camera", "light", "details"],
                                         "properties": {"n": {"type": "integer"},
                                                        "place": {"type": "string", "description": "the real named place shown, or empty"},
                                                        "subject": {"type": "string", "description": "what is in the frame, in one or two concrete sentences"},
                                                        "camera": {"type": "string", "description": "where the camera stands, height, lens"},
                                                        "light": {"type": "string", "description": "time of day and light"},
                                                        "details": {"type": "string", "description": "the materials and textures in frame, in one line (travertine, oak, brushed brass, linen…)"}}}}}}}

PROMPT = """{subject}
{place}Camera: {camera}. Full-frame camera, wide-angle lens on a tripod, straight verticals, level horizon, sharp from front to back.
Light: {light}. True-to-life colour, gentle contrast, real reflections and a little natural haze.
Materials and detail: {details}.
A real photograph from a top Dubai property magazine, vertical 9:16. {calm}
People: none, or small figures from behind and far away.
No text or logos anywhere. Not an illustration or a 3D render.{taste}{avoid}"""

CALM = {"top": "Leave the top third simple (sky, ceiling or water) for a caption.",
        "middle": "Leave the centre simple and a little darker for a caption.",
        "bottom": "Leave the bottom third simple (floor, water or lawn) for a caption."}


def look_of(text: str) -> tuple[str, str]:
    """The first known place a line names, and what it looks like."""
    t = text.lower()
    found = [(m.start(), ALIASES.get(k, k)) for k in (*PLACES, *ALIASES) if (m := re.search(rf"\b{re.escape(k)}\b", t))]
    if not found:
        return "", ""
    name = min(found)[1]  # the one named first
    return (name.upper() if name in ("jbr", "jvc", "jlt", "difc") else name.title()), PLACES[name]


def plan(office: Office, title: str, lines: list[str], about: str) -> list[dict]:
    """One shot per line from the photo director; a line it couldn't plan gets a plain shot built from the line itself."""
    from diwan.providers import meta
    known = [f'{i}. "{x}"' + (f" (place: {p}, which looks like: {lk})" if (p := look_of(x)[0]) and (lk := look_of(x)[1]) else "")
             for i, x in enumerate(lines)]
    got: dict[int, dict] = {}
    try:
        r = meta.look(SYSTEM + f"\n\nThe business: {about}", f"The video: {title}\nPlan one shot for each numbered moment:\n" + "\n".join(known),
                      [], SCHEMA, agent="mthumb")
        got = {s["n"]: s for s in (r or {}).get("shots", []) if isinstance(s, dict) and s.get("subject")}
    except meta.MetaError:
        pass
    out = []
    for i, line in enumerate(lines):
        p, lk = look_of(line)
        s = got.get(i) or {"place": p, "subject": f"A real scene that shows: {line}", "camera": "eye level, 24mm wide lens",
                           "light": "late afternoon golden hour"}
        out.append(s | {"line": line, "looks": lk if (s.get("place") or "").lower() == p.lower() else look_of(s.get("place") or "")[1]})
    return out


def prompt(shot: dict, *, about: str = "", title: str = "", avoid: str = "", words_at: str = "top", taste: str = "") -> str:
    """The brief Muse Image draws from: the subject first, the way an image model weighs words. The business and the
    headline (`about`, `title`) stay out of the picture: they belong to the photo director's planning, and in a picture
    prompt they invite signs and logos. `words_at` is where the caption will sit, so that part is kept simple. `taste`: what
    this office's people have said yes and no to (taste.brief), so a picture they turned down isn't drawn again."""
    place = ""
    if shot.get("place"):
        place = f"Place: {shot['place']}" + (f", which really looks like this: {shot['looks']}" if shot.get("looks") else "") + \
                ". Show it accurately as it looks today; no invented landmarks.\n"
    details = (shot.get("details") or "").strip().rstrip(".") or "natural stone, warm wood, glass and soft fabrics where they fit the scene"
    return PROMPT.format(subject=shot["subject"].strip().rstrip(".") + ".", place=place, camera=shot["camera"], light=shot["light"], details=details,
                         calm=CALM.get(words_at, CALM["top"]), taste=f"\n{taste}" if taste else "", avoid=f"\nThe last picture was turned down: {avoid}. Fix that." if avoid else "")
