import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import settings

PASSWORD_ALGORITHM = "scrypt"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32


class TokenError(Exception):
    pass


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return (
        f"{PASSWORD_ALGORITHM}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}"
        f"${_b64encode(salt)}${_b64encode(digest)}"
    )


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded or encoded == "disabled":
        return False
    try:
        algorithm, n, r, p, salt, digest = encoded.split("$")
        if algorithm != PASSWORD_ALGORITHM:
            return False
        computed = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64decode(digest)),
        )
        return hmac.compare_digest(computed, _b64decode(digest))
    except (ValueError, TypeError):
        return False


def _sign(message: bytes) -> bytes:
    return hmac.new(settings.secret_key.encode("utf-8"), message, hashlib.sha256).digest()


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: str,
    session_id: str,
    minutes: int | None = None,
) -> str:
    issued_at = int(time.time())
    expires_at = issued_at + int(minutes or settings.access_token_minutes) * 60
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    payload = _b64encode(
        json.dumps(
            {
                "sub": user_id,
                "username": username,
                "role": role,
                "sid": session_id,
                "iat": issued_at,
                "exp": expires_at,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    message = f"{header}.{payload}".encode("ascii")
    return f"{header}.{payload}.{_b64encode(_sign(message))}"


def decode_access_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
    except ValueError as exc:
        raise TokenError("malformed token") from exc
    message = f"{header}.{payload}".encode("ascii")
    if not hmac.compare_digest(_b64decode(signature), _sign(message)):
        raise TokenError("invalid signature")
    try:
        header_data = json.loads(_b64decode(header))
        data = json.loads(_b64decode(payload))
    except (ValueError, TypeError) as exc:
        raise TokenError("invalid token payload") from exc
    if header_data.get("alg") != "HS256":
        raise TokenError("unsupported algorithm")
    if int(data.get("exp") or 0) <= int(time.time()):
        raise TokenError("token expired")
    if not data.get("sub") or not data.get("sid"):
        raise TokenError("token missing subject")
    return data


def new_session_id() -> str:
    return secrets.token_hex(16)


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
