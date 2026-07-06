/* Automator 前端逻辑 —— Alpine.js 单页 */

const DEFAULT_YAML = `name: 演示流程
description: 启动应用并截图的示例
variables:
  pkg: com.android.settings
steps:
  - start_app: { package: "\${pkg}" }
  - wait: { seconds: 2 }
  - wait: { text_contains: "设置" , timeout: 5 }
  - assert: { exists: { text_contains: "设置" } }
  - extract:
      as: title
      from: { text_contains: "设置" }
`;

function automatorApp() {
  return {
    tabs: [
      { id: "device", label: "设备" },
      { id: "playground", label: "Playground" },
      { id: "flows", label: "流程" },
      { id: "tasks", label: "任务" },
      { id: "runs", label: "运行记录" },
      { id: "system", label: "系统" },
    ],
    tab: "device",

    // 设备
    device: { alive: false, model: "" },
    screenshotSrc: "",
    autoRefresh: false,
    _refreshTimer: null,

    // 投屏(WebSocket 实时流)
    streaming: false,
    streamStatus: "未连接", // 未连接 / 连接中 / 直播中 / 已断开 / 错误
    streamFps: 0,
    streamSrc: "",
    streamError: "", // 投屏错误详情(空=无错误)
    _ws: null,
    _lastFrameTs: 0,
    _frameTimes: [],
    _blobUrl: null,
    _reconnectTimer: null,
    _userStopped: false,

    // Playground
    pgStreamOn: false,        // playground 是否开启投屏
    pgShotSrc: "",            // playground 单张/投屏画面
    pgAction: "click",        // 当前选中的动作
    pgActions: [],            // 动作清单(来自 /api/playground/actions)
    pgParams: {},             // 动作参数(动态表单绑定)
    pgBusy: false,            // 动作执行中
    pgLogs: [],               // 操作日志 [{action,target,success,detail,duration_ms,ts}]
    pgCrosshair: null,        // 点击投屏时显示的十字光标 {x,y,deviceX,deviceY}

    // 录制
    recActive: false,         // 是否录制中
    recSmartLocator: true,    // 录制点击时是否启用智能定位
    recSteps: [],             // 已录步骤 [{index,type,params,target,success}]
    recName: "",              // 录制/生成的流程名
    recYaml: "",              // 生成的 YAML 预览
    recShowYaml: false,       // 是否展开 YAML 预览
    _recPoll: null,           // 录制状态轮询定时器

    // 流程
    flows: [],
    selectedFlow: null,
    flowForm: { name: "", yaml: DEFAULT_YAML, description: "" },
    validationMsg: "",
    validationOk: false,

    // 任务
    tasks: [],

    // 运行
    runs: [],
    runsFilter: "",
    selectedRunId: null,
    selectedRun: null,
    productSort: "price", // 商品表格排序字段(可带 - 前缀表降序)

    // 系统
    sysInfo: {},

    async init() {
      await Promise.all([
        this.loadDevice(),
        this.loadFlows(),
        this.loadTasks(),
        this.loadRuns(),
        this.loadSysInfo(),
        this.initPlayground(),
      ]);
      // 周期刷新设备状态
      setInterval(() => this.loadDevice(), 5000);
    },

    // ---- 设备 ----
    async loadDevice() {
      try {
        const r = await fetch("/api/devices").then((r) => r.json());
        this.device = r.current || { alive: false };
      } catch (e) {
        this.device = { alive: false, error: String(e) };
      }
    },
    async loadScreenshot() {
      this.screenshotSrc = "/api/devices/screenshot?t=" + Date.now();
    },
    toggleAutoRefresh() {
      this.autoRefresh = !this.autoRefresh;
      if (this.autoRefresh) {
        this.loadScreenshot();
        this._refreshTimer = setInterval(() => this.loadScreenshot(), 3000);
      } else {
        clearInterval(this._refreshTimer);
      }
    },
    async resetDevice() {
      await fetch("/api/devices/reset", { method: "POST" });
      await this.loadDevice();
    },

    // ---- 投屏(WebSocket 实时流)----
    streamUrl() {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      return `${proto}://${location.host}/api/devices/stream`;
    },
    toggleStream() {
      this.streaming ? this.stopStream() : this.startStream();
    },
    startStream() {
      // 关掉旧的单张自动刷新,避免互相干扰
      if (this.autoRefresh) this.toggleAutoRefresh();
      this._userStopped = false;
      this.streaming = true;
      this.streamStatus = "连接中";
      this.streamFps = 0;
      this.streamError = "";
      this._frameTimes = [];
      try {
        this._ws = new WebSocket(this.streamUrl());
      } catch (e) {
        this.streamStatus = "错误";
        this.streaming = false;
        return;
      }
      this._ws.binaryType = "arraybuffer";
      this._ws.onopen = () => {
        this.streamStatus = "直播中";
      };
      this._ws.onmessage = (ev) => {
        if (typeof ev.data === "string") {
          // 文本帧:hello 元信息 / error 状态
          try {
            const msg = JSON.parse(ev.data);
            if (msg.type === "error") {
              this.streamStatus = "错误";
              this.streamError = msg.detail || "设备异常";
            }
          } catch (_) {}
          return;
        }
        // binary 帧:JPEG
        const url = URL.createObjectURL(
          new Blob([ev.data], { type: "image/jpeg" })
        );
        if (this._blobUrl) URL.revokeObjectURL(this._blobUrl);
        this._blobUrl = url;
        this.streamSrc = url;
        // 滑动窗口估算实际 fps
        const now = performance.now();
        if (this._lastFrameTs) {
          this._frameTimes.push(now - this._lastFrameTs);
          if (this._frameTimes.length > 10) this._frameTimes.shift();
          const avg =
            this._frameTimes.reduce((a, b) => a + b, 0) /
            this._frameTimes.length;
          this.streamFps = avg ? Math.round(1000 / avg) : 0;
        }
        this._lastFrameTs = now;
      };
      this._ws.onclose = () => {
        this.streaming = false;
        if (this._userStopped) {
          this.streamStatus = "未连接";
        } else {
          this.streamStatus = "已断开";
          // 自动重连(3s 后),前提是用户没有主动停止
          clearTimeout(this._reconnectTimer);
          this._reconnectTimer = setTimeout(() => {
            if (!this._userStopped) this.startStream();
          }, 3000);
        }
      };
      this._ws.onerror = () => {
        this.streamStatus = "错误";
      };
    },
    stopStream() {
      this._userStopped = true;
      clearTimeout(this._reconnectTimer);
      if (this._ws) {
        try {
          this._ws.close();
        } catch (_) {}
        this._ws = null;
      }
      if (this._blobUrl) {
        URL.revokeObjectURL(this._blobUrl);
        this._blobUrl = null;
      }
      this.streaming = false;
      this.streamStatus = "未连接";
      this.streamSrc = "";
      this.streamFps = 0;
      this.streamError = "";
    },
    deviceInfoRows() {
      const d = this.device || {};
      return {
        serial: d.serial,
        model: d.model,
        brand: d.brand,
        android: d.android_version,
        resolution: (d.resolution || []).join("x"),
        atx: d.atx_version,
      };
    },

    // ---- Playground ----
    async initPlayground() {
      if (!this.pgActions.length) {
        try {
          const r = await fetch("/api/playground/actions").then((r) => r.json());
          this.pgActions = r.actions || [];
        } catch (_) {}
      }
      this.selectPgAction(this.pgAction);
    },
    currentPgAction() {
      return this.pgActions.find((a) => a.name === this.pgAction) || null;
    },
    selectPgAction(name) {
      this.pgAction = name;
      // 重置参数表单:为每个参数建一个空字段
      const params = {};
      const meta = this.currentPgAction();
      if (meta) {
        for (const k of Object.keys(meta.params || {})) params[k] = "";
      }
      this.pgParams = params;
      this.pgCrosshair = null;
    },
    // 点击投屏画面 → 换算成设备坐标 → 执行 click
    async pgClickScreen(ev) {
      if (this.pgBusy) return;
      const img = ev.currentTarget;
      const rect = img.getBoundingClientRect();
      // 显示像素 → 图片自然尺寸(即设备分辨率)
      const scaleX = img.naturalWidth / rect.width;
      const scaleY = img.naturalHeight / rect.height;
      const dx = Math.round((ev.clientX - rect.left) * scaleX);
      const dy = Math.round((ev.clientY - rect.top) * scaleY);
      this.pgCrosshair = {
        x: ev.clientX - rect.left,
        y: ev.clientY - rect.top,
        deviceX: dx,
        deviceY: dy,
      };
      await this.runPgAction("click", { x: dx, y: dy });
    },
    pgCrosshairStyle() {
      if (!this.pgCrosshair) return "";
      return `left:${this.pgCrosshair.x}px;top:${this.pgCrosshair.y}px`;
    },
    // 执行一个动作(action 可省略,默认用当前表单选中动作)
    async runPgAction(action, params) {
      if (this.pgBusy) return;
      const act = action || this.pgAction;
      const p = params || this._collectPgParams(act);
      if (p === null) return; // 校验失败
      this.pgBusy = true;
      try {
        const r = await fetch("/api/playground/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          // 录制时把智能定位开关传给后端(仅对 click 生效)
          body: JSON.stringify({
            action: act,
            params: p,
            smart_locator: this.recSmartLocator,
          }),
        });
        const data = await r.json();
        if (!r.ok) {
          this.pgLogs.unshift({
            action: act, target: "", success: false,
            detail: data.detail || "请求失败", duration_ms: 0, ts: Date.now(),
          });
        } else {
          this.pgLogs.unshift({ ...data, ts: Date.now() });
          // 动作完成后刷新画面(单张快照,带时间戳防缓存)
          this.pgShotSrc = "/api/devices/screenshot?t=" + Date.now();
        }
      } catch (e) {
        this.pgLogs.unshift({
          action: act, target: "", success: false,
          detail: String(e), duration_ms: 0, ts: Date.now(),
        });
      } finally {
        this.pgBusy = false;
        // 只保留最近 50 条
        if (this.pgLogs.length > 50) this.pgLogs.length = 50;
      }
    },
    // 从表单收集参数,做必要的类型转换与必填校验;返回 null 表示校验失败
    _collectPgParams(action) {
      const meta = this.pgActions.find((a) => a.name === action);
      if (!meta) return {};
      const out = {};
      for (const [k, type] of Object.entries(meta.params || {})) {
        const raw = (this.pgParams[k] ?? "").toString().trim();
        const optional = type.endsWith("?");
        if (raw === "") {
          if (optional) continue;
          alert(`参数 ${k} 必填`);
          return null;
        }
        const base = optional ? type.slice(0, -1) : type;
        if (base.startsWith("int")) out[k] = parseInt(raw, 10);
        else if (base.startsWith("float")) out[k] = parseFloat(raw);
        else if (base.startsWith("bool")) out[k] = raw === "true" || raw === "1";
        else if (base.includes("|")) out[k] = raw; // 枚举字符串
        else out[k] = raw;
      }
      return out;
    },
    // 启停 playground 投屏(复用设备页的 WS 实现)
    pgToggleStream() {
      this.pgStreamOn = !this.pgStreamOn;
      if (this.pgStreamOn) {
        this.streaming = true;
        this.startStream();
      } else {
        this.stopStream();
        this.streaming = false;
      }
    },
    pgShot() {
      this.pgShotSrc = "/api/devices/screenshot?t=" + Date.now();
    },
    clearPgLogs() {
      this.pgLogs = [];
    },

    // ---- 录制 ----
    async recStart() {
      const name = this.recName || "";
      const r = await fetch("/api/recorder/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      }).then((r) => r.json()).catch(() => ({}));
      this.recActive = true;
      this.recShowYaml = false;
      this.recYaml = "";
      this._applyRecState(r);
      // 开启轮询,实时拉取已录步骤
      if (this._recPoll) clearInterval(this._recPoll);
      this._recPoll = setInterval(() => this.recRefresh(), 1500);
    },
    async recStop() {
      await fetch("/api/recorder/stop", { method: "POST" });
      this.recActive = false;
      if (this._recPoll) {
        clearInterval(this._recPoll);
        this._recPoll = null;
      }
      await this.recRefresh();
    },
    async recReset() {
      if (!confirm("清空已录步骤?")) return;
      await fetch("/api/recorder/reset", { method: "POST" });
      this.recActive = false;
      this.recSteps = [];
      this.recYaml = "";
      this.recShowYaml = false;
      if (this._recPoll) {
        clearInterval(this._recPoll);
        this._recPoll = null;
      }
    },
    async recRefresh() {
      const r = await fetch("/api/recorder/state").then((r) => r.json()).catch(() => ({}));
      this._applyRecState(r);
    },
    _applyRecState(r) {
      this.recActive = !!r.active;
      this.recSteps = r.steps || [];
      if (r.name) this.recName = r.name;
    },
    async recRemoveStep(index) {
      await fetch(`/api/recorder/step/${index}`, { method: "DELETE" });
      await this.recRefresh();
    },
    async recGenYaml() {
      const r = await fetch(
        `/api/recorder/yaml?name=${encodeURIComponent(this.recName || "")}`
      ).then((r) => r.json()).catch(() => ({}));
      this.recYaml = r.yaml || "";
      this.recShowYaml = true;
    },
    async recSaveAsFlow() {
      if (!this.recYaml) await this.recGenYaml();
      if (!this.recYaml) return;
      const name = this.recName || "录制流程";
      const r = await fetch("/api/flows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          yaml: this.recYaml,
          description: "由录制生成",
        }),
      });
      if (r.ok) {
        const data = await r.json();
        alert(`已保存为流程 #${data.id}`);
        await this.loadFlows();
        // 跳转到流程页并选中刚保存的流程
        this.tab = "flows";
        await this.selectFlow(data.id);
      } else {
        const e = await r.json().catch(() => ({}));
        alert("保存失败: " + (e.detail || r.status));
      }
    },

    // ---- 流程 ----
    async loadFlows() {
      const r = await fetch("/api/flows").then((r) => r.json());
      this.flows = r.items || [];
    },
    newFlow() {
      this.selectedFlow = null;
      this.flowForm = { name: "新流程", yaml: DEFAULT_YAML, description: "" };
      this.validationMsg = "";
    },
    async selectFlow(id) {
      const f = await fetch(`/api/flows/${id}`).then((r) => r.json());
      this.selectedFlow = f;
      this.flowForm = {
        name: f.name,
        yaml: f.yaml,
        description: f.description || "",
      };
      this.validationMsg = "";
    },
    async validateFlow() {
      const r = await fetch("/api/flows/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ yaml: this.flowForm.yaml }),
      }).then((r) => r.json());
      this.validationOk = r.valid;
      this.validationMsg = r.valid
        ? "✓ YAML 校验通过"
        : "✗ " + (r.errors || []).join("; ");
    },
    async saveFlow() {
      const method = this.selectedFlow ? "PUT" : "POST";
      const url = this.selectedFlow
        ? `/api/flows/${this.selectedFlow.id}`
        : "/api/flows";
      const r = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: this.flowForm.name,
          yaml: this.flowForm.yaml,
          description: this.flowForm.description,
        }),
      });
      if (r.ok) {
        await this.loadFlows();
        this.validationMsg = "✓ 已保存";
        this.validationOk = true;
      } else {
        const e = await r.json().catch(() => ({}));
        this.validationMsg = "✗ " + (e.detail || "保存失败");
        this.validationOk = false;
      }
    },
    async deleteFlow() {
      if (!this.selectedFlow) return;
      if (!confirm(`删除流程 ${this.selectedFlow.name}?`)) return;
      await fetch(`/api/flows/${this.selectedFlow.id}`, { method: "DELETE" });
      this.newFlow();
      await this.loadFlows();
    },

    // ---- 任务 ----
    async loadTasks() {
      const r = await fetch("/api/tasks").then((r) => r.json());
      this.tasks = r.items || [];
    },
    async runTask(id) {
      const r = await fetch(`/api/tasks/${id}/run`, { method: "POST" });
      if (r.ok) {
        const data = await r.json();
        alert(`已派发,run_id=${data.run_id}`);
        setTimeout(() => {
          this.loadTasks();
          this.loadRuns();
        }, 1000);
      } else {
        alert("派发失败");
      }
    },

    // ---- 运行 ----
    async loadRuns() {
      const url = this.runsFilter
        ? `/api/runs?task_id=${this.runsFilter}&limit=100`
        : "/api/runs?limit=100";
      const r = await fetch(url).then((r) => r.json());
      this.runs = r.items || [];
      if (this.runs.length && !this.selectedRunId) {
        this.selectRun(this.runs[0].id);
      }
    },
    async selectRun(id) {
      this.selectedRunId = id;
      this.selectedRun = await fetch(`/api/runs/${id}`).then((r) => r.json());
    },

    /**
     * 合并并去重抽取数据中的商品(batch_0/batch_1/...)。
     * 仅当 extracted_data 含 batch_* 列表且元素带 title 字段时启用,
     * 否则返回 null —— 调用方据此回退到原始 JSON 展示(其它 flow 不受影响)。
     */
    mergedProducts() {
      const data = this.selectedRun?.extracted_data;
      if (!data || typeof data !== "object") return null;
      const batches = Object.keys(data)
        .filter((k) => /^batch_\d+$/.test(k))
        .sort();
      if (!batches.length) return null;
      const seen = new Set();
      const merged = [];
      for (const k of batches) {
        const items = data[k];
        if (!Array.isArray(items)) return null; // 结构不符 → 回退
        for (const it of items) {
          if (!it || typeof it !== "object" || !("title" in it)) return null;
          const title = (it.title || "").trim();
          if (!title || seen.has(title)) continue;
          seen.add(title);
          merged.push(it);
        }
      }
      return merged.length ? merged : null;
    },
    /** 价格数值化用于排序(去 ¥、转 float)。 */
    priceNum(p) {
      const m = String(p?.price || "").match(/-?\d+(?:\.\d+)?/);
      return m ? parseFloat(m[0]) : 0;
    },

    /**
     * CSV 单元格转义:含逗号/引号/换行则用双引号包裹,内部双引号翻倍。
     */
    csvCell(v) {
      const s = v == null ? "" : String(v);
      if (/[",\n\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
      return s;
    },
    /**
     * 导出抽取数据为 CSV(浏览器端生成,无后端往返)。
     * 商品列表(batch_*)→ 标题/价格/销量 三列;
     * 其它结构 → 拍平成 key/value 两列;无数据则提示。
     */
    exportCSV() {
      const data = this.selectedRun?.extracted_data;
      if (!data) return;
      const products = this.mergedProducts();
      let csv = "\uFEFF"; // BOM,确保 Excel 正确识别 UTF-8
      if (products) {
        csv += ["商品标题", "价格", "销量"].map(this.csvCell).join(",") + "\r\n";
        for (const p of products) {
          csv += [p.title, p.price, p.sales].map(this.csvCell).join(",") + "\r\n";
        }
      } else {
        csv += ["键", "值"].map(this.csvCell).join(",") + "\r\n";
        for (const [k, v] of Object.entries(data)) {
          csv += [k, typeof v === "object" ? JSON.stringify(v) : v]
            .map(this.csvCell).join(",") + "\r\n";
        }
      }
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `run_${this.selectedRun.id}_extracted.csv`;
      a.click();
      URL.revokeObjectURL(url);
    },

    // ---- 系统 ----
    async loadSysInfo() {
      try {
        this.sysInfo = await fetch("/api/system/env").then((r) => r.json());
      } catch (e) {
        this.sysInfo = { error: String(e) };
      }
    },

    // ---- 辅助 ----
    statusClass(s) {
      return {
        success: "bg-emerald-100 text-emerald-700",
        failed: "bg-rose-100 text-rose-700",
        running: "bg-amber-100 text-amber-700",
        pending: "bg-slate-100 text-slate-600",
        cancelled: "bg-slate-200 text-slate-500",
      }[s] || "bg-slate-100";
    },
    fmtTime(s) {
      if (!s) return "—";
      try {
        return new Date(s).toLocaleString("zh-CN");
      } catch {
        return s;
      }
    },
  };
}
