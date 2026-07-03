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
    _ws: null,
    _lastFrameTs: 0,
    _frameTimes: [],
    _blobUrl: null,
    _reconnectTimer: null,
    _userStopped: false,

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

    // 系统
    sysInfo: {},

    async init() {
      await Promise.all([
        this.loadDevice(),
        this.loadFlows(),
        this.loadTasks(),
        this.loadRuns(),
        this.loadSysInfo(),
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
