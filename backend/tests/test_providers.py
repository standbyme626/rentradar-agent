from app.integrations.base import Capability, ProviderDomain
from app.integrations.registry import load_default_providers, registry


def test_default_providers_registered():
    load_default_providers()
    codes = {provider.meta.code for provider in registry.all()}
    assert {"beike_api", "beike_cdp", "amap", "tianditu", "didi_mcp", "szmc"} <= codes


def test_provider_domains_and_capabilities():
    load_default_providers()
    assert registry.get("beike_api").meta.domain == ProviderDomain.housing
    assert Capability.listing_search in registry.get("beike_api").meta.capabilities
    assert registry.get("tianditu").meta.coord_system == "CGCS2000"
    assert Capability.reverse_geocode in registry.get("tianditu").meta.capabilities
    assert Capability.taxi_estimate in registry.get("didi_mcp").meta.capabilities
    assert Capability.route_driving in registry.get("didi_mcp").meta.capabilities
    assert registry.get("szmc").meta.domain == ProviderDomain.transit
    assert Capability.route_transit in registry.get("szmc").meta.capabilities


def test_provider_registry_domain_filter():
    load_default_providers()
    housing = registry.by_domain("housing")
    maps = registry.by_domain("maps")
    assert {item.meta.code for item in housing} == {"beike_api", "beike_cdp"}
    assert {"amap", "tianditu", "didi_mcp"} <= {item.meta.code for item in maps}


def test_provider_registry_capability_filter():
    load_default_providers()
    transit = registry.providers_for(Capability.route_transit)
    codes = {item.meta.code for item in transit}
    assert {"amap", "didi_mcp", "szmc"} <= codes
