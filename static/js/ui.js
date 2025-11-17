console.log("Tropimon UI loaded");

/**
 * Helper fetch JSON
 */
async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) {
        console.error("HTTP error for", url, res.status);
        return null;
    }
    return await res.json();
}

/**
 * Load global summary stats
 */
async function loadSummary() {
    const data = await fetchJSON("/api/summary");
    if (!data) return;

    const totalCapturesEl   = document.getElementById("stat-total-captures");
    const totalShinyEl      = document.getElementById("stat-total-shiny");
    const totalLegendariesEl= document.getElementById("stat-total-legendaries");
    const totalMythicalsEl  = document.getElementById("stat-total-mythicals");

    if (totalCapturesEl)   totalCapturesEl.textContent    = data.total_captures ?? 0;
    if (totalShinyEl)      totalShinyEl.textContent       = data.total_shiny ?? 0;
    if (totalLegendariesEl)totalLegendariesEl.textContent = data.total_legendaries ?? 0;
    if (totalMythicalsEl)  totalMythicalsEl.textContent   = data.total_mythicals ?? 0;
}

/**
 * Build a chart for player-based endpoints (/api/top/captures, /api/top/shiny, etc.)
 * data format: [{ "player": "Player #ABCD", "count": 123 }, ...]
 */
async function buildPlayerChart(canvasId, apiUrl, label) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const data = await fetchJSON(apiUrl);
    if (!data) return;

    const labels = data.map(row => row.player);
    const counts = data.map(row => row.count);

    new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label,
                data: counts,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    ticks: { color: "#dfe9ff", font: { size: 10 } },
                    grid: { display: false }
                },
                y: {
                    ticks: { color: "#dfe9ff", font: { size: 10 } },
                    grid: { color: "rgba(255,255,255,0.08)" },
                    beginAtZero: true
                }
            }
        }
    });
}

/**
 * Build a chart for species-based endpoints (/api/top/species, /api/top/shiny-species)
 * data format: [{ "species": "cobblemon:geodude", "count": 42 }, ...]
 */
async function buildSpeciesChart(canvasId, apiUrl, label) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const data = await fetchJSON(apiUrl);
    if (!data) return;

    const labels = data.map(row => row.species);
    const counts = data.map(row => row.count);

    new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label,
                data: counts,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    ticks: { display: false },
                    grid: { display: false }
                },
                y: {
                    ticks: { color: "#dfe9ff", font: { size: 10 } },
                    grid: { color: "rgba(255,255,255,0.08)" },
                    beginAtZero: true
                }
            }
        }
    });
}

/**
 * Init dashboard on DOM load
 */
async function initDashboard() {
    // Si on n'est pas sur la page dashboard, ne rien faire
    if (!document.getElementById("stat-total-captures")) return;

    await loadSummary();

    await buildPlayerChart(
        "chart-top-captures",
        "/api/top/captures",
        "Top Captures"
    );
    await buildPlayerChart(
        "chart-top-shiny",
        "/api/top/shiny",
        "Top Shiny"
    );
    await buildPlayerChart(
        "chart-top-legendaries",
        "/api/top/legendaries",
        "Top Légendaires"
    );
    await buildPlayerChart(
        "chart-top-mythicals",
        "/api/top/mythicals",
        "Top Mythiques"
    );
    await buildSpeciesChart(
        "chart-top-species",
        "/api/top/species",
        "Top Species"
    );
    await buildSpeciesChart(
        "chart-top-shiny-species",
        "/api/top/shiny-species",
        "Top Shiny Species"
    );
}

document.addEventListener("DOMContentLoaded", initDashboard);
