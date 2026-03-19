const state = {
  session: false,
  market: "kr",
  watchlist: [],
  activeView: "dashboard",
  dashboardData: null,
  selectedStockIndex: 0,
  csrfToken: null,
  intervalMinutes: 10,
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
            <p>웹 백엔드가 직접 KIS를 조회합니다.</p>
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
          <p>Live KIS dashboard with direct backend market queries and editable watchlists.</p>
        </section>

        <section class="rail-cluster">
          <nav class="nav">
            <button class="${state.activeView === "dashboard" ? "active" : ""}" data-view="dashboard">Dashboard</button>
            <button class="${state.activeView === "watchlist" ? "active" : ""}" data-view="watchlist">Watchlist</button>
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
              <label>Interval</label>
              <strong class="mono">${state.intervalMinutes}m</strong>
            </div>
            <div class="status-chip">
              <label>Symbols</label>
              <strong class="mono">${state.watchlist.length}</strong>
            </div>
          </div>
        </section>

        <section class="rail-scroll">
          ${state.activeView === "watchlist" ? renderWatchlistControl() : renderDashboardControl()}
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
            <span class="pill mono">${state.dashboardData ? `${state.dashboardData.interval_minutes}M LIVE` : "NO DATA"}</span>
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
                <div class="eyebrow">Live Meta</div>
                <h3>Dashboard State</h3>
              </div>
              <div class="artifacts">${renderDashboardMeta()}</div>
            </section>
          </section>
        </section>
      </main>
    </div>
  `;
}

function renderDashboardControl() {
  return `
    <section class="rail-module">
      <div class="module-head">
        <div class="eyebrow">Control Plane</div>
        <h2>Refresh Dashboard</h2>
        <p>백엔드가 직접 KIS를 조회해서 live payload를 반환합니다.</p>
      </div>
      <form id="dashboard-form" class="stack">
        <div class="grid">
          <div class="field">
            <label>Market</label>
            <select name="market">
              <option value="kr" ${state.market === "kr" ? "selected" : ""}>KR</option>
              <option value="us" ${state.market === "us" ? "selected" : ""}>US</option>
            </select>
          </div>
          <div class="field">
            <label>Interval Minutes</label>
            <input name="interval_minutes" type="number" value="${state.intervalMinutes}" min="1" />
          </div>
        </div>
        <div class="actions">
          <button class="button primary full" type="submit">Refresh Dashboard</button>
          <button class="button secondary" type="button" id="refresh-dashboard">Refresh</button>
          <button class="button secondary" type="button" id="logout-button">Logout</button>
        </div>
        <div id="dashboard-status" class="status"></div>
      </form>
    </section>
  `;
}

function renderWatchlistControl() {
  return `
    <section class="rail-module">
      <div class="module-head">
        <div class="eyebrow">Symbol Control</div>
        <h2>Watchlist</h2>
        <p>Market-specific symbol inventory for the live dashboard.</p>
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
          <button class="button secondary full" type="button" id="logout-button">Logout</button>
        </div>
      </form>
    </section>
  `;
}

function renderTopbarTitle() {
  if (!state.dashboardData) {
    return "No Dashboard Loaded";
  }
  return state.dashboardData.title || `${state.market.toUpperCase()} Dashboard`;
}

function renderTopbarSubtitle() {
  if (!state.dashboardData) {
    return "Refresh the live dashboard to hydrate summary cards and intraday chart data.";
  }
  return `${state.dashboardData.subtitle || ""} · ${state.dashboardData.generated_at || ""}`;
}

function renderSummaryStrip() {
  const cards = state.dashboardData?.summary_cards || [];
  if (!cards.length) {
    return `<div class="empty-state">Summary cards will appear after the first live refresh.</div>`;
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
  const cards = state.dashboardData?.stock_cards || [];
  const selected = cards[state.selectedStockIndex] || cards[0];
  if (!selected) {
    return `<div class="empty-state">No stock chart data in the selected dashboard yet.</div>`;
  }
  return `
    <div class="hero-header">
      <div class="hero-title-block">
        <div class="hero-title-row">
          <span class="hero-symbol">${escapeHtml(selected.market || state.market.toUpperCase())}</span>
          <span class="ghost-chip">${(selected.chart?.interval_minutes || state.intervalMinutes)}m candles</span>
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
      <span class="ghost-chip">${escapeHtml(state.dashboardData?.generated_at || "")}</span>
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

function renderDashboardMeta() {
  if (!state.dashboardData) {
    return `<div class="empty-state">Live dashboard metadata will appear here after refresh.</div>`;
  }
  return `
    <article class="artifact-card">
      <div class="artifact-row">
        <div>
          <strong>${escapeHtml(state.dashboardData.market.toUpperCase())} LIVE</strong>
          <div class="muted mono">${escapeHtml(state.dashboardData.generated_at)}</div>
        </div>
      </div>
    </article>
    <article class="artifact-card">
      <div class="artifact-row">
        <div>
          <strong>${state.dashboardData.summary_cards.length} Summary Cards</strong>
          <div class="muted mono">${state.dashboardData.stock_cards.length} Symbols</div>
        </div>
      </div>
    </article>
  `;
}

function bindEvents() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeView = button.dataset.view;
      render();
    });
  });
  document.querySelector("#login-form")?.addEventListener("submit", handleLogin);
  const dashboardForm = document.querySelector("#dashboard-form");
  if (dashboardForm) {
    dashboardForm.addEventListener("submit", handleDashboardRefresh);
    dashboardForm.market?.addEventListener("change", async (event) => {
      state.market = event.target.value;
      await refreshData();
    });
  }
  document.querySelector("#watchlist-form")?.addEventListener("submit", handleWatchlistAdd);
  document.querySelector("#refresh-dashboard")?.addEventListener("click", () => loadDashboard(true));
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
  state.watchlist = [];
  state.dashboardData = null;
  state.selectedStockIndex = 0;
  state.csrfToken = null;
  disposeChart();
  render();
}

async function handleDashboardRefresh(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  state.market = form.get("market");
  state.intervalMinutes = Number(form.get("interval_minutes") || 10);
  await loadDashboard(true);
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
    await Promise.all([loadWatchlist(), loadDashboard()]);
    render();
  }
}

async function removeWatchlist(code) {
  const params = new URLSearchParams({ market: state.market });
  await fetch(`/api/watchlist/${encodeURIComponent(code)}?${params.toString()}`, {
    method: "DELETE",
    headers: { "X-CSRF-Token": state.csrfToken },
  });
  await Promise.all([loadWatchlist(), loadDashboard()]);
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
  await Promise.all([loadWatchlist(), loadDashboard()]);
  render();
}

async function loadWatchlist() {
  const response = await fetch(`/api/watchlist?market=${state.market}`);
  if (!response.ok) {
    return;
  }
  const payload = await response.json();
  state.watchlist = payload.items;
}

async function loadDashboard(renderAfter = false) {
  const status = document.querySelector("#dashboard-status");
  if (status) {
    status.textContent = "Refreshing live dashboard...";
  }
  const params = new URLSearchParams({
    market: state.market,
    interval_minutes: String(state.intervalMinutes),
  });
  const response = await fetch(`/api/dashboard?${params.toString()}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Dashboard refresh failed." }));
    if (status) {
      status.textContent = error.detail || "Dashboard refresh failed.";
    }
    return;
  }
  state.dashboardData = await response.json();
  state.intervalMinutes = Number(state.dashboardData.interval_minutes || state.intervalMinutes);
  state.selectedStockIndex = 0;
  if (status) {
    status.textContent = "Dashboard refreshed.";
  }
  if (renderAfter) {
    render();
  }
}

function disposeChart() {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
}

function mountHeroChart() {
  const host = document.querySelector("#chart-host");
  const chartData = state.dashboardData?.stock_cards?.[state.selectedStockIndex]?.chart;
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
  const palette = state.market === "us" ? { up: "#33d17a", down: "#ff5c7a" } : { up: "#ff6b6b", down: "#4c9bff" };
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
    if (!pointCount) continue;
    const startIndex = cursor;
    const endIndex = cursor + pointCount - 1;
    markAreaData.push([
      {
        name: segment.session,
        xAxis: startIndex,
        itemStyle: { color: `${segment.color}12` },
        label: { color: "#95a3b8", fontFamily: "SF Mono", fontSize: 10 },
      },
      { xAxis: endIndex },
    ]);
    cursor += pointCount;
  }
  return {
    animation: false,
    backgroundColor: "transparent",
    textStyle: { color: "#f1f3fc", fontFamily: "SF Mono, ui-monospace, monospace" },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      backgroundColor: "rgba(17, 23, 34, 0.94)",
      borderColor: "rgba(255,255,255,0.12)",
      textStyle: { color: "#f1f3fc" },
    },
    axisPointer: { link: [{ xAxisIndex: [0, 1] }], label: { backgroundColor: "#20262f" } },
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
        markArea: { silent: true, data: markAreaData },
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

function xAxisStep(length) {
  if (length > 90) return 10;
  if (length > 70) return 8;
  if (length > 50) return 6;
  if (length > 30) return 4;
  if (length > 18) return 2;
  return 1;
}

function diffClass(diff) {
  if (!diff) return "";
  const text = String(diff).trim();
  if (text.startsWith("+")) return "delta-positive";
  if (text.startsWith("-")) return "delta-negative";
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
