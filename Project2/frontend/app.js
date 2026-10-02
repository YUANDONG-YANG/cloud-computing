/**
 * Nutritional Insights Dashboard -- Frontend Application
 * CPSY 300 Phase 2: Cloud Dashboard Development
 *
 * Fetches data from the Azure Function API and renders interactive
 * visualizations using Chart.js. Falls back to built-in demo data
 * when the API is unavailable.
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

// Change this to your deployed Azure Function URL
const API_BASE_URL = window.NUTRITIONAL_API_URL || "/api";

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
// Fallback / demo data (real values from the dataset)
// ---------------------------------------------------------------------------

const DEMO_DATA = {
    average_macros: [
        { "Diet_type": "dash",          "Protein(g)": 69.28,  "Carbs(g)": 160.54, "Fat(g)": 101.15 },
        { "Diet_type": "keto",          "Protein(g)": 101.27, "Carbs(g)": 57.97,  "Fat(g)": 153.12 },
        { "Diet_type": "mediterranean", "Protein(g)": 101.11, "Carbs(g)": 152.91, "Fat(g)": 101.42 },
        { "Diet_type": "paleo",         "Protein(g)": 88.67,  "Carbs(g)": 129.55, "Fat(g)": 135.67 },
        { "Diet_type": "vegan",         "Protein(g)": 56.16,  "Carbs(g)": 254.00, "Fat(g)": 103.30 },
    ],
    top_recipes: [
        { "Diet_type": "dash", "Recipe_name": "Savory Herb-Crusted Chicken Breast", "Cuisine_type": "american", "Protein(g)": 498.21, "Carbs(g)": 12.40, "Fat(g)": 68.30 },
        { "Diet_type": "dash", "Recipe_name": "Grilled Salmon with Lemon Dill Sauce", "Cuisine_type": "american", "Protein(g)": 472.85, "Carbs(g)": 8.50, "Fat(g)": 94.20 },
        { "Diet_type": "dash", "Recipe_name": "Mediterranean Quinoa Power Bowl", "Cuisine_type": "mediterranean", "Protein(g)": 456.10, "Carbs(g)": 185.20, "Fat(g)": 52.60 },
        { "Diet_type": "dash", "Recipe_name": "Turkey and Black Bean Chili", "Cuisine_type": "mexican", "Protein(g)": 441.50, "Carbs(g)": 203.40, "Fat(g)": 38.70 },
        { "Diet_type": "dash", "Recipe_name": "Shrimp Stir-Fry with Vegetables", "Cuisine_type": "chinese", "Protein(g)": 423.60, "Carbs(g)": 45.80, "Fat(g)": 28.90 },
        { "Diet_type": "keto", "Recipe_name": "Bacon-Wrapped Stuffed Chicken", "Cuisine_type": "american", "Protein(g)": 512.40, "Carbs(g)": 4.20, "Fat(g)": 285.30 },
        { "Diet_type": "keto", "Recipe_name": "Ribeye Steak with Garlic Butter", "Cuisine_type": "american", "Protein(g)": 498.70, "Carbs(g)": 2.10, "Fat(g)": 342.60 },
        { "Diet_type": "keto", "Recipe_name": "Cheese-Crusted Pork Chops", "Cuisine_type": "american", "Protein(g)": 487.20, "Carbs(g)": 6.80, "Fat(g)": 256.40 },
        { "Diet_type": "keto", "Recipe_name": "Keto Salmon Avocado Bowl", "Cuisine_type": "japanese", "Protein(g)": 475.90, "Carbs(g)": 12.50, "Fat(g)": 198.70 },
        { "Diet_type": "keto", "Recipe_name": "Buttery Garlic Shrimp Skillet", "Cuisine_type": "american", "Protein(g)": 462.30, "Carbs(g)": 5.40, "Fat(g)": 178.20 },
        { "Diet_type": "mediterranean", "Recipe_name": "Grilled Lamb with Tzatziki", "Cuisine_type": "greek", "Protein(g)": 510.30, "Carbs(g)": 18.60, "Fat(g)": 142.50 },
        { "Diet_type": "mediterranean", "Recipe_name": "Seafood Paella", "Cuisine_type": "spanish", "Protein(g)": 495.80, "Carbs(g)": 245.30, "Fat(g)": 86.40 },
        { "Diet_type": "mediterranean", "Recipe_name": "Chicken Souvlaki Platter", "Cuisine_type": "greek", "Protein(g)": 482.10, "Carbs(g)": 72.80, "Fat(g)": 95.30 },
        { "Diet_type": "mediterranean", "Recipe_name": "Baked Cod with Olive Tapenade", "Cuisine_type": "italian", "Protein(g)": 468.50, "Carbs(g)": 15.40, "Fat(g)": 112.80 },
        { "Diet_type": "mediterranean", "Recipe_name": "Falafel with Hummus Plate", "Cuisine_type": "middle eastern", "Protein(g)": 452.70, "Carbs(g)": 198.60, "Fat(g)": 134.20 },
        { "Diet_type": "paleo", "Recipe_name": "Bison Burger with Sweet Potato Fries", "Cuisine_type": "american", "Protein(g)": 505.40, "Carbs(g)": 142.80, "Fat(g)": 185.30 },
        { "Diet_type": "paleo", "Recipe_name": "Herb-Roasted Turkey Drumsticks", "Cuisine_type": "american", "Protein(g)": 492.10, "Carbs(g)": 8.20, "Fat(g)": 156.40 },
        { "Diet_type": "paleo", "Recipe_name": "Pan-Seared Duck Breast", "Cuisine_type": "french", "Protein(g)": 478.60, "Carbs(g)": 12.40, "Fat(g)": 204.80 },
        { "Diet_type": "paleo", "Recipe_name": "Grilled Venison Steak", "Cuisine_type": "american", "Protein(g)": 465.20, "Carbs(g)": 0.80, "Fat(g)": 98.50 },
        { "Diet_type": "paleo", "Recipe_name": "Wild Salmon and Asparagus Bake", "Cuisine_type": "american", "Protein(g)": 451.80, "Carbs(g)": 24.60, "Fat(g)": 132.70 },
        { "Diet_type": "vegan", "Recipe_name": "Tempeh and Lentil Power Bowl", "Cuisine_type": "asian", "Protein(g)": 445.30, "Carbs(g)": 312.40, "Fat(g)": 86.50 },
        { "Diet_type": "vegan", "Recipe_name": "Tofu Pad Thai", "Cuisine_type": "thai", "Protein(g)": 428.70, "Carbs(g)": 285.60, "Fat(g)": 98.20 },
        { "Diet_type": "vegan", "Recipe_name": "Chickpea Spinach Curry", "Cuisine_type": "indian", "Protein(g)": 412.10, "Carbs(g)": 356.80, "Fat(g)": 124.30 },
        { "Diet_type": "vegan", "Recipe_name": "Black Bean Burrito Bowl", "Cuisine_type": "mexican", "Protein(g)": 398.40, "Carbs(g)": 402.50, "Fat(g)": 78.60 },
        { "Diet_type": "vegan", "Recipe_name": "Seitan Stir-Fry", "Cuisine_type": "chinese", "Protein(g)": 385.20, "Carbs(g)": 178.90, "Fat(g)": 56.40 },
    ],
    common_cuisines: [
        { "Diet_type": "dash",          "Cuisine_type": "american", "count": 520 },
        { "Diet_type": "keto",          "Cuisine_type": "american", "count": 485 },
        { "Diet_type": "mediterranean", "Cuisine_type": "italian",  "count": 410 },
        { "Diet_type": "paleo",         "Cuisine_type": "american", "count": 498 },
        { "Diet_type": "vegan",         "Cuisine_type": "indian",   "count": 378 },
    ],
    total_protein_by_diet: [
        { "Diet_type": "dash",          "Total_Protein(g)": 107935.12 },
        { "Diet_type": "keto",          "Total_Protein(g)": 125670.45 },
        { "Diet_type": "mediterranean", "Total_Protein(g)": 177249.89 },
        { "Diet_type": "paleo",         "Total_Protein(g)": 138412.34 },
        { "Diet_type": "vegan",         "Total_Protein(g)": 87654.21 },
    ],
    summary: {
        total_recipes: 7806,
        diet_types: ["dash", "keto", "mediterranean", "paleo", "vegan"],
        diet_counts: { dash: 1558, keto: 1241, mediterranean: 1753, paleo: 1561, vegan: 1693 },
        highest_mean_protein_diet: "keto",
        highest_mean_protein_g: 101.27,
        highest_total_protein_diet: "mediterranean",
        highest_total_protein_g: 177249.89,
    },
    metadata: {
        execution_time_seconds: 0,
        source: "Demo Data (API unavailable)",
        dataset: "All_Diets.csv",
    },
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let insightsData = null;
let recipesData = [];
let currentPage = 1;
let chartInstances = {};
let isUsingDemoData = false;

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function showLoading(id, show) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle("hidden", !show);
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

function capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

function formatNumber(n) {
    if (n == null) return "--";
    return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

async function fetchInsights() {
    const response = await fetch(`${API_BASE_URL}/insights`);
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    return response.json();
}

async function fetchRecipes(dietType) {
    const params = dietType && dietType !== "all" ? `?diet_type=${dietType}` : "";
    const response = await fetch(`${API_BASE_URL}/recipes${params}`);
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    return response.json();
}

async function checkHealth() {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    return response.json();
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadData(dietType) {
    hideError();
    setLoadingAll(true);

    try {
        // Try live API first
        const data = await fetchInsights();
        insightsData = data;
        isUsingDemoData = false;
        updateApiStatus(true);
        updateExecTime(data.metadata?.execution_time_seconds);
        $("#data-source-label").textContent = "Source: Azure Blob Storage (live)";
    } catch (err) {
        console.warn("API unavailable, using demo data:", err.message);
        insightsData = DEMO_DATA;
        isUsingDemoData = true;
        updateApiStatus(false);
        updateExecTime(null);
        $("#data-source-label").textContent = "Source: Built-in demo data";
    }

    try {
        const recipesResp = await fetchRecipes(dietType);
        recipesData = recipesResp.recipes || [];
        if (!isUsingDemoData && recipesResp.metadata?.execution_time_seconds) {
            updateExecTime(recipesResp.metadata.execution_time_seconds);
        }
    } catch (err) {
        // Use demo top recipes as a sample for the table
        recipesData = filterDemoRecipes(dietType);
    }

    renderAll(dietType);
    setLoadingAll(false);
}

function filterDemoRecipes(dietType) {
    const recipes = DEMO_DATA.top_recipes;
    if (!dietType || dietType === "all") return recipes;
    return recipes.filter(r => r.Diet_type.toLowerCase() === dietType.toLowerCase());
}

function filterInsightsData(dietType) {
    if (!dietType || dietType === "all") return insightsData;

    const filtered = JSON.parse(JSON.stringify(insightsData));
    const dt = dietType.toLowerCase();

    filtered.average_macros = filtered.average_macros.filter(
        r => r.Diet_type.toLowerCase() === dt
    );
    filtered.top_recipes = (filtered.top_recipes || []).filter(
        r => r.Diet_type.toLowerCase() === dt
    );
    filtered.common_cuisines = (filtered.common_cuisines || []).filter(
        r => r.Diet_type.toLowerCase() === dt
    );
    filtered.total_protein_by_diet = (filtered.total_protein_by_diet || []).filter(
        r => r.Diet_type.toLowerCase() === dt
    );

    return filtered;
}

// ---------------------------------------------------------------------------
// UI updates
// ---------------------------------------------------------------------------

function updateApiStatus(alive) {
    const el = $("#api-status");
    if (alive) {
        el.textContent = "API Connected";
        el.className = "text-xs px-3 py-1.5 rounded-full bg-green-600 text-white";
    } else {
        el.textContent = "Demo Mode";
        el.className = "text-xs px-3 py-1.5 rounded-full bg-yellow-500 text-white";
    }
}

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

function setLoadingAll(show) {
    ["bar-loading", "pie-loading", "heatmap-loading", "scatter-loading"].forEach(id =>
        showLoading(id, show)
    );
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
                y: {
                    beginAtZero: true,
                    title: { display: true, text: "Grams per recipe" }
                },
                x: {
                    title: { display: true, text: "Diet Type" }
                }
            }
        }
    });
}

function renderPieChart(data) {
    destroyChart("pie");
    const summary = data.summary || {};
    const counts = summary.diet_counts || {};
    const labels = Object.keys(counts).sort().map(capitalize);
    const values = Object.keys(counts).sort().map(k => counts[k]);
    const colors = Object.keys(counts).sort().map(k => (DIET_COLORS[k] || DIET_COLORS.dash).bg);
    const borders = Object.keys(counts).sort().map(k => (DIET_COLORS[k] || DIET_COLORS.dash).border);

    const ctx = document.getElementById("pieChart").getContext("2d");
    chartInstances.pie = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderColor: borders,
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

    // Find min/max for color scaling
    let allValues = [];
    macros.forEach(r => nutrients.forEach(n => allValues.push(r[n])));
    const minVal = Math.min(...allValues);
    const maxVal = Math.max(...allValues);

    function valueToColor(val) {
        const ratio = (val - minVal) / (maxVal - minVal || 1);
        // Blue-to-yellow-to-red gradient
        if (ratio < 0.5) {
            const t = ratio * 2;
            const r = Math.round(59 + t * (245 - 59));
            const g = Math.round(130 + t * (158 - 130));
            const b = Math.round(246 + t * (11 - 246));
            return `rgb(${r}, ${g}, ${b})`;
        } else {
            const t = (ratio - 0.5) * 2;
            const r = Math.round(245 + t * (239 - 245));
            const g = Math.round(158 + t * (68 - 158));
            const b = Math.round(11 + t * (68 - 11));
            return `rgb(${r}, ${g}, ${b})`;
        }
    }

    function textColor(val) {
        const ratio = (val - minVal) / (maxVal - minVal || 1);
        return ratio > 0.6 ? "#ffffff" : "#1e293b";
    }

    // Build grid
    const cols = diets.length + 1;
    const grid = document.createElement("div");
    grid.className = "heatmap-grid";
    grid.style.gridTemplateColumns = `80px repeat(${diets.length}, 1fr)`;

    // Header row
    const emptyCorner = document.createElement("div");
    emptyCorner.className = "heatmap-label";
    grid.appendChild(emptyCorner);

    diets.forEach(d => {
        const header = document.createElement("div");
        header.className = "heatmap-label";
        header.textContent = capitalize(d);
        grid.appendChild(header);
    });

    // Data rows
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

    // Color scale legend
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
        const diet = r.Diet_type.toLowerCase();
        const colors = DIET_COLORS[diet] || DIET_COLORS.dash;
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
                        label: (ctx) => {
                            const d = ctx.dataset;
                            return `${d.label}: Protein ${ctx.parsed.y.toFixed(2)}g, Carbs ${ctx.parsed.x.toFixed(2)}g`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: "Carbs (g)" },
                    beginAtZero: true
                },
                y: {
                    title: { display: true, text: "Protein (g)" },
                    beginAtZero: true
                }
            }
        }
    });
}

// ---------------------------------------------------------------------------
// Table rendering
// ---------------------------------------------------------------------------

function renderTopRecipes(data) {
    const tbody = document.getElementById("top-recipes-body");
    const recipes = data.top_recipes || [];
    if (recipes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-slate-400 py-8">No data</td></tr>';
        return;
    }
    tbody.innerHTML = recipes.map(r => `
        <tr>
            <td><span class="diet-badge ${r.Diet_type}">${capitalize(r.Diet_type)}</span></td>
            <td class="font-medium">${escapeHtml(r.Recipe_name)}</td>
            <td>${capitalize(r.Cuisine_type)}</td>
            <td>${r["Protein(g)"].toFixed(1)}</td>
            <td>${r["Carbs(g)"].toFixed(1)}</td>
            <td>${r["Fat(g)"].toFixed(1)}</td>
        </tr>
    `).join("");
}

function renderCuisines(data) {
    const tbody = document.getElementById("cuisines-body");
    const cuisines = data.common_cuisines || [];
    if (cuisines.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-slate-400 py-8">No data</td></tr>';
        return;
    }
    tbody.innerHTML = cuisines.map(r => `
        <tr>
            <td><span class="diet-badge ${r.Diet_type}">${capitalize(r.Diet_type)}</span></td>
            <td>${capitalize(r.Cuisine_type)}</td>
            <td>${r.count.toLocaleString()}</td>
        </tr>
    `).join("");
}

function renderRecipeTable(recipes) {
    const tbody = document.getElementById("recipe-body");
    const countEl = document.getElementById("recipe-count");
    countEl.textContent = `${recipes.length.toLocaleString()} recipes`;

    if (recipes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-slate-400 py-8">No recipes found</td></tr>';
        renderPagination(0);
        return;
    }

    const totalPages = Math.ceil(recipes.length / ROWS_PER_PAGE);
    if (currentPage > totalPages) currentPage = 1;
    const start = (currentPage - 1) * ROWS_PER_PAGE;
    const pageRecipes = recipes.slice(start, start + ROWS_PER_PAGE);

    tbody.innerHTML = pageRecipes.map(r => `
        <tr>
            <td><span class="diet-badge ${r.Diet_type}">${capitalize(r.Diet_type)}</span></td>
            <td>${escapeHtml(r.Recipe_name)}</td>
            <td>${capitalize(r.Cuisine_type)}</td>
            <td>${r["Protein(g)"].toFixed(1)}</td>
            <td>${r["Carbs(g)"].toFixed(1)}</td>
            <td>${r["Fat(g)"].toFixed(1)}</td>
        </tr>
    `).join("");

    renderPagination(totalPages);
}

function renderPagination(totalPages) {
    const container = document.getElementById("pagination");
    if (totalPages <= 1) {
        container.innerHTML = "";
        return;
    }

    let html = "";

    // Previous button
    html += `<button onclick="goToPage(${currentPage - 1})"
             class="px-3 py-1.5 text-sm rounded-lg ${currentPage === 1
                 ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                 : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-300'}"
             ${currentPage === 1 ? 'disabled' : ''}>Prev</button>`;

    // Page numbers (show max 7 pages with ellipsis)
    const pages = getPageRange(currentPage, totalPages);
    pages.forEach(p => {
        if (p === "...") {
            html += '<span class="px-2 py-1 text-slate-400">...</span>';
        } else {
            html += `<button onclick="goToPage(${p})"
                     class="px-3 py-1.5 text-sm rounded-lg ${p === currentPage
                         ? 'bg-blue-600 text-white'
                         : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-300'}"
                     >${p}</button>`;
        }
    });

    // Next button
    html += `<button onclick="goToPage(${currentPage + 1})"
             class="px-3 py-1.5 text-sm rounded-lg ${currentPage === totalPages
                 ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                 : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-300'}"
             ${currentPage === totalPages ? 'disabled' : ''}>Next</button>`;

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
}

// Global pagination handler
window.goToPage = function(page) {
    const totalPages = Math.ceil(recipesData.length / ROWS_PER_PAGE);
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    renderRecipeTable(recipesData);
    // Scroll to table
    document.getElementById("recipe-table").scrollIntoView({ behavior: "smooth", block: "start" });
};

// ---------------------------------------------------------------------------
// Main render orchestration
// ---------------------------------------------------------------------------

function renderAll(dietType) {
    const filtered = filterInsightsData(dietType);

    updateStats(insightsData);  // Always show full summary stats
    renderBarChart(filtered);
    renderPieChart(insightsData);  // Pie always shows full distribution
    renderHeatmap(filtered);
    renderScatterChart(filtered);
    renderTopRecipes(filtered);
    renderCuisines(filtered);

    // Recipe table
    if (isUsingDemoData) {
        recipesData = filterDemoRecipes(dietType);
    }
    currentPage = 1;
    renderRecipeTable(recipesData);
}

// ---------------------------------------------------------------------------
// Event listeners & initialization
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    const dietFilter = document.getElementById("diet-filter");
    const refreshBtn = document.getElementById("refresh-btn");

    dietFilter.addEventListener("change", () => {
        const diet = dietFilter.value;
        currentPage = 1;
        if (isUsingDemoData) {
            // For demo data, just re-render with filter
            renderAll(diet);
            setLoadingAll(false);
        } else {
            loadData(diet);
        }
    });

    refreshBtn.addEventListener("click", () => {
        const diet = dietFilter.value;
        loadData(diet);
    });

    // Initial load
    loadData("all");
});
