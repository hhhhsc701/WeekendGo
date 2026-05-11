from app.mcp.region import RegionRouter, fallback_chinese_city_coordinates, is_chinese_city


def test_chinese_city_aliases_are_domestic() -> None:
    assert is_chinese_city("Shanghai")
    assert is_chinese_city("Beijing")
    assert is_chinese_city("Hong Kong")
    assert RegionRouter().region_for_city("Shanghai") == "domestic"


def test_known_international_city_aliases_stay_international() -> None:
    assert not is_chinese_city("Tokyo")
    assert not is_chinese_city("New York")
    assert RegionRouter().region_for_city("Tokyo") == "international"


def test_fallback_coordinates_for_common_chinese_city() -> None:
    assert fallback_chinese_city_coordinates("上海") == (31.2304, 121.4737)
    assert fallback_chinese_city_coordinates("Shanghai") == (31.2304, 121.4737)
