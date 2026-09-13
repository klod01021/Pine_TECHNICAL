const form = document.getElementById("pricer-form");
const priceBtn = document.getElementById("price-btn");
const strikeVolEl = document.getElementById("strike-vol");
const warningsEl = document.getElementById("warnings");
const customPointsEl = document.getElementById("custom-points");
const customPasteEl = document.getElementById("custom-paste");

const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });
const fmtPct = (x) => `${(x * 100).toFixed(2)}%`;
const fmtNum = (x) => (x === null || x === undefined || Number.isNaN(x) ? "—" : fmt.format(x));
const round4 = (x) => Number(Number(x).toFixed(4));

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: "#8b97a8", boxWidth: 10, font: { size: 11 } },
    },
  },
  scales: {
    x: {
      ticks: { color: "#8b97a8", maxTicksLimit: 6 },
      grid: { color: "rgba(36,48,66,0.7)" },
    },
    y: {
      ticks: { color: "#8b97a8" },
      grid: { color: "rgba(36,48,66,0.7)" },
    },
  },
};

const smileChart = new Chart(document.getElementById("smile-chart"), {
  type: "line",
  data: {
    labels: [],
    datasets: [
      {
        label: "σ(K)",
        data: [],
        borderColor: "#d4a017",
        backgroundColor: "rgba(212,160,23,0.12)",
        fill: true,
        tension: 0.25,
        pointRadius: 0,
      },
      {
        label: "Pillars",
        data: [],
        showLine: false,
        pointRadius: 5,
        pointBackgroundColor: "#6ee7b7",
      },
    ],
  },
  options: {
    ...chartDefaults,
    scales: {
      ...chartDefaults.scales,
      y: {
        ...chartDefaults.scales.y,
        ticks: {
          color: "#8b97a8",
          callback: (v) => `${(v * 100).toFixed(1)}%`,
        },
      },
    },
  },
});

const payoffChart = new Chart(document.getElementById("payoff-chart"), {
  type: "line",
  data: {
    labels: [],
    datasets: [
      {
        label: "Intrinsic",
        data: [],
        borderColor: "#fb7185",
        pointRadius: 0,
        tension: 0.05,
      },
      {
        label: "Black–Scholes value",
        data: [],
        borderColor: "#6ee7b7",
        pointRadius: 0,
        tension: 0.2,
      },
    ],
  },
  options: chartDefaults,
});

function pct(name) {
  return Number(form.elements[name].value) / 100;
}

function selected(name) {
  return form.querySelector(`input[name="${name}"]:checked`).value;
}

function smileSource() {
  return selected("smile_source");
}

function defaultPoints() {
  const spot = Number(form.elements.spot.value) || 100;
  const atm = Number(form.elements.atm_vol_pct.value) || 20;
  return [
    { strike: round4(spot * 0.8), volPct: round4(atm + 4) },
    { strike: round4(spot * 0.9), volPct: round4(atm + 1.5) },
    { strike: round4(spot * 1.0), volPct: round4(atm) },
    { strike: round4(spot * 1.1), volPct: round4(Math.max(0.01, atm - 0.8)) },
    { strike: round4(spot * 1.2), volPct: round4(Math.max(0.01, atm - 1.2)) },
  ];
}

function readCustomPoints() {
  return [...customPointsEl.querySelectorAll(".vol-row")]
    .map((row) => ({
      strike: Number(row.querySelector(".pt-strike").value),
      volPct: Number(row.querySelector(".pt-vol").value),
    }))
    .filter((p) => p.strike > 0 && p.volPct > 0);
}

function renderCustomPoints(points) {
  const rows = points.length ? points : defaultPoints();
  customPointsEl.innerHTML = rows
    .map(
      (p) => `<div class="vol-row">
        <label>Strike
          <input class="pt-strike" type="number" step="0.0001" min="0.0001" value="${p.strike}" />
        </label>
        <label>Vol %
          <input class="pt-vol" type="number" step="0.01" min="0.01" value="${p.volPct}" />
        </label>
        <button type="button" class="ghost remove" aria-label="Remove point">×</button>
      </div>`
    )
    .join("");
}

function toggleSmileSource() {
  const custom = smileSource() === "custom";
  document.getElementById("quotes-block").classList.toggle("hidden", custom);
  document.getElementById("custom-block").classList.toggle("hidden", !custom);
  if (custom && !customPointsEl.querySelector(".vol-row")) {
    renderCustomPoints(defaultPoints());
  }
}

function payload() {
  const style = selected("option_style");
  const source = smileSource();
  const body = {
    spot: Number(form.elements.spot.value),
    strike: Number(form.elements.strike.value),
    rate: pct("rate_pct"),
    dividend: pct("div_pct"),
    atm_vol: pct("atm_vol_pct"),
    rr_25d: pct("rr_pct"),
    bf_25d: pct("bf_pct"),
    rr_10d: pct("rr_10_pct"),
    bf_10d: pct("bf_10_pct"),
    expiry_years: Number(form.elements.expiry_days.value) / 365,
    option_style: style,
    option_type: selected("option_type"),
    model: selected("model"),
    mc_paths: Number(form.elements.mc_paths.value),
    mc_steps: Number(form.elements.mc_steps.value),
    compare_models: form.elements.compare_models.checked,
    rebate: Number(form.elements.rebate.value || 0),
    smile_source: source,
  };
  if (source === "custom") {
    body.custom_vols = readCustomPoints().map((p) => ({
      strike: p.strike,
      vol: p.volPct / 100,
    }));
  }
  if (style === "barrier") {
    body.barrier_type = form.elements.barrier_type.value;
    body.barrier = Number(form.elements.barrier.value);
  }
  return body;
}

function toggleBarrier() {
  const show = selected("option_style") === "barrier";
  document.getElementById("barrier-fields").classList.toggle("hidden", !show);
}

async function fetchJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail);
    throw new Error(message);
  }
  return data;
}

function renderSmile(smile, strikeVol) {
  strikeVolEl.textContent = `strike vol ${fmtPct(strikeVol)}`;
  const custom = (smile.pillars || []).some((p) => p.label === "Input");
  smileChart.data.labels = smile.strikes.map((k) => Number(k.toFixed(2)));
  smileChart.data.datasets[1] = {
    label: custom ? "Input points" : "10Δ / 25Δ / ATM",
    data: smile.pillars.map((p) => ({ x: Number(p.strike.toFixed(4)), y: p.vol })),
    showLine: false,
    pointRadius: 5,
    pointBackgroundColor: custom ? "#d4a017" : "#6ee7b7",
    parsing: false,
  };
  smileChart.options.parsing = false;
  smileChart.data.datasets[0] = {
    label: "σ(K)",
    data: smile.strikes.map((k, i) => ({ x: Number(k.toFixed(4)), y: smile.vols[i] })),
    borderColor: "#d4a017",
    backgroundColor: "rgba(212,160,23,0.12)",
    fill: true,
    tension: 0.25,
    pointRadius: 0,
    parsing: false,
  };
  smileChart.options.scales.x.type = "linear";
  smileChart.update();
}

function renderPayoff(payoff) {
  if (!payoff || !payoff.spots) return;
  payoffChart.data.datasets[0].data = payoff.spots.map((s, i) => ({ x: s, y: payoff.intrinsic[i] }));
  payoffChart.data.datasets[1].data = payoff.spots.map((s, i) => ({
    x: s,
    y: payoff.black_scholes[i],
  }));
  payoffChart.options.parsing = false;
  payoffChart.options.scales.x.type = "linear";
  payoffChart.update();
}

function renderResult(data) {
  document.getElementById("price-value").textContent = fmt.format(data.price);
  const se = data.std_error != null ? `  ·  MC stderr ${fmt.format(data.std_error)}` : "";
  const iv = data.implied_vol != null ? `  ·  implied vol ${fmtPct(data.implied_vol)}` : "";
  document.getElementById("price-meta").textContent = `${data.model_label}  ·  ${data.details.engine}${se}${iv}`;
  document.getElementById("model-pill").textContent = data.model_label;
  const g = data.greeks || {};
  document.getElementById("g-delta").textContent = fmtNum(g.delta);
  document.getElementById("g-gamma").textContent = fmtNum(g.gamma);
  document.getElementById("g-vega").textContent = fmtNum(g.vega);
  document.getElementById("g-theta").textContent = fmtNum(g.theta);
  document.getElementById("g-rho").textContent = fmtNum(g.rho);
  document.getElementById("g-vol").textContent = fmtPct(data.vol_used);

  const rows = (data.comparison || []).map((row) => {
    if (row.error) {
      return `<tr><td>${row.label}</td><td colspan="2">${row.error}</td></tr>`;
    }
    const err = row.std_error == null ? "—" : fmt.format(row.std_error);
    return `<tr><td>${row.label}</td><td>${fmt.format(row.price)}</td><td>${err}</td></tr>`;
  });
  document.getElementById("cmp-body").innerHTML =
    rows.join("") || `<tr><td colspan="3" class="empty">No comparison</td></tr>`;

  const custom = data.details && data.details.smile_source === "custom";
  const notes = [
    "Greeks: vega per 1 vol point, theta per day, rho per 1% rate.",
    custom
      ? `Custom smile with ${data.details.input_points} input points. Other strikes interpolated in log-moneyness; wings held flat.`
      : `Fitted 10Δ put ${fmtPct(data.smile.vol_10d_put)}, 25Δ put ${fmtPct(data.smile.vol_25d_put)}, ATM ${fmtPct(data.smile.vol_atm)}, 25Δ call ${fmtPct(data.smile.vol_25d_call)}, 10Δ call ${fmtPct(data.smile.vol_10d_call)}.`,
    ...(data.warnings || []),
  ];
  warningsEl.innerHTML = notes.map((n) => `<li>${n}</li>`).join("");
  renderSmile(data.smile, data.vol_used);
  renderPayoff(data.payoff);
  renderSurface(data.surface || []);
}

function renderSurface(rows) {
  const body = document.getElementById("surface-body");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty">No surface</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map((row) => {
      const cls = row.selected ? "selected" : "";
      return `<tr class="${cls}" data-strike="${row.strike}">
        <td>${fmt.format(row.strike)}</td>
        <td>${row.pillar || ""}</td>
        <td>${fmtPct(row.vol)}</td>
        <td>${fmt.format(row.call)}</td>
        <td>${fmt.format(row.put)}</td>
        <td>${fmtNum(row.call_delta)}</td>
        <td>${fmtNum(row.put_delta)}</td>
      </tr>`;
    })
    .join("");
}

async function price() {
  priceBtn.disabled = true;
  try {
    const data = await fetchJson("/api/price", payload());
    renderResult(data);
  } catch (err) {
    document.getElementById("price-value").textContent = "Error";
    document.getElementById("price-meta").textContent = err.message;
    warningsEl.innerHTML = `<li>${err.message}</li>`;
  } finally {
    priceBtn.disabled = false;
  }
}

async function refreshSmile() {
  try {
    const data = await fetchJson("/api/smile", payload());
    renderSmile(data.smile, data.vol_at_strike);
  } catch {
    /* validation can fail while typing barrier fields */
  }
}

function parsePastedPoints(text) {
  return text
    .split(/[,;\n]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const match = part.match(/(-?\d+(?:\.\d+)?)\s*[:=\s]\s*(-?\d+(?:\.\d+)?)/);
      if (!match) return null;
      const strike = Number(match[1]);
      const volPct = Number(match[2]);
      if (!(strike > 0) || !(volPct > 0)) return null;
      return { strike: round4(strike), volPct: round4(volPct) };
    })
    .filter(Boolean);
}

async function loadFromQuotes() {
  try {
    const body = payload();
    body.smile_source = "quotes";
    delete body.custom_vols;
    const data = await fetchJson("/api/smile", body);
    const points = (data.smile.pillars || []).map((p) => ({
      strike: round4(p.strike),
      volPct: round4(p.vol * 100),
    }));
    if (points.length < 2) throw new Error("Could not read RR / BF pillars");
    renderCustomPoints(points);
    schedulePrice();
  } catch (err) {
    warningsEl.innerHTML = `<li>${err.message}</li>`;
  }
}

let timer = null;
function schedulePrice() {
  clearTimeout(timer);
  timer = setTimeout(price, 280);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  price();
});

form.addEventListener("input", (event) => {
  if (event.target.id === "custom-paste") return;
  toggleBarrier();
  toggleSmileSource();
  refreshSmile();
  schedulePrice();
});

form.addEventListener("change", (event) => {
  if (event.target.id === "custom-paste") {
    const points = parsePastedPoints(event.target.value);
    if (points.length >= 2) {
      renderCustomPoints(points);
      event.target.value = "";
      schedulePrice();
    }
    return;
  }
  toggleBarrier();
  toggleSmileSource();
  schedulePrice();
});

document.getElementById("add-point").addEventListener("click", () => {
  const points = readCustomPoints();
  const last = points[points.length - 1];
  const nextStrike = last ? round4(last.strike * 1.05) : round4(Number(form.elements.spot.value) || 100);
  const nextVol = last ? last.volPct : 20;
  renderCustomPoints([...points, { strike: nextStrike, volPct: nextVol }]);
  schedulePrice();
});

customPointsEl.addEventListener("click", (event) => {
  const button = event.target.closest(".remove");
  if (!button) return;
  const rows = [...customPointsEl.querySelectorAll(".vol-row")];
  if (rows.length <= 2) return;
  button.closest(".vol-row").remove();
  schedulePrice();
});

document.getElementById("load-from-quotes").addEventListener("click", loadFromQuotes);

document.getElementById("tenor-chips").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-days]");
  if (!button) return;
  form.elements.expiry_days.value = button.dataset.days;
  document.querySelectorAll("#tenor-chips button").forEach((el) => el.classList.toggle("active", el === button));
  schedulePrice();
});

document.getElementById("surface-body").addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-strike]");
  if (!row) return;
  form.elements.strike.value = row.dataset.strike;
  schedulePrice();
});

toggleBarrier();
toggleSmileSource();
renderCustomPoints(defaultPoints());
price();
