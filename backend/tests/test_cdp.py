from app.sources.cdp import _looks_like_captcha, _page_key


def test_page_key_ignores_query_and_trailing_slash():
    assert _page_key("https://sz.zu.ke.com/zufang/rco11/pg2/?x=1") == (
        "sz.zu.ke.com",
        "/zufang/rco11/pg2",
    )
    assert _page_key("https://sz.zu.ke.com/") == ("sz.zu.ke.com", "/")


def test_captcha_markers_detected():
    assert _looks_like_captcha("https://sz.zu.ke.com/verify", "")
    assert _looks_like_captcha("https://sz.zu.ke.com/zufang/", "请完成验证后继续")
    assert not _looks_like_captcha("https://sz.zu.ke.com/zufang/", "深圳租房信息")
