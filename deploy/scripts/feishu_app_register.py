#!/usr/bin/env python3
"""RentRadar 飞书应用：官方 App Registration 设备码流程。

用法：
  python3 feishu_app_register.py begin   # 生成扫码 URL + 二维码
  python3 feishu_app_register.py poll    # 轮询，成功后写入 .secrets/feishu-app.json
  python3 feishu_app_register.py status  # 查看是否已创建
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://accounts.feishu.cn"
PATH = "/oauth/v1/app/registration"

ROOT = "/home/kkk/Project/rentradar/.secrets"
STATE = os.path.join(ROOT, "feishu-qr-state.json")
CREDS = os.path.join(ROOT, "feishu-app.json")
QR_PNG = os.path.join(ROOT, "feishu-qr.png")

APP_NAME = "RentRadar 租房雷达"
APP_DESC = "租房雷达：新房源、降价与看房提醒"
SCOPES = [
    "im:message:send_as_bot",
    "im:message:readonly",
    "im:resource",
    "cardkit:card:write",
]


def post_form(body, timeout=30):
    data = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(BASE + PATH, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {"http_error": e.code, "body": raw[:400]}


def b64url(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def begin():
    r = post_form({
        "action": "begin",
        "archetype": "PersonalAgent",
        "auth_method": "client_secret",
        "request_user_info": "open_id",
    })
    if not r.get("device_code"):
        print("begin failed:", json.dumps(r, ensure_ascii=False)[:400])
        return None

    url = urllib.parse.urlparse(r["verification_uri_complete"])
    q = urllib.parse.parse_qsl(url.query, keep_blank_values=True)
    q += [
        ("from", "sdk"),
        ("source", "node-sdk"),
        ("tp", "sdk"),
        ("name", APP_NAME),
        ("desc", APP_DESC),
        ("createOnly", "true"),
        ("addons", b64url({
            "preset": False,
            "scopes": {"tenant": SCOPES},
            "events": {"items": {"tenant": []}},
            "callbacks": {"items": []},
        })),
    ]
    final_url = url._replace(query=urllib.parse.urlencode(q)).geturl()

    os.makedirs(ROOT, mode=0o700, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({
            "device_code": r["device_code"],
            "verify_url": final_url,
            "expires_in": r.get("expires_in", 600),
            "interval": r.get("interval", 5),
            "created_at": int(time.time()),
        }, f, ensure_ascii=False, indent=2)
    os.chmod(STATE, 0o600)

    print("qr_url:", final_url)
    print("expires_in:", r.get("expires_in", 600))
    return final_url


def poll(max_wait=600):
    with open(STATE, encoding="utf-8") as f:
        st = json.load(f)
    code = st["device_code"]
    interval = max(3, int(st.get("interval", 5)))
    deadline = time.time() + max_wait
    last = ""
    while time.time() < deadline:
        r = post_form({"action": "poll", "device_code": code})
        if r.get("client_id") and r.get("client_secret"):
            out = {
                "client_id": r["client_id"],
                "client_secret": r["client_secret"],
                "user_info": r.get("user_info"),
            }
            with open(CREDS, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            os.chmod(CREDS, 0o600)
            print("created app_id:", r["client_id"])
            print("user_info:", json.dumps(r.get("user_info"), ensure_ascii=False))
            return out
        err = r.get("error", "")
        if err in ("access_denied", "expired_token"):
            print("stopped:", err, r.get("error_description", ""))
            return None
        if err == "slow_down":
            interval += 5
        if err != last:
            print("status:", err or "waiting")
            last = err
        time.sleep(interval)
    print("timeout waiting for scan")
    return None


def status():
    if os.path.exists(CREDS):
        with open(CREDS, encoding="utf-8") as f:
            d = json.load(f)
        print("created app_id:", d.get("client_id"))
        print("user_info:", json.dumps(d.get("user_info"), ensure_ascii=False))
        return 0
    print("not created")
    return 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "begin"
    if cmd == "begin":
        begin()
    elif cmd == "poll":
        poll()
    elif cmd == "status":
        sys.exit(status())
    else:
        print("usage: begin|poll|status")
        sys.exit(2)
