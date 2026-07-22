(() => {
    const v2El = document.getElementById("v2-payload");
    if (!v2El) return; // not on a v2 page
    const v2 = JSON.parse(v2El.textContent);

    const COLORS = { primary: "#8a3ffc", median: "#8a97a0", compare: "#b8471f" };

    function isDark() {
        return document.documentElement.getAttribute("data-theme") === "dark";
    }
    function baseLayout(extra) {
        const t = isDark() ? { font: "#f4f4f4", grid: "#393939" } : { font: "#161616", grid: "#e0e0e0" };
        return Object.assign({
            margin: { t: 20, r: 20, b: 40, l: 90 },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            font: { family: "IBM Plex Sans, sans-serif", color: t.font, size: 11 },
        }, extra || {});
    }

    function showEmptyState(div, message) {
        if (!div) return;
        div.innerHTML = `<div class="chart-empty-state">${message}</div>`;
    }

    const rethemeTargets = []; // { div, redraw } for every chart ever drawn, even if now hidden in an unselected tab
    document.addEventListener("atoll-theme-change", () => {
        rethemeTargets.forEach(({ div, redraw }) => Plotly.relayout(div, redraw()));
    });

    // ---------- 1. Product heatmaps (crop_yield, livestock_yield, power_sources) ----------
    function drawHeatmap(divId, productMap, valueLabel) {
        const div = document.getElementById(divId);
        if (!div) return;
        if (!productMap || Object.keys(productMap).length === 0) {
            showEmptyState(div, "No data available for this chart.");
            return;
        }

        const products = Object.keys(productMap);
        const allYears = [...new Set(products.flatMap((p) => productMap[p].years))].sort((a, b) => a - b);
        const z = products.map((p) => {
            const series = productMap[p];
            const yearToVal = Object.fromEntries(series.years.map((y, i) => [y, series.values[i]]));
            return allYears.map((y) => (y in yearToVal ? yearToVal[y] : null));
        });

        const layoutFn = () => baseLayout({ height: Math.max(300, products.length * 22 + 80) });
        Plotly.newPlot(div, [{
            z, x: allYears, y: products, type: "heatmap", colorscale: "YlGnBu",
            hovertemplate: `<b>%{y}</b><br>Year: %{x}<br>${valueLabel}: %{z}<extra></extra>`,
        }], layoutFn(), { responsive: true, displayModeBar: false });

        rethemeTargets.push({ div, redraw: layoutFn });
    }

    // ---------- 2. Ranked top/bottom-10 bar charts ----------
    function drawRanked(divId, ranked, unit) {
        const div = document.getElementById(divId);
        if (!div) return;
        if (!ranked || (!ranked.top.length && !ranked.bottom.length)) {
            showEmptyState(div, "No data available for this chart.");
            return;
        }

        const top = ranked.top.slice().reverse();
        const bottom = ranked.bottom.slice().reverse();

        const layoutFn = () => baseLayout({ height: 420, showlegend: true, legend: { orientation: "h" }, margin: { t: 40, r: 20, b: 40, l: 200 } });
        Plotly.newPlot(div, [
            {
                x: top.map((p) => p[1]), y: top.map((p) => `${p[0]} (top)`),
                type: "bar", orientation: "h", marker: { color: COLORS.primary }, name: "Top 10",
                text: top.map((p) => p[1].toFixed(1)), textposition: "outside",
                hovertemplate: `%{y}: %{x:.2f}${unit}<extra></extra>`,
            },
            {
                x: bottom.map((p) => p[1]), y: bottom.map((p) => `${p[0]} (bottom)`),
                type: "bar", orientation: "h", marker: { color: COLORS.compare }, name: "Bottom 10",
                text: bottom.map((p) => p[1].toFixed(1)), textposition: "outside",
                hovertemplate: `%{y}: %{x:.2f}${unit}<extra></extra>`,
            },
        ], layoutFn(), { responsive: true, displayModeBar: false });

        rethemeTargets.push({ div, redraw: layoutFn });
    }

    // ---------- 3. Tail-risk: overlay compare country on the same chart ----------
    function drawTailRisk(divId, primaryTR, compareTR, primaryName, compareName, unit) {
        const div = document.getElementById(divId);
        if (!div) return;
        if (!primaryTR || !primaryTR.years.length) {
            showEmptyState(div, "No data available for this chart.");
            return;
        }

        const traces = [{
            x: primaryTR.years, y: primaryTR.values, mode: "lines", name: primaryName,
            line: { color: COLORS.primary, width: 1.5 },
            hovertemplate: `Year: %{x}<br>${primaryName}: %{y:.2f}${unit}<extra></extra>`,
        }];

        const extremeX = primaryTR.extremes.map((e) => e.year);
        const extremeY = primaryTR.extremes.map((e) => e.value);
        if (extremeX.length) {
            traces.push({
                x: extremeX, y: extremeY, mode: "markers", name: "Extreme events",
                marker: { color: COLORS.compare, size: 9, symbol: "circle-open", line: { width: 2 } },
                hovertemplate: `Extreme year: %{x}<br>Value: %{y:.2f}${unit}<extra></extra>`,
            });
        }
        if (compareTR) {
            traces.push({
                x: compareTR.years, y: compareTR.values, mode: "lines", name: compareName,
                line: { color: COLORS.median, width: 1.5, dash: "dot" },
                hovertemplate: `Year: %{x}<br>${compareName}: %{y:.2f}${unit}<extra></extra>`,
            });
        }

        const layoutFn = () => baseLayout({
            height: 300, showlegend: true, legend: { orientation: "h" },
            shapes: [
                { type: "line", x0: primaryTR.years[0], x1: primaryTR.years[primaryTR.years.length - 1], y0: primaryTR.mean + primaryTR.threshold, y1: primaryTR.mean + primaryTR.threshold, line: { color: COLORS.compare, dash: "dot", width: 1 } },
                { type: "line", x0: primaryTR.years[0], x1: primaryTR.years[primaryTR.years.length - 1], y0: primaryTR.mean - primaryTR.threshold, y1: primaryTR.mean - primaryTR.threshold, line: { color: COLORS.compare, dash: "dot", width: 1 } },
            ],
        });
        Plotly.newPlot(div, traces, layoutFn(), { responsive: true, displayModeBar: false });
        rethemeTargets.push({ div, redraw: layoutFn });
    }

    // ---------- 4. Sankey: dedicated second diagram for the compare country ----------
    function drawSankey(divId, sankeyData) {
        const div = document.getElementById(divId);
        if (!div) return;
        if (!sankeyData || !sankeyData.links.length) {
            showEmptyState(div, "No power generation flow data available for this chart.");
            return;
        }

        const nodes = [...new Set(sankeyData.links.flatMap((l) => [l.source, l.target]))];
        const nodeIndex = Object.fromEntries(nodes.map((n, i) => [n, i]));

        const layoutFn = () => baseLayout({ height: 420 });
        Plotly.newPlot(div, [{
            type: "sankey",
            node: { label: nodes, pad: 12, thickness: 16, color: COLORS.primary },
            link: {
                source: sankeyData.links.map((l) => nodeIndex[l.source]),
                target: sankeyData.links.map((l) => nodeIndex[l.target]),
                value: sankeyData.links.map((l) => l.value),
            },
        }], layoutFn(), { responsive: true, displayModeBar: false });
        rethemeTargets.push({ div, redraw: layoutFn });
    }

    // ---------- render groups: each fires ONCE, the first time its tab opens ----------
    const renderGroups = {
        land_products: () => {
            drawHeatmap("heatmap-crop_yield", v2.primary.products.crop_yield, "KG/HA");
            drawRanked("ranked-crop_yield", v2.primary.ranked.crop_yield, " KG/HA");
            drawHeatmap("heatmap-livestock_yield", v2.primary.products.livestock_yield, "KG/AN");
            drawRanked("ranked-livestock_yield", v2.primary.ranked.livestock_yield, " KG/AN");
            if (v2.compare) {
                drawHeatmap("heatmap-crop_yield-compare", v2.compare.products.crop_yield, "KG/HA");
                drawRanked("ranked-crop_yield-compare", v2.compare.ranked.crop_yield, " KG/HA");
                drawHeatmap("heatmap-livestock_yield-compare", v2.compare.products.livestock_yield, "KG/AN");
                drawRanked("ranked-livestock_yield-compare", v2.compare.ranked.livestock_yield, " KG/AN");
            }
        },
        land_risk: () => {
            drawTailRisk("tailrisk-rainfall_anomaly", v2.primary.tail_risk.rainfall_anomaly,
                v2.compare ? v2.compare.tail_risk.rainfall_anomaly : null,
                v2.primary.name, v2.compare ? v2.compare.name : null, "mm");
        },
        ocean_risk: () => {
            drawTailRisk("tailrisk-surface_temp_anomaly", v2.primary.tail_risk.surface_temp_anomaly,
                v2.compare ? v2.compare.tail_risk.surface_temp_anomaly : null,
                v2.primary.name, v2.compare ? v2.compare.name : null, "\u00b0C");
        },
        people_mix: () => {
            drawHeatmap("heatmap-power_sources", v2.primary.power_sources, "GWH");
            if (v2.compare) drawHeatmap("heatmap-power_sources-compare", v2.compare.power_sources, "GWH");
        },
        people_flow: () => {
            drawSankey("sankey-power", v2.primary.power_sankey);
            if (v2.compare) drawSankey("sankey-power-compare", v2.compare.power_sankey);
        },
    };

    // ---------- tab controller ----------
    const renderedGroups = new Set();

    function activateTab(tabRoot, buttons, btn) {
        const targetId = btn.dataset.target;

        buttons.forEach((b) => {
            const isActive = b === btn;
            b.classList.toggle("active", isActive);
            b.setAttribute("aria-selected", isActive ? "true" : "false");
            b.tabIndex = isActive ? 0 : -1;
        });
        tabRoot.querySelectorAll(".tab-panel").forEach((panel) => {
            panel.style.display = panel.id === targetId ? "block" : "none";
        });

        const panel = tabRoot.querySelector(`#${targetId}`);
        if (!panel) return;
        const group = panel.dataset.renderGroup;

        if (group && !renderedGroups.has(group)) {
            renderGroups[group]();
            renderedGroups.add(group);
        } else {
            // Already rendered earlier (or is the always-visible Trends
            // panel) -- resize in case it drifted while hidden.
            // Plotly adds "js-plotly-plot" to a div once it's been drawn,
            // so that's a reliable signal a chart actually exists there.
            panel.querySelectorAll(".plotly-chart.js-plotly-plot").forEach((div) => {
                Plotly.Plots.resize(div);
            });
        }
    }

    document.querySelectorAll(".tabs").forEach((tabRoot) => {
        const buttons = Array.from(tabRoot.querySelectorAll(".tab-btn"));

        buttons.forEach((btn, i) => {
            btn.addEventListener("click", () => activateTab(tabRoot, buttons, btn));

            // WAI-ARIA tabs pattern: Left/Right arrow moves focus and
            // activates the adjacent tab; Home/End jump to first/last.
            btn.addEventListener("keydown", (e) => {
                let targetIndex = null;
                if (e.key === "ArrowRight") targetIndex = (i + 1) % buttons.length;
                else if (e.key === "ArrowLeft") targetIndex = (i - 1 + buttons.length) % buttons.length;
                else if (e.key === "Home") targetIndex = 0;
                else if (e.key === "End") targetIndex = buttons.length - 1;
                else return;

                e.preventDefault();
                buttons[targetIndex].focus();
                activateTab(tabRoot, buttons, buttons[targetIndex]);
            });
        });
    });
})();
