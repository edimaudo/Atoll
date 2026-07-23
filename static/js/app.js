(() => {
    // 1. Data Payloads
    const payloadEl = document.getElementById("chart-payload");
    if (!payloadEl) return;
    const payload = JSON.parse(payloadEl.textContent);

    const COLORS = { primary: "#8a3ffc", median: "#8a97a0", compare: "#b8471f" };
    const THEME = {
        light: { font: "#161616", grid: "#e0e0e0" },
        dark: { font: "#f4f4f4", grid: "#393939" },
    };

    function isDark() {
        return document.documentElement.getAttribute("data-theme") === "dark";
    }

    function baseLayout(extra) {
        const t = THEME[isDark() ? "dark" : "light"];
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

    function wrapText(text, maxLen = 20) {
        const regex = new RegExp(`(.{1,${maxLen}})(\\s+|$)`, 'g');
        return text.replace(regex, "$1<br>").trim();
    }

    const rethemeTargets = []; 

    // ---------- Line Charts (Trends) ----------
    function themeLineLayout(unit, label) {
        const t = THEME[isDark() ? "dark" : "light"];
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

    function buildTrace(name, years, values, unit, color, dashed) {
        return {
            x: years, y: values, name, type: "scatter", mode: "lines",
            line: { color, width: 2.5, dash: dashed ? "dot" : "solid" },
            hovertemplate: `<b>Year</b>: %{x}<br><b>${name}</b>: %{y:.2f}${unit}<extra></extra>`,
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

        const layoutFn = () => themeLineLayout(primaryInd.unit, primaryInd.label);
        Plotly.newPlot(div, traces, layoutFn(), { responsive: true, displayModeBar: false });
        rethemeTargets.push({ div, redraw: layoutFn });
    });

    // ---------- Heatmaps ----------
    function drawHeatmap(divId, productMap, valueLabel) {
        const div = document.getElementById(divId);
        if (!div) return;
        if (!productMap || Object.keys(productMap).length === 0) {
            showEmptyState(div, "No data available for this chart.");
            return;
        }

        const products = Object.keys(productMap);
        // Map and wrap long labels to prevent cutoff
        const wrappedProducts = products.map(p => wrapText(p, 22));
        const allYears = [...new Set(products.flatMap((p) => productMap[p].years))].sort((a, b) => a - b);
        
        const z = products.map((p) => {
            const series = productMap[p];
            const yearToVal = Object.fromEntries(series.years.map((y, i) => [y, series.values[i]]));
            return allYears.map((y) => (y in yearToVal ? yearToVal[y] : null));
        });

        const layoutFn = () => baseLayout({ 
            height: Math.max(300, products.length * 28 + 80),
            yaxis: { automargin: true } // Let Plotly handle remaining cutoff math naturally
        });

        Plotly.newPlot(div, [{
            z, x: allYears, y: wrappedProducts, type: "heatmap", colorscale: "YlGnBu",
            hovertemplate: `<b>%{y}</b><br>Year: %{x}<br>${valueLabel}: %{z}<extra></extra>`,
        }], layoutFn(), { responsive: true, displayModeBar: false });

        rethemeTargets.push({ div, redraw: layoutFn });
    }

    // ---------- Split Ranked Charts (Top & Bottom separate) ----------
    function drawRankedSplit(divId, dataSet, unit, color, nameStr) {
        const div = document.getElementById(divId);
        if (!div) return;
        if (!dataSet || dataSet.length === 0) {
            showEmptyState(div, "No data available.");
            return;
        }

        const layoutFn = () => baseLayout({ 
            height: Math.max(250, dataSet.length * 25 + 60), 
            showlegend: false, 
            yaxis: { automargin: true },
            margin: { t: 20, r: 40, b: 40, l: 150 } 
        });

        Plotly.newPlot(div, [{
            x: dataSet.map((p) => p[1]), 
            y: dataSet.map((p) => wrapText(p[0], 18)),
            type: "bar", orientation: "h", marker: { color: color }, name: nameStr,
            text: dataSet.map((p) => p[1].toFixed(1)), textposition: "outside",
            hovertemplate: `%{y}: %{x:.2f}${unit}<extra></extra>`,
        }], layoutFn(), { responsive: true, displayModeBar: false });

        rethemeTargets.push({ div, redraw: layoutFn });
    }

    // ---------- Tail Risk ----------
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

    // ---------- Sankey ----------
    function drawSankey(divId, sankeyData) {
        const div = document.getElementById(divId);
        if (!div) return;
        if (!sankeyData?.links?.length) {
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

    // ---------- Render Groups Mapper ----------
    const renderGroups = {
        land_products: () => {
            // Primary Country
            drawHeatmap("heatmap-crop_yield", payload.primary.products?.crop_yield, "KG/HA");
            if (payload.primary.ranked?.crop_yield) {
                drawRankedSplit("ranked-crop_yield-top", payload.primary.ranked.crop_yield.top.slice().reverse(), " KG/HA", COLORS.primary, "Top 10");
                drawRankedSplit("ranked-crop_yield-bottom", payload.primary.ranked.crop_yield.bottom.slice().reverse(), " KG/HA", COLORS.compare, "Bottom 10");
            }

            drawHeatmap("heatmap-livestock_yield", payload.primary.products?.livestock_yield, "KG/AN");
            if (payload.primary.ranked?.livestock_yield) {
                drawRankedSplit("ranked-livestock_yield-top", payload.primary.ranked.livestock_yield.top.slice().reverse(), " KG/AN", COLORS.primary, "Top 10");
                drawRankedSplit("ranked-livestock_yield-bottom", payload.primary.ranked.livestock_yield.bottom.slice().reverse(), " KG/AN", COLORS.compare, "Bottom 10");
            }

            // Compare Country
            if (payload.compare) {
                drawHeatmap("heatmap-crop_yield-compare", payload.compare.products?.crop_yield, "KG/HA");
                if (payload.compare.ranked?.crop_yield) {
                    drawRankedSplit("ranked-crop_yield-compare-top", payload.compare.ranked.crop_yield.top.slice().reverse(), " KG/HA", COLORS.primary, "Top 10");
                    drawRankedSplit("ranked-crop_yield-compare-bottom", payload.compare.ranked.crop_yield.bottom.slice().reverse(), " KG/HA", COLORS.compare, "Bottom 10");
                }

                drawHeatmap("heatmap-livestock_yield-compare", payload.compare.products?.livestock_yield, "KG/AN");
                if (payload.compare.ranked?.livestock_yield) {
                    drawRankedSplit("ranked-livestock_yield-compare-top", payload.compare.ranked.livestock_yield.top.slice().reverse(), " KG/AN", COLORS.primary, "Top 10");
                    drawRankedSplit("ranked-livestock_yield-compare-bottom", payload.compare.ranked.livestock_yield.bottom.slice().reverse(), " KG/AN", COLORS.compare, "Bottom 10");
                }
            }
        },
        land_risk: () => {
            drawTailRisk("tailrisk-rainfall_anomaly", payload.primary.tail_risk?.rainfall_anomaly,
                payload.compare ? payload.compare.tail_risk?.rainfall_anomaly : null,
                payload.primary.name, payload.compare ? payload.compare.name : null, "mm");
        },
        ocean_risk: () => {
            drawTailRisk("tailrisk-surface_temp_anomaly", payload.primary.tail_risk?.surface_temp_anomaly,
                payload.compare ? payload.compare.tail_risk?.surface_temp_anomaly : null,
                payload.primary.name, payload.compare ? payload.compare.name : null, "\u00b0C");
        },
        people_power: () => {
            // Merged Heatmap and Sankey into one mapped render group matching the HTML tab structure
            drawHeatmap("heatmap-power_sources", payload.primary.power_sources, "GWH");
            drawSankey("sankey-power", payload.primary.power_sankey);
            if (payload.compare) {
                drawHeatmap("heatmap-power_sources-compare", payload.compare.power_sources, "GWH");
                drawSankey("sankey-power-compare", payload.compare.power_sankey);
            }
        }
    };

    // ---------- Tab Controller ----------
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
            if(renderGroups[group]) renderGroups[group]();
            renderedGroups.add(group);
        } else {
            panel.querySelectorAll(".plotly-chart.js-plotly-plot").forEach((div) => {
                Plotly.Plots.resize(div);
            });
        }
    }

    document.querySelectorAll(".tabs").forEach((tabRoot) => {
        const buttons = Array.from(tabRoot.querySelectorAll(".tab-btn"));

        buttons.forEach((btn, i) => {
            btn.addEventListener("click", () => activateTab(tabRoot, buttons, btn));

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

    // ---------- Live Retheming ----------
    document.addEventListener("atoll-theme-change", () => {
        rethemeTargets.forEach(({ div, redraw }) => Plotly.relayout(div, redraw()));
    });

    // ---------- Markdown Rendering & API Calling ----------
    const summaryEl = document.getElementById("trend-summary-markdown");
    if (summaryEl) {
        summaryEl.innerHTML = marked.parse(summaryEl.dataset.raw || "");
    }

    const generateBtn = document.getElementById("generatePlanBtn");
    const outputDiv = document.getElementById("actionPlanOutput");
    const statusDiv = document.getElementById("actionPlanStatus");
    const contextEl = document.getElementById("action-context");

    if (generateBtn) {
        generateBtn.addEventListener("click", async () => {
            const actionContext = contextEl ? JSON.parse(contextEl.textContent) : {};
            const country = actionContext.country || "";
            const summary = summaryEl ? summaryEl.dataset.raw : actionContext.summary || "";

            generateBtn.disabled = true;
            statusDiv.textContent = "Generating custom action plan...";
            outputDiv.style.display = "none";

            try {
                const response = await fetch("/api/action-plan", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ country, summary }),
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.error || `Server error: ${response.status}`);
                }

                const data = await response.json();
                outputDiv.innerHTML = typeof marked !== "undefined" ? marked.parse(data.markdown) : data.markdown;
                outputDiv.style.display = "block";
                statusDiv.textContent = "";
            } catch (err) {
                statusDiv.textContent = `Failed to generate plan: ${err.message}`;
            } finally {
                generateBtn.disabled = false;
            }
        });
    }
})();
