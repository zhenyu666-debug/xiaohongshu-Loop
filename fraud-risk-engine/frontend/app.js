// fraud-risk-engine frontend — vanilla JS, no build, no CDN.
// Talks to the FastAPI app at /api/* endpoints.

const API = {
  health: () => fetch("/api/health").then((r) => r.json()),
  config: () => fetch("/api/config").then((r) => r.json()),
  dataset: () => fetch("/api/dataset").then((r) => r.json()),
  buildDataset: (body) =>
    fetch("/api/dataset", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then((r) => r.json()),
  runLoader: (body) =>
    fetch("/api/loader/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body || { stages: ["ping"] }),
    }).then((r) => r.json()),
  runDetector: (body) =>
    fetch("/api/detector/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body || { backend: "auto" }),
    }).then((r) => r.json()),
  runLatest: () => fetch("/api/detector/latest").then((r) => r.json()),
  staticMemory: () => fetch("/api/memory/static").then((r) => r.json()),
  dynamicMemory: () => fetch("/api/memory/dynamic").then((r) => r.json()),
};

// ---------------------------------------------------------------------------
// Tiny SVG helpers
// ---------------------------------------------------------------------------

const NS = "http://www.w3.org/2000/svg";

function svgEl(name, attrs) {
  const el = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs || {})) {
    el.setAttribute(k, v);
  }
  return el;
}

function clear(svg) {
  while (svg.firstChild) svg.removeChild(svg.firstChild);
}

function svgBarChart(svg, labels, values, colors) {
  clear(svg);
  const W = 320, H = 220, PAD = 30;
  const max = Math.max(...values, 1);
  const bw = (W - PAD * 2) / labels.length;
  const xAxis = svgEl("line", { x1: PAD, y1: H - PAD, x2: W - PAD, y2: H - PAD, stroke: "#444" });
  svg.appendChild(xAxis);
  labels.forEach((lab, i) => {
    const x = PAD + i * bw + bw * 0.15;
    const y = H - PAD - ((H - PAD * 2) * (values[i] || 0)) / max;
    const h = (H - PAD * 2) * (values[i] || 0) / max;
    const r = svgEl("rect", {
      x, y, width: bw * 0.7, height: h,
      fill: colors[i % colors.length] || "#6ad1ff",
    });
    svg.appendChild(r);
    const t = svgEl("text", {
      x: x + bw * 0.35, y: H - PAD + 14,
      "text-anchor": "middle",
      fill: "#8a91a4",
      "font-size": "10",
    });
    t.textContent = lab;
    svg.appendChild(t);
    const v = svgEl("text", {
      x: x + bw * 0.35, y: y - 4,
      "text-anchor": "middle",
      fill: "#d7dde9",
      "font-size": "10",
    });
    v.textContent = values[i];
    svg.appendChild(v);
  });
}

function svgPie(svg, labels, values, colors) {
  clear(svg);
  const cx = 160, cy = 110, r = 80;
  const total = values.reduce((a, b) => a + b, 0) || 1;
  let angle = -Math.PI / 2;
  labels.forEach((lab, i) => {
    const v = values[i];
    const slice = (v / total) * Math.PI * 2;
    const x1 = cx + r * Math.cos(angle);
    const y1 = cy + r * Math.sin(angle);
    angle += slice;
    const x2 = cx + r * Math.cos(angle);
    const y2 = cy + r * Math.sin(angle);
    const large = slice > Math.PI ? 1 : 0;
    const path = svgEl("path", {
      d: `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`,
      fill: colors[i % colors.length],
      opacity: 0.85,
    });
    svg.appendChild(path);
    const tx = cx + r * 0.6 * Math.cos((angle - slice / 2));
    const ty = cy + r * 0.6 * Math.sin((angle - slice / 2));
    const t = svgEl("text", {
      x: tx, y: ty, "text-anchor": "middle", fill: "#0f1115", "font-size": "11",
    });
    t.textContent = `${lab}\n${v}`;
    svg.appendChild(t);
  });
}

function svgDotPlot(svg, scores) {
  clear(svg);
  const W = 320, H = 220, PAD = 30;
  const N = scores.length;
  scores.forEach((s, i) => {
    const x = PAD + ((W - PAD * 2) * i) / Math.max(1, N - 1);
    const y = H - PAD - (H - PAD * 2) * s.score;
    const dot = svgEl("circle", {
      cx: x, cy: y, r: 5,
      fill: severityColor(s.severity),
      stroke: "#0f1115", "stroke-width": 1,
    });
    svg.appendChild(dot);
    const lab = svgEl("text", {
      x, y: H - PAD + 12,
      "text-anchor": "middle", fill: "#8a91a4", "font-size": "8",
    });
    lab.textContent = s.kind.split("_")[0].slice(0, 4);
    svg.appendChild(lab);
  });
  const axis = svgEl("line", { x1: PAD, y1: H - PAD, x2: W - PAD, y2: H - PAD, stroke: "#444" });
  svg.appendChild(axis);
}

function severityColor(s) {
  switch ((s || "").toLowerCase()) {
    case "critical": return "#ff5d6c";
    case "high": return "#ff9c4a";
    case "medium": return "#ffd866";
    case "low": return "#6ad1ff";
    default: return "#999";
  }
}

function renderGraphOverview(svg, snapshot, planted, alerts) {
  clear(svg);
  const W = 1100, H = 360;
  const involved = new Set();
  (alerts || []).forEach((a) => (a.involved || []).forEach((v) => involved.add(v)));
  const plantedSet = new Set();
  (planted || []).forEach((r) => (r.accounts || []).forEach((a) => plantedSet.add(a)));

  // Use first 30 vertices of each kind for layout.
  const accountIds = Object.keys(snapshot?.vertices || {}).length === 0
    ? Array.from({ length: 24 }, (_, i) => `A${i.toString().padStart(6, "0")}`)
    : [];

  // Place 30 nodes on a circle.
  const N = 28;
  const nodes = [];
  for (let i = 0; i < N; i++) {
    const id = `A${(i * 53).toString().padStart(6, "0")}`;
    const angle = (i / N) * Math.PI * 2;
    const r = 130;
    nodes.push({
      id,
      x: W / 2 + r * Math.cos(angle),
      y: H / 2 + r * Math.sin(angle),
      isPlanted: plantedSet.has(id) || involved.has(id),
    });
  }
  // Edges: connect consecutive nodes (linked-list). Highlight if both planted.
  for (let i = 0; i < N; i++) {
    const a = nodes[i];
    const b = nodes[(i + 1) % N];
    const planted = a.isPlanted && b.isPlanted;
    const line = svgEl("line", {
      x1: a.x, y1: a.y, x2: b.x, y2: b.y,
      stroke: planted ? "#ff5d6c" : "#3a3f4f",
      "stroke-width": planted ? 2.5 : 1.2,
      opacity: planted ? 0.95 : 0.55,
    });
    svg.appendChild(line);
  }
  nodes.forEach((n) => {
    const c = svgEl("circle", {
      cx: n.x, cy: n.y, r: n.isPlanted ? 8 : 5,
      fill: n.isPlanted ? "#ff5d6c" : "#6ad1ff",
      stroke: "#0f1115", "stroke-width": 1.5,
    });
    svg.appendChild(c);
    const t = svgEl("text", {
      x: n.x, y: n.y + 3,
      "text-anchor": "middle", fill: "#0f1115",
      "font-size": 9, "font-weight": 600,
    });
    t.textContent = n.id.split("A").join("");
    svg.appendChild(t);
  });
  // Legend
  const legend = svgEl("g", {});
  legend.setAttribute("transform", "translate(20, 20)");
  const items = [
    ["#6ad1ff", "Account"],
    ["#ff5d6c", "In a fraud ring"],
  ];
  items.forEach(([c, label], i) => {
    legend.appendChild(svgEl("circle", { cx: i * 120, cy: 8, r: 5, fill: c }));
    const t = svgEl("text", { x: i * 120 + 12, y: 12, fill: "#d7dde9", "font-size": "11" });
    t.textContent = label;
    legend.appendChild(t);
  });
  svg.appendChild(legend);
}

function renderFocusGraph(svg, accounts) {
  clear(svg);
  const W = 900, H = 320;
  const list = (accounts || []).slice(0, 18);
  const N = list.length || 1;
  list.forEach((id, i) => {
    const angle = (i / N) * Math.PI * 2;
    const x = W / 2 + 100 * Math.cos(angle);
    const y = H / 2 + 100 * Math.sin(angle);
    const c = svgEl("circle", { cx: x, cy: y, r: 9, fill: "#ff9c4a", stroke: "#0f1115", "stroke-width": 1.5 });
    svg.appendChild(c);
    const lab = svgEl("text", { x, y: y + 4, "text-anchor": "middle", fill: "#0f1115", "font-size": 10 });
    lab.textContent = id;
    svg.appendChild(lab);
    if (i > 0) {
      const prev = list[i - 1];
      const a = (i / N) * Math.PI * 2 - (Math.PI * 2) / N;
      const pa = W / 2 + 100 * Math.cos(a);
      const pa2 = H / 2 + 100 * Math.sin(a);
      const line = svgEl("line", { x1: x, y1: y, x2: pa, y2: pa2, stroke: "#ff9c4a", "stroke-width": 1.5, opacity: 0.8 });
      svg.appendChild(line);
    }
  });
}

// ---------------------------------------------------------------------------
// Renderer
// ---------------------------------------------------------------------------

const State = { alerts: [], snapshot: {}, planted: [] };

function setBadgeForTigerGraph(health) {
  const badge = document.getElementById("tigergraph-badge");
  const tg = health.tigergraph || {};
  if (tg.status === "ok") {
    badge.textContent = "TigerGraph OK";
    badge.classList.add("ok");
  } else if (tg.status === "degraded") {
    badge.textContent = "TigerGraph degraded";
    badge.classList.add("degraded");
  } else {
    badge.textContent = "TigerGraph offline — using local fallback";
    badge.classList.add("unreachable");
  }
}

function renderMultiView() {
  const alerts = State.alerts || [];
  // Severity counts
  const sevCount = alerts.reduce((acc, a) => ((acc[a.severity] = (acc[a.severity] || 0) + 1), acc), {});
  const sevs = ["critical", "high", "medium", "low"].filter((s) => sevCount[s]);
  svgBarChart(
    document.getElementById("svg-severity"),
    sevs, sevs.map((s) => sevCount[s]),
    sevs.map(severityColor),
  );

  // Kind composition
  const kinds = Array.from(new Set(alerts.map((a) => a.kind)));
  svgPie(
    document.getElementById("svg-kind"),
    kinds, kinds.map((k) => alerts.filter((a) => a.kind === k).length),
    ["#6ad1ff", "#ff9c4a", "#ffd866", "#ff5d6c", "#a08fff"],
  );

  // Risk score dot plot
  svgDotPlot(
    document.getElementById("svg-score"),
    alerts.slice(0, 15),
  );

  // Graph overview
  renderGraphOverview(document.getElementById("svg-graph"), State.snapshot, State.planted, alerts);
}

function renderDashboard() {
  const snap = State.snapshot || {};
  const verts = snap.vertices || {};
  const edges = snap.edges || {};
  document.getElementById("kpi-vertices").textContent =
    Object.values(verts).reduce((a, b) => a + b, 0);
  document.getElementById("kpi-edges").textContent =
    Object.values(edges).reduce((a, b) => a + b, 0);
  document.getElementById("kpi-alerts").textContent = State.alerts.length;
  document.getElementById("kpi-backend").textContent = State.backend || "—";

  const tv = document.getElementById("tbl-vertex");
  tv.innerHTML = "<tr><th>Type</th><th>Count</th></tr>" +
    Object.entries(verts).map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");
  const te = document.getElementById("tbl-edge");
  te.innerHTML = "<tr><th>Type</th><th>Count</th></tr>" +
    Object.entries(edges).map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");

  const ta = document.getElementById("tbl-alerts");
  ta.innerHTML = "<tr><th>Severity</th><th>Kind</th><th>Score</th><th>Title</th></tr>" +
    (State.alerts || []).map((a, i) =>
      `<tr data-idx="${i}"><td><span class="chip" style="color:${severityColor(a.severity)}">${a.severity}</span></td>` +
      `<td>${a.kind}</td><td>${a.score.toFixed(3)}</td><td>${a.title}</td></tr>`).join("");

  ta.querySelectorAll("tr[data-idx]").forEach((row) => {
    row.addEventListener("click", () => {
      switchView("investigation");
      const idx = Number(row.dataset.idx);
      renderInvestigation(State.alerts[idx]);
    });
  });
}

function renderInvestigation(focus) {
  const tbl = document.getElementById("tbl-investigation");
  tbl.innerHTML = "<tr><th>Severity</th><th>Kind</th><th>Score</th><th>Title</th></tr>" +
    State.alerts.map((a, i) =>
      `<tr data-idx="${i}" class="${focus && focus === a ? "active" : ""}">` +
      `<td><span class="chip" style="color:${severityColor(a.severity)}">${a.severity}</span></td>` +
      `<td>${a.kind}</td><td>${a.score.toFixed(3)}</td><td>${a.title}</td></tr>`).join("");
  tbl.querySelectorAll("tr[data-idx]").forEach((row) => {
    row.addEventListener("click", () => {
      const a = State.alerts[Number(row.dataset.idx)];
      document.getElementById("focus-title").textContent = a.title;
      document.getElementById("focus-description").textContent = a.description;
      renderFocusGraph(document.getElementById("svg-focus"), a.involved);
      const cl = document.getElementById("focus-involved");
      cl.innerHTML = (a.involved || []).slice(0, 60).map((x) => `<span class="chip">${x}</span>`).join("");
      document.getElementById("focus-evidence").textContent = JSON.stringify(a.evidence, null, 2);
    });
  });
  if (focus) {
    document.getElementById("focus-title").textContent = focus.title;
    document.getElementById("focus-description").textContent = focus.description;
    renderFocusGraph(document.getElementById("svg-focus"), focus.involved);
    const cl = document.getElementById("focus-involved");
    cl.innerHTML = (focus.involved || []).slice(0, 60).map((x) => `<span class="chip">${x}</span>`).join("");
    document.getElementById("focus-evidence").textContent = JSON.stringify(focus.evidence, null, 2);
  }
}

async function renderMemory() {
  const s = await API.staticMemory();
  document.getElementById("md-static").textContent = s.markdown || "(empty)";
  document.getElementById("static-meta").textContent =
    `(${s.char_count} chars @ ${s.path})`;
  const d = await API.dynamicMemory();
  document.getElementById("md-dynamic").textContent = d.markdown || "(empty)";
  document.getElementById("dynamic-meta").textContent =
    `(${d.char_count} chars · ${d.alert_count} alerts)`;
}

function switchView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.getElementById("view-" + name).classList.add("active");
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.view === name));
  if (name === "memory") renderMemory();
}

async function refreshAll() {
  const health = await API.health();
  setBadgeForTigerGraph(health);

  // Build dataset + run detector. backend=auto (falls back to local if
  // TigerGraph is unreachable).
  await API.buildDataset({});
  const det = await API.runDetector({ backend: "auto", top_k: 50 });

  State.alerts = det.alerts || [];
  State.snapshot = det.snapshot || {};
  State.planted = (det.snapshot && det.snapshot.planted_rings) || [];
  State.backend = det.backend || "—";

  renderMultiView();
  renderDashboard();
  renderInvestigation(State.alerts[0]);
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => switchView(tab.dataset.view));
});
document.getElementById("btn-refresh").addEventListener("click", refreshAll);

refreshAll().catch((err) => {
  console.error("refresh failed", err);
  document.getElementById("tigergraph-badge").textContent = "API offline";
  document.getElementById("tigergraph-badge").classList.add("unreachable");
});
