const state = {
  session: false,
  market: "kr",
  artifacts: [],
  watchlist: [],
  activeView: "generate",
  latestArtifact: null,
  csrfToken: null,
};

const app = document.querySelector("#app");

function render() {
  app.innerHTML = `
    <div class="shell">
      <aside class="sidebar">
        <div class="brand">
          <div class="eyebrow">Obsidian Terminal</div>
          <h1>KIS Command Center</h1>
          <div class="muted">CLI는 그대로 두고, 웹에서 생성과 watchlist를 관리합니다.</div>
        </div>
        <nav class="nav">
          <button class="${state.activeView === "generate" ? "active" : ""}" data-view="generate">Generate</button>
          <button class="${state.activeView === "watchlist" ? "active" : ""}" data-view="watchlist">Watchlist</button>
          <button class="${state.activeView === "artifacts" ? "active" : ""}" data-view="artifacts">Artifacts</button>
        </nav>
      </aside>
      <main class="content">
        <section class="topbar">
          <div>
            <div class="eyebrow">Terminal Session</div>
            <strong>${state.session ? "Authenticated" : "Locked"}</strong>
            <div class="muted">Market-aware dashboard generation and artifact tracking.</div>
          </div>
          <div class="topbar-stats">
            <div class="stat">
              <label>Active Market</label>
              <strong class="mono">${state.market.toUpperCase()}</strong>
            </div>
            <div class="stat">
              <label>Artifacts</label>
              <strong class="mono">${state.artifacts.length}</strong>
            </div>
          </div>
        </section>
        ${state.session ? renderAuthenticated() : renderLogin()}
      </main>
    </div>
  `;

  bindEvents();
}

function renderLogin() {
  return `
    <section class="panel" style="max-width: 460px;">
      <div class="stack">
        <div>
          <div class="eyebrow">Access</div>
          <h2>관리자 로그인</h2>
          <p class="muted">세션 쿠키 기반으로 API를 잠급니다.</p>
        </div>
        <form id="login-form" class="stack">
          <div class="field">
            <label>Password</label>
            <input name="password" type="password" placeholder="dashboard password" required />
          </div>
          <div class="actions">
            <button class="button primary" type="submit">Open Session</button>
          </div>
          <div id="login-status" class="status"></div>
        </form>
      </div>
    </section>
  `;
}

function renderAuthenticated() {
  return `
    <section class="dashboard">
      <section class="panel stack">
        <div>
          <div class="eyebrow">Control Plane</div>
          <h2>Generate Dashboard</h2>
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
              <input name="interval_minutes" type="number" value="10" min="1" />
            </div>
            <div class="field">
              <label>Candle Width Scale</label>
              <input name="candle_width_scale" type="number" step="0.1" value="1.0" min="0.3" max="2" />
            </div>
            <div class="field">
              <label>Width PX</label>
              <input name="width_px" type="number" value="1080" min="480" />
            </div>
            <div class="field">
              <label>Height PX</label>
              <input name="height_px" type="number" placeholder="auto" min="480" />
            </div>
            <div class="field">
              <label>Render Scale</label>
              <input name="render_scale" type="number" value="2.0" step="0.1" min="1" />
            </div>
            <div class="field">
              <label>WEBP Quality</label>
              <input name="webp_quality" type="number" value="90" min="1" max="100" />
            </div>
          </div>
          <div class="actions">
            <button class="button primary" type="submit">Generate Artifact</button>
            <button class="button secondary" type="button" id="refresh-artifacts">Refresh Artifacts</button>
            <button class="button secondary" type="button" id="logout-button">Logout</button>
          </div>
          <div id="generate-status" class="status"></div>
        </form>

        <div class="stack ${state.activeView === "generate" ? "" : "hidden"}">
          <div>
            <div class="eyebrow">Market Snapshot</div>
            <h3>Latest Artifact</h3>
          </div>
          ${renderLatestArtifact()}
        </div>
      </section>

      <section class="stack">
        <section class="panel stack ${state.activeView === "watchlist" ? "" : "hidden"}">
          <div>
            <div class="eyebrow">Watchlist</div>
            <h2>${state.market.toUpperCase()} Symbols</h2>
          </div>
          <form id="watchlist-form" class="grid">
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
            <div class="actions">
              <button class="button primary" type="submit">Add Symbol</button>
            </div>
          </form>
          <div id="watchlist" class="watchlist-list">${renderWatchlistItems()}</div>
        </section>

        <section class="panel stack ${state.activeView === "generate" ? "" : "hidden"}">
          <div>
            <div class="eyebrow">Preview</div>
            <h2>Artifact Surface</h2>
          </div>
          <div class="preview">${renderPreview()}</div>
        </section>

        <section class="panel stack ${state.activeView === "artifacts" ? "" : "hidden"}">
          <div>
            <div class="eyebrow">Artifacts</div>
            <h2>Recent Runs</h2>
          </div>
          <div id="artifacts" class="artifacts">${renderArtifacts()}</div>
        </section>
      </section>
    </section>
  `;
}

function renderLatestArtifact() {
  if (!state.latestArtifact) {
    return `<div class="summary-grid"><div class="summary-card"><strong>No artifact yet</strong><span class="muted">Run generate to populate preview and artifacts.</span></div></div>`;
  }
  return `
    <div class="summary-grid">
      <div class="summary-card"><div class="eyebrow">Market</div><strong class="mono">${state.latestArtifact.market.toUpperCase()}</strong></div>
      <div class="summary-card"><div class="eyebrow">Format</div><strong class="mono">${state.latestArtifact.format.toUpperCase()}</strong></div>
      <div class="summary-card"><div class="eyebrow">Interval</div><strong class="mono">${state.latestArtifact.interval_minutes}m</strong></div>
      <div class="summary-card"><div class="eyebrow">Stocks</div><strong class="mono">${state.latestArtifact.stock_count}</strong></div>
      <div class="summary-card"><div class="eyebrow">Summary</div><strong class="mono">${state.latestArtifact.summary_count}</strong></div>
    </div>
  `;
}

function renderArtifacts() {
  if (!state.artifacts.length) {
    return `<div class="artifact-card"><strong>No artifacts</strong><span class="muted">Generated outputs will appear here.</span></div>`;
  }
  return state.artifacts
    .map(
      (artifact) => `
      <div class="artifact-card">
        <div class="watchlist-row">
          <div>
            <strong>${artifact.market.toUpperCase()} ${artifact.format.toUpperCase()}</strong>
            <div class="muted mono">${artifact.created_at}</div>
          </div>
          <a class="button secondary" href="${artifact.preview_url}" target="_blank" rel="noreferrer">Download</a>
        </div>
      </div>`
    )
    .join("");
}

function renderWatchlistItems() {
  if (!state.watchlist.length) {
    return `<div class="watchlist-item"><strong>No symbols</strong><span class="muted">Add the first symbol for ${state.market.toUpperCase()}.</span></div>`;
  }
  return state.watchlist
    .map(
      (item) => `
        <div class="watchlist-item">
          <div class="watchlist-row">
            <div>
              <strong>${item.name}</strong>
              <div class="muted mono">${item.code}${item.excd ? ` · ${item.excd}` : ""}</div>
            </div>
            <button class="button danger" data-remove="${item.code}">Remove</button>
          </div>
        </div>`
    )
    .join("");
}

function renderPreview() {
  if (!state.latestArtifact) {
    return `<div class="muted">No preview yet.</div>`;
  }
  return `<img src="${state.latestArtifact.preview_url}" alt="latest artifact preview" />`;
}

function bindEvents() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeView = button.dataset.view;
      render();
    });
  });

  const loginForm = document.querySelector("#login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", handleLogin);
  }

  const generateForm = document.querySelector("#generate-form");
  if (generateForm) {
    generateForm.addEventListener("submit", handleGenerate);
    generateForm.market?.addEventListener("change", async (event) => {
      state.market = event.target.value;
      await refreshData();
    });
  }

  const watchlistForm = document.querySelector("#watchlist-form");
  if (watchlistForm) {
    watchlistForm.addEventListener("submit", handleWatchlistAdd);
  }

  document.querySelector("#refresh-artifacts")?.addEventListener("click", refreshData);
  document.querySelector("#logout-button")?.addEventListener("click", handleLogout);
  document.querySelectorAll("[data-remove]").forEach((button) => {
    button.addEventListener("click", () => removeWatchlist(button.dataset.remove));
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
  state.csrfToken = null;
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
  const data = await response.json();
  state.latestArtifact = data.artifact;
  status.textContent = "Artifact generated.";
  await refreshData(false);
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
  }
}

async function removeWatchlist(code) {
  const params = new URLSearchParams({ market: state.market });
  await fetch(`/api/watchlist/${encodeURIComponent(code)}?${params.toString()}`, {
    method: "DELETE",
    headers: { "X-CSRF-Token": state.csrfToken },
  });
  await loadWatchlist();
}

async function refreshData(renderAfter = true) {
  const session = await fetch("/api/session");
  state.session = session.ok;
  if (!state.session) {
    render();
    return;
  }
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
  state.latestArtifact = payload.artifacts[0] || state.latestArtifact;
}

async function loadWatchlist() {
  const response = await fetch(`/api/watchlist?market=${state.market}`);
  if (!response.ok) {
    return;
  }
  const payload = await response.json();
  state.watchlist = payload.items;
}

refreshData();
render();
