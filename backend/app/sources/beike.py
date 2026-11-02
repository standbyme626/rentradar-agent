import re
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.sources.base import EmptyPageError, ListingDraft

ORIENTATIONS = {"东", "南", "西", "北", "东南", "东北", "西南", "西北", "南北"}
FLOOR_WORDS = ("低楼层", "中楼层", "高楼层", "顶层", "底层")
AREA_RE = re.compile(r"([\d.]+)\s*㎡")
LAYOUT_RE = re.compile(r"(\d+室\d+厅(?:\d+卫)?)")
FLOOR_RE = re.compile(r"(低楼层|中楼层|高楼层|顶层|底层)")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def build_list_url(
    city_code: str,
    page: int = 1,
    sort: str = "default",
    district: str = "",
    line: str = "",
) -> str:
    if line:
        path = f"https://{city_code}.zu.ke.com/ditiezufang/{line.strip('/')}/"
    else:
        path = f"https://{city_code}.zu.ke.com/zufang/"
        if district:
            path += f"{district.strip('/')}/"
    if sort == "newest":
        path += "rco11/"
    if page > 1:
        path += f"pg{page}/"
    return path


def _parse_des(des_text: str) -> tuple[float | None, str | None, str | None, str | None]:
    area = None
    orientation = None
    layout = None
    floor = None
    area_match = AREA_RE.search(des_text)
    if area_match:
        try:
            area = float(area_match.group(1))
        except ValueError:
            area = None
    layout_match = LAYOUT_RE.search(des_text)
    if layout_match:
        layout = layout_match.group(1)
    floor_match = FLOOR_RE.search(des_text)
    if floor_match:
        floor = floor_match.group(1)
    for segment in (item.strip() for item in des_text.split("/")):
        if segment in ORIENTATIONS:
            orientation = segment
            break
    return area, orientation, layout, floor


def parse_list(html: str, city_code: str = "sz") -> list[ListingDraft]:
    tree = HTMLParser(html)
    nodes = tree.css("div.content__list--item[data-house_code]")
    if not nodes:
        raise EmptyPageError("no listing cards found; page may be a captcha/login/empty page")

    base = f"https://{city_code}.zu.ke.com"
    seen: set[str] = set()
    drafts: list[ListingDraft] = []
    for node in nodes:
        code = (node.attributes.get("data-house_code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)

        title_node = node.css_first("p.content__list--item--title a")
        title = _clean(title_node.text() if title_node else "")
        href = (title_node.attributes.get("href") if title_node else "") or ""
        if not href:
            aside = node.css_first("a.content__list--item--aside")
            href = (aside.attributes.get("href") if aside else "") or ""

        des_node = node.css_first("p.content__list--item--des")
        des_text = _clean(des_node.text() if des_node else "")
        links = des_node.css("a") if des_node else []
        district = _clean(links[0].text()) if links else None
        community_name = None
        for link in links:
            title_attr = (link.attributes.get("title") or "").strip()
            if title_attr:
                community_name = title_attr
        if not community_name and len(links) >= 3:
            community_name = _clean(links[2].text())
        if not community_name and "·" in title:
            tail = title.split("·", 1)[1].strip()
            community_name = tail.split(" ")[0] if tail else None
        area, orientation, layout, floor = _parse_des(des_text)

        price_node = node.css_first("span.content__list--item-price em")
        rent = None
        if price_node:
            try:
                rent = int(_clean(price_node.text()).replace(",", ""))
            except ValueError:
                rent = None

        tags = [
            _clean(tag.text())
            for tag in node.css("p.content__list--item--bottom i")
            if _clean(tag.text())
        ]

        image_node = node.css_first("a.content__list--item--aside img")
        image_url = None
        if image_node:
            image_url = (
                image_node.attributes.get("data-src") or image_node.attributes.get("src") or ""
            ).strip()
            if "default/" in image_url:
                image_url = None

        brand_node = node.css_first("p.content__list--item--brand .brand")
        brand = _clean(brand_node.text() if brand_node else "")
        bu_desc = (node.attributes.get("data-bu_desc") or "").strip()
        time_node = node.css_first("span.content__list--item--time")
        maintain_time = _clean(time_node.text() if time_node else "")

        agent_type = (
            "apartment"
            if (
                "/apartment/" in href
                or title.startswith("独栋·")
                or "省心租" in bu_desc
                or "贝壳" in brand
                or "自营" in brand
            )
            else "unknown"
        )

        drafts.append(
            ListingDraft(
                source_listing_id=code,
                url=urljoin(base, href) if href else f"{base}/zufang/{code}.html",
                title=title,
                community_name=community_name,
                district=district,
                layout=layout,
                area=area,
                orientation=orientation,
                floor=floor,
                rent=rent,
                tags=tags,
                image_url=image_url,
                agent_type=agent_type,
                raw={
                    "des": des_text,
                    "brand": brand,
                    "bu_desc": bu_desc,
                    "maintain_time": maintain_time,
                    "data_t": node.attributes.get("data-t"),
                    "total": node.attributes.get("data-total"),
                },
            )
        )
    if not drafts:
        raise EmptyPageError("listing cards parsed but no valid drafts")
    return drafts
