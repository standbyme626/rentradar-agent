# 天地图底图能力与 RentRadar 接入方案

> 调研日期：2026-11-04 ｜ 适用：RentRadar（Vue 3 + FastAPI，深圳租房）｜ 本文不含任何 Key、Cookie 或代理凭据。
> 说明：本会话的 `web_search` 因未配置搜索 API Key 不可用；以下结论以天地图官方文档、WMTS `GetCapabilities` 元数据、官方页面源码及公开技术资料交叉核对，链接见第 8 节。

## 0. 结论与推荐方案（先看这里）

1. **天地图没有面向个人开发者的“瓦片打包下载”产品。** 全国平台/开发者站提供的是**在线** JavaScript API 4.0 与 OGC WMTS 服务；所谓“地图下载”在省市级节点实际是**参考图/标准地图成图**下载，在全国目录系统则是**测绘成果数据**下载（需单位账号、审批/保密信息），都不是可离线部署的瓦片包 [1][7][10][11]。
2. **推荐架构：后端 WMTS 代理 + 磁盘缓存 + Leaflet 前端。** Key 只放服务端，浏览器只访问同源 `/api/maps/tiles/...`；这样既隐藏 Key，又能复用现有 SOCKS 出口、配额与熔断能力。
3. **本项目后端已具备雏形**：`backend/app/api/routes/maps.py`、`backend/app/services/map_service.py`、`TiandituProvider.fetch_tile()` 已实现代理、磁盘缓存、GCJ-02→WGS-84 和配额计数；前端 `MapPanel.vue` 已改为自研的 Web 墨卡托瓦片渲染 + 真实 marker（不引入 Leaflet 依赖）；剩余缺口是瓦片失败降级、认证续期与审图号展示。
4. **WMTS 用 `_w`（Web 墨卡托）矩阵集**：`https://t{s}.tianditu.gov.cn/{layer}_w/wmts?...&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=...`；`t0`–`t7`，1–18 级，256×256，`TILEROW=y / TILECOL=x`，不要做 TMS 的 y 翻转 [1][14]。
5. **坐标系必须转换**：天地图是 CGCS2000/WGS-84（`_c` 为 EPSG:4490，`_w` 为 EPSG:900913≈3857），贝壳房源是 GCJ-02；深圳偏移约 400–600 m。天地图 JS API **不会**自动纠正 GCJ-02，直接传会整体偏移 [14][15][18]。
6. **配额按 Key、按自然日（北京时间）计**：官方只承诺“个人/企业分级配额，控制台可升级”，公开资料普遍为个人约 1 万次/日；瓦片是最大消耗项。必须缓存优先、设日预算、超限/失效时降级，不能靠多 Key 轮换绕过 [3][4][19][20]。
7. **合规边界**：在线展示需保留“© 天地图”和审图号；按需缓存可以，批量抓取、整城/全国离线镜像、再分发或对外提供离线包均不在公开授权内；公网/商业/离线交付需向国家基础地理信息中心或当地测绘主管部门申请并做地图审核 [5][7]。
8. **若必须完全离线/内网**：不要抓天地图瓦片；改用 OSM 自建瓦片（ODbL，需署名/相同方式共享）或采购合规底图，天地图仅作为在线底图/可选增强。

## 1. 天地图官方能力盘点

### 1.1 地图展示：JS API 与 WMTS 两条路
| 能力 | 入口/形式 | 是否需 Key | 说明 |
|---|---|---|---|
| JavaScript API 4.0 | `https://api.tianditu.gov.cn/api?v=4.0&tk=...` | 是 | 官方推荐 Web 端方式，内置地图、标注、地理编码等；Key 出现在 script URL 中 [1][2] |
| JavaScript API 3.0 / 4.0 开源库 | `lbs.tianditu.gov.cn` 开发文档 | 是 | 老项目/扩展开源库；新项目优先 4.0 [1] |
| WMTS 1.0.0 | `https://t{0-7}.tianditu.gov.cn/{layer}_{w|c}/wmts` | 是（瓦片） | 标准 OGC KVP 接口，可用 Leaflet/OpenLayers/QGIS/Cesium 接入 [1] |
| 数据 API（WFS） | `http://gisserver.tianditu.gov.cn/TDTService/wfs` | 否（公开） | 1:100 万地形衍生的政区/交通/水系/居民地矢量，不是底图瓦片 [13] |
| 静态地图 API | `lbs.tianditu.gov.cn/staticapi/static.html` | 是 | 返回静态图片，适合分享图，不适合交互底图 [1] |

官方栅格底图**只提供 WMTS**；未发现公开的 WMS 底图服务。WMTS 的 `GetCapabilities` 可匿名读取，但取瓦片必须带 `tk`；`Fees=none`、`AccessConstraints=none` 只是 OGC 元数据，不等于放弃服务条款/数据许可 [14][15]。

### 1.2 图层与矩阵集（官方名称）
| 图层 | 代码 | 说明 | `_w` 示例 |
|---|---|---|---|
| 矢量底图 | `vec` | 道路/水系/建筑轮廓 | `vec_w` |
| 矢量注记 | `cva` | 中文地名/道路名，透明叠加 | `cva_w` |
| 影像底图 | `img` | 卫星影像 | `img_w` |
| 影像注记 | `cia` | 影像上的地名 | `cia_w` |
| 地形晕渲 | `ter` | 地形阴影 | `ter_w` |
| 地形注记 | `cta` | 地形图地名 | `cta_w` |
| 全球境界 | `ibo` | 国界/境界 | `ibo_w` |

每个图层都有 `_w`（球面墨卡托）和 `_c`（经纬度）两套。`GetCapabilities` 显示：`_w` 的 `SupportedCRS` 为 `urn:ogc:def:crs:EPSG::900913`（与 EPSG:3857 等价），`_c` 为 `urn:ogc:def:crs:EPSG::4490`（CGCS2000 经纬度）；两套均有 **1–18 级、256×256**，无 0 级 [14][15]。

### 1.3 “地图下载”到底是什么
截至调研日，在以下官方入口中**没有**“瓦片包下载”：

| 入口 | 实际内容 | 对象/门槛 | 是否瓦片 |
|---|---|---|---|
| 天地图首页“地图服务”菜单 | 在线地图、专题图层、标准地图、多时相影像、重要地理信息数据、成果目录 | 公开浏览 | 否 |
| 标准地图服务系统 `bzdt.ch.mnr.gov.cn` | 中国全图/世界地图等**JPG/EPS 成图**，带审图号 | 免费下载 | 否 [12] |
| 全国地理信息资源目录服务系统 `mulu.tianditu.gov.cn` | 测绘成果**目录查询、订单下载**；申请表含批准单位、批准文号、保密单位等 | 注册会员/单位，部分需审批 | 否 [7] |
| 天地图服务中心 `cloudcenter.tianditu.gov.cn/dataSource` | “数据资源/数据下载”：行政区划可视化，选省/市/县，格式仅 **GeoJSON**；页面注明“数据更新时间 2026 年 10 月”“该数据仅供地图可视化使用” | 登录 + 滑块验证；官方文档称服务中心**仅面向单位用户** | 否 [8][9] |
| 河南许昌/濮阳等市级节点“地图下载” | “参考图/普通地图下载”，如许昌市区图、禹州市地图、濮阳市地图（2023），提供单位为省/市地图院，带审图号 | 部分需登录 | 否 [10][11] |
| 第三方“天地图下载器/教程” | 按 WMTS 逐块抓取，常配多 Key 轮换 | 非官方 | 技术上是瓦片，但不推荐 [20] |

结论：产品 owner 听到的“天地图有地图下载”**部分成立，但下载的是成图/成果数据，不是底图瓦片**。真正要替换 mock 地图，应走在线 WMTS + 本地缓存，而不是寻找“官方瓦片包”。

### 1.4 许可与审批要点
- 个人可免费注册开发者、创建应用、获取 Key，用于在线 API/WMTS；企业认证可提升配额 [3][4]。
- 服务中心仅面向单位用户；成果数据下载还需会员/单位及审批。《数据下载协议》明确：只享有“有限的、不排它的使用权”，未经测绘主管机构允许不得有偿/无偿转让，不得直接用作对外分发数据库/产品/服务的一部分，不得私自向国外提供；成果需注明来源、送样并送审 [7][9]。
- 标准地图可直接使用，但必须保留审图号，不得修改国界/重要地理要素 [12]。
- 公网展示/商业使用还涉及《测绘法》、地图审核、审图号展示；本项目若仅内部使用，风险较低，但一旦对外分享需重新评估 [5][7]。

## 2. WMTS URL 模板（可直接给 Leaflet）

### 2.1 官方 KVP 模板
把 `YOUR_TK` 换成自己的 Key（不要提交到仓库；本文不提供真实 Key）：

```text
https://t{s}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0
  &LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles
  &TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=YOUR_TK
```

- `{s}` 取 `0`–`7`，即 `t0`…`t7`；官方允许随机/轮询选择，用于分摊连接数 [1]。
- `{z}` 为 1–18；`{x}` 为列号（`TILECOL`），`{y}` 为行号（`TILEROW`）；**不要交换，也不要做 TMS 的 y 翻转**（天地图原点在左上）[1][14]。
- `FORMAT=tiles` 是天地图的固定值，返回 256×256 的 JPEG/PNG；Leaflet 不需要关心具体格式。
- `_c` 版本把 `vec_w` 改为 `vec_c`、`TILEMATRIXSET=w` 改为 `c`；但 Leaflet 默认 CRS 与 `_c` 的瓦片网格不一致，**Web 端只用 `_w`**。官方支持 HTTP/HTTPS，生产用 HTTPS 避免混合内容 [1]。

### 2.2 各图层模板
| 用途 | 路径与 `LAYER` |
|---|---|
| 矢量底图 / 注记 | `vec_w` / `cva_w`，`LAYER=vec` / `cva` |
| 影像底图 / 注记 | `img_w` / `cia_w`，`LAYER=img` / `cia` |
| 地形晕渲 / 注记 | `ter_w` / `cta_w`，`LAYER=ter` / `cta` |
| 完整参数 | 同 2.1 模板，仅替换路径与 `LAYER`；例：`img_w`/`img`、`ter_w`/`ter`、`cva_w`/`cva` |

Leaflet 可直接把 WMTS KVP 当 XYZ 模板用：

```ts
L.tileLayer('https://t{s}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=' + key, {
  subdomains: '01234567', minZoom: 10, maxZoom: 18, maxNativeZoom: 18,
  detectRetina: false, attribution: '© 天地图',
}).addTo(map)
```

注意：官方“升级向导”示例曾把 `TILEROW/TILECOL` 写成 `{x}/{y}`，与 `MapService` 页相反；以 `MapService` 页和 `GetCapabilities` 为准，照抄错误示例会得到空白瓦片 [1][4]。

## 3. 配额、条款与缓存/离线边界

### 3.1 配额
- 官方口径：为保证服务稳定，对个人/企业开发者实行**调用量配额**，需要更高调用可在控制台升级账号；配额按 Key/应用计，具体数值以控制台“服务配额”为准 [3][4]。
- 公开资料与项目配置的常见值：个人约 **10,000 次/日**，企业更高（常见“30 万/日”说法）；按北京时间自然日重置；超限常见 HTTP 429/403，表现为底图突然空白 [19][20]。
- 本项目 `QuotaPolicy(period="day", limit=10000)`，`period_key()` 已按 `Asia/Shanghai` 计算；瓦片缓存命中不计费，只有回源 `units=1` 计数。**同一 Key 的瓦片与地理编码共享/分别计算以控制台为准**，设计上按“总共 1 万/日”保守处理 [3]。
- 不要用多 Key 轮换、代理池绕过配额；这既容易触发风控，也不符合服务条款。需要更高配额应走企业认证/商务申请。

### 3.2 条款与署名
- 服务条款要求：使用“天地图”网站内容应注明来源；转载/引用须注明“转自（或引自）天地图”并标明 `www.tianditu.gov.cn`；不得干扰正常服务、不得用于非法目的、不得散布商业广告 [5][6]。
- 地图展示至少保留：`© 天地图` + 官网链接 + 当前底图审图号（审图号随版本更新，不要硬编码；2026 年官方页面已出现 `GS（2026）4921号`，旧页面为 `GS(2019)1719号`）[8]。
- 数据下载协议另有更严格的限制：不得转让/对外分发、不得涉外提供、成果需注明来源并送审 [7]。

### 3.3 批量下载/缓存是否允许？
- **没有公开授权“批量下载瓦片/离线镜像”**。WMTS 是在线服务；官方提供的“下载”是成图或成果数据，且附带单位/审批/不得再分发等限制 [7][8][10]。
- 为**显示目的**做按需、有上限的浏览器/反向代理缓存是正常工程实践，也是配额管理所必需；但把整城/全国瓦片长期落盘、打包分发、对外提供离线底图，超出公开授权范围。
- 公网/商业/离线交付：先向国家基础地理信息中心（`tdt@ngcc.cn`）或当地测绘主管部门书面确认，完成地图审核/审图号，再谈离线包；不要默认“能下载就能再分发”。
- 完全离线/内网：优先 OSM 自建瓦片或采购合规底图；OSM 需遵守 ODbL（署名、相同方式共享），且中国境内 POI/道路完整性不如天地图。

## 4. 坐标系：CGCS2000 / EPSG:3857 vs 贝壳 GCJ-02

### 4.1 天地图用什么
- `_c`：`EPSG:4490`，CGCS2000 经纬度；`_w`：`EPSG:900913`（旧代码，等价 EPSG:3857）Web 墨卡托。CGCS2000 与 WGS-84 差异为厘米级，Web 展示可视为同一坐标 [14][15]。
- JavaScript API 的 `T.LngLat(lng, lat)` 按 CGCS2000/WGS-84 经纬度解释；官方文档没有 GCJ-02 参数、纠偏开关或“火星坐标”选项 [2]。
- 因此：**把 GCJ-02 直接传给天地图（JS API 或 WMTS 上的 marker）会整体偏移，API 不会自动纠正。**

### 4.2 偏移有多大
- GCJ-02 是对 WGS-84 做非线性偏移后的“火星坐标”，全国数百米级；深圳约 **400–600 m**，且随位置缓慢变化，不能用固定常量修正。
- 贝壳房源坐标为 GCJ-02；天地图地理编码返回 CGCS2000/WGS-84。项目现有做法是：`TiandituProvider._location()` 把天地图结果转成 GCJ-02 入库，`map_service.communities()` 再把库里的 GCJ-02 转成 WGS-84 返给地图。这个“**库内统一 GCJ-02，出口按需 WGS-84**”的约定是合理的，不要在前端再转一次 [18]。

### 4.3 转换实现
- 后端已有 `backend/app/geo/coords.py`：`gcj02_to_wgs84()` 用 4 次迭代反解，精度优于 1 m；`gcj02_to_cgcs2000()` 是同一实现的别名。
- 前端若拿到原始 GCJ-02（而不是 `/api/maps/communities` 的 WGS-84），需要同样的反解；可直接复用 `coordtransform` 的 JS 版本，不要用“加固定偏移”土办法 [18]。
- Leaflet 的坐标顺序是 `[lat, lng]`；API 返回 `[lng, lat]`。`L.marker([c.lat, c.lng])`，`map.setView([center[1], center[0]])`，不要写反。
- 若未来切换回高德/腾讯，仍需在出口转回 GCJ-02；建议在 API 响应里显式带 `coord_system: "wgs84"`（现有实现已带），前端断言后再渲染。

## 5. 推荐架构（结合现有代码）

### 5.1 现状：后端已大半完成，前端未接
| 层 | 现状 | 判断 |
|---|---|---|
| 后端路由 | `GET /api/maps/tiles/{layer}/{z}/{x}/{y}`，登录态校验，返回 `X-Tile-Cache` | 可用，需补 304/错误头/限流 |
| 瓦片抓取 | `TiandituProvider.fetch_tile()` 走 `TIANDITU_PROXY`，`(x+y)%8` 选 `t0`–`t7`，校验图片类型/大小 | 可用，需复用 HTTP 客户端、失败重试另一子域 |
| 缓存 | `data/map-tiles/{layer}/{z}/{x}/{y}.png`，TTL 30 天，原子写 | 可用，需单飞、stale、内容类型、LRU/上限 |
| 配额 | `provider_runtime.invoke(..., units=1)`，日配额、熔断、用量记账 | 可用，需瓦片日预算/降级/告警 |
| 坐标 | `/communities` 已 GCJ-02→WGS-84，返回 `coord_system: wgs84` | 正确，前端不要再转 |
| 前端 | `MapPanel.vue` 仍是高德 JS API/占位；`MapPreview.vue` 是纯 mock；`mapApi`/`MapData` 类型已就绪 | **主要缺口**；`package.json` 尚无 Leaflet |

### 5.2 目标链路
```text
Browser (Leaflet)
  └─ GET /api/maps/communities            -> 小区点（WGS-84）+ tiles 配置（建议加审图号）
  └─ GET /api/maps/tiles/vec/{z}/{x}/{y}  -> FastAPI（同源 Cookie）
        ├─ 命中磁盘缓存 -> 直接返回（不打上游）
        └─ 未命中 -> provider_runtime -> TiandituProvider.fetch_tile()
              └─ httpx.AsyncClient(proxy=TIANDITU_PROXY) -> t{0-7}.tianditu.gov.cn
```

### 5.3 后端需要补的 8 件事
1. **单飞（single-flight）**：并发未命中同一瓦片时只回源一次；用 `asyncio.Lock` 字典或 `anyio` 锁，拿到锁后二次检查缓存。
2. **stale-on-error**：缓存过期但上游 403/429/5xx 时，继续返回旧瓦片并标 `X-Tile-Cache: stale`；不要直接 502 让整张图变白。
3. **内容类型**：当前命中缓存固定返回 `image/png`，但上游 `vec` 多为 JPEG；落盘时存 sidecar `.json`（content-type/etag）或按 magic bytes 判断，避免错误的 `Content-Type`。
4. **共享 HTTP 客户端**：`fetch_tile()` 每次 `async with httpx.AsyncClient(...)` 都会新建连接/代理隧道；改为 Provider 级长生命周期 client，设置 `limits`、`timeout=5s`、`trust_env=False`，关闭时 `aclose()`。
5. **失败切子域**：某个 `tN` 超时/5xx 时重试下一个子域（最多 1 次）；403 不重试，直接熔断并告警。
6. **缓存治理**：TTL 30 天 + 最大体积（如 2 GB）/LRU；`tile_cache_stats()` 不要每次 `rglob` 全盘扫描，维护计数或异步统计。
7. **认证**：当前依赖 15 分钟 access cookie；`<img>` 请求无法触发 refresh，长时间停留后瓦片会 401。P1 可在 `/communities` 里下发短时签名 `sig`/`exp` 供瓦片 URL 使用，或前端每 10 分钟静默 refresh；生产更推荐签名瓦片 URL。
8. **防滥用**：校验 layer/z/x/y 已做；再加深圳 bbox 白名单、每用户令牌桶（如 10 req/s，burst 30）和 `Referer`/同源检查，避免登录用户把接口当免费代理刷配额。

### 5.4 缓存头与错误行为
| 场景 | 建议响应 |
|---|---|
| 命中/回源成功 | `Cache-Control: private, max-age=604800, stale-while-revalidate=86400`；`ETag: "<mtime>-<size>"`；`Content-Type` 正确；`X-Tile-Cache: hit/miss`；`X-Content-Type-Options: nosniff` |
| 条件请求 | `If-None-Match` 命中返回 304（省流量，不占配额） |
| 缓存过期但上游失败 | 返回旧瓦片，`X-Tile-Cache: stale`，`Cache-Control: private, max-age=60` |
| 无 Key | `/communities.tiles.enabled=false`；瓦片 503 `{"detail":"底图未配置"}`，前端显示网格+marker，不请求瓦片 |
| Key 失效/IP 不匹配 | 403 熔断 5 分钟；有旧缓存则 stale，否则 503；管理端告警；不要循环重试 |
| 配额耗尽/429 | 停止回源，stale/503；`Retry-After: 3600`；前端横幅“底图额度已用完，显示缓存” |
| 上游非图片/空内容 | 视为失败，不落盘；负缓存 30 秒，避免打爆 |

> 当前实现是 `Cache-Control: private, max-age=2592000`（30 天）+ `X-Tile-Cache`。30 天对底图可以，但底图版本更新后旧瓦片会长期滞留；建议降到 7 天，或在 URL 加 `?v=` 版本号。

### 5.5 前端：Leaflet 接入要点
- 依赖：`leaflet@^1.9.4` + `@types/leaflet`（dev）；如要聚合，再加 `leaflet.markercluster` + 类型。直接 `onMounted` 初始化即可，不必上 Vue 包装库；也不建议自写 canvas 瓦片渲染器（手势/惯性/瓦片金字塔/无障碍成本高、收益低）。
- URL 用同源代理，不暴露 `t0-t7`/`tk`：`/api/maps/tiles/vec/{z}/{x}/{y}`（`apiConfig.baseUrl` 为 `/api` 时拼成 `/api/maps/...`）。
- 底图：`vec` + `cva` 两层，`cva` 置顶；影像模式 `img` + `cia`；`ter` 可选。`detectRetina: false`（否则会请求 z+1，配额翻倍），`maxNativeZoom: 18`，`keepBuffer: 2`。
- 视野：深圳 bbox 约 `[[22.35,113.70],[22.95,114.70]]`；初始 center `[22.54,114.06]`、zoom 12；`minZoom:10`、`maxZoom:18`、`maxBounds` 略放宽，`noWrap:true`。
- 点：`/communities` 最多 800 个；低 zoom 用聚合/圆点，高 zoom 用 `divIcon`；popup 显示小区名、租金中位数、评分、通勤 p50；点击联动 `ListingDetailDrawer`。
- 归因：`map.attributionControl` 固定显示 `© 天地图` + 官网链接 + 审图号；不要因为 UI 紧凑而移除。
- 降级：`tiles.enabled=false` 或 `tileerror` 时，保留 Leaflet 画布和 marker，叠加网格背景 + “底图暂不可用（已显示小区位置）”；不要整块替换成 mock 插画。
- 认证：同源 Cookie 对 `<img>` 自动携带；若前后端跨源，`SameSite=Lax` 会导致瓦片 401，必须用 Vite/nginx 同源反代，或签名 URL，不要给瓦片加 Bearer header（`<img>` 不支持）。

### 5.6 天地图 JS API 4.0 作为替代方案
| 维度 | Leaflet + 后端代理（推荐） | 天地图 JS API 4.0 |
|---|---|---|
| Key 位置 | 仅服务端，浏览器看不到 | script URL/网络面板可见，可被复制 |
| 与现有 Key 兼容 | 兼容（Key 绑定服务器出口 IP） | **不兼容**：浏览器直连，IP 不匹配会 403 |
| 代理/出口 | 可走 SOCKS、可审计 | 文档未提供代理配置，瓦片由浏览器直连 `t0-t7` |
| 缓存/配额 | 可磁盘缓存、单飞、限额、stale | 无服务端缓存，配额不可控 |
| 依赖 | 自托管 Leaflet（约 42 KB gzip） | 外部脚本 + 外部 CSS，受 CSP/可用性影响 |
| 功能 | 需自己接 marker/cluster/popup | 内置控件、标注、地理编码、绘制 |
| 适用 | 本项目的长期方案 | 快速原型/浏览器端 Key 且不介意暴露时 |

结论：现有 Key 是“服务端 + IP 白名单”模式，**JS API 直接上会 403**；即使换浏览器 Key，也等于把配额暴露给每个访客。除非产品决定放弃代理与缓存，否则不建议。

### 5.7 P1 落地状态（2026-11-04）

已落地：

1. `MapPanel.vue` 未引入 Leaflet，改为自研 Web 墨卡托瓦片层 + marker（少一个前端依赖）；调 `mapApi.communities()`，按 `tiles.enabled` 挂载/不挂载瓦片层，支持底图/注记、租金/评分着色、通勤筛选、marker popup、`© 天地图` 和“瓦片不可用回退坐标视图”。
2. 后端 `map_service.py` + `routes/maps.py`：`vec/cva` 图层代理、磁盘缓存 30 天、Key 不下发、无 Key 返回 503、按 z/x/y 校验、GCJ-02→WGS-84、缓存命中不回源。
3. `TiandituProvider.fetch_tile()`：子域轮转、`_w` 矩阵集、错误分类、经 10943 出口。
4. `docs/API-SOURCES.md` 已把天地图坐标从“GCJ-02”修正为 CGCS2000/WGS-84。
5. 单元测试覆盖缓存命中/回源/无 Key/坐标/瓦片范围；前端 `npm run build` 通过。

仍待（不是本 PR 范围）：

1. 单飞、stale-on-error、ETag/304、缓存上限/LRU、线程化文件 I/O。
2. 共享 `AsyncClient`、子域重试、失败分类指标；日志中绝不能打印含 `tk` 的 URL。
3. `/api/maps/tiles` 的错误头/`Retry-After`、可选签名 URL 或限流；`/communities` 的 bbox/min_zoom。
4. 部署时 `APP_MAP_TILE_CACHE_DIR` 指到持久卷并确认磁盘余量；审图号需运营确认后再展示。
5. 403/429/非图片/超时的集成测试与断网/过期 Key 手工演练。

## 6. 2025–2026 年可核实的变化
- **数据下载内容更新**：服务中心“行政区划可视化”标注“数据更新时间 2026 年 10 月”，格式仅 GeoJSON，且“仅供地图可视化使用” [8]。
- **审图号更新**：2026 年官方页面出现 `GS（2026）4921号`（旧页面为 `GS(2019)1719号`）；前端不要把审图号写死 [8]。
- **API v5 加载器出现**：官方数据门户已引用 `https://api.tianditu.gov.cn/api/v5/js?tk=...`；直接访问该地址不带 `tk` 返回 `308010`，说明 v5 存在且仍需 Key。但开发者文档仍以 4.0 为主，**不要在生产盲迁 v5**；继续用 4.0/WMTS 即可 [17]。
- **控制台迁移**：开发者站“控制台”现在跳转 `cloudcenter.tianditu.gov.cn`；老 `console.tianditu.gov.cn` 在部分网络已不可解析，教程里的老地址可能失效 [21]。
- 未发现官方“配额上调/取消”公告；按个人 1 万/日保守设计，实际以控制台为准 [3][19]。

## 7. 风险与待确认
1. **配额口径**：瓦片与地理编码是否共享同一个日配额、个人 Key 的瓦片上限具体多少，只能登录控制台确认；当前按 1 万/日总预算设计。
2. **`sk` 安全密钥是否适用于 WMTS**：官方文档只给了搜索/地理编码的 nginx 代理示例，未明确瓦片；不要假设 `sk` 能替代服务端代理 [9]。
3. **公网/商业展示合规**：是否需要地图审核、审图号如何展示、内部系统边界，需产品/法务确认。
4. **Key 出口绑定**：现有 Key 绑定 SOCKS 出口 IP；新增 API 实例/换机房必须复用同一出口或在控制台更新白名单，否则 403。
5. **v5 稳定性**：无公开迁移文档；等官方文档明确后再评估。

## 8. 来源

1. [天地图地图服务（WMTS 图层/地址/示例）](https://lbs.tianditu.gov.cn/server/MapService.html)
2. [JavaScript API 4.0 入门](https://lbs.tianditu.gov.cn/api/js4.0/guide.html)
3. [Web 服务 API 概述（配额说明）](https://lbs.tianditu.gov.cn/server/guide.html)
4. [应用开发许可升级说明（配额管理/Key）](https://lbs.tianditu.gov.cn/authorization/authorization.html)
5. [天地图服务条款](https://www.tianditu.gov.cn/about/service)
6. [天地图版权声明](https://www.tianditu.gov.cn/about/copyright)
7. [全国地理信息资源目录服务系统（含《数据下载协议》）](https://mulu.tianditu.gov.cn/)
8. [天地图服务中心/数据资源（数据下载、行政区划 GeoJSON）](https://cloudcenter.tianditu.gov.cn/dataSource)
9. [天地图帮助文档（服务中心仅面向单位用户、安全密钥代理）](https://lbs.tianditu.gov.cn/docs/)
10. [天地图·许昌 地图下载（参考图）](https://henan.tianditu.gov.cn/xuchang/downMap.htm)
11. [天地图·濮阳 地图下载中心（普通地图）](https://henan.tianditu.gov.cn/puyang/dtxz)
12. [标准地图服务系统（JPG/EPS 成图）](http://bzdt.ch.mnr.gov.cn/)
13. [天地图数据 API（OGC WFS）](https://lbs.tianditu.gov.cn/data/dataapi.html)
14. [`vec_w` WMTS GetCapabilities（EPSG:900913，1–18 级，256）](https://t0.tianditu.gov.cn/vec_w/wmts?request=GetCapabilities&service=wmts)
15. [`vec_c` WMTS GetCapabilities（EPSG:4490）](https://t0.tianditu.gov.cn/vec_c/wmts?request=GetCapabilities&service=wmts)
16. [JavaScript API 4.0 加载器](https://api.tianditu.gov.cn/api?v=4.0)
17. [API v5 加载器（不带 tk 返回 308010）](https://api.tianditu.gov.cn/api/v5/js)
18. [GCJ-02/WGS-84 转换实现](https://github.com/wandergis/coordtransform)
19. [天地图 Token 配额管理（2026，公开技术文章，二手）](https://blog.csdn.net/weixin_29306875/article/details/158819129)
20. [天地图个人 Key 每日 1 万次瓦片（2023，公开技术文章，二手）](https://blog.csdn.net/qq_40772640/article/details/130920905)
21. [天地图开发者控制台](https://cloudcenter.tianditu.gov.cn/center/development/myApp)

> 二手资料（19/20）仅用于“个人约 1 万/日、按日重置、超限 429”的旁证；配额准确值以控制台“服务配额”页为准。本文未使用任何真实 Key 调用天地图数据接口；WMTS `GetCapabilities` 为匿名元数据请求。
