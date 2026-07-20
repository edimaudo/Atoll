(() => {
    const payload = JSON.parse(document.getElementById("chart-payload").textContent);

    // Locator is a pure server-rendered SVG (see app.html) -- no map tile
    // server, no JS needed, nothing that depends on external network calls.

    // ---------- charts: one Plotly line chart per pillar indicator ----------
    const COLORS = { primary: "#1c7c8c", median: "#8a97a0", compare: "#e2603a" };
    const THEME = {
        light: { font: "#16242c", grid: "#ede3cf" },
        dark: { font: "#eef3f2", grid: "#24414d" },
    };

    const chartDivs = []; // track for live re-theming

    function buildTrace(name, years, values, unit, color, dashed) {
        return {
            x: years,
            y: values,
            name,
            type: "scatter",
            mode: "lines",
            line: { color, width: 2.5, dash: dashed ? "dot" : "solid" },
            hovertemplate: `<b>Year</b>: %{x}<br><b>${name}</b>: %{y:.2f}${unit}<extra></extra>`,
        };
    }

    function themeLayout(unit, label) {
        const t = THEME[document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light"];
        return {
            margin: { t: 10, r: 20, b: 40, l: 55 },
            height: 300,
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            font: { family: "IBM Plex Sans, sans-serif", color: t.font, size: 12 },
            hovermode: "x unified",
            showlegend: false,
            xaxis: { title: "", gridcolor: t.grid },
            yaxis: { title: unit || label, gridcolor: t.grid },
        };
    }

    document.querySelectorAll("div.plotly-chart[data-indicator]").forEach((div) => {
        const key = div.dataset.indicator;
        const primaryInd = payload.primary.indicators[key];
        if (!primaryInd) return;

        const traces = [
            buildTrace(payload.primary.name, primaryInd.years, primaryInd.values, primaryInd.unit, COLORS.primary, false),
            buildTrace("Regional median", primaryInd.years, primaryInd.regional_median, primaryInd.unit, COLORS.median, true),
        ];

        if (payload.compare && payload.compare.indicators[key]) {
            const cmp = payload.compare.indicators[key];
            traces.push(buildTrace(payload.compare.name, cmp.years, cmp.values, cmp.unit, COLORS.compare, false));
        }

        Plotly.newPlot(div, traces, themeLayout(primaryInd.unit, primaryInd.label), {
            responsive: true,
            displayModeBar: false,
        });

        chartDivs.push({ div, unit: primaryInd.unit, label: primaryInd.label });
    });

    // ---------- live re-theme on dark/light toggle ----------
    document.addEventListener("atoll-theme-change", () => {
        chartDivs.forEach(({ div, unit, label }) => {
            Plotly.relayout(div, themeLayout(unit, label));
        });
    });

    // ---------- render the dynamic trend summary (markdown) ----------
    const summaryEl = document.getElementById("trend-summary-markdown");
    if (summaryEl) {
        summaryEl.innerHTML = marked.parse(summaryEl.dataset.raw || "");
    }

    // ---------- Climate Action Steps: generate plan via Airia AI ----------
    const genBtn = document.getElementById("generatePlanBtn");
    if (genBtn) {
        const actionContextEl = document.getElementById("action-context");
        const actionContext = actionContextEl ? JSON.parse(actionContextEl.textContent) : null;
        const statusEl = document.getElementById("actionPlanStatus");
        const outputEl = document.getElementById("actionPlanOutput");

        genBtn.addEventListener("click", async () => {
            statusEl.textContent = "Generating action plan...";
            outputEl.style.display = "none";
            genBtn.disabled = true;

            try {
                const res = await fetch("/api/action-plan", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(actionContext),
                });
                const data = await res.json();

                if (!res.ok) {
                    statusEl.textContent = data.error || "Couldn't generate a plan right now.";
                    return;
                }

                outputEl.innerHTML = marked.parse(data.markdown || "");
                outputEl.style.display = "block";
                statusEl.textContent = "";
            } catch (err) {
                statusEl.textContent = "Something went wrong reaching the action-plan service.";
            } finally {
                genBtn.disabled = false;
            }
        });
    }
})();
