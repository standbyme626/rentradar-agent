from app.integrations.ai.streaming import (
    parse_openai_stream_chunk,
    parse_openai_stream_usage,
)


def test_parse_text_delta():
    assert (
        parse_openai_stream_chunk(
            {"choices": [{"delta": {"content": "你好"}}]}
        )
        == "你好"
    )
    assert parse_openai_stream_chunk({"choices": []}) == ""
    assert (
        parse_openai_stream_chunk(
            {"choices": [{"delta": {"content": [{"type": "text", "text": "abc"}]}}]}
        )
        == "abc"
    )


def test_parse_usage():
    assert parse_openai_stream_usage(
        {
            "model": "deepseek-v4.1-flash",
            "choices": [],
            "usage": {"prompt_tokens": 12, "completion_tokens": 34},
        }
    ) == (12, 34, "deepseek-v4.1-flash")
