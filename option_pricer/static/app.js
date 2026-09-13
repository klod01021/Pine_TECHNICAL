const form = document.getElementById("pricer-form");
const priceBtn = document.getElementById("price-btn");
const strikeVolEl = document.getElementById("strike-vol");
const warningsEl = document.getElementById("warnings");
const swapBody = document.getElementById("swap-body");
const volHead = document.getElementById("vol-head");
const volBody = document.getElementById("vol-body");

const TENORS = ["1M", "3M", "6M", "1Y"];
const TENOR_DAYS = { "1M": 30, "3M": 90, "6M": 180, "1Y": 365 };
const STORAGE_KEY = "optionPricer.desk.v1";

const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });
const fmtPct = (x) => `${(x * 100).toFixed(2)}%`;
const fmtNum = (x) => (x === null || x === undefined || Number.isNaN(x) ? "—" : fmt.format(x));
const round4 = (x) => Number(Number(x).toFixed(4));

function todayIso() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function addDays(iso, days) {
  const date = new Date(`${iso}T00:00:00`);
  date.setDate(date.getDate() + Number(days));
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function defaultStrikes(spot) {
  return [0.8, 0.9, 1.0, 1.1, 1.2].map((m) => round4(spot * m));
}

function defaultVolPct(rel, tenor) {
  const atm = { "1M": 21, "3M": 20, "6M": 19.5, "1Y": 19 }[tenor];
  const skew = rel <= 0.85 ? 4 : rel <= 0.95 ? 1.5 : rel >= 1.15 ? -1.2 : rel >= 1.05 ? -0.8 : 0;
  return round4(Math.max(0.5, atm + skew));
}

function defaultMarket() {
  const spotMid = 100;
  const strikes = defaultStrikes(spotMid);
  const vols = {};
  for (const strike of strikes) {
    vols[String(strike)] = {};
    for (const tenor of TENORS) {
      const mid = defaultVolPct(strike / spotMid, tenor);
      vols[String(strike)][tenor] = { bid: round4(mid - 0.1), offer: round4(mid + 0.1) };
    }
  }
  return {
    valueDate: todayIso(),
    expiryDate: addDays(todayIso(), 90),
    activeTenor: "3M",
    swapScale: 1,
    spotBid: 99.98,
    spotOffer: 100.02,
    rateBidPct: 4.98,
    rateOfferPct: 5.02,
    swaps: {
      "1M": { bid: 0.31, offer: 0.35 },
      "3M": { bid: 0.96, offer: 1.02 },
      "6M": { bid: 1.94, offer: 2.02 },
      "1Y": { bid: 4.02, offer: 4.14 },
    },
    strikes,
    vols,
  };
}

let desk = defaultMarket();

function loadDesk() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    desk = { ...defaultMarket(), ...saved, swaps: { ...defaultMarket().swaps, ...(saved.swaps || {}) } };
  } catch {
    desk = defaultMarket();
  }
}

function saveDesk() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(desk));
}

function selected(name) {
  return form.querySelector(`input[name="${name}"]:checked`).value;
}

function num(name) {
  return Number(form.elements[name].value);
}

function mid(bid, offer) {
  return 0.5 * (Number(bid) + Number(offer));
}

function syncFormToDesk() {
  desk.valueDate = form.elements.value_date.value || desk.valueDate;
  desk.expiryDate = form.elements.expiry_date.value || desk.expiryDate;
  desk.swapScale = num("swap_scale") || 1;
  desk.spotBid = num("spot_bid");
  desk.spotOffer = num("spot_offer");
  desk.rateBidPct = num("rate_bid_pct");
  desk.rateOfferPct = num("rate_offer_pct");
  for (const tenor of TENORS) {
    const bid = document.querySelector(`[data-swap-bid="${tenor}"]`);
    const offer = document.querySelector(`[data-swap-offer="${tenor}"]`);
    if (bid && offer) desk.swaps[tenor] = { bid: Number(bid.value), offer: Number(offer.value) };
  }
  const nextVols = {};
  const nextStrikes = [];
  for (const row of volBody.querySelectorAll("tr")) {
    const strike = Number(row.querySelector(".pt-strike").value);
    if (!(strike > 0)) continue;
    nextStrikes.push(strike);
    nextVols[String(strike)] = {};
    for (const tenor of TENORS) {
      const bid = Number(row.querySelector(`[data-vol-bid="${tenor}"]`).value);
      const offer = Number(row.querySelector(`[data-vol-offer="${tenor}"]`).value);
      nextVols[String(strike)][tenor] = { bid, offer };
    }
  }
  if (nextStrikes.length) {
    desk.strikes = nextStrikes;
    desk.vols = nextVols;
  }
  saveDesk();
}

function renderSwaps() {
  const spotBid = num("spot_bid") || desk.spotBid;
  const spotOffer = num("spot_offer") || desk.spotOffer;
  const scale = num("swap_scale") || desk.swapScale || 1;
  swapBody.innerHTML = TENORS.map((tenor) => {
    const row = desk.swaps[tenor];
    const fwdBid = spotBid + row.bid / scale;
    const fwdOffer = spotOffer + row.offer / scale;
    return `<tr>
      <th>${tenor}</th>
      <td><input data-swap-bid="${tenor}" type="number" step="any" value="${row.bid}" /></td>
      <td><input data-swap-offer="${tenor}" type="number" step="any" value="${row.offer}" /></td>
      <td class="fwd">${fmt.format(fwdBid)}</td>
      <td class="fwd">${fmt.format(fwdOffer)}</td>
    </tr>`;
  }).join("");
}

function renderVolGrid() {
  volHead.innerHTML = `<tr>
    <th>Strike</th>
    ${TENORS.map((tenor) => `<th>${tenor} bid</th><th>${tenor} offer</th>`).join("")}
  </tr>`;
  volBody.innerHTML = desk.strikes
    .map((strike) => {
      const cells = TENORS.map((tenor) => {
        const cell = (desk.vols[String(strike)] || {})[tenor] || { bid: 20, offer: 20.2 };
        return `<td><input data-vol-bid="${tenor}" type="number" step="any" min="0.01" value="${cell.bid}" /></td>
          <td><input data-vol-offer="${tenor}" type="number" step="any" min="0.01" value="${cell.offer}" /></td>`;
      }).join("");
      return `<tr>
        <td class="strike-cell"><input class="pt-strike" type="number" step="0.0001" min="0.0001" value="${strike}" /></td>
        ${cells}
      </tr>`;
    })
    .join("");
}

function applyDeskToForm() {
  form.elements.value_date.value = desk.valueDate;
  form.elements.expiry_date.value = desk.expiryDate;
  form.elements.swap_scale.value = desk.swapScale;
  form.elements.spot_bid.value = desk.spotBid;
  form.elements.spot_offer.value = desk.spotOffer;
  form.elements.rate_bid_pct.value = desk.rateBidPct;
  form.elements.rate_offer_pct.value = desk.rateOfferPct;
  renderSwaps();
  renderVolGrid();
  document.querySelectorAll("#tenor-chips button").forEach((el) => {
    el.classList.toggle("active", el.dataset.tenor === desk.activeTenor);
  });
}

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
  data: { datasets: [] },
  options: {
    ...chartDefaults,
    parsing: false,
    scales: {
      ...chartDefaults.scales,
      x: { ...chartDefaults.scales.x, type: "linear" },
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
    datasets: [
      { label: "Intrinsic", data: [], borderColor: "#fb7185", pointRadius: 0, tension: 0.05 },
      { label: "Black–Scholes value", data: [], borderColor: "#6ee7b7", pointRadius: 0, tension: 0.2 },
    ],
  },
  options: { ...chartDefaults, parsing: false, scales: { ...chartDefaults.scales, x: { ...chartDefaults.scales.x, type: "linear" } } },
});

function tenorSlices() {
  return TENORS.map((tenor) => ({
    tenor,
    swap_points: desk.swaps[tenor],
    vols: desk.strikes.map((strike) => {
      const cell = (desk.vols[String(strike)] || {})[tenor] || { bid: 20, offer: 20.2 };
      return { strike, bid: cell.bid / 100, offer: cell.offer / 100 };
    }),
  }));
}

function payload() {
  syncFormToDesk();
  const style = selected("option_style");
  const spot = mid(desk.spotBid, desk.spotOffer);
  const rate = mid(desk.rateBidPct, desk.rateOfferPct) / 100;
  const onPricer = !document.getElementById("page-pricer").classList.contains("hidden");
  const body = {
    spot,
    spot_bid: desk.spotBid,
    spot_offer: desk.spotOffer,
    strike: Number(form.elements.strike.value),
    rate,
    rate_bid: desk.rateBidPct / 100,
    rate_offer: desk.rateOfferPct / 100,
    dividend: 0,
    value_date: desk.valueDate,
    expiry_date: desk.expiryDate,
    option_style: style,
    option_type: selected("option_type"),
    model: selected("model"),
    mc_paths: Number(form.elements.mc_paths.value),
    mc_steps: Number(form.elements.mc_steps.value),
    compare_models: onPricer ? false : form.elements.compare_models.checked,
    rebate: Number(form.elements.rebate.value || 0),
    swap_point_scale: desk.swapScale,
    tenors: tenorSlices(),
    smile_source: "custom",
  };
  if (style === "barrier") {
    body.barrier_type = form.elements.barrier_type.value;
    body.barrier = Number(form.elements.barrier.value);
  }
  return body;
}

function quotesBody(side, expiryYears) {
  const prefix = side === "bid" ? "bid" : "offer";
  const spot = side === "bid" ? desk.spotBid : desk.spotOffer;
  const rate = (side === "bid" ? desk.rateBidPct : desk.rateOfferPct) / 100;
  return {
    spot,
    strike: Number(form.elements.strike.value),
    rate,
    dividend: 0.01,
    atm_vol: num(`atm_${prefix}_pct`) / 100,
    rr_25d: num(`rr_${prefix}_pct`) / 100,
    bf_25d: num(`bf_${prefix}_pct`) / 100,
    rr_10d: num(`rr_10_${prefix}_pct`) / 100,
    bf_10d: num(`bf_10_${prefix}_pct`) / 100,
    expiry_years: expiryYears,
    option_style: "european",
    option_type: "call",
    smile_source: "quotes",
    compare_models: false,
  };
}

function toggleBarrier() {
  const show = selected("option_style") === "barrier";
  document.getElementById("barrier-fields").classList.toggle("hidden", !show);
}

function showPage(name) {
  document.getElementById("page-pricer").classList.toggle("hidden", name !== "pricer");
  document.getElementById("page-market").classList.toggle("hidden", name !== "market");
  document.getElementById("nav-pricer").classList.toggle("active", name === "pricer");
  document.getElementById("nav-market").classList.toggle("active", name === "market");
  location.hash = name;
  setTimeout(() => {
    smileChart.resize();
    payoffChart.resize();
  }, 0);
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

function renderSmile(smile, strikeVol, volBid, volOffer) {
  const bidTxt = volBid != null ? ` bid ${fmtPct(volBid)}` : "";
  const offerTxt = volOffer != null ? ` / offer ${fmtPct(volOffer)}` : "";
  strikeVolEl.textContent = `strike vol ${fmtPct(strikeVol)}${bidTxt}${offerTxt}`;
  smileChart.data.datasets = [
    {
      label: "σ mid",
      data: smile.strikes.map((k, i) => ({ x: Number(k.toFixed(4)), y: smile.vols[i] })),
      borderColor: "#d4a017",
      backgroundColor: "rgba(212,160,23,0.12)",
      fill: true,
      tension: 0.25,
      pointRadius: 0,
    },
    {
      label: "Input",
      data: (smile.pillars || []).map((p) => ({ x: Number(p.strike.toFixed(4)), y: p.vol })),
      showLine: false,
      pointRadius: 5,
      pointBackgroundColor: "#6ee7b7",
    },
  ];
  smileChart.update();
}

function renderPayoff(payoff) {
  if (!payoff || !payoff.spots) return;
  payoffChart.data.datasets[0].data = payoff.spots.map((s, i) => ({ x: s, y: payoff.intrinsic[i] }));
  payoffChart.data.datasets[1].data = payoff.spots.map((s, i) => ({
    x: s,
    y: payoff.black_scholes[i],
  }));
  payoffChart.update();
}

function renderSurface(rows) {
  const body = document.getElementById("surface-body");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="8" class="empty">No surface</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map((row) => {
      const cls = row.selected ? "selected" : "";
      return `<tr class="${cls}" data-strike="${row.strike}">
        <td>${fmt.format(row.strike)}</td>
        <td>${row.pillar || ""}</td>
        <td>${fmtPct(row.vol_bid ?? row.vol)}</td>
        <td>${fmtPct(row.vol_offer ?? row.vol)}</td>
        <td>${fmt.format(row.call_bid ?? row.call)}</td>
        <td>${fmt.format(row.call_offer ?? row.call)}</td>
        <td>${fmt.format(row.put_bid ?? row.put)}</td>
        <td>${fmt.format(row.put_offer ?? row.put)}</td>
      </tr>`;
    })
    .join("");
}

function renderResult(data) {
  document.getElementById("price-bid").textContent = fmt.format(data.price_bid ?? data.price);
  document.getElementById("price-offer").textContent = fmt.format(data.price_offer ?? data.price);
  const se = data.std_error != null ? `  ·  MC stderr ${fmt.format(data.std_error)}` : "";
  const fwd = data.forward != null ? `  ·  fwd ${fmt.format(data.forward)}` : "";
  document.getElementById("price-meta").textContent = `${data.model_label}  ·  ${data.details.engine}${fwd}${se}`;

  const rows = (data.comparison || []).map((row) => {
    if (row.error) {
      return `<tr><td>${row.label}</td><td colspan="3">${row.error}</td></tr>`;
    }
    const err = row.std_error == null ? "—" : fmt.format(row.std_error);
    return `<tr><td>${row.label}</td><td>${fmt.format(row.price_bid ?? row.price)}</td><td>${fmt.format(row.price_offer ?? row.price)}</td><td>${err}</td></tr>`;
  });
  document.getElementById("cmp-body").innerHTML =
    rows.join("") || `<tr><td colspan="4" class="empty">No comparison</td></tr>`;

  const notes = [
    "Greeks: vega per 1 vol point, theta per day, rho per 1% rate.",
    `Expiry ${data.details.expiry_date || "tenor"} · strike vol bid ${fmtPct(data.vol_bid ?? data.vol_used)} / offer ${fmtPct(data.vol_offer ?? data.vol_used)}.`,
    ...(data.warnings || []),
  ];
  warningsEl.innerHTML = notes.map((n) => `<li>${n}</li>`).join("");
  renderSmile(data.smile, data.vol_used, data.vol_bid, data.vol_offer);
  renderPayoff(data.payoff);
  renderSurface(data.surface || []);
}

async function price() {
  priceBtn.disabled = true;
  try {
    const data = await fetchJson("/api/price", payload());
    renderResult(data);
  } catch (err) {
    document.getElementById("price-bid").textContent = "Error";
    document.getElementById("price-offer").textContent = "Error";
    document.getElementById("price-meta").textContent = err.message;
    warningsEl.innerHTML = `<li>${err.message}</li>`;
  } finally {
    priceBtn.disabled = false;
  }
}

function writePillarsToTenor(tenor, bidSmile, offerSmile) {
  const strikes = [];
  const seen = new Set();
  for (const pillar of [...(bidSmile.pillars || []), ...(offerSmile.pillars || [])]) {
    const key = Number(pillar.strike.toFixed(4));
    if (seen.has(key)) continue;
    seen.add(key);
    strikes.push(key);
  }
  strikes.sort((a, b) => a - b);
  if (strikes.length < 2) return;
  for (const strike of strikes) {
    if (!desk.strikes.includes(strike)) desk.strikes.push(strike);
    if (!desk.vols[String(strike)]) {
      desk.vols[String(strike)] = {};
      for (const other of TENORS) {
        const midVol = defaultVolPct(strike / mid(desk.spotBid, desk.spotOffer), other);
        desk.vols[String(strike)][other] = { bid: round4(midVol - 0.1), offer: round4(midVol + 0.1) };
      }
    }
    const bidP = (bidSmile.pillars || []).find((p) => Math.abs(p.strike - strike) < 0.05);
    const offerP = (offerSmile.pillars || []).find((p) => Math.abs(p.strike - strike) < 0.05);
    desk.vols[String(strike)][tenor] = {
      bid: round4((bidP ? bidP.vol : offerP.vol) * 100),
      offer: round4((offerP ? offerP.vol : bidP.vol) * 100),
    };
  }
  desk.strikes = [...new Set(desk.strikes)].sort((a, b) => a - b);
}

async function fillFromQuotes(all) {
  syncFormToDesk();
  const targets = all ? TENORS : [desk.activeTenor];
  try {
    for (const tenor of targets) {
      const t = TENOR_DAYS[tenor] / 365;
      const bid = await fetchJson("/api/smile", quotesBody("bid", t));
      const offer = await fetchJson("/api/smile", quotesBody("offer", t));
      writePillarsToTenor(tenor, bid.smile, offer.smile);
    }
    renderVolGrid();
    saveDesk();
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

form.addEventListener("input", () => {
  toggleBarrier();
  if (document.activeElement && document.activeElement.closest("#swap-table, #vol-grid, [name=spot_bid], [name=spot_offer], [name=swap_scale]")) {
    syncFormToDesk();
    renderSwaps();
  }
  schedulePrice();
});

form.addEventListener("change", () => {
  toggleBarrier();
  syncFormToDesk();
  schedulePrice();
});

document.getElementById("nav-pricer").addEventListener("click", () => {
  showPage("pricer");
  schedulePrice();
});
document.getElementById("nav-market").addEventListener("click", () => {
  showPage("market");
  schedulePrice();
});

document.getElementById("tenor-chips").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-tenor]");
  if (!button) return;
  desk.activeTenor = button.dataset.tenor;
  desk.expiryDate = addDays(form.elements.value_date.value || desk.valueDate, button.dataset.days);
  form.elements.expiry_date.value = desk.expiryDate;
  document.querySelectorAll("#tenor-chips button").forEach((el) => el.classList.toggle("active", el === button));
  saveDesk();
  schedulePrice();
});

document.getElementById("add-strike").addEventListener("click", () => {
  syncFormToDesk();
  const last = desk.strikes[desk.strikes.length - 1] || mid(desk.spotBid, desk.spotOffer);
  const strike = round4(last * 1.05);
  desk.strikes.push(strike);
  desk.vols[String(strike)] = {};
  for (const tenor of TENORS) {
    const midVol = defaultVolPct(strike / mid(desk.spotBid, desk.spotOffer), tenor);
    desk.vols[String(strike)][tenor] = { bid: round4(midVol - 0.1), offer: round4(midVol + 0.1) };
  }
  renderVolGrid();
  saveDesk();
  schedulePrice();
});

document.getElementById("remove-strike").addEventListener("click", () => {
  syncFormToDesk();
  if (desk.strikes.length <= 2) return;
  const removed = desk.strikes.pop();
  delete desk.vols[String(removed)];
  renderVolGrid();
  saveDesk();
  schedulePrice();
});

document.getElementById("fill-active").addEventListener("click", () => fillFromQuotes(false));
document.getElementById("fill-all").addEventListener("click", () => fillFromQuotes(true));

document.getElementById("surface-body").addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-strike]");
  if (!row) return;
  form.elements.strike.value = row.dataset.strike;
  schedulePrice();
});

loadDesk();
if (!form.elements.value_date.value) {
  applyDeskToForm();
} else {
  applyDeskToForm();
}
if (location.hash === "#market") showPage("market");
else showPage("pricer");
toggleBarrier();
price();
