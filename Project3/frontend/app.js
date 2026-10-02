/**
 * Main Application JavaScript — Project 3 (Phase 3)
 * Nutritional Insights Cloud Dashboard
 *
 * Handles: auth state, chart rendering, API calls, diet filter,
 * keyword search (debounced), pagination, and logout.
 */

/* ------------------------------------------------------------------
 * Configuration
 * ----------------------------------------------------------------*/
// Resolved by config.js, which deploy.sh rewrites with the Function App URL.
const API_BASE = window.API_BASE;

/* ------------------------------------------------------------------
 * State
 * ----------------------------------------------------------------*/
let currentPage = 1;
let currentPageSize = 20;
let currentDiet = "";
let currentSearch = "";
let debounceTimer = null;
let chartsInitialized = false;

// Chart instances (so we can destroy & rebuild)
let barChart = null;
let pieChart = null;
let heatmapChart = null;
let scatterChart = null;

/* Palette for diets */
const DIET_COLORS = {
  dash:          { bg: "rgba(59,130,246,0.7)",  border: "#2563eb" },
  keto:          { bg: "rgba(236,72,153,0.7)",  border: "#db2777" },
  mediterranean: { bg: "rgba(16,185,129,0.7)",  border: "#059669" },
  paleo:         { bg: "rgba(245,158,11,0.7)",  border: "#d97706" },
  vegan:         { bg: "rgba(139,92,246,0.7)",  border: "#7c3aed" },
};

const DIET_BG = Object.values(DIET_COLORS).map(c => c.bg);
const DIET_BORDER = Object.values(DIET_COLORS).map(c => c.border);

/* There is deliberately no sample dataset here.  Sample numbers that mirror
 * the real result set make an empty cache look identical to a working one,
 * and proving that results come from the cache is the point of this phase.
 * When the API has nothing cached it says so, and the page shows that. */

/* ------------------------------------------------------------------
 * Initialization
 * ----------------------------------------------------------------*/
document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});

async function initDashboard() {
  // Check auth
  if (!isAuthenticated()) {
    window.location.href = "login.html";
    return;
  }

  // Show user name
  const user = getCurrentUser();
  const nameEl = document.getElementById("userName");
  if (nameEl && user) {
    nameEl.textContent = user.name || user.email || "User";
  }

  // Bind controls
  const dietFilter = document.getElementById("dietFilter");
  const searchInput = document.getElementById("searchInput");

  if (dietFilter) {
    dietFilter.addEventListener("change", () => {
      currentDiet = dietFilter.value;
      currentPage = 1;
      loadRecipes();
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentSearch = searchInput.value.trim();
        currentPage = 1;
        loadRecipes();
      }, 350);
    });
  }

  // Load data
  await Promise.all([loadInsights(), loadRecipes()]);
  updateSecurityStatus();
}

/* ------------------------------------------------------------------
 * Load Insights (charts)
 * ----------------------------------------------------------------*/
async function loadInsights() {
  let json = null;
  let responseTime = 0;

  try {
    const start = performance.now();
    const resp = await authFetch(API_BASE + "/insights");
    responseTime = Math.round(performance.now() - start);

    if (resp.status === 401) return redirectToLogin();

    json = await resp.json();
    if (!resp.ok) {
      showBanner(json.error || `Insights unavailable (${resp.status}).`);
      updateStatusBar("unavailable", responseTime, 0);
      return;
    }
  } catch (err) {
    console.error("Insights request failed:", err);
    showBanner("Cannot reach the API. Check that it is running and that " +
               "CORS allows this origin.");
    updateStatusBar("unreachable", 0, 0);
    return;
  }

  const data = json.data || {};
  clearBanner();
  updateStatusBar(json.source || "cache",
                  json.response_time_ms || responseTime,
                  data.total_recipes || 0);
  populateDietFilter(data.diet_types || []);

  renderBarChart(data);
  renderPieChart(data);
  renderHeatmap(data);
  renderScatter(data);
  chartsInitialized = true;
}

/**
 * Fill the diet dropdown from the cached dataset rather than a hardcoded
 * list, so the filter stays correct if the dataset changes.
 */
function populateDietFilter(dietTypes) {
  const select = document.getElementById("dietFilter");
  if (!select || !dietTypes.length) return;

  const previous = select.value;
  select.innerHTML = '<option value="">All Diet Types</option>' +
    dietTypes.map(d =>
      `<option value="${escapeHtml(d)}">${escapeHtml(
        d.charAt(0).toUpperCase() + d.slice(1))}</option>`
    ).join("");
  if (dietTypes.includes(previous)) select.value = previous;
}

/* ------------------------------------------------------------------
 * Load Recipes (table with search/filter/pagination)
 * ----------------------------------------------------------------*/
async function loadRecipes() {
  const params = new URLSearchParams();
  if (currentDiet) params.set("diet", currentDiet);
  if (currentSearch) params.set("search", currentSearch);
  params.set("page", currentPage);
  params.set("pageSize", currentPageSize);

  let result = null;
  try {
    const resp = await authFetch(API_BASE + "/recipes?" + params.toString());
    if (resp.status === 401) return redirectToLogin();

    result = await resp.json();
    if (!resp.ok) {
      showTableMessage(result.error || `Recipes unavailable (${resp.status}).`);
      renderPagination({ page: 1, totalPages: 1, total: 0 });
      return;
    }
  } catch (err) {
    console.error("Recipes request failed:", err);
    showTableMessage("Cannot reach the API.");
    renderPagination({ page: 1, totalPages: 1, total: 0 });
    return;
  }

  renderRecipeTable(result.results || []);
  renderPagination(result);
}

/* ------------------------------------------------------------------
 * Error surfaces
 * ----------------------------------------------------------------*/

function showBanner(message) {
  let el = document.getElementById("dataBanner");
  if (!el) {
    el = document.createElement("div");
    el.id = "dataBanner";
    el.className = "data-banner";
    const body = document.querySelector(".dashboard-body");
    const status = document.getElementById("statusBar");
    if (body) body.insertBefore(el, status ? status.nextSibling : body.firstChild);
  }
  el.textContent = message;
  el.style.display = "block";
}

function clearBanner() {
  const el = document.getElementById("dataBanner");
  if (el) el.style.display = "none";
}

function showTableMessage(message) {
  const tbody = document.getElementById("recipeBody");
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="7" class="no-results"></td></tr>';
    tbody.querySelector("td").textContent = message;
  }
}

function redirectToLogin() {
  clearToken();
  window.location.replace("login.html");
}

/* ------------------------------------------------------------------
 * Chart Rendering
 * ----------------------------------------------------------------*/

function renderBarChart(data) {
  const ctx = document.getElementById("barChart");
  if (!ctx) return;
  if (barChart) barChart.destroy();

  const macros = data.average_macros || {};
  const diets = Object.keys(macros);

  barChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: diets.map(d => d.charAt(0).toUpperCase() + d.slice(1)),
      datasets: [
        {
          label: "Protein (g)",
          data: diets.map(d => macros[d].Protein),
          backgroundColor: "rgba(59,130,246,0.75)",
          borderColor: "#2563eb",
          borderWidth: 1.5,
        },
        {
          label: "Carbs (g)",
          data: diets.map(d => macros[d].Carbs),
          backgroundColor: "rgba(16,185,129,0.75)",
          borderColor: "#059669",
          borderWidth: 1.5,
        },
        {
          label: "Fat (g)",
          data: diets.map(d => macros[d].Fat),
          backgroundColor: "rgba(245,158,11,0.75)",
          borderColor: "#d97706",
          borderWidth: 1.5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: { display: false },
        legend: { position: "bottom", labels: { padding: 15, usePointStyle: true } },
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: "Grams per recipe" } },
      },
    },
  });
}

function renderPieChart(data) {
  const ctx = document.getElementById("pieChart");
  if (!ctx) return;
  if (pieChart) pieChart.destroy();

  const counts = data.recipe_counts || {};
  const diets = Object.keys(counts);

  pieChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: diets.map(d => d.charAt(0).toUpperCase() + d.slice(1)),
      datasets: [{
        data: diets.map(d => counts[d]),
        backgroundColor: DIET_BG,
        borderColor: DIET_BORDER,
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { padding: 15, usePointStyle: true } },
      },
    },
  });
}

function renderHeatmap(data) {
  const ctx = document.getElementById("heatmapChart");
  if (!ctx) return;
  if (heatmapChart) heatmapChart.destroy();

  const hm = data.heatmap || data;
  const diets = hm.diets || Object.keys(data.average_macros || {});
  const nutrients = ["Protein", "Carbs", "Fat"];
  const values = hm.values || [];

  // Build bubble-style heatmap using scatter with point sizes.
  // Guard the divisor: Math.max() of an empty array is -Infinity, and an
  // all-zero macro column would make every radius NaN, which Chart.js drops.
  const points = [];
  const flat = values.flat().filter(Number.isFinite);
  const maxVal = flat.length ? Math.max(...flat) : 0;
  const scale = maxVal > 0 ? maxVal : 1;

  for (let row = 0; row < values.length; row++) {
    for (let col = 0; col < (values[row] || []).length; col++) {
      const val = values[row][col];
      points.push({ x: col, y: row, r: Math.max(8, (val / scale) * 30), v: val });
    }
  }

  heatmapChart = new Chart(ctx, {
    type: "bubble",
    data: {
      datasets: [{
        data: points,
        backgroundColor: points.map(p => {
          const ratio = p.v / scale;
          const r = Math.round(37 + ratio * 180);
          const g = Math.round(99 + (1 - ratio) * 100);
          const b = Math.round(235 - ratio * 100);
          return `rgba(${r},${g},${b},0.75)`;
        }),
        borderColor: "rgba(30,58,95,0.3)",
        borderWidth: 1,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const p = ctx.raw;
              const diet = diets[p.y] || "";
              const nut = nutrients[p.x] || "";
              return `${diet} - ${nut}: ${p.v}g`;
            },
          },
        },
      },
      scales: {
        x: {
          type: "linear",
          min: -0.5,
          max: nutrients.length - 0.5,
          ticks: {
            stepSize: 1,
            callback: (val) => nutrients[val] || "",
          },
          title: { display: true, text: "Nutrient" },
        },
        y: {
          type: "linear",
          min: -0.5,
          max: diets.length - 0.5,
          ticks: {
            stepSize: 1,
            callback: (val) => {
              const d = diets[val] || "";
              return d.charAt(0).toUpperCase() + d.slice(1);
            },
          },
          title: { display: true, text: "Diet Type" },
        },
      },
    },
  });
}

/** First argument that is a finite number, else 0. */
function firstNumber(...candidates) {
  for (const c of candidates) {
    if (Number.isFinite(c)) return c;
  }
  return 0;
}

function renderScatter(data) {
  const ctx = document.getElementById("scatterChart");
  if (!ctx) return;
  if (scatterChart) scatterChart.destroy();

  const topRecipes = data.top_recipes || [];
  const dietGroups = {};

  topRecipes.forEach(r => {
    const diet = r.diet || r.Diet_type || "unknown";
    if (!dietGroups[diet]) dietGroups[diet] = [];
    // `||` would treat a legitimate 0 g as absent and fall through to the
    // next alternative, so pick the first key that is actually a number.
    dietGroups[diet].push({
      x: firstNumber(r.carbs, r["Carbs(g)"]),
      y: firstNumber(r.protein, r["Protein(g)"]),
      label: r.recipe || r.Recipe_name || "",
    });
  });

  const datasets = Object.entries(dietGroups).map(([diet, points], i) => {
    const colors = DIET_COLORS[diet] || { bg: DIET_BG[i % DIET_BG.length], border: DIET_BORDER[i % DIET_BORDER.length] };
    return {
      label: diet.charAt(0).toUpperCase() + diet.slice(1),
      data: points,
      backgroundColor: colors.bg,
      borderColor: colors.border,
      borderWidth: 1.5,
      pointRadius: 6,
      pointHoverRadius: 9,
    };
  });

  scatterChart = new Chart(ctx, {
    type: "scatter",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { padding: 15, usePointStyle: true } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const p = ctx.raw;
              return `${p.label}: P=${p.y}g, C=${p.x}g`;
            },
          },
        },
      },
      scales: {
        x: { title: { display: true, text: "Carbs (g)" }, beginAtZero: true },
        y: { title: { display: true, text: "Protein (g)" }, beginAtZero: true },
      },
    },
  });
}

/* ------------------------------------------------------------------
 * Recipe Table
 * ----------------------------------------------------------------*/
function renderRecipeTable(recipes) {
  const tbody = document.getElementById("recipeBody");
  if (!tbody) return;

  if (!recipes || recipes.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="no-results">No recipes found. Try adjusting your search or filter.</td></tr>';
    return;
  }

  tbody.innerHTML = recipes.map((r, i) => {
    // Every interpolated value originates in the uploaded CSV. clean_data
    // strips and casefolds the text columns but does not sanitise markup, so
    // escaping here is what stops a crafted Diet_type from breaking out of the
    // class attribute and reading the token out of localStorage.
    const diet = escapeHtml((r.Diet_type || "").toLowerCase());
    return `<tr>
      <td>${(currentPage - 1) * currentPageSize + i + 1}</td>
      <td>${escapeHtml(r.Recipe_name || "")}</td>
      <td><span class="diet-badge ${diet}">${diet}</span></td>
      <td>${escapeHtml(r.Cuisine_type || "")}</td>
      <td>${escapeHtml(formatMacro(r["Protein(g)"]))}</td>
      <td>${escapeHtml(formatMacro(r["Carbs(g)"]))}</td>
      <td>${escapeHtml(formatMacro(r["Fat(g)"]))}</td>
    </tr>`;
  }).join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Render a macronutrient cell. A plain `value || 0` would be fine for a real
 * 0 but would also print "0" for a missing value, claiming a measurement that
 * was never there; an em dash says "not available" instead.
 */
function formatMacro(value) {
  // The API sends JSON numbers, but accept a numeric string too so a
  // hand-edited cache document still renders instead of reading as missing.
  // 44 rows in the dataset hold a legitimate 0 g macro, so 0 must print as 0.
  const n = typeof value === "number" ? value
          : (typeof value === "string" && value.trim() !== "" ? Number(value)
                                                             : NaN);
  return Number.isFinite(n) ? String(n) : "\u2014";
}

/* ------------------------------------------------------------------
 * Pagination
 * ----------------------------------------------------------------*/
function renderPagination(result) {
  const container = document.getElementById("pagination");
  if (!container) return;

  const { page, totalPages, total, hasNext, hasPrev } = result;
  if (totalPages <= 1) {
    container.innerHTML = `<span class="page-info">Showing ${total} recipe${total !== 1 ? "s" : ""}</span>`;
    return;
  }

  let html = "";

  // Previous button
  html += `<button ${hasPrev ? "" : "disabled"} onclick="goToPage(${page - 1})">Previous</button>`;

  // Page numbers
  const maxButtons = 7;
  let start = Math.max(1, page - 3);
  let end = Math.min(totalPages, start + maxButtons - 1);
  start = Math.max(1, end - maxButtons + 1);

  if (start > 1) {
    html += `<button onclick="goToPage(1)">1</button>`;
    if (start > 2) html += `<span class="page-info">...</span>`;
  }

  for (let p = start; p <= end; p++) {
    html += `<button class="${p === page ? "active" : ""}" onclick="goToPage(${p})">${p}</button>`;
  }

  if (end < totalPages) {
    if (end < totalPages - 1) html += `<span class="page-info">...</span>`;
    html += `<button onclick="goToPage(${totalPages})">${totalPages}</button>`;
  }

  // Next button
  html += `<button ${hasNext ? "" : "disabled"} onclick="goToPage(${page + 1})">Next</button>`;

  // Info
  html += `<span class="page-info">${total} total</span>`;

  container.innerHTML = html;
}

function goToPage(p) {
  currentPage = p;
  loadRecipes();
  // Scroll to table
  const table = document.querySelector(".table-section");
  if (table) table.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ------------------------------------------------------------------
 * Status Bar
 * ----------------------------------------------------------------*/
/**
 * The source pill is the evidence that a request was served from the cache
 * rather than recalculated, so it names the store the API actually read.
 */
function updateStatusBar(source, responseTime, totalRecipes) {
  const el = document.getElementById("statusBar");
  if (!el) return;

  const label = {
    redis: "Served from Redis",
    cosmosdb: "Served from Cosmos DB",
    memory: "Served from in-process cache",
    fallback: "Sample data (ENABLE_DEMO_FALLBACK is on)",
    unavailable: "Cache empty",
    unreachable: "API unreachable",
  }[source] || `Served from ${source}`;

  el.innerHTML = `
    <span class="status-pill"><span class="dot"></span> ${escapeHtml(label)}</span>
    <span class="status-pill">${responseTime}ms response</span>
    <span class="status-pill">${Number(totalRecipes || 0).toLocaleString()} recipes</span>
  `;
}

/* ------------------------------------------------------------------
 * Security Status
 * ----------------------------------------------------------------*/
/**
 * Fill the security cards from /api/health so they report the backend's live
 * configuration. Asserting "AES-256" in the markup proves nothing; if no
 * database is configured, this says so.
 */
async function updateSecurityStatus() {
  const user = getCurrentUser();
  const token = getToken();

  setSecurityCard("secAuth", user
    ? `Signed in as ${user.email || user.name}`
    : "Not authenticated");

  const claims = token ? decodeJWT(token) : null;
  if (claims && claims.exp) {
    const hoursLeft = Math.round((claims.exp * 1000 - Date.now()) / 3600000);
    setSecurityCard("secJWT", `Valid (${hoursLeft}h remaining)`);
  } else {
    setSecurityCard("secJWT", token ? "Active" : "None");
  }

  try {
    const resp = await authFetch(API_BASE + "/health");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const security = (await resp.json()).security || {};
    setSecurityCard("secEncrypt", security.encryption_at_rest || "Unknown");
    setSecurityCard("secHash", security.password_hashing || "Unknown");
  } catch (err) {
    console.warn("Could not read backend security status:", err.message);
    setSecurityCard("secEncrypt", "Unknown (API unreachable)");
    setSecurityCard("secHash", "Unknown (API unreachable)");
  }
}

function setSecurityCard(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

/* ------------------------------------------------------------------
 * Logout
 * ----------------------------------------------------------------*/
function handleLogout() {
  // Call logout endpoint (fire and forget)
  try {
    fetch(API_BASE + "/auth/logout", { method: "POST" }).catch(() => {});
  } catch (e) { /* ignore */ }
  logout();
}
