# 地图尺寸前后对比（2026-11-04）

| 项 | 值 |
|---|---|
| Before | 生产 `main` 当前部署（本次改动前，地图固定 440px） |
| After | 本分支（地图默认约 0.7 视口高 + 全屏按钮） |
| 视口 | 1440 × 1000，Playwright Chromium |
| 数据 | 真实生产 API / 天地图瓦片；临时 viewer 账号，仅读 |
| 应用 | Before 为生产构建，After 为同一源码的 Vite dev（走同一 `/api` 代理） |

| 场景 | 文件 |
|---|---|
| Before 地图 tab（440px，仍被左侧对话挤压） | `before-map.png` |
| After 地图 tab 默认（更高，带全屏按钮） | `after-map.png` |
| After 全屏地图（占满视口，marker/筛选/详情可点） | `after-map-fullscreen.png` |
| After 地铁线路层（SZMC 17 线/433 站，开关可关） | `after-map-subway.png` |

说明：
- 三张图使用同一登录账号、同一驾驶需求、同一视口；Before/After 只比较地图尺寸与全屏能力。
- 地图底图为天地图 WMTS（真实 Key），marker 来自 `/api/maps/communities` 的真实小区聚合。
- 地铁线路层来自 SZMC 官方站点字典（17 线/433 站），无登录/Key；截图里的线路/站点为真实数据。
- 截图不含 `.env`、Token、手机号或私人地址；临时账号已删除。
