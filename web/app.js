const $ = (id) => document.getElementById(id);

const state = {
  pdfs: [],
  currentJob: null,
  source: null,
  summary: null,
  staffRows: [],
};

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => showView(btn.dataset.view));
});
$("dropzone").addEventListener("click", () => $("pdf-input").click());
$("btn-add-pdfs").addEventListener("click", () => $("pdf-input").click());
$("btn-add-folder").addEventListener("click", () => $("pdf-folder-input").click());
$("btn-choose-list").addEventListener("click", () => $("list-file").click());
$("list-file").addEventListener("change", (e) => {
  const file = e.target.files[0];
  $("list-file-name").value = file ? file.name : "";
});
$("btn-clear-pdfs").addEventListener("click", () => { state.pdfs = []; $("pdf-input").value = ""; $("pdf-folder-input").value = ""; renderPdfList(); });
$("dropzone").addEventListener("dragover", (e) => {
  e.preventDefault();
  $("dropzone").classList.add("drag");
});
$("dropzone").addEventListener("dragleave", () => $("dropzone").classList.remove("drag"));
$("dropzone").addEventListener("drop", (e) => {
  e.preventDefault();
  $("dropzone").classList.remove("drag");
  addPdfs([...e.dataTransfer.files]);
});
$("pdf-input").addEventListener("change", (e) => addPdfs([...e.target.files]));
$("pdf-folder-input").addEventListener("change", (e) => addPdfs([...e.target.files]));
$("btn-clear-log").addEventListener("click", () => { $("log").textContent = ""; });
$("btn-start").addEventListener("click", startJob);
$("btn-save-settings").addEventListener("click", saveSettings);
$("dash-q").addEventListener("input", renderDash);
$("dash-filter").addEventListener("change", renderDash);
$("staff-q").addEventListener("input", renderStaff);
$("btn-open-report").addEventListener("click", () => showView("dashboard"));
$("btn-export-report").addEventListener("click", exportReport);

function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $(`view-${name}`).classList.add("active");
  if (name === "staff") loadStaff();
  if (name === "dashboard") renderDash();
}

function addPdfs(files) {
  for (const f of files) {
    if (!f.name.toLowerCase().endsWith(".pdf")) continue;
    if (state.pdfs.some((x) => x.name === f.name && x.size === f.size)) continue;
    state.pdfs.push(f);
  }
  renderPdfList();
}

function renderPdfList() {
  const ul = $("pdf-list");
  ul.innerHTML = "";
  state.pdfs.forEach((f, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${f.name} · ${(f.size / 1024).toFixed(0)} KB</span>`;
    const rm = document.createElement("button");
    rm.textContent = "✕";
    rm.title = "Xóa file này";
    rm.onclick = () => { state.pdfs.splice(i, 1); renderPdfList(); };
    li.appendChild(rm);
    ul.appendChild(li);
  });
  $("pdf-count").textContent = `${state.pdfs.length} file PDF đã chọn`;
}

function logLine(msg, level = "INFO") {
  const el = $("log");
  const span = document.createElement("div");
  span.className = `log-${level}`;
  span.textContent = msg;
  el.appendChild(span);
  el.scrollTop = el.scrollHeight;
}

function setSteps(step, status) {
  document.querySelectorAll("#steps span").forEach((el) => {
    el.classList.remove("active", "done", "err");
    const order = ["read", "extract", "merge", "done"];
    const cur = order.indexOf(step);
    const mine = order.indexOf(el.dataset.step);
    if (status === "error" && mine === cur) el.classList.add("err");
    else if (mine < cur || (step === "done" && status === "done")) el.classList.add("done");
    else if (mine === cur) el.classList.add("active");
  });
}

function applyJob(job) {
  state.currentJob = job;
  $("bar").style.width = `${(job.progress || 0) * 100}%`;
  setSteps(job.step, job.status);
  if (job.status === "done") {
    state.summary = job.summary;
    $("btn-download").classList.remove("hidden");
    $("btn-download").href = `/api/jobs/${job.id}/pdf`;
    $("btn-start").disabled = false;
    $("btn-open-report").classList.remove("hidden");
    renderDash();
  }
  if (job.status === "error") {
    $("btn-start").disabled = false;
  }
}

function listen(jobId) {
  if (state.source) state.source.close();
  state.source = new EventSource(`/api/jobs/${jobId}/events`);
  state.source.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.entry) logLine(msg.entry.message, msg.entry.level || "INFO");
    if (msg.job) applyJob(msg.job);
    if (msg.type === "done" || msg.type === "error") state.source.close();
  };
}

async function startJob() {
  $("btn-start").disabled = true;
  $("btn-download").classList.add("hidden");
  $("btn-open-report").classList.add("hidden");
  $("log").textContent = "";
  setSteps("read", "running");
  $("bar").style.width = "2%";

  try {
    let job;
    if (!state.pdfs.length) throw new Error("Chọn ít nhất một PDF.");
    const list = $("list-file").files[0];
    if (!list) throw new Error("Chọn file danh sách mã CSV/TXT.");
    const fd = new FormData();
    state.pdfs.forEach((f) => fd.append("pdfs", f));
    fd.append("list_file", list);
    if ($("output-path").value.trim()) fd.append("output", $("output-path").value.trim());
    const res = await fetch("/api/jobs/upload", { method: "POST", body: fd });
    if (!res.ok) throw new Error(await errText(res));
    job = await res.json();
    applyJob(job);
    listen(job.id);
  } catch (e) {
    logLine(e.message, "ERROR");
    $("btn-start").disabled = false;
  }
}

async function postPathJob(body) {
  const res = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await errText(res));
  return res.json();
}

async function errText(res) {
  try {
    const j = await res.json();
    return j.detail || JSON.stringify(j);
  } catch {
    return res.statusText;
  }
}

function renderDash() {
  const s = state.summary;
  const empty = $("dash-empty");
  const kpi = $("kpi");
  if (!s) {
    empty.classList.remove("hidden");
    kpi.classList.add("hidden");
    $("staff-chips").classList.add("hidden");
    $("staff-chips").innerHTML = "";
    $("dash-body").innerHTML = "";
    return;
  }
  empty.classList.add("hidden");
  kpi.classList.remove("hidden");
  kpi.innerHTML = `
    <div class="card"><span>Tổng PDF / Trang</span><b>${s.total_pdfs} / ${s.total_pages}</b></div>
    <div class="card"><span>Tổng Số Lượng (Qty)</span><b>${Number(s.total_qty).toLocaleString("vi-VN")}</b></div>
    <div class="card"><span>Độ Phủ Cửa Hàng</span><b>${s.total_codes_found} / ${s.total_codes_expected}</b></div>
    <div class="card"><span>Mã Thiếu / Dư</span><b>${s.missing_codes.length} / ${s.extra_codes.length}</b></div>`;

  const chips = $("staff-chips");
  const staffTotals = s.staff_totals || {};
  chips.innerHTML = Object.keys(staffTotals).sort().map((staff) =>
    `<span>👤 ${staff}: ${Number(staffTotals[staff]).toLocaleString("vi-VN")} Qty</span>`
  ).join("");
  chips.classList.toggle("hidden", !chips.innerHTML);

  const q = $("dash-q").value.trim().toLowerCase();
  const filter = $("dash-filter").value;
  let codes;
  if (filter === "missing") codes = s.missing_codes;
  else if (filter === "extra") codes = s.extra_codes;
  else {
    codes = Object.keys(s.code_name_map || {});
    for (const c of s.extra_codes || []) if (!codes.includes(c)) codes.push(c);
    if (!codes.length) codes = Object.keys(s.store_qty_map || {});
  }

  const rows = [];
  for (const code of codes) {
    const name = (s.code_name_map || {})[code] || "";
    const staff = (s.code_staff_map || {})[code] || "Chưa phân công";
    const qty = (s.store_qty_map || {})[code] || 0;
    if (q && ![code, name, staff].some((x) => String(x).toLowerCase().includes(q))) continue;
    let st = "ℹ️ Chuẩn";
    let cls = "";
    if ((s.missing_codes || []).includes(code)) { st = "Thiếu PO"; cls = "st-missing"; }
    else if ((s.extra_codes || []).includes(code)) { st = "Dư PO"; cls = "st-extra"; }
    else if (qty > 0) { st = "Đã gộp"; cls = "st-ok"; }
    rows.push(`<tr><td>${code}</td><td>${staff}</td><td>${qty || "-"}</td><td>${name}</td><td class="${cls}">${st}</td></tr>`);
  }
  $("dash-body").innerHTML = rows.join("") || `<tr><td colspan="5">Không có dòng</td></tr>`;
}

async function loadStaff() {
  const listFile = $("set-list").value.trim();
  const url = listFile ? `/api/staff?list_file=${encodeURIComponent(listFile)}` : "/api/staff";
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(await errText(res));
    const data = await res.json();
    state.staffRows = data.rows || [];
    renderStaff();
  } catch (e) {
    $("staff-count").textContent = e.message;
    $("staff-body").innerHTML = "";
  }
}

function renderStaff() {
  const q = $("staff-q").value.trim().toLowerCase();
  const rows = state.staffRows.filter((r) =>
    !q || [r.staff, r.code, r.name].some((x) => String(x).toLowerCase().includes(q))
  );
  $("staff-count").textContent = `${rows.length} cửa hàng`;
  $("staff-body").innerHTML = rows.map((r) =>
    `<tr><td>${r.staff}</td><td>${r.code}</td><td>${r.name}</td></tr>`
  ).join("");
}

async function loadSettings() {
  const s = await (await fetch("/api/settings")).json();
  $("app-ver").textContent = `v${s.version}`;
  $("set-list").value = s.last_list_file || "";
  $("set-pdf-folder").value = s.default_pdf_folder || "";
  $("set-out-dir").value = s.last_output_dir || "";
  $("set-pattern").value = s.custom_pattern || "";
  $("set-theme").value = s.theme_mode || "dark";
  applyTheme(s.theme_mode || "dark");
  if (s.last_list_file) $("set-list").value = s.last_list_file;
  if (s.suggested_output) $("output-path").value = s.suggested_output.split(/[\\/]/).pop();
}

async function saveSettings() {
  applyTheme($("set-theme").value);
  const res = await fetch("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      last_list_file: $("set-list").value.trim(),
      default_pdf_folder: $("set-pdf-folder").value.trim(),
      last_output_dir: $("set-out-dir").value.trim(),
      custom_pattern: $("set-pattern").value.trim(),
      theme_mode: $("set-theme").value,
    }),
  });
  if (!res.ok) {
    $("set-status").textContent = await errText(res);
    return;
  }
  $("set-status").textContent = "Đã lưu.";
  setTimeout(() => { $("set-status").textContent = ""; }, 2500);
}

function applyTheme(theme) {
  if (theme === "system") {
    document.body.dataset.theme = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    return;
  }
  document.body.dataset.theme = theme;
}

function exportReport() {
  const s = state.summary;
  if (!s) return;
  const lines = [
    `BÁO CÁO XỬ LÝ PO - ${s.timestamp || ""}`,
    "",
    `- Tổng số file PDF input: ${s.total_pdfs}`,
    `- Tổng số trang xử lý: ${s.total_pages}`,
    `- Tổng số lượng (Qty sau chia 2): ${s.total_qty}`,
    `- Tổng số mã chuẩn: ${s.total_codes_expected}`,
    `- Tổng số mã tìm thấy: ${s.total_codes_found}`,
    `- File output kết quả: ${s.output_path || ""}`,
    "", "--- DANH SÁCH MÃ THIẾU PO ---",
    ...(s.missing_codes.length ? s.missing_codes.map((code) => `  • ${code}`) : ["  (Không có mã nào thiếu)"]),
    "", "--- DANH SÁCH MÃ DƯ PO ---",
    ...(s.extra_codes.length ? s.extra_codes.map((code) => `  • ${code}`) : ["  (Không có mã nào dư)"]),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `PO_Report_${new Date().toISOString().replace(/[T:]/g, "-").slice(0, 19)}.txt`;
  link.click();
  URL.revokeObjectURL(url);
}

loadSettings();
