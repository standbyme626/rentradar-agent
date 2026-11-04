# 贝壳采集代理池（3 台云主机）

> 目标：把 3 台云主机作为贝壳 App API 的出口，降低单 IP 频率/封禁风险。
> 推荐安全做法：**SSH SOCKS 跳板**（生产机本机 11081/11082/11083 → 3 台云主机），不要在公网开免认证 HTTP 代理。

## 1. 应用侧已支持

- `backend/app/sources/beike_api.py` 读取 `BEIKE_PROXIES`（逗号分隔）。
- 每个请求轮换代理；单个代理 403/429/5xx 后冷却 5 分钟，换下一个。
- 所有请求串行 + 页间隔 1.5–3s；不会因为代理池变成并发轰炸。
- 直连行为不变：`BEIKE_PROXIES` 为空时仍走服务器单 IP。
- 代理 URL 只放 `.env`（600/640），不要提交或发聊天。
- SOCKS5 需要 `httpx[socks]`（`pip install 'httpx[socks]'`）。

## 2. 云主机提示词（复制给有 root 权限的云主机 agent）

```text
你是这台云主机的管理员。为 RentRadar 配置一个仅用于 SSH SOCKS 跳板的受限账号，不要安装/开放公网 HTTP 代理。

要求：
1. 创建系统用户 rentradar-proxy（无 sudo、无登录 shell 可设为 /usr/sbin/nologin 但必须允许 SSH 端口转发；若必须 shell，限制为 rbash）。
2. 把下面这把生产机公钥写入 /home/rentradar-proxy/.ssh/authorized_keys（700/600，所有者正确）：
   <PRODUCTION_PUBLIC_KEY>
3. sshd 仅允许该用户公钥登录，禁用密码；AllowTcpForwarding yes；不要开放除 SSH 外的公网端口。
4. 防火墙只允许生产出口公网 IP <PRODUCTION_PUBLIC_IP> 访问 SSH；若 IP 不固定，至少限制 key-only 并禁用密码。
5. 验证：ss -ltnp 不应出现 3128/8080 等代理端口；sshd 配置 sshd -t 通过；systemctl restart ssh。
6. 返回：公网 IP、SSH 端口、用户名、主机指纹；并确认 `ssh -N -D 127.0.0.1:11081 rentradar-proxy@<ip>` 可建立隧道。
```

对 3 台机器重复，生产侧用不同本地端口（11081/11082/11083）。

## 3. 生产侧隧道（operator/root）

```bash
# 生产机生成/使用专用 key（如果还没有）
ssh-keygen -t ed25519 -f /home/kkk/.ssh/rentradar-proxy -N ''

# 先手动验证三台
ssh -i /home/kkk/.ssh/rentradar-proxy -N -D 127.0.0.1:11081 rentradar-proxy@CLOUD1
# 另开终端
curl --socks5-hostname 127.0.0.1:11081 -sS 'https://app.api.ke.com/Rentplat/v2/house/list?city_id=440300&limit=1&offset=0&scene=list'
```

systemd 模板（三份 `rentradar-proxy-1/2/3.service`）：

```ini
[Unit]
Description=RentRadar Beike SOCKS tunnel 1
After=network-online.target
Wants=network-online.target

[Service]
User=kkk
ExecStart=/usr/bin/ssh -i /home/kkk/.ssh/rentradar-proxy -N -D 127.0.0.1:11081 \
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  rentradar-proxy@CLOUD1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用：

```bash
systemctl daemon-reload
systemctl enable --now rentradar-proxy-1 rentradar-proxy-2 rentradar-proxy-3
```

## 4. 生产 `.env` 与重启

```bash
# /home/kkk/Project/rentradar/.env（600/640，别提交）
BEIKE_PROXIES=socks5h://127.0.0.1:11081,socks5h://127.0.0.1:11082,socks5h://127.0.0.1:11083
```

```bash
cd /home/kkk/Project/rentradar/backend
.venv/bin/pip install 'httpx[socks]'
systemctl restart rentradar-worker rentradar-scheduler rentradar-api
journalctl -u rentradar-worker -n 30 --no-pager
```

## 5. 验收

- `python -c "from app.core.config import settings; from app.sources.beike_api import parse_proxies; print(len(parse_proxies(settings.beike_proxies)))"` → 3。
- 跑一轮 `crawl --task-id 1 --pages 1 --transport api`，看 provider 日志与新增数据；失败时检查 worker 日志。
- 观察 `runs`/覆盖看板；403/412 仍会触发暂停逻辑（直连或单代理时）。
- 代理池不是无限制：仍保持低频、分片、失败即停；不要把 3 台代理当成并发爬虫。

## 6. 回滚

```bash
# .env 清空 BEIKE_PROXIES=
systemctl restart rentradar-worker
```
恢复单 IP 直连；隧道 unit 可 `systemctl disable --now`。
