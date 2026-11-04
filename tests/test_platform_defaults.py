"""Where a post goes: Instagram, Facebook and LinkedIn by default, Property Finder for a listing only; TikTok and YouTube
Shorts only when picked, and only for a video. A version is written only for a platform the post can go to."""
import pytest

from diwan import business, demo, platforms
from diwan.events import EventLog
from diwan.office import Office


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


def test_the_defaults(office):
    assert platforms.for_post(office, listing=False, video=False) == ["Instagram", "Facebook", "LinkedIn"]
    assert platforms.for_post(office, listing=False, video=True) == ["Instagram", "Facebook", "LinkedIn"]  # video platforms are off until picked
    assert platforms.for_post(office, listing=True, video=True) == ["Instagram", "Facebook", "LinkedIn", "Property Finder"]


def test_picked_platforms_but_only_where_the_post_can_go(office):
    business.save(office, {"platforms": "Instagram, TikTok, YouTube Shorts, Property Finder, LinkedIn"}, by="maya")
    assert platforms.for_post(office, listing=True, video=True) == ["Instagram", "TikTok", "YouTube Shorts", "Property Finder", "LinkedIn"]
    assert platforms.for_post(office, listing=True, video=False) == ["Instagram", "Property Finder", "LinkedIn"]  # pictures: no video-only platform
    assert platforms.for_post(office, listing=False, video=True) == ["Instagram", "TikTok", "YouTube Shorts", "LinkedIn"]  # a topic: no portal


def test_instagram_is_always_there(office):
    business.save(office, {"platforms": "LinkedIn"}, by="maya")
    assert platforms.for_post(office, listing=False, video=False) == ["Instagram", "LinkedIn"]


def test_versions_are_written_only_for_those_platforms(office):
    caption = "Meet Diwan Realty. We help families buy their first home in Dubai.\n\n#DiwanRealty #DubaiRealEstate #DubaiHomes #MovingToDubai"
    assert set(platforms.versions(office, caption, listing=False, video=False)) == {"Instagram", "Facebook", "LinkedIn"}
    assert set(platforms.versions(office, caption, listing=True, video=False)) == {"Instagram", "Facebook", "LinkedIn", "Property Finder"}
    assert set(platforms.versions(office, caption, platforms=["TikTok"])) == {"TikTok"}  # given outright: as given
