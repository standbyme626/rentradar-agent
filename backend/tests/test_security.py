import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip():
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("scrypt$")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)
    assert not verify_password("anything", "disabled")


def test_access_token_roundtrip():
    token = create_access_token(
        user_id=7, username="alice", role="viewer", session_id="sid-1", minutes=5
    )
    payload = decode_access_token(token)
    assert payload["sub"] == 7
    assert payload["username"] == "alice"
    assert payload["role"] == "viewer"
    assert payload["sid"] == "sid-1"


def test_access_token_rejects_tampering_and_expiry():
    token = create_access_token(
        user_id=1, username="admin", role="admin", session_id="sid-2", minutes=5
    )
    header, payload, signature = token.split(".")
    with pytest.raises(TokenError):
        decode_access_token(f"{header}.{payload}.{signature}A")

    expired = create_access_token(
        user_id=1, username="admin", role="admin", session_id="sid-3", minutes=-1
    )
    with pytest.raises(TokenError):
        decode_access_token(expired)


def test_refresh_token_hash_is_stable():
    token = "refresh-token-value"
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert hash_refresh_token(token) != hash_refresh_token(f"{token}x")
