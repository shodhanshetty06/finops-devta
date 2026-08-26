"""Unit tests for the single, authoritative region-priority function (user
override > workbook region > application default) - see
app/domain/region_resolution.py. These cover the exact five scenarios from
the region-handling fix: no override/no workbook region -> default;
workbook has the default region -> workbook (not silently treated as
"default" just because the values happen to match); workbook has a
different region -> workbook; user overrides a workbook region -> user
wins; user selects with no workbook region -> user wins."""
import pytest

from app.core.exceptions import FinOpsError
from app.domain.enums import Region
from app.domain.region_resolution import DEFAULT_REGION, resolve_region


def test_no_user_override_no_workbook_region_uses_default():
    region, source = resolve_region(None, None)
    assert region == DEFAULT_REGION == Region.ASIA_SOUTH1
    assert source == "default"


def test_workbook_explicitly_names_the_default_region():
    region, source = resolve_region(None, "asia-south1")
    assert region == Region.ASIA_SOUTH1
    assert source == "workbook"  # explicitly present, not just coincidentally the default


def test_workbook_names_a_different_region_and_user_does_not_override():
    region, source = resolve_region(None, "europe-west1")
    assert region == Region.EUROPE_WEST1
    assert source == "workbook"


def test_user_override_wins_over_workbook_region():
    region, source = resolve_region("us-west1", "europe-west1")
    assert region == Region.US_WEST1
    assert source == "selected"


def test_user_override_wins_with_no_workbook_region():
    region, source = resolve_region("us-west1", None)
    assert region == Region.US_WEST1
    assert source == "selected"


def test_invalid_user_override_raises_clear_error():
    with pytest.raises(FinOpsError, match="not a supported GCP region"):
        resolve_region("mars-north1", "europe-west1")


def test_invalid_workbook_region_raises_clear_error():
    with pytest.raises(FinOpsError, match="not a supported GCP region"):
        resolve_region(None, "mars-north1")


def test_empty_string_is_treated_as_absent_not_invalid():
    # "" is falsy - must fall through to the next priority tier rather than
    # being rejected as an invalid region string.
    region, source = resolve_region("", "")
    assert region == DEFAULT_REGION
    assert source == "default"
