from dataclasses import dataclass, field


@dataclass(slots=True)
class ListingDraft:
    source_listing_id: str
    url: str
    title: str = ""
    community_name: str | None = None
    district: str | None = None
    layout: str | None = None
    area: float | None = None
    orientation: str | None = None
    floor: str | None = None
    rent: int | None = None
    tags: list[str] = field(default_factory=list)
    image_url: str | None = None
    agent_type: str | None = None
    raw: dict = field(default_factory=dict)


class SourceError(Exception):
    pass


class LoginRequiredError(SourceError):
    pass


class EmptyPageError(SourceError):
    pass


class CaptchaRequiredError(SourceError):
    pass
