const form = document.getElementById("pricer-form");
const priceBtn = document.getElementById("price-btn");
const strikeVolEl = document.getElementById("strike-vol");
const warningsEl = document.getElementById("warnings");

const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });
const fmtPct = (x) => `${(x * 100).toFixed(2)}%`;
const fmtNum = (x) => (x === null || x === undefined || Number.isNaN(x) ? "—" : fmt.format(x));

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

function payload() {
  const style = selected("option_style");
  const body = {
    spot: Number(form.elements.spot.value),
    strike: Number(form.elements.strike.value),
    rate: pct("rate_pct"),
    dividend: pct("div_pct"),
    atm_vol: pct("atm_vol_pct"),
    rr_25d: pct("rr_pct"),
    bf_25d: pct("bf_pct"),
    expiry_years: Number(form.elements.expiry_days.value) / 365,
    option_style: style,
    option_type: selected("option_type"),
    model: selected("model"),
    mc_paths: Number(form.elements.mc_paths.value),
    mc_steps: Number(form.elements.mc_steps.value),
    compare_models: form.elements.compare_models.checked,
    rebate: Number(form.elements.rebate.value || 0),
  };
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
  smileChart.data.labels = smile.strikes.map((k) => Number(k.toFixed(2)));
  smileChart.data.datasets[0].data = smile.vols;
  smileChart.data.datasets[1].data = smile.strikes.map((k) => {
    const pillar = smile.pillars.find((p) => Math.abs(p.strike - k) < 1e-8);
    return pillar ? pillar.vol : null;
  });
  const pillarPoints = smile.pillars.map((p) => ({ x: Number(p.strike.toFixed(2)), y: p.vol }));
  smileChart.data.datasets[1] = {
    label: "25Δ / ATM",
    data: pillarPoints,
    showLine: false,
    pointRadius: 5,
    pointBackgroundColor: "#6ee7b7",
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

  const notes = [
    "Greeks: vega per 1 vol point, theta per day, rho per 1% rate.",
    `Fitted 25Δ put vol ${fmtPct(data.smile.vol_25d_put)}, ATM ${fmtPct(data.smile.vol_atm)}, 25Δ call ${fmtPct(data.smile.vol_25d_call)}.`,
    ...(data.warnings || []),
  ];
  warningsEl.innerHTML = notes.map((n) => `<li>${n}</li>`).join("");
  renderSmile(data.smile, data.vol_used);
  renderPayoff(data.payoff);
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

let timer = null;
function schedulePrice() {
  clearTimeout(timer);
  timer = setTimeout(price, 280);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  price();
});

form.addEventListener("input", () => {
  toggleBarrier();
  refreshSmile();
  schedulePrice();
});

form.addEventListener("change", () => {
  toggleBarrier();
  schedulePrice();
});

document.getElementById("tenor-chips").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-days]");
  if (!button) return;
  form.elements.expiry_days.value = button.dataset.days;
  document.querySelectorAll("#tenor-chips button").forEach((el) => el.classList.toggle("active", el === button));
  schedulePrice();
});

toggleBarrier();
price();
