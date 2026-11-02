from types import SimpleNamespace

from app.services.provider_runtime import _effective_limit


def provider(limit: int):
    return SimpleNamespace(meta=SimpleNamespace(quota=SimpleNamespace(limit=limit)))


def usage(value: int):
    return SimpleNamespace(limit_value=value)


def test_limit_uses_admin_cap_when_lower():
    assert (
        _effective_limit(
            provider(5000),
            usage=usage(5000),
            admin_settings={"amapMonthlyCap": 900},
            cap_key="amapMonthlyCap",
        )
        == 900
    )


def test_limit_uses_meta_when_cap_higher():
    assert (
        _effective_limit(
            provider(5000),
            usage=None,
            admin_settings={"amapMonthlyCap": 8000},
            cap_key="amapMonthlyCap",
        )
        == 5000
    )


def test_zero_cap_blocks_calls():
    assert (
        _effective_limit(
            provider(5000), usage=None, admin_settings={"aiDailyCap": 0}, cap_key="aiDailyCap"
        )
        == 0
    )


def test_unlimited_provider_without_cap():
    assert (
        _effective_limit(
            provider(0), usage=None, admin_settings={}, cap_key=None
        )
        is None
    )


def test_unlimited_provider_with_cap():
    assert (
        _effective_limit(
            provider(0),
            usage=None,
            admin_settings={"amapMonthlyCap": 300},
            cap_key="amapMonthlyCap",
        )
        == 300
    )
