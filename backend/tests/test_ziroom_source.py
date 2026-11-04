from app.sources.ziroom import _layout, _price, parse_room

ROOM = {
    "id": "200619856",
    "house_id": "320084512",
    "name": "德润荣君府1居室-西",
    "price": ["//static8.ziroom.com/price.png", [5, 9, 1, 4]],
    "area": "30.09",
    "floor": "7",
    "floor_total": "31",
    "photo": "//img.ziroom.com/pic/cover.jpg",
    "type_text": "整租",
    "bedroom": 1,
    "parlor": 1,
    "resblock_name": "德润荣君府",
    "district_name": "龙岗区",
    "face": "西",
    "lng": 114.07496235532,
    "lat": 22.631678216476,
    "tags": [{"title": "业主原装"}, {"title": "可闪定"}],
}


SPRITE_ORDER = "8652039147"


def test_price_uses_sprite_glyph_indices():
    # [5, 9, 1, 4] indexes into sprite order "8652039147" -> 3,7,6,0
    assert _price(ROOM, SPRITE_ORDER) == 3760
    assert _price({"price": 4200}, SPRITE_ORDER) == 4200
    assert _price({"price": ["x.png", []]}, SPRITE_ORDER) is None


def test_parse_ziroom_room_price_layout_and_image():
    draft = parse_room(ROOM, sprite_order_value=SPRITE_ORDER)
    assert draft is not None
    assert draft.source_listing_id == "320084512"
    assert draft.rent == 3760
    assert draft.layout == "1室1厅"
    assert draft.community_name == "德润荣君府"
    assert draft.area == 30.09
    assert draft.image_url == "https://img.ziroom.com/pic/cover.jpg"
    assert "整租" in draft.tags and "可闪定" in draft.tags
    assert draft.raw["lng"] == 114.07496235532
    assert "city_code=440300" in draft.url


def test_parse_ziroom_room_rejects_missing_id_or_price():
    assert (
        parse_room({**ROOM, "id": "", "house_id": ""}, sprite_order_value=SPRITE_ORDER)
        is None
    )
    assert (
        parse_room(
            {**ROOM, "price": ["x.png", []]}, sprite_order_value=SPRITE_ORDER
        )
        is None
    )


def test_layout_helpers():
    assert _layout({"bedroom": 2, "parlor": 1}) == "2室1厅"
    assert _layout({"name": "某小区3居室-南"}) == "3室"
