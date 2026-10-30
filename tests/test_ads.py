"""Our own ad account, read-only: the account id gets its act_ prefix, numbers come from the Marketing API as they are."""
import httpx

from diwan.providers import ads


def test_our_ads_are_read_with_the_act_prefix_and_an_ad_that_never_ran_has_no_numbers(monkeypatch):
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "2917")
    monkeypatch.setenv("META_ADS_TOKEN", "t")
    monkeypatch.setattr(ads, "offline", lambda: False)
    seen = []

    def handle(req: httpx.Request):
        seen.append(req.url.path)
        if req.url.path.endswith("/act_2917"):
            return httpx.Response(200, json={"name": "Test account", "currency": "AED"})
        if req.url.path.endswith("/insights"):
            return httpx.Response(200, json={"data": [{"spend": "12.50", "reach": "900", "impressions": "1500", "clicks": "30",
                                                       "actions": [{"action_type": "lead", "value": "2"}]}]})
        return httpx.Response(200, json={"data": [{"id": "1", "name": "Price reveal", "effective_status": "PAUSED"},
                                                  {"id": "2", "name": "Tour", "effective_status": "ACTIVE",
                                                   "insights": {"data": [{"spend": "12.50", "reach": "900", "clicks": "30"}]}}]})
    monkeypatch.setattr(ads, "TRANSPORT", httpx.MockTransport(handle))
    r = ads.report()
    assert seen[0] == "/v21.0/act_2917" and r["currency"] == "AED"
    assert r["total"] == {"spend": 12.5, "reach": 900, "impressions": 1500, "clicks": 30, "ctr": None, "cpc": None, "leads": 2}
    assert r["ads"][0]["status"] == "paused" and r["ads"][0]["spend"] is None  # never ran: no numbers, not zeros
    assert r["ads"][1]["reach"] == 900


def test_without_settings_it_says_what_is_missing(monkeypatch):
    monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(ads, "env", lambda k, d=None: None)
    assert ads.missing() == ["META_AD_ACCOUNT_ID", "META_ADS_TOKEN"] and not ads.ready()
