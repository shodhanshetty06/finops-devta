"""Tests for CloudBillingCatalogClient against a fake HTTP transport shaped
exactly like the real Cloud Billing Catalog API's documented response
schema (see https://cloud.google.com/billing/docs/reference/rest/v1/services.skus).
No network calls are made - `httpx.MockTransport` intercepts every request."""
import httpx
import pytest

from app.core.exceptions import PricingProviderError
from app.pricing.gcp_client import CloudBillingCatalogClient, GcpSku, _money_to_float


def _services_page(services):
    return httpx.Response(200, json={"services": services})


def _skus_page(skus, next_page_token=None):
    body = {"skus": skus}
    if next_page_token:
        body["nextPageToken"] = next_page_token
    return httpx.Response(200, json=body)


def _sample_sku(sku_id="SKU1", description="N2 Instance Core running in Americas"):
    return {
        "skuId": sku_id,
        "description": description,
        "category": {
            "serviceDisplayName": "Compute Engine",
            "resourceFamily": "Compute",
            "resourceGroup": "N2Standard",
            "usageType": "OnDemand",
        },
        "serviceRegions": ["us-central1"],
        "pricingInfo": [{
            "pricingExpression": {
                "usageUnit": "h",
                "tieredRates": [
                    {"startUsageAmount": 0, "unitPrice": {"currencyCode": "USD", "units": "0", "nanos": 31611000}},
                ],
            },
        }],
    }


def test_money_conversion_handles_units_and_nanos():
    assert _money_to_float({"units": "0", "nanos": 31611000}) == pytest.approx(0.031611)
    assert _money_to_float({"units": "2", "nanos": 500000000}) == pytest.approx(2.5)
    assert _money_to_float({}) == 0.0


def test_find_service_returns_matching_service():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/services"
        return _services_page([
            {"serviceId": "SVC-CE", "displayName": "Compute Engine"},
            {"serviceId": "SVC-SQL", "displayName": "Cloud SQL"},
        ])

    client = CloudBillingCatalogClient(api_key="k", transport=httpx.MockTransport(handler))
    service = client.find_service("Cloud SQL")
    assert service.service_id == "SVC-SQL"
    client.close()


def test_find_service_raises_when_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return _services_page([{"serviceId": "SVC-CE", "displayName": "Compute Engine"}])

    client = CloudBillingCatalogClient(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(PricingProviderError, match="did not return a service"):
        client.find_service("Nonexistent Service")
    client.close()


def test_list_skus_follows_pagination_to_completion():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        token = request.url.params.get("pageToken")
        if not token:
            return _skus_page([_sample_sku("A")], next_page_token="page2")
        elif token == "page2":
            return _skus_page([_sample_sku("B")], next_page_token="page3")
        else:
            return _skus_page([_sample_sku("C")])

    client = CloudBillingCatalogClient(api_key="k", transport=httpx.MockTransport(handler))
    skus = client.list_skus("SVC-CE")
    assert [s.sku_id for s in skus] == ["A", "B", "C"]
    assert call_count["n"] == 3
    client.close()


def test_list_skus_parses_full_realistic_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return _skus_page([_sample_sku()])

    client = CloudBillingCatalogClient(api_key="k", transport=httpx.MockTransport(handler))
    [sku] = client.list_skus("SVC-CE")
    assert sku.description == "N2 Instance Core running in Americas"
    assert sku.resource_family == "Compute"
    assert sku.usage_type == "OnDemand"
    assert sku.service_regions == ("us-central1",)
    assert sku.base_unit_price("USD") == pytest.approx(0.031611)
    client.close()


def test_api_key_auth_sent_as_query_param():
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params["key"] = request.url.params.get("key")
        return _skus_page([])

    client = CloudBillingCatalogClient(api_key="my-secret-key", transport=httpx.MockTransport(handler))
    client.list_skus("SVC-CE")
    assert seen_params["key"] == "my-secret-key"
    client.close()


def test_retries_on_5xx_then_succeeds():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503, text="temporarily unavailable")
        return _skus_page([_sample_sku()])

    client = CloudBillingCatalogClient(api_key="k", transport=httpx.MockTransport(handler))
    skus = client.list_skus("SVC-CE")
    assert len(skus) == 1
    assert attempts["n"] == 3
    client.close()


def test_gives_up_after_max_retries_on_persistent_5xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    client = CloudBillingCatalogClient(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(PricingProviderError, match="HTTP 503"):
        client.list_skus("SVC-CE")
    client.close()


def test_non_retryable_error_raises_immediately():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(403, text="permission denied")

    client = CloudBillingCatalogClient(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(PricingProviderError, match="HTTP 403"):
        client.list_skus("SVC-CE")
    assert attempts["n"] == 1  # no retries for a non-retryable status
    client.close()


def test_requires_either_service_account_or_api_key():
    with pytest.raises(PricingProviderError, match="requires either"):
        CloudBillingCatalogClient()


def test_context_manager_closes_client():
    def handler(request: httpx.Request) -> httpx.Response:
        return _skus_page([])

    with CloudBillingCatalogClient(api_key="k", transport=httpx.MockTransport(handler)) as client:
        client.list_skus("SVC-CE")
    # No assertion beyond "no exception" - proves __exit__ doesn't blow up.
