import pytest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from O365.utils.windows_tz import get_iana_tz, get_windows_tz

# Windows zones added in 2026 for the Canadian time changes of 2026-11-01.
# CLDR windowsZones maps them since commit c4bb2c199c.
CANADA_2026 = [
    ("America/Vancouver", "British Columbia Standard Time"),
    ("America/Edmonton", "Alberta Standard Time"),
    ("America/Winnipeg", "Manitoba Standard Time"),
]


@pytest.mark.parametrize("iana, windows", CANADA_2026)
def test_canada_2026_iana_to_windows(iana, windows):
    assert get_windows_tz(ZoneInfo(iana)) == windows


@pytest.mark.parametrize("iana, windows", CANADA_2026)
def test_canada_2026_windows_to_iana(iana, windows):
    assert get_iana_tz(windows).key == iana


def test_unknown_windows_tz_raises():
    with pytest.raises(ZoneInfoNotFoundError):
        get_iana_tz("No Such Standard Time")
