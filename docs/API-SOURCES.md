# RentRadar · 外部数据源与接口清单

版本：v1.0
日期：2026-10-30
状态：调研完成，待按优先级接入
目标城市：深圳（其他城市需替换 city_id / 城市代码）

> 状态说明：
> - `已验证`：2026-10-30 本机实测通
> - `待验证`：有公开实现/文档，未在本机跑通
> - `不可用`：需要签名/登录/已失效，不建议投入

---

## 1. 房源数据

### 1.1 贝壳 App 接口（首选）

**列表 v2（推荐）**

```
GET https://app.api.ke.com/Rentplat/v2/house/list
    ?city_id=440300
    &condition=rco11          # 可选：rco11 最新 / rco21 价格 / rco31 面积
    &offset=0                 # 上限 2999
    &limit=30                 # 上限 30
    &scene=list
    &from=default_list
    &page_uicode=matrix_homepage
```

- 免登录、免签名；静态头可选（`lianjia-city-id`、`lianjia-version`、`user-agent` 等），裸请求也能返回
- 状态：已验证
- 实测：深圳全城 total 约 46,000，5 号线 6,000+

关键字段（v2 比 v1 多）：

| 字段 | 说明 |
|---|---|
| `house_code` | 房源唯一 ID |
| `house_title` / `resblock_name` / `district_name` / `bizcircle_name` | 标题/小区/区/商圈 |
| `rent_price_listing` / `rent_area` / `layout` / `frame_orientation` | 价格/面积/户型/朝向 |
| `geolatitudelongitude` | **房源坐标**（lat,lng，GCJ-02） |
| `subway_distance` | 距地铁距离（部分为空） |
| `latest_price_change` | `{changePrice, time, type}` 最近一次调价 |
| `app_plat_ctime` | 上架时间（epoch 秒） |
| `availableRentTime` | 可入住时间 |
| `floor_level` / `floor_total` | 楼层（编码）/总层数 |
| `house_tags` | 精装/电梯/押一付一/近地铁等标签 |
| `list_picture` | 封面图 |

**列表 v1（兼容保留）**

```
GET https://app.api.ke.com/Rentplat/v1/house/list?city_id=440300&offset=0&limit=30&scene=list
```

- 字段较少，无坐标/调价/上架时间；状态：已验证

**小区维度**

```
condition=c{resblock_id}
# 例：condition=c247014176796200（赛格ECO中心）
```

- 实测返回该小区在租房源；状态：已验证

**筛选字典（行政区/地铁线/站点 + 坐标）**

```
GET https://m.lianjia.com/chuzu/aj/config/filter?city_id=440300
```

- 返回 `d`（行政区）、`li`（地铁线及站点）、`x`（其他）结构
- 站点示例：5 号线深圳北站 `{id: 100021298, latitude: 22.616667, longitude: 114.037138, pinyin: li110460696s100021298/}`
- 站点 pinyin 可直接用于列表 `condition`；状态：已验证

**分片覆盖工具（P0/W1）**

单条件 `offset` 上限 2999（30 条/页 → 最多约 3000 条），5 号线整线 total 约 6300，整线翻页抓不全；按站点拆成 `li110460696s<站点id>` 后，每个分片都能在 offset 上限内抓完。

```bash
cd backend
.venv/bin/python -m app.cli shards --line 5号线 --stations 20
.venv/bin/python -m app.cli shards --line 5号线 --stations 20 --pages 1 --probe
.venv/bin/python -m app.cli shards --line 5号线 --pages 0 --probe --json
```

- `shards` 读取本接口生成站点条件，并输出逐站 `crawl --line ...` 命令；不写库。
- `--probe` 实际请求 App 列表接口，输出每站 total / 已抓 / 跨站去重（`house_code`）/ 缺页原因；不写库。
- `--pages 0` 按每站 total 自动抓全（仍受 3000 条 offset 上限约束）。
- 只有探测结果为「完整」的分片才建议加 `--full-scan`，避免不完整范围误标 `suspect`。
- 站点条件会重叠：2026-11-04 按每站 1 页抽查，37 站 `total` 合计 8,828，线路 `total` 6,329；因此评估真实覆盖用 `去重后 / 线路 total`（`coverage_vs_line`），`scope_total` 只表示分片规模。
- 站点条件依赖 `feed_query_id` 按分片重置；`beike_api.BeikeAPIFetcher.reset_condition()` 负责切换分片前清空翻页游标。

**图片**

- 列表仅返回 1 张封面 `list_picture`，默认 `...jpg.280x210.jpg`
- 改后缀可取大图：`.1280x960`（实测 200 / 192KB）、`.800x600`
- 去掉尺寸后缀访问原图返回 403，必须保留后缀
- 多图需详情接口（需鉴权），列表场景不需要

**组合过滤**

- 多个条件用 `/` 拼接：`li110460696/rt200600000001`（5 号线整租）、`li110460696/rp2`（价格档）
- `rt200600000001` 为整租，具体档位以 Web/App 前端为准

**已知坑**

- **翻页必须回传上一页的 `data.feed_query_id`**，否则 `offset` 可能被忽略（0/30/60 返回同一批）
- 列表结果存在随机性/不完整：同一条件多次请求结果会变化，翻页会重复；全量抓取需多轮按 `house_code` 去重
- 高频/新开标签页会触发人机验证；建议低频、复用连接、指数退避
- 非公开接口，参数和字段可能变化；不要作为唯一数据源，保留 CDP/HTML 兜底

**详情接口（不可用）**

- v1 `Rentplat/v1/house/detail` 需 appid
- v3 `apps.api.ke.com/Rentplat/v3/house/list` 需 `WLL-KGSA` HMAC-SHA256 + `Authorization` SHA1 双签名（2026-09 有逆向文章，密钥打码）
- 结论：不做详情，列表字段已满足监控与画像

**其他贝壳端点（需 Authorization，暂不接入）**

| 端点 | 用途 |
|---|---|
| `GET app.api.ke.com/house/chengjiao/searchv2` | 成交记录 |
| `GET app.api.ke.com/house/ershoufang/searchv4` | 二手房搜索 |
| `GET app.api.ke.com/house/ershoufang/detailpart1v2` | 二手房详情 |
| `GET app.api.ke.com/config/home/content?city_id=` | 贝壳指数（全市均价/昨日成交） |
| `POST app.api.lianjia.com/config/config/initData` | 城市/区/商圈字典 |
| `GET app.api.ke.com/newhouse/shellapp/feed` | 新房 feed |

- 鉴权方式：`Authorization = base64(app_id + ":" + sha1(app_secret + 按 key 排序的 "k=v" 拼接))`
- GitHub 公开的 app_id/secret 为 2021 年版本，实测裸请求返回空/无效；如后续确有成交需求，优先用住建局公开数据

### 1.2 其他房源平台

参考实现：`liguobao/HouseSearch` 的 `Crawlers/Room/` 目录共 28 个文件，其中 25 个是平台适配器（另 3 个是 BaseCrawler/接口/基类）。完整盘点见 1.3。

#### 已实测可用

| 平台 | 接口 | 说明 | 状态 |
|---|---|---|---|
| **自如** | `GET https://m.ziroom.com/v7/room/list.json?city_code=440300&page=1&...` | 深圳 `city_code=440300`；返回 `data.rooms[]`（id/house_id/name/area/floor/photo 等） | 已接入 `backend/app/sources/ziroom.py`（2026-11-04） |
| 自如详情 | `GET https://m.ziroom.com/wap/detail/room.json?city_code=440300&id={id}` | 需带 referer/accept 版本；实测部分 id 返回「已下架」 | 待验证 |

自如价格字段是 PNG 精灵图 + 数字索引数组；`ziroom.py` 从精灵图字形 dHash 模板解出数字顺序，再按索引还原月租（未知精灵图会跳过该条，不会猜价）。列表有分页，建议低频；`ziroom` source 默认停用，需在 `/admin/ops` 启用。

#### 接口存活、但需要城市 ID / 参数

| 平台 | 接口 | 现状 |
|---|---|---|
| 巴乐兔 | `POST https://api.baletu.com/App401/Homes/guessLikeRecHouseList`，body `P=1&S=50&device_id=...&v=4.6.2&from=3&city_id={id}` | 接口有响应；深圳 `city_id` 未确认（盲试 1-30 为空），需从 App/H5 抓一次 |
| 蘑菇租房 | `POST https://renterfind.mgzf.com/mogoroom-find/v2/find/getRoomListByCriteria`，body `rentTypes=2&currentPage=1&cityId={id}&pageSize=50` | 接口存活；`cityId=440300` 返回空，需内部城市 ID |
| 城家公寓 | `POST https://m.cjia.com/restapi/svr/productsearch/product/searchListUnitEx/0`，JSON body，需 `header` 头 | 端点存在；本次探测 405，需按 App 参数重试 |
| 青客 | `POST https://i.qk365.com/unit/findNewRoom`，body `cityPinyin=shenzhen&queryDto...` | 深圳返回空，可能未覆盖深圳 |
| 小黄鸡 | `POST http://m.xhj.com/wap/search/findByCondition`，JSON body `{houseType:12,cityId,cityName,...}` | JSON 接口；深圳 cityId 未验证 |

#### 网页/需登录态

| 平台 | 方式 | 说明 |
|---|---|---|
| **豆瓣租房** | `https://www.douban.com/group/szsh/discussion`（深圳小组） | 需 cookie；`Yazzyk/douban-rent-room` 9★（2025-02，深圳实测）可参考；个人房东直租比例高 |
| 安居客 | `api.anjuke.com/mobile/v6/...` + `nsign` MD5（2021 逆向） | 风控较严，待验证 |
| 58 同城 | `m.58.com` HTML | 参考 `house-cli` 适配器 |
| V2EX 租房 | `https://www.v2ex.com/go/{board}` HTML | 信息量小，可低频 |
| 我爱我家/相寓 | `m.5i5j.com` HTML / App `appapi.5i5j.com` | 端点未完整确认 |

#### 已失效 / 不建议

| 平台 | 原因 |
|---|---|
| 房天下 | `soufunappesf.3g.fang.com` 返回 `invalid vua`（签名失效） |
| 房多多 | `m.fangdd.com/api/data/zufangFetchRentList` 返回 502 |
| 58 品牌公寓 | `appgongyu.58.com/gongyu` 302 到 404 |
| 建行租房 | `api.jiayuan.ccbhome.cn` 返回 403（APIKey 失效） |
| Zuber | `apiservices.zuber.im` 返回 401（需 token） |
| 闲鱼 | `h5api.m.taobao.com` mtop 需 `sign`，维护成本高 |
| 链家 | `robots.txt` 禁止抓取，不自动抓，仅保留手动链接 |

### 1.3 HouseSearch 25 个房源适配器盘点（2026-10-30）

`Crawlers/Room/` 共 28 个文件，25 个是平台源码。仓库主体约 2019 年，多数端点已失效；价值在于端点/字段/解析逻辑索引，不是开箱即用。

| # | 平台 | 端点/方式 | 深圳状态 |
|---|---|---|---|
| 1 | 贝壳 | `app.api.ke.com/Rentplat/v2/house/list` | 可用（首选） |
| 2 | 自如 | `m.ziroom.com/v7/room/list.json?city_code=440300` | 可用（价格图片需 OCR） |
| 3 | 巴乐兔 | `POST api.baletu.com/App401/Homes/guessLikeRecHouseList` | 接口活，缺深圳 `city_id` |
| 4 | 蘑菇租房 | `POST renterfind.mgzf.com/.../getRoomListByCriteria` | 接口活，缺内部 `cityId` |
| 5 | 城家公寓 | `POST m.cjia.com/restapi/.../searchListUnitEx/0` | 端点存在，需 App 头/参数 |
| 6 | 青客 | `POST i.qk365.com/unit/findNewRoom` | 深圳返回空，可能未覆盖 |
| 7 | 嗨住/楼立方 | `GET s.loulifang.com.cn/houselist.html` | 无响应 |
| 8 | 房多多 | `POST m.fangdd.com/api/data/zufangFetchRentList` | 502 |
| 9 | 小黄鸡 | `POST m.xhj.com/wap/search/findByCondition` | JSON 接口，深圳 cityId 未验证 |
| 10 | 豆瓣（API） | `frodo.douban.com` | 需豆瓣 apikey |
| 11 | 豆瓣（微信） | 自建 Node 代理 `/topics?city=` | 依赖私有代理 |
| 12 | V2EX | `https://www.v2ex.com/go/{board}` | HTML 可用，量小 |
| 13 | 闲鱼 | `h5api.m.taobao.com` mtop | 需 sign，不建议 |
| 14 | 安居客 | `m.anjuke.com/{city}/rentlistbypage/...` | HTML，实测跳验证码 |
| 15 | 房天下 | `soufunappesf.3g.fang.com/http/sfservice.jsp` | `invalid vua` 失效 |
| 16 | 58 品牌公寓 | `appgongyu.58.com/gongyu` | 302 → 404 |
| 17 | 建行租房 | `api.jiayuan.ccbhome.cn/hlsp/...` | 403，APIKey 失效 |
| 18 | 百姓网 | `mpapi.baixing.com/v1.2.10` `listing.getAds` | 需关注公众号，直连返回提示页 |
| 19 | 互助租房 | `huzhumaifang.com:8080/hzmf-integration/getHouseList.action` | 上海平台，未测 |
| 20 | 合租找室友 | LeanCloud `listHouse` | 空响应/已失效 |
| 21 | 暖租 | `nuan.io/get-room-results` | 接口活，但各城市返回 0 |
| 22 | 品质优租 | `psy.hetaoapis.com/graphql` | 空响应/已失效 |
| 23 | Zuber | `apiservices.zuber.im/client/search/bed` | 401，需 token |
| 24 | 杭州住房租赁 | `zl.hzfc.gov.cn/webrent/gphouselist.htm` | 官方平台，仅杭州 |
| 25 | AnXuan | 本地 `192.168.1.2/58-anxuan` | 不可用 |

结论：能直接用于深圳的只有 **贝壳、自如** 两个 API，加上 **豆瓣深圳小组/V2EX** 两个网页源；巴乐兔/蘑菇/城家/小黄鸡需要补城市 ID 或 App 参数后才可评估。

### 1.4 品牌公寓 / 保障性租赁住房（直营渠道）

这类不是流量平台，是**房源供给方/运营商**，用户在自己的小程序/App 预约看房。深圳主要有：

| 品牌 | 归属 | 特点 | 数据入口 |
|---|---|---|---|
| **安居乐寓** | 深圳市安居集团（国企） | 市场化租赁住房 + 保租房；有「深梦扬帆」毕业生 15 天免费住 | 微信小程序「安居乐寓」预约；官网 `szrcaj.com` 只有新闻/项目 |
| **寓见安居** | 深圳市安居集团 | 与安居乐寓并行的安居集团品牌 | 小程序/官网 |
| **泊寓** | 万科 | 集中式公寓，深圳门店多 | 泊寓 App/小程序 |
| **冠寓** | 龙湖 | 集中式公寓 | 冠寓 App/小程序 |
| **微棠** | 深圳城中村改造运营方 | 城中村整栋改造，宝安/龙华等 | 微棠 App/小程序 |
| 自如寓/自如 | 自如 | 分散式合租/整租 + 集中式公寓 | 已有列表 API（1.2） |
| 城家 / 魔方 / 乐乎 | 各运营商 | 集中式公寓 | 各家 App/小程序 |

**数据获取现实**

- 公开网页基本没有房源列表，核心入口是微信小程序，需要抓包（登录态 + 签名，成本高于贝壳）
- 政府侧可拿到项目清单/保障房信息，可做「项目级」而不是「房源级」：
  - 人才住房和保障性住房项目信息 `01900899`
  - 政府保障房-小区基本信息 `01900914`
  - 政府保障房-房屋基本信息 `01900911`
  - 公租房申请/获批 `01900906`
  - 公租房轮候 `01903488`、轮候册认租 `01903494`
  - 商品房批准预售 `01903508`（含配建保租房线索）
- 部分品牌房源会同步到贝壳/58，可用贝壳 `resblock_name` 反查
- 口碑：小红书/大众点评搜「安居乐寓 XX 店」「泊寓 XX 店」

**对 RentRadar 的定位**

- 不并入「主流平台」计数；单独作为 `brand_apartment` 数据源
- 优先级低于贝壳/自如，高于纯网页抓取
- 先做项目级覆盖（官方项目清单 + 坐标），房源级等小程序抓包方案确定后再做
- 目标人群：预算敏感、毕业生、人才房、无中介费偏好

---

## 2. 通勤 / 交通

### 2.1 深圳地铁官方路径规划（首选，零额度）

```
POST https://www.szmc.net/algorithm/Ticketing/MinTimeJson.do
Content-Type: application/x-www-form-urlencoded

departureStation=0521&arriveStation=0403&ridingType=0
```

- 状态：已验证
- 返回：`useTime`（秒）、`ticketPrice`（元）、`times`（换乘次数）、`lineList`（每段线路/首末班车/站间耗时）
- 实测：
  - 深圳北(0521) → 会展中心(0403)：943s / ¥4 / 直达
  - 深圳北(0521) → 国贸(0102)：1814s / ¥5 / 换乘 2 次
- 站点 code 每线不同：深圳北 4号线 `0410`、5号线 `0521`、6号线 `0608`
- 站点字典：`GET https://www.szmc.net/styles/index/sz-subway/mcdata/shentie.json`（17 线 433 站）
- 注意：官网内部接口，无公开文档；控制频率，失败重试
- 2026-10-31 落地：已接 `szmc` provider（站点字典 `shentie.json` + `MinTimeJson`），负责地铁+步行通勤；高德/滴滴已停用

### 2.2 OpenMetro（多城市地铁结构化数据）

- 仓库：`Naptie/openmetro`（2026-10 活跃）
- 数据：`data/cn-shenzhen/*.json`
- 深圳：351 个物理站，**GCJ-02 坐标**、官方 code、设施、线路、区间耗时、换乘时间、首末班车、票价矩阵
- 生成时间：2026-09-28
- 用途：本地缓存/离线计算，避免每次请求官网

### 2.3 高德地铁图 JSON（免 Key）

```
GET https://map.amap.com/service/subway?_1469083453978&srhdata=4403_drw_shenzhen.json
```

- 状态：已验证
- 17 条线、443 站；站点字段 `sl` 为 `lng,lat`，`sid` 为站点 ID
- 深圳北站：`114.030865,22.610815`
- 用途：线网拓扑/站点映射；与高德同坐标系（GCJ-02）

### 2.4 滴滴 MCP（官方，打车 + 地图）

```
生产：https://mcp.didichuxing.com/mcp-servers?key=YOUR_MCP_KEY
调试：https://mcp.didichuxing.com/mcp-servers-sandbox?key=YOUR_MCP_KEY
协议：Streamable HTTP / JSON-RPC
```

- 状态：官方文档已核对，未用 Key 实测
- Key：`https://mcp.didichuxing.com/` 个人账号激活
- 工具：
  - 打车：`taxi_estimate`（车型/价格预估）、`taxi_generate_ride_app_link`、`taxi_create_order`、`taxi_query_order`、`taxi_cancel_order`、`taxi_get_driver_location`
  - 地图：`maps_textsearch`、`maps_regeocode`、`maps_place_around`、`maps_direction_driving/transit/walking/bicycling`
- 用途：Top 候选房源的打车通勤成本/时间；地图工具可作为独立于高德的额度
- 注意：
  - 经纬度参数必须传字符串，格式 `lng,lat`
  - 估算不产生订单；下单才产生真实费用，禁止自动下单
  - 沙箱返回固定 Mock 数据，真实预估需生产 Key

### 2.5 车来了（公交实时）

- 仓库：`afterglowsdev/chelaile-api-collect` 22★（2026-03 更新）
- 旧接口 `citylist` 实测可用（深圳）；新版 H5 接口需 AES 解密，仓库含脚本
- 用途：公交通勤真实等待时间/车辆位置
- 注意：非官方、参数易变，仅低频使用

### 2.6 12306 MCP

- 仓库：`Joooook/12306-mcp` 2.4k★
- 用途：跨城通勤（如惠州/东莞）时查余票/中转；日常租房场景弱相关

---

## 3. 地图 / POI / 地理编码

| 来源 | 额度（参考） | 能力 | 状态 |
|---|---|---|---|
| 百度地图 MCP `baidu-maps/mcp` 447★ | 约 5,000 次/天 | geocode/POI/批量算路/路况 | 官方，已核对工具 |
| 高德（现有 Key） | 项目 Key 约 5,000 次/月 | 通勤/POI 主力 | 现役，省着用 |
| 天地图 | 个人约 10,000 次/天 | geocode/POI/WMTS 瓦片；CGCS2000/WGS-84（与 GCJ-02 有偏移） | 需注册 tk，官方文档已核对 |
| 高德 MCP | 与高德 Key 共享额度 | 12+ 工具 | 官方；需支付宝实名（X 用户反馈） |
| OSM Overpass | 免费 | POI 分流 | 公共实例常满负载，建议自建/换镜像 |

**天地图接入（2026-10-31 已接）**

- 正向地理编码：`GET /geocoder?ds={"keyWord":"..."}`（已验证）
- POI 周边：`GET /v2/search` + `postStr.queryType=3` + `pointLonlat`（已验证）
- 公交路径：`/transit` 经 10943 出口实测超时，暂不接；通勤改深圳地铁官方

1. 手机号注册账号 → 申请成为开发者（个人即可）
2. 控制台 → 应用管理 → 创建应用 → 获取 Key（tk）
3. 请求加 `tk=`；无 tk 实测返回 `308011/308010` 参数错误
4. 现成 MCP：`bailaohe/mcp_tianditu`（地理编码/逆地理/周边/行政区/驾车/公交 6 工具）

**额度策略**

```
百度（约 5000/天） → 高德（剩余额度） → 天地图（约 1 万/天）
```

- 慢数据（学校/公园/医院）优先用深圳开放数据，不消耗地图额度
- 实时/批量通勤用深圳地铁官方接口（零额度）
- 打车用滴滴 MCP（独立额度）

---

## 4. 口碑 / 生活配套

| 来源 | 能力 | 状态 |
|---|---|---|
| 小红书 MCP（本机已装） | 小区避雷/租房攻略/女性独居/养宠 | 可用，注意频控 |
| 大众点评 MCP `qianwj/dp-mcp` 6★ | 店铺评分/精选评论，复用浏览器登录 | 可用，需登录 |
| 黑猫投诉 / 知乎 | 物业投诉、真实评价 | 无公开 API，走搜索/浏览器 |
| 高德/百度 POI | 超市/餐饮/医院/公园/健身 | 现有 |

参考实现：`kunhai1994/house-hunter` 把上述来源串成小区调研流水线，含 12 条避雷信号和评分模型，可借鉴其规则。

---

## 5. 深圳开放数据平台

- 地址：`https://opendata.sz.gov.cn`
- 注册：个人可注册（广东省统一认证平台实名，手机号一致）；另有机构注册
- 开放级别：
  - 无条件开放：匿名可看元数据/文件列表
  - 实名认证开放：登录后可见
  - 有条件开放：需申请审批
- 下载文件实测需登录（匿名能看文件列表，不能下）
- API：控制台创建应用获取 appKey
- **实时性**：不是实时数据。按日/月/季/年/不定期更新；「按日」通常为 T-1 批量

### 5.1 房源/租赁/物业

| 数据集 | resId | 更新 | 关键字段/用途 |
|---|---|---|---|
| 小区租赁参考价格 | `01903546` | 有更新（2026-08-27） | 4,319 小区；多层/高层/低密度租金；GEOM 为 CGCS2000 multipolygon |
| 城中村租赁参考价格 | `01903545` | 有更新 | 2,042 条 |
| 产业园区租赁参考价格 | `01903547` | 有更新 | 园区租金 |
| 二手住房成交参考价 | `01903516` | 有更新 | 463 条；小区成交参考价 |
| 二手房成交（按日） | `01903513` | 按日 | 日期/成交套数/面积/用途/所属区 |
| 一手商品房成交（按日） | `01903510` | 按日 | 成交 + 可售套数/面积 |
| 商品房批准预售信息 | `01903508` | 有更新 | 区域新增供应 |
| 可办理公积金贷款的预售房源 | `01903502` | 按年 | 新房源线索 |
| 租赁平台机构注册数据 | `01903497` | 有更新 | 562 家；机构名称/统一社会信用代码 → 中介验真 |
| 物业管理区域基础信息 | `01903550` | 按年 | 1,931 万条；物业区域/地址/总建筑面积/宗地号/状态 |
| 物业企业查询 | `01900886` | 按年 | 物业公司 |
| 物业从业人员查询 | `01900884` | 按年 | 人员 |
| 物业服务企业评价 | `01903536` | 有更新 | 企业评价 |
| 小区物业项目查询 | `01900885` | 按年 | 小区 ↔ 物业 |
| 政府保障房-小区/楼栋/房屋 | `01900914/01900910/01900911` | 有更新 | 区分保障房/商品房 |
| 消防备案 | `01903517` | 有更新 | 项目/地点/办结结果 |

### 5.2 交通/通勤

| 数据集 | resId | 用途 |
|---|---|---|
| 地铁站点信息（交通局） | `00403624` | 线路/站点/介绍 |
| 地铁站点出入口及换乘 | `00403625` | 换乘 |
| 地铁线路信息 | `00403636` | 线路 |
| 深圳地铁站点/线路（地铁集团） | `63800003/63800001` | 官方站点 |
| 深圳地铁公共交通服务指标 | `63800010` | 年度指标（按年） |
| 公交线路上行/下行 | `00403645/00403646` | 票价/始发/终点（上行已存档） |
| 公交线路表/轨迹 | `00403597/00403600` | 已存档 |
| 各街道人口密度 | `03302390` | 区域画像 |

### 5.3 环境/安全/风险

| 数据集 | resId | 用途 |
|---|---|---|
| 积涝点水位 | `01403147` | 内涝风险 |
| 水库站点降雨量实时信息 | `01403150` | 降雨 |
| 水库水位表 | `01400986` | 水位 |
| 城市供水水质公报 | `01400402` | 按月，水质 |
| 空气质量数据 | `01003608` | 有更新 |
| 空气质量日报 | `01000198` | 按周 |
| 城市更新单元计划/规划 | `00303518` / `00303355` | 旧改/拆迁/施工风险 |
| 建筑物数据 | `00300237` | 52.5 万条；编码/名称/地址 |
| 南山区房屋楼栋基础数据 | `04003598` | 楼栋 |
| 福田区建筑物信息 | `02703707` | 楼栋 |
| 建设工程规划许可/验收 | `00300326/00303539` | 周边新工地 |
| 电梯信息 | `01303594` | 老楼电梯/安全 |
| 施工噪声许可（盐田/龙华） | `03700813/04703733` | 噪音风险 |
| 噪声在线监测（大鹏） | `03001156` | 存档 |
| 噪音日统计（宝安） | `02803198` | 存档 |
| 派出所地址及电话 | `00200322` | 安全 |
| 新能源汽车充电桩（分区） | `02703894` 等 | 便利 |
| 居民生活用水价格 | `04300772` | 生活成本 |

### 5.4 学校/医疗/公园/文体

| 数据集 | resId | 用途 |
|---|---|---|
| 三级医院 / 二级医院 | `01500315/01500318` | 医疗 |
| 深圳市公园名录 | `00103028` | 1,320 条 |
| 公共体育场馆/健身设施 | `01600803` | 文体 |
| 图书馆一览表 | `01600362` | 文体 |
| 各区学校名单/幼儿园 | 福田 `02703742/02700573`、南山 `04003918/04003595`、罗湖 `02903706/02903707`、龙岗 `03803736`、坪山 `03200693/03200692`、大鹏 `03000614/03000613`、光明 `03103650/03103734` | 教育配套（区级覆盖不统一） |

### 5.5 已知坑

- 「小区租赁参考价格」的 `GEOM` 是 **CGCS2000 / EPSG:4547 multipolygon EWKT**，不是经纬度；需 PostGIS 解出再转 GCJ-02
- 取巧：用小区名称/地址与贝壳 `resblock_name` 做 join，不依赖坐标
- 元数据接口（免登录）：`POST /data/catalog/selectDataCatalogByResId`，`resId` 形如 `29200/01903546`
- 文件列表（免登录）：`POST /data/dataSet/getFileList`
- 下载（需登录）：`POST /data/dataSet/downloadFile`

---

## 6. 参考项目

| 项目 | 星 | 用途 |
|---|---|---|
| `liguobao/HouseSearch` | 1.4k | 贝壳 App 接口用法、多源租房 |
| `kunhai1994/house-hunter` | - | 小区调研流水线：贝壳+小红书+知乎+黑猫+三层地图+12 条避雷信号 |
| `Naptie/openmetro` | 6 | 多城市地铁结构化数据 |
| `afterglowsdev/chelaile-api-collect` | 22 | 车来了公交实时接口 |
| `Luxuzhou/house-cli` | 28 | 多平台房源 CLI 架构 |
| `dengqiangxi/ziroom_crawler` | 35 | 自如备用源 |
| `Yazzyk/douban-rent-room` | 9 | 豆瓣租房爬虫（深圳实测，需 cookie） |
| `Carlos-Zen/scrapy-houses` | 4 | 58/贝壳/巴乐兔/蛋壳/链家多平台 spider |
| `Alfred1984/interesting-python` | 5k | 同贝壳接口的早期实现（分片经验） |
| `waugustus/lianjia-spider` | 68 | 二手房 + Electron UI（参考） |

---

## 7. 不建议 / 不可用

| 项 | 原因 |
|---|---|
| 贝壳详情 v3 | HMAC+SHA1 双签名，成本高；列表字段已够 |
| 贝壳成交/二手房搜索 | 需要 app Authorization，公开 secret 已过期 |
| 贝壳 `m.ke.com` 详情页 | 302 到登录/验证 |
| 高德 MCP 刷 POI | 与现有 Key 共享额度，无收益 |
| 链家自动抓取 | robots 禁止 |
| 付费数据 API | 项目约束：优先免费/已有额度 |

---

## 8. 落地优先级

### P0：替换现有瓶颈

1. **贝壳 v2 `rco11` + `c{resblock_id}`** 替换 CDP 列表抓取
   - 收益：免验证码、拿坐标/调价/上架时间
   - 注意：多轮去重、低频；翻页带 `feed_query_id`
   - 状态：已接入 `backend/app/sources/beike_api.py`（任务 1 `transport=api`，2026-10-30）
2. **深圳地铁 `MinTimeJson` + OpenMetro** 替换/校验高德通勤
   - 收益：官方时间/票价/末班车，零额度
3. **住建局小区租赁参考价** 接入评分
   - 收益：性价比从「同小区挂牌中位数」升级为「官方参考价 + 溢价率」

### P1：画像增强

4. 滴滴 MCP：只对 Top 候选算打车成本/时间
5. 百度 MCP + 天地图：分流 POI，保护高德额度
6. 小红书/点评：补口碑；开放数据：物业/电梯/水质/空气/内涝/旧改

### P2：可选

7. 车来了：公交换乘实时
8. 安居客/自如：备用房源
9. 12306：跨城通勤（按需）

---

## 9. 凭据与环境变量约定

- 所有 Key 放项目 `.env`（600，gitignored），禁止提交
- 建议变量名：
  - `BAIDU_MAPS_API_KEY`
  - `AMAP_MAPS_API_KEY`（现有 `AMAP_WEB_KEY`）
  - `TIANDITU_API_KEY`
  - `DIDI_MCP_KEY`
  - `SZ_OPENDATA_APP_KEY`
- 天地图/开放数据均需个人实名注册；滴滴 MCP 用个人账号激活


---

## 10. P1 新增接口（2026-11-04）

### Agent 工具运行时（W4）

- `POST /api/agent/messages/stream`：SSE 事件不变；新增真实工具步骤（`search_listings` / `get_listing` / `compare_listings` / `commute_lookup` / `price_history`），`budget` 事件带 `ai` 额度信息。
- `GET /api/admin/agent/sessions`：新增 `guardrails` 与 `toolCalls`（每次工具调用的参数/耗时/摘要/错误）。
- `GET /api/admin/agent/eval`：最近一次与历史规则基线评测。
- `POST /api/admin/agent/eval/run`：运行 60 条黄金集（48 查询 + 12 护栏），不调用外部模型。
- `GET /api/admin/agent/cost?days=7`：会话 token/成本/兜底/工具/护栏/ModelScope 额度聚合。
- 护栏：`aiDailyCap` 调用前硬停；手机号/邮箱/身份证脱敏后才可送模型；注入/越权/危险指令命中时不送模型，只走规则。

### 封面图片（W5）

- `GET /api/admin/images`：队列 + 统计 + 重复封面组。
- `POST /api/admin/images/analyze`：入队 `image_analysis`，只分析候选（有封面 URL、按评分排序）。
- `GET /api/admin/images/{listing_id}/file`：读取本地缓存封面。
- 数据：贝壳列表 API 的 `image_url` 单张封面；详情多图需鉴权，未接入。
- 算法：64-bit dHash（汉明距离 ≤10 重复）；价格中位异常（同小区/同区同户型 ≥5 样本）；中介话术关键词；≥2 个非质量信号才标可疑。视觉标签需 Qwen-VL/本地 VL 授权，默认关闭（`APP_IMAGE_VISION_ENABLED=false`）。

### 口碑证据（W6）

- `GET /api/admin/reputation`：有/无证据小区、高风险、最近证据。
- `GET /api/admin/reputation/communities?q=`、`GET /api/admin/reputation/communities/{id}`。
- `POST /api/admin/reputation/mentions`、`PATCH .../mentions/{id}`、`DELETE .../mentions/{id}`：人工录入/确认/排除证据，链接去重。
- `POST /api/admin/reputation/extract`：把粘贴原文交给已配置的 ModelScope 文本模型抽草稿；结果默认 `uncertain`，人工确认后才计分。
- 聚合：180 天半衰期，`verified` 参与评分，`uncertain` 只展示，`rejected` 排除；无证据时中性分并显示“数据不足”。

### 地图（W7）

- `GET /api/maps/communities`：真实小区坐标（GCJ-02→WGS-84）、房源数、中位租金、评分、通勤 p50/p90、代表房源。
- `GET /api/maps/tiles/{layer}/{z}/{x}/{y}`：天地图 WMTS 代理 + 磁盘缓存（默认 30 天）；Key 仅在服务端，沿用 10943 出口。
- `GET /api/maps/tiles/stats/cache`：缓存统计（admin）。
- 天地图 WMTS：`https://t{0-7}.tianditu.gov.cn/{layer}_w/wmts?...&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=...`；`_w` 矩阵集，1–18 级，256px；详见 `docs/TIANDITU-MAP.md`。

---

## 10. P2/P3 新增数据源与接口（2026-11-04）

### 10.1 OpenCode Go（AI，已接入）

```
POST https://opencode.ai/zen/go/v1/chat/completions
Authorization: Bearer <OPENCODE_GO_API_KEY>
User-Agent: RentRadar/<version> (self-hosted; +https://github.com/standbyme626/rentradar-agent)
x-opencode-session: rentradar-<stable-hash>
```

- 模型：`deepseek-v4.1-flash`（`GET /zen/go/v1/models` 可列目录）。
- 原生 `tools` / `tool_calls` 已实测可用；`reasoning_content` 可能非空。
- 缺真实 UA 或 session header 会被 Cloudflare 拒绝（HTTP 403，`error code: 1010`）。
- 服务端已封装 `backend/app/integrations/ai/opencode_go.py`，业务不直接调 HTTP。

### 10.2 手动房源源（已接入）

- `manual` source：JSON 数组/`{items: []}` 或 CSV；字段 `id/url/community_name/layout/area/rent/tags/city`。
- 默认停用；在 `/admin/ops` 启用后由任务 `filters.feed_path` 或 `python -m app.cli import-listings` 导入。
- 跨源去重：同城市 + 规范化小区 + 同户型 + 租金 ±3% + 面积 ±5%；命中只记 alias，不新增房源行。
- `ziroom` 仅预留 source 行，未接入抓取。

### 10.3 参考租金（人工导入）

- 表 `reference_rents`：城市/小区/户型/月份/月租/来源/URL/置信度。
- 当前无住建局 API Key；用 `/admin/ops` 或 `python -m app.cli import-reference-rents --file ...` 导入。
- 评分价格项在有参考价且置信度 ≥0.5 时优先使用参考价，否则回落到同小区/同区挂牌中位价。
