from app.integrations.base import BaseProvider, Capability, ProviderDomain

DOMAIN_ORDER = {
    ProviderDomain.housing.value: 10,
    ProviderDomain.maps.value: 20,
    ProviderDomain.transit.value: 30,
    ProviderDomain.opendata.value: 40,
    ProviderDomain.reputation.value: 50,
    ProviderDomain.ai.value: 60,
    ProviderDomain.notify.value: 70,
}


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider) -> None:
        self._providers[provider.meta.code] = provider

    def get(self, code: str) -> BaseProvider | None:
        return self._providers.get(code)

    def all(self) -> list[BaseProvider]:
        return sorted(
            self._providers.values(),
            key=lambda item: (
                DOMAIN_ORDER.get(item.meta.domain.value, 99),
                item.meta.priority,
                item.meta.code,
            ),
        )

    def by_domain(self, domain: str | None = None) -> list[BaseProvider]:
        if domain is None:
            return self.all()
        return [item for item in self.all() if item.meta.domain.value == domain]

    def providers_for(self, capability: Capability) -> list[BaseProvider]:
        return [item for item in self.all() if capability in item.meta.capabilities]

    async def close_all(self) -> None:
        for provider in self._providers.values():
            await provider.close()


registry = ProviderRegistry()
_loaded = False


def load_default_providers() -> ProviderRegistry:
    global _loaded
    if _loaded:
        return registry
    from app.integrations.ai.modelscope import ModelScopeProvider
    from app.integrations.ai.opencode_go import OpenCodeGoProvider
    from app.integrations.housing.beike_api import BeikeApiProvider
    from app.integrations.housing.beike_cdp import BeikeCdpProvider
    from app.integrations.maps.amap import AmapProvider
    from app.integrations.maps.didi_mcp import DidiMcpProvider
    from app.integrations.maps.tianditu import TiandituProvider
    from app.integrations.transit.szmc import SzmcProvider

    for provider in (
        BeikeApiProvider(),
        BeikeCdpProvider(),
        DidiMcpProvider(),
        TiandituProvider(),
        SzmcProvider(),
        AmapProvider(),
        OpenCodeGoProvider(),
        ModelScopeProvider(),
    ):
        registry.register(provider)
    _loaded = True
    return registry
