const state = {
  session: false,
  market: "kr",
  artifacts: [],
  watchlist: [],
  activeView: "generate",
  latestArtifact: null,
  latestDashboard: null,
  selectedStockIndex: 0,
  csrfToken: null,
};

const app = document.querySelector("#app");
let chartInstance = null;

function render() {
  app.innerHTML = state.session ? renderAuthenticated() : renderLogin();
  bindEvents();
  mountHeroChart();
}

function renderLogin() {
  return `
    <div class="login-shell">
      <section class="login-panel">
        <div class="stack">
          <div class="module-head">
            <div class="eyebrow">Access Node</div>
            <h2>관리자 로그인</h2>
            <p>세션 쿠키와 CSRF 토큰으로 웹 대시보드를 잠급니다.</p>
          </div>
          <form id="login-form" class="stack">
            <div class="field">
              <label>Password</label>
              <input name="password" type="password" placeholder="dashboard password" required />
            </div>
            <div class="actions">
              <button class="button primary full" type="submit">Open Session</button>
            </div>
            <div id="login-status" class="status"></div>
          </form>
        </div>
      </section>
    </div>
  `;
}

function renderAuthenticated() {
  return `
    <div class="terminal-shell">
      <aside class="control-rail">
        <section class="rail-brand">
          <div class="eyebrow">Obsidian Terminal</div>
          <h1>KIS Command Center</h1>
          <p>Generate dashboards, steer watchlists, and inspect artifacts without touching the existing CLI pipeline.</p>
        </section>

        <section class="rail-cluster">
          <nav class="nav">
            <button class="${state.activeView === "generate" ? "active" : ""}" data-view="generate">Generate</button>
            <button class="${state.activeView === "watchlist" ? "active" : ""}" data-view="watchlist">Watchlist</button>
            <button class="${state.activeView === "artifacts" ? "active" : ""}" data-view="artifacts">Artifacts</button>
          </nav>
          <div class="rail-status">
            <div class="status-chip">
              <label>Session</label>
              <strong>${state.session ? "ONLINE" : "LOCKED"}</strong>
            </div>
            <div class="status-chip">
              <label>Market</label>
              <strong class="mono">${state.market.toUpperCase()}</strong>
            </div>
            <div class="status-chip">
              <label>Artifacts</label>
              <strong class="mono">${state.artifacts.length}</strong>
            </div>
            <div class="status-chip">
              <label>Symbols</label>
              <strong class="mono">${state.watchlist.length}</strong>
            </div>
          </div>
        </section>

        <section class="rail-scroll">
          ${renderRailModule()}
        </section>
      </aside>

      <main class="terminal-main">
        <section class="terminal-topbar">
          <div class="topbar-copy">
            <div class="eyebrow">Trading Instrument</div>
            <strong>${renderTopbarTitle()}</strong>
            <p>${renderTopbarSubtitle()}</p>
          </div>
          <div class="topbar-actions">
            <span class="pill mono">${state.market.toUpperCase()} MODE</span>
            <span class="pill mono">${state.latestArtifact ? `${state.latestArtifact.interval_minutes}M CANDLES` : "NO ARTIFACT"}</span>
          </div>
        </section>

        <section class="market-strip">
          ${renderSummaryStrip()}
        </section>

        <section class="hero-grid">
          <section class="hero-chart-panel">
            ${renderHeroChart()}
          </section>

          <section class="side-stack">
            <section class="side-panel">
              <div class="module-head">
                <div class="eyebrow">Watchlist Feed</div>
                <h3>${state.market.toUpperCase()} Symbols</h3>
              </div>
              <div class="watchlist-list">${renderWatchlistItems()}</div>
            </section>

            <section class="side-panel">
              <div class="module-head">
                <div class="eyebrow">Artifact Log</div>
                <h3>Recent Runs</h3>
              </div>
              <div class="artifacts">${renderArtifacts()}</div>
            </section>
          </section>
        </section>
      </main>
    </div>
  `;
}

function renderRailModule() {
  if (state.activeView === "watchlist") {
    return `
      <section class="rail-module">
        <div class="module-head">
          <div class="eyebrow">Symbol Control</div>
          <h2>Watchlist</h2>
          <p>Market-specific symbol inventory for the CLI dashboard.</p>
        </div>
        <form id="watchlist-form" class="stack">
          <div class="grid">
            <div class="field">
              <label>Code</label>
              <input name="code" required />
            </div>
            <div class="field">
              <label>Name</label>
              <input name="name" required />
            </div>
            <div class="field">
              <label>Market Label</label>
              <input name="market_label" />
            </div>
            <div class="field ${state.market === "us" ? "" : "hidden"}">
              <label>EXCD</label>
              <input name="excd" value="NAS" />
            </div>
          </div>
          <div class="actions">
            <button class="button primary full" type="submit">Add Symbol</button>
          </div>
        </form>
      </section>
    `;
  }

  if (state.activeView === "artifacts") {
    return `
      <section class="rail-module">
        <div class="module-head">
          <div class="eyebrow">Artifact Controls</div>
          <h2>Artifacts</h2>
          <p>Refresh artifact state or tear down the session.</p>
        </div>
        <div class="actions">
          <button class="button primary full" type="button" id="refresh-artifacts">Refresh Artifacts</button>
          <button class="button secondary full" type="button" id="logout-button">Logout</button>
        </div>
      </section>
    `;
  }

  return `
    <section class="rail-module">
      <div class="module-head">
        <div class="eyebrow">Control Plane</div>
        <h2>Generate Dashboard</h2>
        <p>CLI options are exposed here one-to-one, but the chart stays center stage.</p>
      </div>
      <form id="generate-form" class="stack">
        <div class="grid">
          <div class="field">
            <label>Market</label>
            <select name="market">
              <option value="kr" ${state.market === "kr" ? "selected" : ""}>KR</option>
              <option value="us" ${state.market === "us" ? "selected" : ""}>US</option>
            </select>
          </div>
          <div class="field">
            <label>Format</label>
            <select name="format">
              <option value="png">PNG</option>
              <option value="webp">WEBP</option>
            </select>
          </div>
          <div class="field">
            <label>Interval Minutes</label>
            <input name="interval_minutes" type="number" value="${state.latestArtifact?.interval_minutes || 10}" min="1" />
          </div>
          <div class="field">
            <label>Candle Width Scale</label>
            <input name="candle_width_scale" type="number" step="0.1" value="${state.latestArtifact?.candle_width_scale || 1.0}" min="0.3" max="2" />
          </div>
          <div class="field">
            <label>Width PX</label>
            <input name="width_px" type="number" value="${state.latestArtifact?.width_px || 1080}" min="480" />
          </div>
          <div class="field">
            <label>Height PX</label>
            <input name="height_px" type="number" placeholder="auto" min="480" value="${state.latestArtifact?.height_px || ""}" />
          </div>
          <div class="field">
            <label>Render Scale</label>
            <input name="render_scale" type="number" value="${state.latestArtifact?.render_scale || 2.0}" step="0.1" min="1" />
          </div>
          <div class="field">
            <label>WEBP Quality</label>
            <input name="webp_quality" type="number" value="${state.latestArtifact?.webp_quality || 90}" min="1" max="100" />
          </div>
        </div>
        <div class="actions">
          <button class="button primary full" type="submit">Generate Artifact</button>
          <button class="button secondary" type="button" id="refresh-artifacts">Refresh</button>
          <button class="button secondary" type="button" id="logout-button">Logout</button>
        </div>
        <div id="generate-status" class="status"></div>
      </form>
    </section>
  `;
}

function renderTopbarTitle() {
  if (!state.latestDashboard) {
    return "No Artifact Loaded";
  }
  return state.latestDashboard.title || `${state.market.toUpperCase()} Dashboard`;
}

function renderTopbarSubtitle() {
  if (!state.latestDashboard) {
    return "Generate a dashboard artifact to hydrate market strip, chart, and artifact log.";
  }
  return state.latestDashboard.subtitle || state.latestArtifact?.created_at || "";
}

function renderSummaryStrip() {
  const cards = state.latestDashboard?.summary_cards || [];
  if (!cards.length) {
    return `<div class="empty-state">Summary cards will appear after the first successful generation.</div>`;
  }
  return cards
    .map((card) => {
      const deltaClass = diffClass(card.diff);
      return `
        <article class="summary-chip">
          <div class="summary-chip-head">
            <div>
              <div class="eyebrow">${escapeHtml(card.market || card.label || "")}</div>
              <strong>${escapeHtml(card.name)}</strong>
            </div>
            ${card.label ? `<span class="ghost-chip">${escapeHtml(card.label)}</span>` : ""}
          </div>
          <div class="summary-chip-value">
            <div class="summary-chip-price">${escapeHtml(card.price)}</div>
            <div class="summary-chip-delta ${deltaClass}">
              <div>${escapeHtml(card.diff || "-")}</div>
              <div>${escapeHtml(card.pct || "-")}</div>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderHeroChart() {
  const cards = state.latestDashboard?.stock_cards || [];
  const selected = cards[state.selectedStockIndex] || cards[0];
  if (!selected) {
    return `<div class="empty-state">No stock chart data in the selected artifact yet.</div>`;
  }
  return `
    <div class="hero-header">
      <div class="hero-title-block">
        <div class="hero-title-row">
          <span class="hero-symbol">${escapeHtml(selected.market || state.market.toUpperCase())}</span>
          <span class="ghost-chip">${(selected.chart?.interval_minutes || state.latestArtifact?.interval_minutes || 10)}m candles</span>
        </div>
        <h2 class="hero-title">${escapeHtml(selected.name)}</h2>
        <div class="hero-price-row">
          <span class="hero-price">${escapeHtml(selected.price)}</span>
          <span class="hero-delta ${diffClass(selected.diff)}">${escapeHtml(selected.diff)} (${escapeHtml(selected.pct)})</span>
        </div>
      </div>
      <div class="hero-meta">
        ${
          cards.length
            ? `<div class="field">
                <label>Symbol Focus</label>
                <select id="stock-select">
                  ${cards
                    .map(
                      (stock, index) =>
                        `<option value="${index}" ${index === state.selectedStockIndex ? "selected" : ""}>${escapeHtml(stock.name)}</option>`
                    )
                    .join("")}
                </select>
              </div>`
            : ""
        }
      </div>
    </div>
    <div class="chart-frame">
      <div id="chart-host" class="chart-host"></div>
    </div>
    <div class="hero-foot">
      <div class="hero-notes">
        ${(selected.chart?.segments || []).map((segment) => `<span class="ghost-chip">${escapeHtml(segment.session)}</span>`).join("")}
      </div>
      <a class="button secondary" href="${state.latestArtifact?.preview_url || "#"}" target="_blank" rel="noreferrer">Open Rendered Image</a>
    </div>
  `;
}

function renderWatchlistItems() {
  if (!state.watchlist.length) {
    return `<div class="empty-state">Add the first symbol for ${state.market.toUpperCase()}.</div>`;
  }
  return state.watchlist
    .map(
      (item) => `
        <article class="watchlist-item">
          <div class="watchlist-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <div class="muted mono">${escapeHtml(item.code)}${item.excd ? ` · ${escapeHtml(item.excd)}` : ""}</div>
            </div>
            <button class="button danger" data-remove="${escapeHtml(item.code)}">Remove</button>
          </div>
        </article>
      `
    )
    .join("");
}

function renderArtifacts() {
  if (!state.artifacts.length) {
    return `<div class="empty-state">Generated outputs will appear here.</div>`;
  }
  return state.artifacts
    .slice(0, 6)
    .map(
      (artifact) => `
        <article class="artifact-card">
          <div class="artifact-row">
            <div>
              <strong>${artifact.market.toUpperCase()} ${artifact.format.toUpperCase()}</strong>
              <div class="muted mono">${escapeHtml(artifact.created_at)}</div>
            </div>
            <a class="button secondary" href="${artifact.preview_url}" target="_blank" rel="noreferrer">Open</a>
          </div>
        </article>
      `
    )
    .join("");
}

function bindEvents() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeView = button.dataset.view;
      render();
    });
  });

  document.querySelector("#login-form")?.addEventListener("submit", handleLogin);

  const generateForm = document.querySelector("#generate-form");
  if (generateForm) {
    generateForm.addEventListener("submit", handleGenerate);
    generateForm.market?.addEventListener("change", async (event) => {
      state.market = event.target.value;
      await refreshData();
    });
  }

  document.querySelector("#watchlist-form")?.addEventListener("submit", handleWatchlistAdd);
  document.querySelector("#refresh-artifacts")?.addEventListener("click", refreshData);
  document.querySelector("#logout-button")?.addEventListener("click", handleLogout);
  document.querySelectorAll("[data-remove]").forEach((button) => {
    button.addEventListener("click", () => removeWatchlist(button.dataset.remove));
  });
  document.querySelector("#stock-select")?.addEventListener("change", (event) => {
    state.selectedStockIndex = Number(event.target.value || 0);
    render();
  });
}

async function handleLogin(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const response = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: form.get("password") }),
  });
  const status = document.querySelector("#login-status");
  if (!response.ok) {
    status.textContent = "로그인에 실패했습니다.";
    return;
  }
  const payload = await response.json();
  state.session = true;
  state.csrfToken = payload.csrf_token;
  await refreshData();
}

async function handleLogout() {
  await fetch("/api/logout", { method: "POST" });
  state.session = false;
  state.artifacts = [];
  state.watchlist = [];
  state.latestArtifact = null;
  state.latestDashboard = null;
  state.selectedStockIndex = 0;
  state.csrfToken = null;
  disposeChart();
  render();
}

async function handleGenerate(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  state.market = form.get("market");
  const payload = {
    market: form.get("market"),
    format: form.get("format"),
    interval_minutes: Number(form.get("interval_minutes")),
    candle_width_scale: Number(form.get("candle_width_scale")),
    width_px: Number(form.get("width_px")),
    height_px: form.get("height_px") ? Number(form.get("height_px")) : null,
    render_scale: Number(form.get("render_scale")),
    webp_quality: Number(form.get("webp_quality")),
  };
  const status = document.querySelector("#generate-status");
  status.textContent = "Generating artifact...";
  const response = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Generate failed." }));
    status.textContent = error.detail || "Generate failed.";
    return;
  }
  status.textContent = "Artifact generated.";
  await refreshData();
}

async function handleWatchlistAdd(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    market: state.market,
    code: form.get("code"),
    name: form.get("name"),
    market_label: form.get("market_label") || null,
    excd: form.get("excd") || null,
  };
  const response = await fetch("/api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken },
    body: JSON.stringify(payload),
  });
  if (response.ok) {
    event.currentTarget.reset();
    await loadWatchlist();
    render();
  }
}

async function removeWatchlist(code) {
  const params = new URLSearchParams({ market: state.market });
  await fetch(`/api/watchlist/${encodeURIComponent(code)}?${params.toString()}`, {
    method: "DELETE",
    headers: { "X-CSRF-Token": state.csrfToken },
  });
  await loadWatchlist();
  render();
}

async function refreshData() {
  const session = await fetch("/api/session");
  state.session = session.ok;
  if (!state.session) {
    disposeChart();
    render();
    return;
  }
  const sessionPayload = await session.json();
  state.csrfToken = sessionPayload.csrf_token;
  await Promise.all([loadArtifacts(), loadWatchlist()]);
  render();
}

async function loadArtifacts() {
  const response = await fetch("/api/artifacts");
  if (!response.ok) {
    return;
  }
  const payload = await response.json();
  state.artifacts = payload.artifacts;
  const nextLatest = payload.artifacts[0] || null;
  const changed = nextLatest?.id !== state.latestArtifact?.id;
  state.latestArtifact = nextLatest || state.latestArtifact;
  if (state.latestArtifact && (changed || !state.latestDashboard)) {
    await loadArtifactDetail(state.latestArtifact.id);
  }
}

async function loadArtifactDetail(artifactId) {
  const response = await fetch(`/api/artifacts/${artifactId}`);
  if (!response.ok) {
    state.latestDashboard = null;
    return;
  }
  const payload = await response.json();
  state.latestDashboard = payload.dashboard;
  const cards = payload.dashboard?.stock_cards || [];
  if (state.selectedStockIndex >= cards.length) {
    state.selectedStockIndex = 0;
  }
}

async function loadWatchlist() {
  const response = await fetch(`/api/watchlist?market=${state.market}`);
  if (!response.ok) {
    return;
  }
  const payload = await response.json();
  state.watchlist = payload.items;
}

function disposeChart() {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
}

function mountHeroChart() {
  const host = document.querySelector("#chart-host");
  const chartData = state.latestDashboard?.stock_cards?.[state.selectedStockIndex]?.chart;
  if (!host || !chartData || !window.echarts) {
    disposeChart();
    return;
  }

  const rows = flattenChartSegments(chartData);
  if (!rows.length) {
    disposeChart();
    host.innerHTML = "";
    return;
  }

  disposeChart();
  chartInstance = window.echarts.init(host, null, { renderer: "canvas" });
  chartInstance.setOption(buildChartOption(rows, chartData.segments || []), true);
  window.addEventListener("resize", resizeChartOnce, { once: true });
}

function resizeChartOnce() {
  chartInstance?.resize();
}

function flattenChartSegments(chart) {
  return (chart.segments || []).flatMap((segment) =>
    (segment.points || []).map((point) => ({
      label: point.time,
      session: segment.session,
      color: segment.color,
      open: Number(point.open),
      high: Number(point.high),
      low: Number(point.low),
      close: Number(point.close),
      volume: Number(point.volume || 0),
    }))
  );
}

function buildChartOption(rows, segments) {
  const palette = state.market === "us"
    ? { up: "#33d17a", down: "#ff5c7a" }
    : { up: "#ff6b6b", down: "#4c9bff" };

  const categories = rows.map((row) => row.label);
  const candleData = rows.map((row) => [row.open, row.close, row.low, row.high]);
  const volumeData = rows.map((row) => ({
    value: row.volume,
    itemStyle: { color: row.close >= row.open ? `${palette.up}88` : `${palette.down}88` },
  }));

  let cursor = 0;
  const markAreaData = [];
  for (const segment of segments) {
    const pointCount = (segment.points || []).length;
    if (!pointCount) {
      continue;
    }
    const startIndex = cursor;
    const endIndex = cursor + pointCount - 1;
    markAreaData.push([
      {
        name: segment.session,
        xAxis: startIndex,
        itemStyle: { color: `${segment.color}12` },
        label: { color: "#95a3b8", fontFamily: "JetBrains Mono", fontSize: 10 },
      },
      { xAxis: endIndex },
    ]);
    cursor += pointCount;
  }

  return {
    animation: false,
    backgroundColor: "transparent",
    textStyle: {
      color: "#f1f3fc",
      fontFamily: "JetBrains Mono, monospace",
    },
    legend: { show: false },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      backgroundColor: "rgba(17, 23, 34, 0.94)",
      borderColor: "rgba(153, 247, 255, 0.16)",
      textStyle: { color: "#f1f3fc" },
    },
    axisPointer: {
      link: [{ xAxisIndex: [0, 1] }],
      label: { backgroundColor: "#20262f" },
    },
    grid: [
      { left: 18, right: 64, top: 18, height: "68%" },
      { left: 18, right: 64, top: "79%", height: "14%" },
    ],
    xAxis: [
      {
        type: "category",
        data: categories,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "rgba(149,163,184,0.18)" } },
        axisLabel: {
          color: "#95a3b8",
          hideOverlap: true,
          formatter: (_, index) => {
            const step = xAxisStep(categories.length);
            return index % step === 0 ? categories[index] : "";
          },
        },
        splitLine: { show: false },
        min: "dataMin",
        max: "dataMax",
      },
      {
        type: "category",
        gridIndex: 1,
        data: categories,
        boundaryGap: true,
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "rgba(149,163,184,0.18)" } },
      },
    ],
    yAxis: [
      {
        scale: true,
        splitNumber: 4,
        position: "right",
        axisLine: { show: false },
        axisLabel: { color: "#c7d0dd" },
        splitLine: { lineStyle: { color: "rgba(149,163,184,0.12)" } },
      },
      {
        scale: true,
        gridIndex: 1,
        position: "right",
        axisLine: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 0, end: 100 },
      {
        type: "slider",
        xAxisIndex: [0, 1],
        bottom: 4,
        height: 14,
        borderColor: "transparent",
        backgroundColor: "rgba(32, 38, 47, 0.68)",
        fillerColor: "rgba(153, 247, 255, 0.18)",
        moveHandleStyle: { color: "#99f7ff" },
        textStyle: { color: "#95a3b8" },
      },
    ],
    series: [
      {
        name: "Price",
        type: "candlestick",
        data: candleData,
        itemStyle: {
          color: palette.up,
          color0: palette.down,
          borderColor: palette.up,
          borderColor0: palette.down,
        },
        markArea: {
          silent: true,
          data: markAreaData,
        },
      },
      {
        name: "Volume",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeData,
      },
    ],
  };
}

function autoInterval(length) {
  return xAxisStep(length) - 1;
}

function xAxisStep(length) {
  if (length > 90) {
    return 10;
  }
  if (length > 70) {
    return 8;
  }
  if (length > 50) {
    return 6;
  }
  if (length > 30) {
    return 4;
  }
  if (length > 18) {
    return 2;
  }
  return 1;
}

function diffClass(diff) {
  if (!diff) {
    return "";
  }
  const text = String(diff).trim();
  if (text.startsWith("+")) {
    return "delta-positive";
  }
  if (text.startsWith("-")) {
    return "delta-negative";
  }
  return "";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

refreshData();
