"""Adding one listing by hand (the Knowledge page's Listings tab)."""
from diwan import listing_add, sitelistings
from diwan.events import EventLog
from diwan.office import Office


def test_a_listing_typed_in_by_hand(tmp_path):
    import pytest
    o = Office(EventLog(str(tmp_path / "o.db")))
    v = {"title": "Corner 2BR canal view", "community": "Palm Grove", "type": "apartment", "beds": "2", "price": "1,250,000", "currency": "aed"}
    with pytest.raises(listing_add.Invalid, match="Only"):
        listing_add.add(o, v, by="omar")  # a broker proposes; the listing owners add
    with pytest.raises(listing_add.Invalid, match="not a number"):
        listing_add.add(o, v | {"price": "a lot"}, by="layla")
    with pytest.raises(listing_add.Invalid, match="title"):
        listing_add.add(o, v | {"title": " "}, by="layla")
    r = listing_add.add(o, v, by="layla")
    props = o.graph().nodes[f"listing:{r['ref']}"].props
    assert (props["price_aed"], props["beds"], props["source"], r["advertised"]) == (1250000, 2, "typed", False)  # no permit: kept, not advertised
    assert all(k in props for k in sitelistings.CRM)
    with pytest.raises(listing_add.Duplicate) as d:
        listing_add.add(o, v, by="layla")  # same beds, price, community
    assert d.value.ref == r["ref"]
    assert listing_add.add(o, v, by="layla", anyway=True)["ref"] != r["ref"]
