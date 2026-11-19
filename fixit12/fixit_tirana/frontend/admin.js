let reports = [];
let latestAnalysis = null;

const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[char]));

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) { window.location.href = "/login.html"; throw new Error("Sesioni ka përfunduar."); }
  if (!response.ok) throw new Error(data.detail || "Ndodhi një gabim.");
  return data;
}

function statusClass(status) {
  return ({ "E re": "status-new", "Në shqyrtim": "status-review", "Në proces": "status-progress", "E zgjidhur": "status-done" })[status] || "status-new";
}

function renderReports(items) {
  $("reportsBody").innerHTML = items.length ? items.map((report) => `
    <tr>
      <td><div class="report-title">${escapeHtml(report.category)}</div><small class="report-desc">${escapeHtml(report.description.slice(0, 82))}${report.description.length > 82 ? "…" : ""}</small></td>
      <td>${escapeHtml(report.location)}</td><td>${escapeHtml(report.created_at)}</td>
      <td><select class="status-select ${statusClass(report.status)}" data-status-id="${report.id}">
        ${["E re", "Në shqyrtim", "Në proces", "E zgjidhur"].map(s => `<option ${s === report.status ? "selected" : ""}>${s}</option>`).join("")}
      </select></td>
      <td><button class="view-button" data-view-id="${report.id}">Shiko ↗</button></td>
    </tr>`).join("") : '<tr><td colspan="5" class="empty-cell">Nuk u gjet asnjë raportim.</td></tr>';
  $("reportsBody").querySelectorAll("[data-status-id]").forEach((select) => {
    select.addEventListener("change", async () => {
      try {
        await api(`/api/reports/${select.dataset.statusId}/status`, { method: "PATCH", body: JSON.stringify({ status: select.value }) });
        select.className = `status-select ${statusClass(select.value)}`;
        await loadReports();
      } catch (error) { alert(error.message); }
    });
  });
  $("reportsBody").querySelectorAll("[data-view-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const report = reports.find((item) => item.id === Number(button.dataset.viewId));
      if (!report) return;
      $("aiReportSelect").value = String(report.id);
      $("analysisArea").innerHTML = `<div class="report-detail"><b>Raportimi #${report.id} · ${escapeHtml(report.category)}</b><p>${escapeHtml(report.description)}</p><small>Vendndodhja: ${escapeHtml(report.location)} · Statusi: ${escapeHtml(report.status)}</small>${report.photo ? `<img class="report-photo" src="/uploads/${encodeURIComponent(report.photo)}" alt="Foto e raportimit">` : ""}</div>`;
      $("analysisMessage").textContent = "Raportimi u zgjodh. Mund ta analizosh me Gemini.";
      $("recommendations").scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });
}

async function loadReports() {
  const params = new URLSearchParams();
  if ($("statusFilter").value !== "Të gjitha") params.set("status", $("statusFilter").value);
  if ($("searchReports").value.trim()) params.set("search", $("searchReports").value.trim());
  const data = await api(`/api/reports?${params}`);
  reports = data.reports;
  renderReports(reports);
  $("sideCount").textContent = reports.length;
  $("totalCount").textContent = reports.length;
  $("reviewCount").textContent = reports.filter(r => r.status === "Në shqyrtim").length;
  $("progressCount").textContent = reports.filter(r => r.status === "Në proces").length;
  $("doneCount").textContent = reports.filter(r => r.status === "E zgjidhur").length;
  const current = $("aiReportSelect").value;
  $("aiReportSelect").innerHTML = '<option value="">Pa raportim të zgjedhur</option>' + reports.map(r =>
    `<option value="${r.id}">#${r.id} · ${escapeHtml(r.category)} — ${escapeHtml(r.location)}</option>`).join("");
  if (current && reports.some(r => String(r.id) === current)) $("aiReportSelect").value = current;
}

function addBubble(text, role) {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role === "user" ? "user-bubble" : "assistant-bubble"}`;
  bubble.textContent = text;
  $("chatMessages").appendChild(bubble);
  $("chatMessages").scrollTop = $("chatMessages").scrollHeight;
}

$("chatForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("chatInput");
  const message = input.value.trim();
  if (!message) return;
  addBubble(message, "user");
  input.value = "";
  const pending = document.createElement("div");
  pending.className = "chat-bubble assistant-bubble pending";
  pending.textContent = "Po mendoj…";
  $("chatMessages").appendChild(pending);
  try {
    const data = await api("/api/ai/chat", { method: "POST", body: JSON.stringify({
      message, report_id: $("aiReportSelect").value || null
    }) });
    pending.remove();
    addBubble(data.answer, "assistant");
  } catch (error) {
    pending.remove();
    addBubble(error.message, "assistant");
  }
});

$("clearChat").addEventListener("click", async () => {
  try {
    await api("/api/ai/chat", { method: "DELETE" });
    $("chatMessages").innerHTML = "";
    addBubble("Biseda u pastrua. Si mund të të ndihmoj?", "assistant");
  } catch (error) { addBubble(error.message, "assistant"); }
});

$("analyzeButton").addEventListener("click", async () => {
  const reportId = $("aiReportSelect").value;
  if (!reportId) { $("analysisMessage").textContent = "Zgjidh fillimisht një raportim."; return; }
  const button = $("analyzeButton");
  button.disabled = true;
  button.textContent = "Gemini po analizon…";
  $("analysisMessage").textContent = "";
  try {
    const data = await api("/api/ai/analyze-report", { method: "POST", body: JSON.stringify({ report_id: Number(reportId) }) });
    latestAnalysis = data;
    $("analysisArea").innerHTML = `
      <div class="analysis-result">
        <div class="priority-line"><span>PRIORITETI I SUGJERUAR</span><b class="priority-${data.priority === "Urgjente" ? "urgent" : data.priority === "E lartë" ? "high" : data.priority === "Mesatare" ? "medium" : "low"}">${escapeHtml(data.priority)}</b></div>
        <h3>Përmbledhje</h3><p>${escapeHtml(data.summary)}</p>
        <h3>Shkaqe të mundshme</h3><ul>${data.possible_causes.map(x => `<li>${escapeHtml(x)}</li>`).join("") || "<li>Nuk u specifikuan.</li>"}</ul>
        <h3>Hapa të rekomanduar</h3><ul>${data.recommended_steps.map(x => `<li>${escapeHtml(x)}</li>`).join("") || "<li>Nuk u specifikuan.</li>"}</ul>
        <h3>Institucioni i mundshëm</h3><p>${escapeHtml(data.responsible_institution)}</p>
        <small>${escapeHtml(data.priority_reason)}</small>
        <p class="ai-disclaimer">Ky është sugjerim i gjeneruar nga AI. Verifiko institucionin dhe hapat përmes burimeve zyrtare.</p>
      </div>`;
    $("saveRecommendation").classList.remove("hidden");
    $("analysisMessage").textContent = "Analiza u përfundua. Mund ta ruash rekomandimin.";
    await loadReports();
  } catch (error) {
    $("analysisMessage").className = "form-message error";
    $("analysisMessage").textContent = error.message;
  } finally {
    button.disabled = false;
    button.innerHTML = 'Analizo raportimin e zgjedhur <span>✳</span>';
  }
});

$("saveRecommendation").addEventListener("click", async () => {
  if (!latestAnalysis) return;
  const reportId = $("aiReportSelect").value || null;
  const content = [
    `Prioriteti: ${latestAnalysis.priority}`,
    `Përmbledhje: ${latestAnalysis.summary}`,
    `Hapat: ${latestAnalysis.recommended_steps.join("; ")}`,
    `Institucioni i mundshëm: ${latestAnalysis.responsible_institution}`
  ].join("\n");
  try {
    await api("/api/recommendations", { method: "POST", body: JSON.stringify({ report_id: reportId ? Number(reportId) : null, content }) });
    $("analysisMessage").className = "form-message success";
    $("analysisMessage").textContent = "Rekomandimi u ruajt në platformë.";
  } catch (error) { $("analysisMessage").textContent = error.message; }
});

$("statusFilter").addEventListener("change", () => loadReports().catch(err => alert(err.message)));
let searchTimer;
$("searchReports").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadReports().catch(err => alert(err.message)), 250);
});

loadReports().catch((error) => {
  $("reportsBody").innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHtml(error.message)}</td></tr>`;
});


/* ===== Raportime shembull me sugjerime AI ===== */
const DEMO_REPORTS = [
  { id: "d1", name: "Arben K.", category: "Ujë dhe kanalizime", location: "Rruga e Kavajës, afër Kompleksit Sportiv", date: "Para 2 orësh",
    description: "Një tubacion i ujit është çarë në trotuar. Uji rrjedh që nga mëngjesi dhe ka formuar një pellg të madh; banesat përballë kanë presion shumë të ulët uji." },
  { id: "d2", name: "Elda M.", category: "Ndriçim publik", location: "Rruga Dritan Hoxha, Ish-Blloku", date: "Dje",
    description: "Pesë shtyllat e ndriçimit në një segment prej rreth 150 m janë të fikura që prej një jave. Natën rruga është e errët dhe e rrezikshme për këmbësorët." },
  { id: "d3", name: "Gentian P.", category: "Rrugë dhe trotuare", location: "Unaza e Re, para stacionit të autobusit", date: "Para 3 ditësh",
    description: "Ka një gropë të thellë rreth 40 cm në korsinë e djathtë. Disa makina kanë dëmtuar gomat dhe motorrët e shmangin ngushtë." },
  { id: "d4", name: "Marsela D.", category: "Mbetje dhe pastërti", location: "Sheshi Wilson, pranë shkollës", date: "Para 1 dite",
    description: "Kontejnerët e plehrave janë të mbushur përtej kapacitetit prej disa ditësh. Mbeturinat shpërndahen përreth dhe ka erë të rëndë, pranë një shkolle." },
  { id: "d5", name: "Ilir S.", category: "Hapësira publike", location: "Parku i Madh, zona e lojërave për fëmijë", date: "Para 5 ditësh",
    description: "Disa pjesë të një shtrati lodrash janë të thyera dhe kanë skaje të mprehta. Fëmijët luajnë aty çdo pasdite dhe ekziston rrezik lëndimi." }
];

const FALLBACK = {
  "Ujë dhe kanalizime": [
    ["Riparim urgjent i tubacionit", "Ekip emergjence izolon segmentin, zëvendëson pjesën e çarë dhe rikthen presionin.", "Sot / brenda 24 orëve", "Zgjidhje përfundimtare, por kërkon ndërprerje të shkurtër të ujit."],
    ["Izolim i përkohshëm dhe riparim i planifikuar", "Mbyllet vana e zonës, vendoset kapëse e përkohshme dhe riparimi bëhet në orar me më pak ndikim.", "1–3 ditë", "Më pak ndërprerje, por humbjet e ujit vazhdojnë pak më gjatë."],
    ["Zëvendësim i segmentit të vjetër", "Inspektohet gjendja e tubacionit dhe ndërrohet i gjithë segmenti për të shmangur çarje të përsëritura.", "1–3 javë", "Më e qëndrueshme, por më e kushtueshme dhe e ngadaltë."]],
  "Ndriçim publik": [
    ["Kontroll elektrik dhe zëvendësim llambash", "Teknikët kontrollojnë ushqimin elektrik dhe ndërrojnë llambat/driverat e dëmtuar.", "1–3 ditë", "E shpejtë dhe e lirë, nëse defekti është vetëm te llambat."],
    ["Riparim i linjës ushqyese", "Nëse të gjitha shtyllat nuk marrin energji, kontrollohet kabllo, kutia e shpërndarjes dhe siguresat.", "3–7 ditë", "Zgjidh shkakun real, por kërkon diagnostikim më të thellë."],
    ["Kalim në ndriçim LED", "Zëvendësohen armaturat me LED efikase me kontroll automatik.", "2–6 javë", "Kursim energjie afatgjatë, por kërkon buxhet fillestar."]],
  "Rrugë dhe trotuare": [
    ["Mbushje e menjëhershme e gropës", "Mbushje me asfalt të ftohtë dhe sinjalizim i përkohshëm i zonës.", "1–2 ditë", "Shpejt e lirë, por mund të mos zgjasë shumë."],
    ["Riparim i plotë me asfalt të nxehtë", "Priten skajet, pastrohet baza dhe vendoset asfalt i ri i ngjeshur.", "1–2 javë", "Më e qëndrueshme, kërkon mbyllje të pjesshme të korsisë."],
    ["Rikonstruim i segmentit", "Verifikohet kullimi dhe baza e rrugës, pastaj rindërtohet shtresa.", "1–3 muaj", "Zgjidhje afatgjatë, por e shtrenjtë dhe me ndikim në trafik."]],
  "Mbetje dhe pastërti": [
    ["Zbrazje e menjëhershme dhe pastrim", "Dërgohet një kamion shtesë për zbrazjen e kontejnerëve dhe pastrimin e zonës.", "Sot / nesër", "Zgjidh gjendjen aktuale, por nuk parandalon përsëritjen."],
    ["Shtim kontejnerësh ose rritje frekuence", "Analizohet volumi dhe shtohen kontejnerë ose ngritet frekuenca e grumbullimit.", "1–2 javë", "Adreson shkakun, por kërkon burime shtesë."],
    ["Ndërgjegjësim dhe monitorim", "Njoftime për banorët, kontroll i vendeve të shkarkimit të paligjshëm dhe monitorim periodik.", "2–4 javë", "Ndikim afatgjatë, rezultate më të ngadalta."]],
  "Hapësira publike": [
    ["Rrethim i përkohshëm i zonës", "Pjesa e rrezikshme izolohet me rrethim dhe shenja paralajmëruese.", "Sot", "Siguri e menjëhershme, por fëmijët humbasin përkohësisht lojërat."],
    ["Riparim i elementëve të dëmtuar", "Ndërrohen ose lëmohen pjesët e thyera sipas standardeve të sigurisë.", "3–10 ditë", "Rikthen përdorimin shpejt me kosto të moderuar."],
    ["Zëvendësim i shtratit të lodrave", "Instalohet pajisje e re e certifikuar me sipërfaqe amortizuese.", "1–2 muaj", "Zgjidhje e plotë, por kërkon buxhet dhe prokurim."]]
};

const demoState = {};

function renderDemo() {
  $("demoGrid").innerHTML = DEMO_REPORTS.map((r) => `
    <article class="demo-card" id="card-${r.id}">
      <div class="demo-head">
        <div class="demo-who"><div class="admin-avatar">${escapeHtml(r.name[0])}</div><div><b>${escapeHtml(r.name)}</b><small>${escapeHtml(r.date)} · ${escapeHtml(r.location)}</small></div></div>
        <span class="demo-cat">${escapeHtml(r.category)}</span>
      </div>
      <p>${escapeHtml(r.description)}</p>
      <button class="primary-button" data-suggest="${r.id}" type="button">Merr 3 sugjerime nga AI ✳</button>
      <div id="opts-${r.id}"></div>
    </article>`).join("");
  $("demoGrid").querySelectorAll("[data-suggest]").forEach((b) => b.addEventListener("click", () => suggestFor(b.dataset.suggest, b)));
}

async function suggestFor(id, button) {
  const r = DEMO_REPORTS.find((x) => x.id === id);
  button.disabled = true; button.textContent = "Gemini po mendon…";
  let data, note = "";
  try {
    data = await api("/api/ai/suggest-solutions", { method: "POST", body: JSON.stringify({ category: r.category, location: r.location, description: r.description }) });
  } catch (error) {
    data = { options: FALLBACK[r.category].map(([title, summary, timeframe, tradeoff]) => ({
      title, summary, steps: [], responsible_institution: "Duhet verifikuar", timeframe, tradeoff })) };
    note = `Gemini nuk është i disponueshëm (${error.message}). Po shfaqen sugjerime shembull të para-ngarkuara.`;
  }
  demoState[id] = data;
  button.disabled = false; button.textContent = "Rigjenero sugjerimet ✳";
  $(`opts-${id}`).innerHTML = (note ? `<div class="demo-note">${escapeHtml(note)}</div>` : "") + `
    <div class="opt-grid">${data.options.map((o, i) => `
      <div class="opt" data-opt="${id}-${i}">
        <h4>${i + 1}. ${escapeHtml(o.title)}</h4><p>${escapeHtml(o.summary)}</p>
        ${o.steps.length ? `<ol>${o.steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ol>` : ""}
        <small>⏱ ${escapeHtml(o.timeframe)}<br>⚖ ${escapeHtml(o.tradeoff)}<br>🏛 ${escapeHtml(o.responsible_institution)}</small>
        <button type="button" data-choose="${id}:${i}">Zgjidh këtë</button>
      </div>`).join("")}</div>
    <div class="demo-status" id="status-${id}"></div>`;
  $(`opts-${id}`).querySelectorAll("[data-choose]").forEach((b) => b.addEventListener("click", () => chooseOption(...b.dataset.choose.split(":"))));
}

async function chooseOption(id, index) {
  const r = DEMO_REPORTS.find((x) => x.id === id);
  const o = demoState[id].options[Number(index)];
  document.querySelectorAll(`[data-opt^="${id}-"]`).forEach((el) => {
    el.classList.toggle("selected", el.dataset.opt === `${id}-${index}`);
    el.querySelector("[data-choose]").textContent = el.dataset.opt === `${id}-${index}` ? "✓ E zgjedhur" : "Zgjidh këtë";
  });
  $(`card-${id}`).classList.add("chosen");
  const content = `Raportim nga ${r.name} (${r.category}, ${r.location})\nZgjidhja e zgjedhur: ${o.title}\n${o.summary}\nHapat: ${o.steps.join("; ") || "—"}\nKoha: ${o.timeframe}\nInstitucioni i mundshëm: ${o.responsible_institution}`;
  try {
    await api("/api/recommendations", { method: "POST", body: JSON.stringify({ report_id: null, content }) });
    $(`status-${id}`).textContent = `Zgjidhja “${o.title}” u zgjodh dhe u ruajt te rekomandimet.`;
  } catch (error) {
    $(`status-${id}`).textContent = `Zgjidhja u shënua, por nuk u ruajt: ${error.message}`;
  }
}

renderDemo();
