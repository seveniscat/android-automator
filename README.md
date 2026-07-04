# Automator · Android 真机自动化平台

> 基于 **uiautomator2** 的可扩展 Android 自动化平台,采用分层架构,
> 本期落地"App 测试 / 爬虫"的确定性流程编排,并预留 OCR / VLM / LLM / 多设备的扩展位。

---

## ✨ 特性

- **真机优先**:基于 openatx/uiautomator2,USB/WiFi 直连,调用速度快
- **YAML DSL 流程编排**:写 YAML 即可编排多步任务,支持变量插值、断言、抽取(爬虫)
- **Web 控制台**:设备实时画面 / 流程编辑 / 任务派发 / 运行回放(每步截图)
- **Web 实时投屏**:WebSocket 把手机屏幕镜像到浏览器,多客户端共享抓帧,可边跑任务边看画面
- **Playground**:在浏览器里点击画面即可操控手机、或用动作面板即时执行点击/滑动/输入/按键等单步动作,快速探索设备能力(不落库)
- **分层可扩展**:`Device` / `Perception` / `Planner` 均为抽象接口
  - 未来接 **LLM Planner** 即可升级为"AI 自主任务"模式
  - 未来接 **OCR/VLM** 即可让流程"看屏幕做事"
  - 未来接 **atxserver2** 即可平滑扩展为设备农场
- **人类化动作**:点击抖动 + 随机时延,降低反爬/反辅助检测
- **运行可观测**:每步截图、耗时、错误均落库,便于回放排错

---

## 🏗 架构

```
┌───────────────────────────────────────────────┐
│  Web 控制台 (Alpine.js 单页,FastAPI 内嵌)     │
├───────────────────────────────────────────────┤
│  API 层      (FastAPI routes)                  │
├───────────────────────────────────────────────┤
│  任务/调度层 (Executor + Scheduler)            │
├───────────────────────────────────────────────┤
│  流程编排层  (Flow / Step / YAML DSL)          │
├──────────┬──────────────┬─────────────────────┤
│  感知层  │   决策层     │    动作层           │
│ 截图     │  规则引擎    │  uiautomator2       │
│ OCR*     │  LLM Planner*│  + adb + 输入       │
│ VLM*     │              │                     │
├──────────┴──────────────┴─────────────────────┤
│  设备抽象层 (Device / DeviceManager)           │
├───────────────────────────────────────────────┤
│  真机 / 模拟器 / 远程 atxserver2*              │
└───────────────────────────────────────────────┘
   (* = 预留接口)
```

---

## 🚀 快速开始

### 1. 环境准备

- Python ≥ 3.10
- adb(`brew install android-platform-tools` 或下载 platform-tools)
- 一台开启 **USB 调试** 的 Android 手机(在开发者选项中开启)

### 2. 安装

```bash
cd automator
pip install -e ".[dev]"           # 或用 uv:uv pip install -e ".[dev]"
```

### 3. 初始化设备(安装 atx-agent + UiA2 APK)

```bash
python scripts/init_device.py             # 自动选第一台
python scripts/init_device.py <serial>    # 指定设备
```

### 4. 环境自检

```bash
python scripts/doctor.py
```

### 5. 配置(可选)

```bash
cp .env.example .env
# 修改 AUTOMATOR_DEVICE_SERIAL / 端口等
```

### 6. 启动平台

```bash
uvicorn automator.main:app --reload        # 开发
# 或:
automator                                   # 安装后
```

打开浏览器访问 http://localhost:8000

---

## 📖 YAML DSL 语法

```yaml
name: 微信发消息
description: 启动微信并给指定联系人发消息
variables:
  contact: 文件传输助手
  message: hello from automator

steps:
  - start_app: { package: "com.tencent.mm" }
  - wait: { seconds: 3 }
  - click: { text_contains: "搜索", timeout: 5 }
  - input: { text: "${contact}" }
  - wait: { seconds: 1 }
  - click: { text: "${contact}" }
  - input: { text: "${message}" }
  - press: { key: enter }
  - assert: { exists: { text_contains: "${message}" } }
```

### 内置步骤

| 类型 | 用法示例 | 说明 |
|---|---|---|
| `start_app` | `{ package: "com.x" }` 或 `{ package: "com.x", activity: ".Main" }` | 启动应用 |
| `stop_app`  | `{ package: "com.x" }` | 停止应用 |
| `click`     | `{ x: 100, y: 200 }` 或 `{ text: "登录" }` 或 `{ resource_id: "..." }` 或 `{ xpath: "..." }` | 点击 |
| `swipe`     | `{ direction: up }` 或 `{ x1,y1,x2,y2 }` | 滑动 |
| `input`     | `{ text: "abc" }` 或 `{ into: {...}, text: "abc", clear: true }` | 输入文本 |
| `wait`      | `{ seconds: 2 }` 或 `{ text: "OK", timeout: 5 }` | 等待 |
| `press`     | `{ key: back }`  (back/home/menu/enter/...) | 按键 |
| `assert`    | `{ exists: {...} }` 或 `{ not_exists: {...} }` | 断言 |
| `extract`   | 单值:`{ as: k, from: {...} }`;列表:`{ as: k, list: "//xpath", fields: {...} }` | 数据抽取(爬虫) |

### 步骤控制(以 `_` 开头的元字段)

- `_name`: 步骤显示名
- `_on_failure`: `abort`(默认)/ `continue`
- `_retries`: 失败重试次数

### 变量插值

- `${var}` — 流程变量 / 运行期变量
- `${env.HOME}` — 环境变量
- `${extracted.x}` — `extract` 步骤抽取的数据

完整 `${var}` 占位整串时保留原类型(数字/列表),否则转字符串。

---

## 🔌 主要 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET  | `/api/system/health` | 健康检查 |
| GET  | `/api/system/env` | 环境信息 + 可用步骤 |
| GET  | `/api/devices` | 设备列表 + 当前连接 |
| GET  | `/api/devices/screenshot` | 实时截图(PNG) |
| WS   | `/api/devices/stream` | 实时投屏(WebSocket, JPEG 帧) |
| GET  | `/api/devices/hierarchy` | UI 层级 XML |
| GET  | `/api/playground/actions` | 列出可即时执行的动作 |
| POST | `/api/playground/action` | 即时执行单动作(不落库) |
| GET/POST/PUT/DELETE | `/api/flows` | 流程 CRUD |
| POST | `/api/flows/validate` | 校验 YAML |
| GET  | `/api/flows/steps/list` | 列出步骤类型 |
| GET/POST | `/api/tasks` | 任务 CRUD |
| POST | `/api/tasks/{id}/run` | 立即执行任务 |
| GET  | `/api/runs` | 运行记录 |
| GET  | `/api/runs/{id}` | 运行详情(含每步结果) |
| GET  | `/api/runs/{id}/screenshot/{step}` | 单步截图 |

完整交互文档:启动后访问 http://localhost:8000/docs

### 📺 Web 实时投屏

打开 Web 控制台「设备」页 → 点「开始投屏」,手机屏幕即镜像到浏览器。

- **协议**:WebSocket `/api/devices/stream`。服务端先发一帧 JSON `{type:"hello",fps}`,
  之后持续推 binary(JPEG);设备异常时发 `{type:"error",detail}`。
- **共享抓帧**:后台单例 `StreamHub` 起一个抓帧线程,所有浏览器标签共享同一份抓帧,
  不会因多开页面而重复抓帧压垮设备。首个客户端连接时启动,全部断开后自动停止。
- **帧率/带宽**:受 u2 截图耗时限制,实测约 2–5fps;可通过 `.env` 调节:
  ```ini
  AUTOMATOR_STREAM_FPS=4           # 抓帧帧率
  AUTOMATOR_STREAM_QUALITY=60      # JPEG 质量 1-100
  AUTOMATOR_STREAM_MAX_WIDTH=720   # 最大宽度(0=不缩放)
  ```
- **与任务并发**:任务运行期间投屏不中断;由于 u2 调用偶有竞争,画面可能偶发卡顿,属正常。

### 🎮 Playground(设备能力探索)

打开 Web 控制台「Playground」页,可即时体验 automator 的设备操控能力,**操作不落库**,纯探索/调试用。

- **点击画面即操控**:开启投屏后,直接点击画面任意位置,会按设备真实分辨率换算坐标并触发设备点击(画面上以十字光标标记点击点)。
- **动作面板**:选择动作类型 → 填参数 → 执行,即时返回成功/耗时并刷新画面。支持:
  - `click`(坐标点击)/ `click_by`(按 resource_id/text/content_desc 等定位点击)
  - `swipe_direction`(方向滑动)/ `swipe`(坐标滑动)
  - `input_text`(输入文本)/ `press`(系统按键)
  - `start_app` / `stop_app`(启停应用)
- **快捷区**:返回/主页/最近/回车按键、四方向滑动,一键触发。
- **操作日志**:每次动作记录动作名/目标/成败/耗时,最近 50 条。
- 默认关闭人类化延迟(humanize=False),操作反馈即时;正式跑流程才在 YAML 里开启人类化。

---

## 🧱 代码结构

```
automator/
├── automator/                 # 后端核心包
│   ├── device/                # 设备抽象层(U2Device + 单机管理器)
│   ├── perception/            # 感知层(截图;OCR/VLM 预留)
│   ├── action/                # 动作层(人类化封装)
│   ├── cognition/             # 决策层(规则引擎;LLM 预留)
│   ├── flow/                  # 流程编排(YAML DSL + Runner + Steps)
│   ├── task/                  # 任务/调度层
│   ├── storage/               # SQLAlchemy 数据层
│   ├── api/                   # FastAPI 路由
│   └── main.py                # 入口
├── web/                       # 单页 Web UI(Alpine.js + Tailwind)
├── flows/examples/            # 示例流程
├── scripts/                   # 设备初始化与自检
├── tests/                     # 单元测试
└── data/                      # 运行时产物(库 + 截图 + 日志)
```

---

## 🧪 测试

```bash
pytest                      # 全部
pytest tests/test_yaml_loader.py
```

测试不依赖真机,覆盖 YAML 解析、上下文插值、存储 CRUD、API 路由。

---

## 🛣 路线图

- ✅ MVP:u2 设备 + YAML 流程 + 任务执行 + Web UI + 每步截图
- 🔜 OCR 接入(PaddleOCR)→ YAML 支持 `click_text: "登录"`
- 🔜 LLM Planner 接入 → AI 自主任务模式("帮我订张机票")
- 🔜 定时任务面板(Cron 编辑 UI)
- 🔜 atxserver2 多设备农场

---

## ❓ 常见问题

**Q: 为什么选 uiautomator2 而不是 Appium?**
A: u2 通过 atx-agent 常驻 + HTTP 直连,单设备调用速度最快;Python 原生,易向上接 AI/数据;Appium 的多层 RPC 在高频爬虫/测试场景下偏慢。

**Q: 设备显示离线?**
A: ① 确认 `adb devices` 能看到设备;② 已运行 `python scripts/init_device.py`;③ 手机与 PC 同网段(WiFi 模式);④ 端口 7912 未被占用。

**Q: 反爬检测?**
A: 动作层默认开启人类化时延(可在 `U2Actions` 调参);点击带 ±3px 抖动;如需更强可叠加随机滑动轨迹。

**Q: 如何扩展自定义步骤?**
A: 在 `automator/flow/steps/` 新建模块,用 `@register("your_step")` 装饰一个签名为
   `(actions, device, ctx, params) -> StepResult` 的函数,并在 `steps/__init__.py` 导入。
