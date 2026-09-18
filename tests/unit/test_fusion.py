from datetime import date
from carbon_mrv.change.fusion import Evidence,fuse_event

def test_confirmed_requires_two_strong_families():
    out=fuse_event([Evidence("sentinel2","strong","loss",date(2021,8,1),date(2021,9,20)),Evidence("gfc","strong","loss",date(2021,1,1),date(2021,12,31))])
    assert out["confidence"]=="confirmed"; assert out["cause_status"]=="cause_not_established"

def test_fire_requires_modis_plus_sentinel_and_compatible_time():
    out=fuse_event([Evidence("sentinel2","strong","loss",date(2021,8,1),date(2021,9,20)),Evidence("modis","strong","loss",date(2021,9,10),date(2021,9,14),supports_fire=True)])
    assert out["cause"]=="fire"; assert out["confidence"]=="confirmed"

def test_conflicting_intervals_are_flagged_not_averaged():
    out=fuse_event([Evidence("sentinel2","strong","loss",date(2021,8,1),date(2021,8,10)),Evidence("modis","strong","loss",date(2021,9,10),date(2021,9,14),supports_fire=True)])
    assert out["date_conflict"] is True; assert out["cause"] is None


def test_date_precision_is_explicit():
    out=fuse_event([
        Evidence("sentinel2","strong","loss",date(2021,9,10),date(2021,9,14)),
        Evidence("modis","strong","loss",date(2021,9,11),date(2021,9,13),supports_fire=True),
    ])
    assert out["date_precision"] == "week"
