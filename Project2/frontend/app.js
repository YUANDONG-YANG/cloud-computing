/**
 * Nutritional Insights Dashboard -- Frontend Application
 * CPSY 300 Phase 2: Cloud Dashboard Development
 *
 * Fetches data from the Azure Function API and renders interactive
 * visualizations using Chart.js.
 *
 * If the Function cannot be reached the dashboard shows an explicit offline
 * banner and renders the committed Project 1 batch results instead, so live
 * and fallback figures are never mixed in the same view.
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

// The deployed Function endpoint is injected by index.html via
// window.NUTRITIONAL_API_URL. "/api" only works when the dashboard and the
// Function are served from the same origin (e.g. a Static Web App with a
// linked API, or `func start` behind the same host).
const API_BASE_URL = String(window.NUTRITIONAL_API_URL || "/api").replace(/\/+$/, "");

const DIET_COLORS = {
    dash:          { bg: "rgba(59, 130, 246, 0.7)",  border: "#3b82f6" },
    keto:          { bg: "rgba(236, 72, 153, 0.7)",  border: "#ec4899" },
    mediterranean: { bg: "rgba(16, 185, 129, 0.7)",  border: "#10b981" },
    paleo:         { bg: "rgba(245, 158, 11, 0.7)",  border: "#f59e0b" },
    vegan:         { bg: "rgba(139, 92, 246, 0.7)",  border: "#8b5cf6" },
};

const MACRO_COLORS = {
    "Protein(g)": { bg: "rgba(59, 130, 246, 0.7)",  border: "#3b82f6" },
    "Carbs(g)":   { bg: "rgba(245, 158, 11, 0.7)",  border: "#f59e0b" },
    "Fat(g)":     { bg: "rgba(239, 68, 68, 0.7)",   border: "#ef4444" },
};

const ROWS_PER_PAGE = 50;

// ---------------------------------------------------------------------------
// Offline fallback data
//
// These values are the real Project 1 batch results, generated from
// All_Diets.csv and committed under Project1/docs/results/:
//   average_macros.csv, total_protein.csv, common_cuisines.csv,
//   top5_protein_recipes.csv
//
// They are used only when the Azure Function is unreachable. The dashboard
// shows an explicit offline banner in that case -- see setOfflineBanner().
// ---------------------------------------------------------------------------

const DEMO_DATA = {
    average_macros: [
        { "Diet_type": "dash",           "Protein(g)":   69.28, "Carbs(g)":  160.54, "Fat(g)":  101.15 },
        { "Diet_type": "keto",           "Protein(g)":  101.27, "Carbs(g)":   57.97, "Fat(g)":  153.12 },
        { "Diet_type": "mediterranean",  "Protein(g)":  101.11, "Carbs(g)":  152.91, "Fat(g)":  101.42 },
        { "Diet_type": "paleo",          "Protein(g)":   88.67, "Carbs(g)":  129.55, "Fat(g)":  135.67 },
        { "Diet_type": "vegan",          "Protein(g)":   56.16, "Carbs(g)":  254.00, "Fat(g)":  103.30 },
    ],
    top_recipes: [
        { "Diet_type": "dash", "Recipe_name": "Salmon Mousse", "Cuisine_type": "nordic", "Protein(g)": 1239.47, "Carbs(g)": 22.40, "Fat(g)": 983.36 },
        { "Diet_type": "dash", "Recipe_name": "Homemade Turkey Alphabet Soup", "Cuisine_type": "american", "Protein(g)": 1190.35, "Carbs(g)": 49.13, "Fat(g)": 297.45 },
        { "Diet_type": "dash", "Recipe_name": "Barbecue Chicken Legs", "Cuisine_type": "mediterranean", "Protein(g)": 1017.25, "Carbs(g)": 241.93, "Fat(g)": 1002.07 },
        { "Diet_type": "dash", "Recipe_name": "12th Man Hot Wings", "Cuisine_type": "american", "Protein(g)": 807.03, "Carbs(g)": 49.17, "Fat(g)": 649.49 },
        { "Diet_type": "dash", "Recipe_name": "Jazzed Up Turkey Tetrazzini", "Cuisine_type": "american", "Protein(g)": 517.47, "Carbs(g)": 575.58, "Fat(g)": 377.75 },
        { "Diet_type": "keto", "Recipe_name": "Sara Louise's Keto Smoked Holiday Turkey", "Cuisine_type": "american", "Protein(g)": 1092.00, "Carbs(g)": 49.28, "Fat(g)": 313.81 },
        { "Diet_type": "keto", "Recipe_name": "Mayo Free Deviled Eggs (Paleo, Whole30 + Keto)", "Cuisine_type": "italian", "Protein(g)": 766.99, "Carbs(g)": 41.29, "Fat(g)": 287.59 },
        { "Diet_type": "keto", "Recipe_name": "Low Carb Beef and Cheddar Cauliflower Bake, THM S meal, Keto too", "Cuisine_type": "british", "Protein(g)": 710.81, "Carbs(g)": 112.56, "Fat(g)": 1154.61 },
        { "Diet_type": "keto", "Recipe_name": "Orange and Five-Spice Roasted Chicken Legs | Keto, Paleo", "Cuisine_type": "mediterranean", "Protein(g)": 677.22, "Carbs(g)": 41.71, "Fat(g)": 686.90 },
        { "Diet_type": "keto", "Recipe_name": "Low Carb Salmon Cakes (Keto, Grain Free)", "Cuisine_type": "nordic", "Protein(g)": 656.95, "Carbs(g)": 13.25, "Fat(g)": 501.19 },
        { "Diet_type": "mediterranean", "Recipe_name": "Fava Bean Salad with Mountain Ham and Mint", "Cuisine_type": "american", "Protein(g)": 970.31, "Carbs(g)": 823.34, "Fat(g)": 322.84 },
        { "Diet_type": "mediterranean", "Recipe_name": "Poached Salt Cod with Vegetables and Garlic Mayonnaise", "Cuisine_type": "mediterranean", "Protein(g)": 656.65, "Carbs(g)": 315.52, "Fat(g)": 73.73 },
        { "Diet_type": "mediterranean", "Recipe_name": "Mediterranean Pizza", "Cuisine_type": "italian", "Protein(g)": 628.29, "Carbs(g)": 3405.55, "Fat(g)": 333.76 },
        { "Diet_type": "mediterranean", "Recipe_name": "Orange and Cumin Leg of Lamb with Roasted Tomatoes and Garlic Recipe", "Cuisine_type": "mediterranean", "Protein(g)": 607.03, "Carbs(g)": 109.27, "Fat(g)": 489.93 },
        { "Diet_type": "mediterranean", "Recipe_name": "Meatballs Braised with Kale", "Cuisine_type": "mediterranean", "Protein(g)": 531.48, "Carbs(g)": 279.16, "Fat(g)": 566.41 },
        { "Diet_type": "paleo", "Recipe_name": "Swiss Paleo\u2019s Homemade Italian & Chorizo Sausage", "Cuisine_type": "italian", "Protein(g)": 1273.61, "Carbs(g)": 83.34, "Fat(g)": 1608.54 },
        { "Diet_type": "paleo", "Recipe_name": "Turkey Soup", "Cuisine_type": "american", "Protein(g)": 1142.58, "Carbs(g)": 693.64, "Fat(g)": 287.86 },
        { "Diet_type": "paleo", "Recipe_name": "Orange and Five-Spice Roasted Chicken Legs | Keto, Paleo", "Cuisine_type": "mediterranean", "Protein(g)": 677.22, "Carbs(g)": 41.71, "Fat(g)": 686.90 },
        { "Diet_type": "paleo", "Recipe_name": "Vietnamese Pho Pressure Cooker (Noodle Soup)", "Cuisine_type": "south east asian", "Protein(g)": 602.91, "Carbs(g)": 274.87, "Fat(g)": 400.01 },
        { "Diet_type": "paleo", "Recipe_name": "Paleo Slow Cooker Honey Garlic Chicken and Vegetables recipes", "Cuisine_type": "mediterranean", "Protein(g)": 501.65, "Carbs(g)": 312.39, "Fat(g)": 58.06 },
        { "Diet_type": "vegan", "Recipe_name": "Tangy Teriyaki Salmon", "Cuisine_type": "nordic", "Protein(g)": 431.10, "Carbs(g)": 39.47, "Fat(g)": 276.51 },
        { "Diet_type": "vegan", "Recipe_name": "Mini nut roasts with candied carrots", "Cuisine_type": "american", "Protein(g)": 421.72, "Carbs(g)": 1636.67, "Fat(g)": 267.25 },
        { "Diet_type": "vegan", "Recipe_name": "Vegan Pinto Bean Chili", "Cuisine_type": "american", "Protein(g)": 381.55, "Carbs(g)": 1264.46, "Fat(g)": 37.23 },
        { "Diet_type": "vegan", "Recipe_name": "Vegan Chili and Cornbread Casserole", "Cuisine_type": "american", "Protein(g)": 319.54, "Carbs(g)": 1159.00, "Fat(g)": 291.70 },
        { "Diet_type": "vegan", "Recipe_name": "Kentucky fried seitan", "Cuisine_type": "mediterranean", "Protein(g)": 317.43, "Carbs(g)": 703.99, "Fat(g)": 534.41 },
    ],
    common_cuisines: [
        { "Diet_type": "dash",           "Cuisine_type": "american",      "count":  639 },
        { "Diet_type": "keto",           "Cuisine_type": "american",      "count":  663 },
        { "Diet_type": "mediterranean",  "Cuisine_type": "mediterranean", "count": 1274 },
        { "Diet_type": "paleo",          "Cuisine_type": "american",      "count":  535 },
        { "Diet_type": "vegan",          "Cuisine_type": "american",      "count":  925 },
    ],
    total_protein_by_diet: [
        { "Diet_type": "dash",           "Total_Protein(g)": 120897.57 },
        { "Diet_type": "keto",           "Total_Protein(g)": 153114.96 },
        { "Diet_type": "mediterranean",  "Total_Protein(g)": 177249.89 },
        { "Diet_type": "paleo",          "Total_Protein(g)": 112971.65 },
        { "Diet_type": "vegan",          "Total_Protein(g)":  85471.00 },
    ],
    summary: {
        total_recipes: 7806,
        diet_types: ["dash", "keto", "mediterranean", "paleo", "vegan"],
        diet_counts: { dash: 1745, keto: 1512, mediterranean: 1753, paleo: 1274, vegan: 1522 },
        highest_mean_protein_diet: "keto",
        highest_mean_protein_g: 101.27,
        highest_total_protein_diet: "mediterranean",
        highest_total_protein_g: 177249.89,
    },
    metadata: {
        execution_time_seconds: null,
        source: "Offline fallback (Project 1 batch results)",
        dataset: "All_Diets.csv",
    },
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let insightsData = null;
let isOffline = false;

// Recipe table state. When the API is reachable, paging is served by the
// Function (`?page=&limit=`); offline the fallback rows are sliced in-browser.
const recipeState = {
    rows: [],
    page: 1,
    totalPages: 1,
    total: 0,
    serverPaged: false,
};

let chartInstances = {};

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

const $ = (sel) => document.querySelector(sel);

function showLoading(id, show) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle("hidden", !show);
}

function setLoadingAll(show) {
    ["bar-loading", "pie-loading", "heatmap-loading", "scatter-loading"].forEach(id =>
        showLoading(id, show)
    );
}

function showError(message) {
    const banner = $("#error-banner");
    const msg = $("#error-message");
    if (banner && msg) {
        msg.textContent = message;
        banner.classList.remove("hidden");
    }
}

function hideError() {
    const banner = $("#error-banner");
    if (banner) banner.classList.add("hidden");
}

/**
 * Offline mode must be unmistakable: every number on the page then comes from
 * the committed Project 1 batch results, not from the deployed Function.
 */
function setOfflineBanner(reason) {
    const banner = $("#offline-banner");
    const detail = $("#offline-detail");
    if (!banner) return;
    if (reason) {
        if (detail) detail.textContent = reason;
        banner.classList.remove("hidden");
    } else {
        banner.classList.add("hidden");
    }
}

function capitalize(s) {
    if (!s) return s;
    return String(s).split(" ")
        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
}

function formatNumber(n) {
    if (n == null) return "--";
    return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
}

/** Diet values are interpolated into a class attribute, so allow only [a-z-]. */
function dietClass(diet) {
    return String(diet || "").toLowerCase().replace(/[^a-z-]/g, "");
}

function grams(value) {
    return Number(value).toFixed(1);
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

async function apiGet(path) {
    const response = await fetch(`${API_BASE_URL}${path}`);
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    return response.json();
}

const fetchHealth = () => apiGet("/health");
const fetchInsights = () => apiGet("/insights");

function fetchRecipes(dietType, page) {
    const params = new URLSearchParams({ page: String(page), limit: String(ROWS_PER_PAGE) });
    if (dietType && dietType !== "all") params.set("diet_type", dietType);
    return apiGet(`/recipes?${params.toString()}`);
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

/**
 * Load everything for the given diet filter.
 *
 * If either call fails the whole dashboard switches to offline mode, so live
 * and fallback data are never mixed in the same view.
 */
async function loadData(dietType, page = 1) {
    hideError();
    setLoadingAll(true);

    let health = null;
    try {
        health = await fetchHealth();
    } catch (err) {
        console.warn("Health check failed:", err.message);
    }

    try {
        const data = await fetchInsights();
        const recipesResp = await fetchRecipes(dietType, page);

        insightsData = data;
        isOffline = false;

        recipeState.rows = recipesResp.recipes || [];
        recipeState.page = recipesResp.page || 1;
        recipeState.totalPages = recipesResp.total_pages || 1;
        recipeState.total = recipesResp.total != null
            ? recipesResp.total
            : recipeState.rows.length;
        recipeState.serverPaged = true;

        updateApiStatus(true, health);
        updateExecTime(data.metadata?.execution_time_seconds);
        setOfflineBanner(null);
        $("#data-source-label").textContent = "Source: Azure Blob Storage (live)";
    } catch (err) {
        console.warn("API unavailable, using offline fallback:", err.message);
        insightsData = DEMO_DATA;
        isOffline = true;

        loadOfflineRecipes(dietType, 1);

        updateApiStatus(false, health);
        updateExecTime(null);
        setOfflineBanner(`Could not reach ${API_BASE_URL} (${err.message}).`);
        $("#data-source-label").textContent = "Source: offline fallback";
    }

    renderAll(dietType);
    setLoadingAll(false);
}

function loadOfflineRecipes(dietType, page) {
    const all = (dietType && dietType !== "all")
        ? DEMO_DATA.top_recipes.filter(r => r.Diet_type.toLowerCase() === dietType.toLowerCase())
        : DEMO_DATA.top_recipes;

    const totalPages = Math.max(1, Math.ceil(all.length / ROWS_PER_PAGE));
    const current = Math.min(Math.max(page, 1), totalPages);
    const start = (current - 1) * ROWS_PER_PAGE;

    recipeState.rows = all.slice(start, start + ROWS_PER_PAGE);
    recipeState.page = current;
    recipeState.totalPages = totalPages;
    recipeState.total = all.length;
    recipeState.serverPaged = false;
}

/** Narrow the insights payload to one diet for the per-diet charts and tables. */
function filterInsightsData(dietType) {
    if (!dietType || dietType === "all") return insightsData;

    const dt = dietType.toLowerCase();
    const byDiet = (rows) => (rows || []).filter(r => String(r.Diet_type).toLowerCase() === dt);

    return {
        ...insightsData,
        average_macros: byDiet(insightsData.average_macros),
        top_recipes: byDiet(insightsData.top_recipes),
        common_cuisines: byDiet(insightsData.common_cuisines),
        total_protein_by_diet: byDiet(insightsData.total_protein_by_diet),
    };
}

// ---------------------------------------------------------------------------
// UI updates
// ---------------------------------------------------------------------------

function updateApiStatus(alive, health) {
    const el = $("#api-status");
    if (alive) {
        el.textContent = health ? `API Connected (v${health.version})` : "API Connected";
        el.className = "text-xs px-3 py-1.5 rounded-full bg-green-600 text-white";
    } else {
        el.textContent = "Offline - fallback data";
        el.className = "text-xs px-3 py-1.5 rounded-full bg-amber-500 text-white";
    }
}

/** Shows the /api/insights execution time reported by the Function. */
function updateExecTime(seconds) {
    const container = $("#exec-time-display");
    const value = $("#exec-time-value");
    if (seconds != null) {
        value.textContent = `${(seconds * 1000).toFixed(0)} ms`;
        container.classList.remove("hidden");
    } else {
        container.classList.add("hidden");
    }
}

function updateStats(data) {
    const s = data.summary || {};
    $("#stat-total").textContent = formatNumber(s.total_recipes);
    $("#stat-diets").textContent = s.diet_types ? s.diet_types.length : "--";
    $("#stat-highest-mean").textContent = capitalize(s.highest_mean_protein_diet) || "--";
    $("#stat-highest-mean-val").textContent = s.highest_mean_protein_g != null
        ? `${formatNumber(s.highest_mean_protein_g)}g` : "--";
    $("#stat-highest-total").textContent = capitalize(s.highest_total_protein_diet) || "--";
    $("#stat-highest-total-val").textContent = s.highest_total_protein_g != null
        ? `${formatNumber(s.highest_total_protein_g)}g` : "--";
}

// ---------------------------------------------------------------------------
// Chart rendering
// ---------------------------------------------------------------------------

function destroyChart(name) {
    if (chartInstances[name]) {
        chartInstances[name].destroy();
        delete chartInstances[name];
    }
}

function renderBarChart(data) {
    destroyChart("bar");
    const macros = data.average_macros || [];
    const labels = macros.map(r => capitalize(r.Diet_type));
    const datasets = ["Protein(g)", "Carbs(g)", "Fat(g)"].map(macro => ({
        label: macro.replace("(g)", " (g)"),
        data: macros.map(r => r[macro]),
        backgroundColor: MACRO_COLORS[macro].bg,
        borderColor: MACRO_COLORS[macro].border,
        borderWidth: 1,
        borderRadius: 4,
    }));

    const ctx = document.getElementById("barChart").getContext("2d");
    chartInstances.bar = new Chart(ctx, {
        type: "bar",
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "top" },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)}g`
                    }
                }
            },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: "Grams per recipe" } },
                x: { title: { display: true, text: "Diet Type" } }
            }
        }
    });
}

function renderPieChart(data) {
    destroyChart("pie");
    const counts = (data.summary || {}).diet_counts || {};
    const keys = Object.keys(counts).sort();
    const palette = (k) => DIET_COLORS[k] || DIET_COLORS.dash;

    const ctx = document.getElementById("pieChart").getContext("2d");
    chartInstances.pie = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: keys.map(capitalize),
            datasets: [{
                data: keys.map(k => counts[k]),
                backgroundColor: keys.map(k => palette(k).bg),
                borderColor: keys.map(k => palette(k).border),
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "right" },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = ((ctx.parsed / total) * 100).toFixed(1);
                            return `${ctx.label}: ${ctx.parsed.toLocaleString()} (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

function renderHeatmap(data) {
    const container = document.getElementById("heatmap");
    container.innerHTML = "";

    const macros = data.average_macros || [];
    if (macros.length === 0) {
        container.innerHTML = '<p class="text-sm text-slate-400 text-center py-8">No data available</p>';
        return;
    }

    const diets = macros.map(r => r.Diet_type);
    const nutrients = ["Protein(g)", "Carbs(g)", "Fat(g)"];
    const nutrientLabels = ["Protein", "Carbs", "Fat"];

    const allValues = macros.flatMap(r => nutrients.map(n => r[n]));
    const minVal = Math.min(...allValues);
    const maxVal = Math.max(...allValues);

    function valueToColor(val) {
        const ratio = (val - minVal) / (maxVal - minVal || 1);
        // Blue -> amber -> red
        if (ratio < 0.5) {
            const t = ratio * 2;
            return `rgb(${Math.round(59 + t * 186)}, ${Math.round(130 + t * 28)}, ${Math.round(246 - t * 235)})`;
        }
        const t = (ratio - 0.5) * 2;
        return `rgb(${Math.round(245 - t * 6)}, ${Math.round(158 - t * 90)}, ${Math.round(11 + t * 57)})`;
    }

    function textColor(val) {
        const ratio = (val - minVal) / (maxVal - minVal || 1);
        return ratio > 0.6 ? "#ffffff" : "#1e293b";
    }

    const grid = document.createElement("div");
    grid.className = "heatmap-grid";
    grid.style.gridTemplateColumns = `80px repeat(${diets.length}, 1fr)`;

    grid.appendChild(Object.assign(document.createElement("div"), { className: "heatmap-label" }));
    diets.forEach(d => {
        const header = document.createElement("div");
        header.className = "heatmap-label";
        header.textContent = capitalize(d);
        grid.appendChild(header);
    });

    nutrients.forEach((nutrient, ni) => {
        const label = document.createElement("div");
        label.className = "heatmap-label";
        label.textContent = nutrientLabels[ni];
        grid.appendChild(label);

        diets.forEach((diet, di) => {
            const val = macros[di][nutrient];
            const cell = document.createElement("div");
            cell.className = "heatmap-cell";
            cell.style.backgroundColor = valueToColor(val);
            cell.style.color = textColor(val);
            cell.textContent = val.toFixed(1);
            cell.title = `${capitalize(diet)} - ${nutrientLabels[ni]}: ${val.toFixed(2)}g`;
            grid.appendChild(cell);
        });
    });

    container.appendChild(grid);

    const legend = document.createElement("div");
    legend.className = "flex items-center justify-center gap-2 mt-3 text-xs text-slate-500";
    legend.innerHTML = `
        <span>${minVal.toFixed(0)}g</span>
        <div style="width: 120px; height: 10px; border-radius: 5px;
             background: linear-gradient(to right, rgb(59,130,246), rgb(245,158,11), rgb(239,68,68));">
        </div>
        <span>${maxVal.toFixed(0)}g</span>
    `;
    container.appendChild(legend);
}

function renderScatterChart(data) {
    destroyChart("scatter");
    const macros = data.average_macros || [];

    const datasets = macros.map(r => {
        const colors = DIET_COLORS[String(r.Diet_type).toLowerCase()] || DIET_COLORS.dash;
        return {
            label: capitalize(r.Diet_type),
            data: [{ x: r["Carbs(g)"], y: r["Protein(g)"] }],
            backgroundColor: colors.bg,
            borderColor: colors.border,
            borderWidth: 2,
            pointRadius: 10,
            pointHoverRadius: 13,
        };
    });

    const ctx = document.getElementById("scatterChart").getContext("2d");
    chartInstances.scatter = new Chart(ctx, {
        type: "scatter",
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "top" },
                tooltip: {
                    callbacks: {
                        label: (ctx) =>
                            `${ctx.dataset.label}: Protein ${ctx.parsed.y.toFixed(2)}g, Carbs ${ctx.parsed.x.toFixed(2)}g`
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: "Carbs (g)" }, beginAtZero: true },
                y: { title: { display: true, text: "Protein (g)" }, beginAtZero: true }
            }
        }
    });
}

// ---------------------------------------------------------------------------
// Table rendering
// ---------------------------------------------------------------------------

function recipeRow(r) {
    return `
        <tr>
            <td><span class="diet-badge ${dietClass(r.Diet_type)}">${escapeHtml(capitalize(r.Diet_type))}</span></td>
            <td class="font-medium">${escapeHtml(r.Recipe_name)}</td>
            <td>${escapeHtml(capitalize(r.Cuisine_type))}</td>
            <td>${grams(r["Protein(g)"])}</td>
            <td>${grams(r["Carbs(g)"])}</td>
            <td>${grams(r["Fat(g)"])}</td>
        </tr>
    `;
}

function renderTopRecipes(data) {
    const tbody = document.getElementById("top-recipes-body");
    const recipes = data.top_recipes || [];
    tbody.innerHTML = recipes.length === 0
        ? '<tr><td colspan="6" class="text-center text-slate-400 py-8">No data</td></tr>'
        : recipes.map(recipeRow).join("");
}

function renderCuisines(data) {
    const tbody = document.getElementById("cuisines-body");
    const cuisines = data.common_cuisines || [];
    tbody.innerHTML = cuisines.length === 0
        ? '<tr><td colspan="3" class="text-center text-slate-400 py-8">No data</td></tr>'
        : cuisines.map(r => `
            <tr>
                <td><span class="diet-badge ${dietClass(r.Diet_type)}">${escapeHtml(capitalize(r.Diet_type))}</span></td>
                <td>${escapeHtml(capitalize(r.Cuisine_type))}</td>
                <td>${Number(r.count).toLocaleString()}</td>
            </tr>
        `).join("");
}

function renderRecipeTable() {
    const tbody = document.getElementById("recipe-body");
    const countEl = document.getElementById("recipe-count");

    const shown = recipeState.rows.length;
    countEl.textContent = shown === 0
        ? "0 recipes"
        : `${recipeState.total.toLocaleString()} recipes` +
          (recipeState.totalPages > 1 ? ` (page ${recipeState.page} of ${recipeState.totalPages})` : "");

    tbody.innerHTML = shown === 0
        ? '<tr><td colspan="6" class="text-center text-slate-400 py-8">No recipes found</td></tr>'
        : recipeState.rows.map(recipeRow).join("");

    renderPagination();
}

function renderPagination() {
    const container = document.getElementById("pagination");
    const { page, totalPages } = recipeState;
    if (totalPages <= 1) {
        container.innerHTML = "";
        return;
    }

    const btn = (label, target, disabled, active) => {
        const base = "px-3 py-1.5 text-sm rounded-lg";
        const style = disabled
            ? "bg-slate-200 text-slate-400 cursor-not-allowed"
            : active
                ? "bg-blue-600 text-white"
                : "bg-white text-slate-700 hover:bg-slate-100 border border-slate-300";
        return `<button type="button" class="${base} ${style}" data-page="${target}" ${disabled ? "disabled" : ""}>${label}</button>`;
    };

    let html = btn("Prev", page - 1, page === 1, false);
    getPageRange(page, totalPages).forEach(p => {
        html += p === "..."
            ? '<span class="px-2 py-1 text-slate-400">...</span>'
            : btn(p, p, false, p === page);
    });
    html += btn("Next", page + 1, page === totalPages, false);

    container.innerHTML = html;
}

function getPageRange(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    const pages = [];
    if (current <= 4) {
        for (let i = 1; i <= 5; i++) pages.push(i);
        pages.push("...", total);
    } else if (current >= total - 3) {
        pages.push(1, "...");
        for (let i = total - 4; i <= total; i++) pages.push(i);
    } else {
        pages.push(1, "...", current - 1, current, current + 1, "...", total);
    }
    return pages;
}

async function goToPage(page) {
    if (page < 1 || page > recipeState.totalPages || page === recipeState.page) return;

    if (recipeState.serverPaged) {
        const diet = document.getElementById("diet-filter").value;
        try {
            const resp = await fetchRecipes(diet, page);
            recipeState.rows = resp.recipes || [];
            recipeState.page = resp.page || page;
            recipeState.totalPages = resp.total_pages || recipeState.totalPages;
            recipeState.total = resp.total != null ? resp.total : recipeState.total;
            hideError();
        } catch (err) {
            showError(`Could not load page ${page}: ${err.message}`);
            return;
        }
    } else {
        loadOfflineRecipes(document.getElementById("diet-filter").value, page);
    }

    renderRecipeTable();
    document.getElementById("recipe-table").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------------------------------------------------------------------------
// Main render orchestration
// ---------------------------------------------------------------------------

function renderAll(dietType) {
    const filtered = filterInsightsData(dietType);

    updateStats(insightsData);       // headline stats always describe the full dataset
    renderPieChart(insightsData);    // distribution always shows every diet
    renderBarChart(filtered);
    renderHeatmap(filtered);
    renderScatterChart(filtered);
    renderTopRecipes(filtered);
    renderCuisines(filtered);
    renderRecipeTable();
}

// ---------------------------------------------------------------------------
// Event listeners & initialization
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    const dietFilter = document.getElementById("diet-filter");
    const refreshBtn = document.getElementById("refresh-btn");

    dietFilter.addEventListener("change", () => loadData(dietFilter.value, 1));
    refreshBtn.addEventListener("click", () => loadData(dietFilter.value, 1));

    // Pagination is delegated, so no inline handlers and no global needed.
    document.getElementById("pagination").addEventListener("click", (event) => {
        const button = event.target.closest("button[data-page]");
        if (button && !button.disabled) goToPage(Number(button.dataset.page));
    });

    loadData("all", 1);
});
