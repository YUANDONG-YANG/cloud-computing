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
const API_BASE =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:7071/api"
    : "/api";

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

/* ------------------------------------------------------------------
 * Fallback / Demo Data
 * ----------------------------------------------------------------*/
const FALLBACK_INSIGHTS = {
  total_recipes: 7806,
  diet_types: ["dash", "keto", "mediterranean", "paleo", "vegan"],
  average_macros: {
    dash:          { Protein: 69.28,  Carbs: 160.54, Fat: 101.15 },
    keto:          { Protein: 101.27, Carbs: 57.97,  Fat: 153.12 },
    mediterranean: { Protein: 101.11, Carbs: 152.91, Fat: 101.42 },
    paleo:         { Protein: 88.67,  Carbs: 129.55, Fat: 135.67 },
    vegan:         { Protein: 56.16,  Carbs: 254.00, Fat: 103.30 },
  },
  recipe_counts: { dash: 1546, keto: 1580, mediterranean: 1564, paleo: 1543, vegan: 1573 },
  heatmap: {
    diets: ["dash", "keto", "mediterranean", "paleo", "vegan"],
    nutrients: ["Protein(g)", "Carbs(g)", "Fat(g)"],
    values: [
      [69.28, 160.54, 101.15],
      [101.27, 57.97, 153.12],
      [101.11, 152.91, 101.42],
      [88.67, 129.55, 135.67],
      [56.16, 254.00, 103.30],
    ],
  },
  top_recipes: [
    { diet: "dash", recipe: "Grilled Chicken Salad", cuisine: "american", protein: 35.0, carbs: 12.5, fat: 8.2 },
    { diet: "keto", recipe: "Keto Butter Chicken", cuisine: "indian", protein: 42.5, carbs: 8.3, fat: 28.7 },
    { diet: "keto", recipe: "Bacon Cheese Burger Bowl", cuisine: "american", protein: 38.2, carbs: 5.1, fat: 35.4 },
    { diet: "mediterranean", recipe: "Greek Lemon Chicken", cuisine: "greek", protein: 38.5, carbs: 15.2, fat: 22.1 },
    { diet: "paleo", recipe: "Paleo Pumpkin Pie", cuisine: "american", protein: 30.91, carbs: 302.59, fat: 96.76 },
    { diet: "vegan", recipe: "Tofu Stir Fry", cuisine: "chinese", protein: 22.1, carbs: 28.5, fat: 14.6 },
  ],
  common_cuisines: {},
};

const FALLBACK_RECIPES = [
  { Diet_type: "keto", Recipe_name: "Keto Butter Chicken", Cuisine_type: "indian", "Protein(g)": 42.5, "Carbs(g)": 8.3, "Fat(g)": 28.7 },
  { Diet_type: "keto", Recipe_name: "Bacon Cheese Burger Bowl", Cuisine_type: "american", "Protein(g)": 38.2, "Carbs(g)": 5.1, "Fat(g)": 35.4 },
  { Diet_type: "keto", Recipe_name: "Grilled Salmon with Avocado", Cuisine_type: "american", "Protein(g)": 45.0, "Carbs(g)": 4.2, "Fat(g)": 32.1 },
  { Diet_type: "keto", Recipe_name: "Low-Carb Cauliflower Mac", Cuisine_type: "american", "Protein(g)": 22.5, "Carbs(g)": 12.3, "Fat(g)": 18.9 },
  { Diet_type: "paleo", Recipe_name: "Bone Broth From Nom Nom Paleo", Cuisine_type: "american", "Protein(g)": 5.22, "Carbs(g)": 1.29, "Fat(g)": 3.2 },
  { Diet_type: "paleo", Recipe_name: "Paleo Pumpkin Pie", Cuisine_type: "american", "Protein(g)": 30.91, "Carbs(g)": 302.59, "Fat(g)": 96.76 },
  { Diet_type: "paleo", Recipe_name: "Strawberry Guacamole", Cuisine_type: "mexican", "Protein(g)": 9.62, "Carbs(g)": 75.78, "Fat(g)": 59.89 },
  { Diet_type: "paleo", Recipe_name: "Sweet Potato Hash", Cuisine_type: "american", "Protein(g)": 18.3, "Carbs(g)": 42.5, "Fat(g)": 15.6 },
  { Diet_type: "vegan", Recipe_name: "Vegan Black Bean Tacos", Cuisine_type: "mexican", "Protein(g)": 18.5, "Carbs(g)": 45.2, "Fat(g)": 12.3 },
  { Diet_type: "vegan", Recipe_name: "Tofu Stir Fry", Cuisine_type: "chinese", "Protein(g)": 22.1, "Carbs(g)": 28.5, "Fat(g)": 14.6 },
  { Diet_type: "vegan", Recipe_name: "Chickpea Curry", Cuisine_type: "indian", "Protein(g)": 15.8, "Carbs(g)": 42.3, "Fat(g)": 18.9 },
  { Diet_type: "vegan", Recipe_name: "Quinoa Buddha Bowl", Cuisine_type: "american", "Protein(g)": 16.4, "Carbs(g)": 52.1, "Fat(g)": 14.2 },
  { Diet_type: "dash", Recipe_name: "Grilled Chicken Salad", Cuisine_type: "american", "Protein(g)": 35.0, "Carbs(g)": 12.5, "Fat(g)": 8.2 },
  { Diet_type: "dash", Recipe_name: "Salmon with Quinoa", Cuisine_type: "american", "Protein(g)": 40.2, "Carbs(g)": 38.1, "Fat(g)": 15.6 },
  { Diet_type: "dash", Recipe_name: "Turkey Meatball Soup", Cuisine_type: "italian", "Protein(g)": 28.7, "Carbs(g)": 22.4, "Fat(g)": 11.3 },
  { Diet_type: "dash", Recipe_name: "Mediterranean Wrap", Cuisine_type: "middle eastern", "Protein(g)": 24.1, "Carbs(g)": 35.6, "Fat(g)": 12.8 },
  { Diet_type: "mediterranean", Recipe_name: "Greek Lemon Chicken", Cuisine_type: "greek", "Protein(g)": 38.5, "Carbs(g)": 15.2, "Fat(g)": 22.1 },
  { Diet_type: "mediterranean", Recipe_name: "Falafel Wrap", Cuisine_type: "middle eastern", "Protein(g)": 18.9, "Carbs(g)": 42.5, "Fat(g)": 16.8 },
  { Diet_type: "mediterranean", Recipe_name: "Grilled Sea Bass", Cuisine_type: "greek", "Protein(g)": 44.2, "Carbs(g)": 5.8, "Fat(g)": 18.5 },
  { Diet_type: "mediterranean", Recipe_name: "Hummus Plate", Cuisine_type: "middle eastern", "Protein(g)": 12.5, "Carbs(g)": 28.3, "Fat(g)": 14.1 },
];

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
  let data = null;
  let source = "fallback";
  let responseTime = 0;

  try {
    const start = performance.now();
    const resp = await fetch(API_BASE + "/insights");
    responseTime = Math.round(performance.now() - start);

    if (resp.ok) {
      const json = await resp.json();
      data = json.data || json;
      source = json.source || "api";
      responseTime = json.response_time_ms || responseTime;
    }
  } catch (err) {
    console.warn("Insights API unavailable, using fallback data:", err.message);
  }

  if (!data) {
    data = FALLBACK_INSIGHTS;
    source = "demo";
    responseTime = 0;
  }

  // Update status pills
  updateStatusBar(source, responseTime, data.total_recipes || 7806);

  // Render charts
  renderBarChart(data);
  renderPieChart(data);
  renderHeatmap(data);
  renderScatter(data);
  chartsInitialized = true;
}

/* ------------------------------------------------------------------
 * Load Recipes (table with search/filter/pagination)
 * ----------------------------------------------------------------*/
async function loadRecipes() {
  let result = null;

  try {
    const params = new URLSearchParams();
    if (currentDiet) params.set("diet", currentDiet);
    if (currentSearch) params.set("search", currentSearch);
    params.set("page", currentPage);
    params.set("pageSize", currentPageSize);

    const resp = await fetch(API_BASE + "/recipes?" + params.toString());
    if (resp.ok) {
      result = await resp.json();
    }
  } catch (err) {
    console.warn("Recipes API unavailable, using fallback data:", err.message);
  }

  if (!result) {
    // Use fallback with client-side filter/search/pagination
    result = clientSideFilter(FALLBACK_RECIPES);
  }

  renderRecipeTable(result.results || []);
  renderPagination(result);
}

function clientSideFilter(recipes) {
  let filtered = [...recipes];

  if (currentDiet) {
    filtered = filtered.filter(r => (r.Diet_type || "").toLowerCase() === currentDiet);
  }
  if (currentSearch) {
    const q = currentSearch.toLowerCase();
    filtered = filtered.filter(r =>
      (r.Recipe_name || "").toLowerCase().includes(q) ||
      (r.Cuisine_type || "").toLowerCase().includes(q) ||
      (r.Diet_type || "").toLowerCase().includes(q)
    );
  }

  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / currentPageSize));
  const page = Math.min(currentPage, totalPages);
  const offset = (page - 1) * currentPageSize;
  const results = filtered.slice(offset, offset + currentPageSize);

  return {
    total,
    page,
    pageSize: currentPageSize,
    totalPages,
    hasNext: page < totalPages,
    hasPrev: page > 1,
    results,
  };
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

  // Build bubble-style heatmap using scatter with point sizes
  const points = [];
  const maxVal = Math.max(...values.flat());

  for (let row = 0; row < values.length; row++) {
    for (let col = 0; col < (values[row] || []).length; col++) {
      const val = values[row][col];
      points.push({ x: col, y: row, r: Math.max(8, (val / maxVal) * 30), v: val });
    }
  }

  heatmapChart = new Chart(ctx, {
    type: "bubble",
    data: {
      datasets: [{
        data: points,
        backgroundColor: points.map(p => {
          const ratio = p.v / maxVal;
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

function renderScatter(data) {
  const ctx = document.getElementById("scatterChart");
  if (!ctx) return;
  if (scatterChart) scatterChart.destroy();

  const topRecipes = data.top_recipes || [];
  const dietGroups = {};

  topRecipes.forEach(r => {
    const diet = r.diet || r.Diet_type || "unknown";
    if (!dietGroups[diet]) dietGroups[diet] = [];
    dietGroups[diet].push({
      x: r.carbs || r["Carbs(g)"] || 0,
      y: r.protein || r["Protein(g)"] || 0,
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
    tbody.innerHTML = '<tr><td colspan="6" class="no-results">No recipes found. Try adjusting your search or filter.</td></tr>';
    return;
  }

  tbody.innerHTML = recipes.map((r, i) => {
    const diet = (r.Diet_type || "").toLowerCase();
    return `<tr>
      <td>${(currentPage - 1) * currentPageSize + i + 1}</td>
      <td>${escapeHtml(r.Recipe_name || "")}</td>
      <td><span class="diet-badge ${diet}">${diet}</span></td>
      <td>${escapeHtml(r.Cuisine_type || "")}</td>
      <td>${r["Protein(g)"] || 0}</td>
      <td>${r["Carbs(g)"] || 0}</td>
      <td>${r["Fat(g)"] || 0}</td>
    </tr>`;
  }).join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
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
function updateStatusBar(source, responseTime, totalRecipes) {
  const el = document.getElementById("statusBar");
  if (!el) return;

  el.innerHTML = `
    <span class="status-pill"><span class="dot"></span> ${source === "demo" || source === "fallback" ? "Demo Mode" : "Cache: " + source}</span>
    <span class="status-pill">${responseTime}ms response</span>
    <span class="status-pill">${totalRecipes.toLocaleString()} recipes</span>
  `;
}

/* ------------------------------------------------------------------
 * Security Status
 * ----------------------------------------------------------------*/
function updateSecurityStatus() {
  const user = getCurrentUser();
  const token = getToken();

  // Auth method
  setSecurityCard("secAuth", user ? "Authenticated" : "Not authenticated");

  // JWT status
  if (token) {
    const claims = decodeJWT(token);
    if (claims && claims.exp) {
      const expires = new Date(claims.exp * 1000);
      const hoursLeft = Math.round((expires - Date.now()) / 3600000);
      setSecurityCard("secJWT", `Valid (${hoursLeft}h remaining)`);
    } else {
      setSecurityCard("secJWT", "Active");
    }
  } else {
    setSecurityCard("secJWT", "None");
  }

  // Encryption
  setSecurityCard("secEncrypt", "AES-256 (Cosmos DB)");

  // Password hashing
  setSecurityCard("secHash", "bcrypt (12 rounds)");
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
