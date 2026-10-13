"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const kinds = {schedule: "Course schedule", student_card: "Student card", receipt: "Tuition receipt"};
const kindIcons = {schedule: "calendar-days", student_card: "contact-round", receipt: "receipt-text"};
const state = {token: "", profiles: [], resources: [], batches: [], sources: {}, batch: null,
  kind: "schedule", zoom: 1, activeTask: null, pollTimer: null, keyConfigured: false, view: "workspace",
  pendingRegeneration: false};
let toastTimer;

function icons() { window.lucide.createIcons({attrs: {"aria-hidden": "true"}}); }
function node(tag, className, text) {
  const result = document.createElement(tag);
  if (className) result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
}
function icon(name) { const el = node("i"); el.dataset.lucide = name; return el; }
function toast(text, error = false) {
  const element = $("#toast");
  element.textContent = text; element.classList.toggle("error", error); element.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { element.hidden = true; }, error ? 8000 : 3500);
}
async function api(url, options = {}) {
  const headers = {"X-Studio-Token": state.token, ...options.headers};
  if (options.body && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  let response;
  try { response = await fetch(url, {...options, headers}); }
  catch { throw new Error("Cannot reach the local studio. Check the server and refresh."); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
function settings() { return {base_url: $("#base-url").value.trim(), model: $("#model").value.trim(), timeout: Number($("#timeout").value)}; }
function mode() { return $('input[name="render-mode"]:checked').value; }
function currentProfile() { return state.profiles.find((p) => p.id === $("#profile-select").value); }
function dateText(value) { return new Date(value).toLocaleString("en-US", {month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"}); }
function downloadLink(element, url) {
  element.setAttribute("aria-disabled", url ? "false" : "true");
  if (url) element.href = url; else element.removeAttribute("href");
}

function fillProfiles(selected = $("#profile-select").value) {
  const select = $("#profile-select"); select.replaceChildren();
  for (const profile of state.profiles) {
    const option = node("option", "", profile.full_name); option.value = profile.id; select.append(option);
  }
  if (state.profiles.some((p) => p.id === selected)) select.value = selected;
  showProfile();
}
function showProfile() {
  const p = currentProfile(); if (!p) return;
  $("#profile-name").textContent = p.full_name;
  $("#profile-id").textContent = p.student_id;
  $("#profile-dob").textContent = p.date_of_birth;
  $("#profile-age").textContent = String(p.age);
  $("#profile-initials").textContent = p.full_name.split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0]).join("");
  const portrait = $("#profile-portrait");
  if (p.portrait_url) {
    portrait.src = `${p.portrait_url}?v=${encodeURIComponent(p.student_id)}`;
    portrait.hidden = false; $("#profile-initials").hidden = true;
  } else {
    portrait.removeAttribute("src"); portrait.hidden = true; $("#profile-initials").hidden = false;
  }
  profileImageState();
}
function fillResources(selected = $("#resource-select").value) {
  const select = $("#resource-select"); select.replaceChildren();
  const base = node("option", "", "Verified source snapshot"); base.value = ""; select.append(base);
  for (const resource of state.resources) {
    const option = node("option", "", resource.name); option.value = resource.id; select.append(option);
  }
  select.value = selected;
}
function generationState() {
  const ai = mode() === "ai";
  $("#model").disabled = !ai || Boolean(state.activeTask);
  const warning = $("#generation-warning");
  warning.hidden = !(ai && !state.keyConfigured);
  warning.textContent = "OPENAI_API_KEY is not configured on the server.";
  $("#generate").disabled = Boolean(state.activeTask) || (ai && !state.keyConfigured);
  const complete = state.batch?.status === "complete";
  $("#generate span").textContent = state.activeTask ? "Generation in progress" : complete ? "Regenerate 3 images" : "Generate 3 images";
  $$('input[name="render-mode"]').forEach((input) => { input.disabled = Boolean(state.activeTask); });
  profileImageState();
}
function profileImageState() {
  const button = $("#generate-profile-image");
  if (!button) return;
  button.disabled = Boolean(state.activeTask) || !state.keyConfigured || !currentProfile();
  button.title = state.keyConfigured ? "Generate student image" : "OPENAI_API_KEY is not configured on the server";
}
function fitImage() {
  const image = $("#document-image"), stage = $("#preview-stage"), wrap = $("#sheet-wrap");
  if (image.hidden || !image.naturalWidth) { wrap.style.width = "100%"; wrap.style.height = "100%"; return; }
  const padding = window.innerWidth < 740 ? 30 : 50;
  const factor = Math.min((stage.clientWidth - padding) / image.naturalWidth, (stage.clientHeight - padding) / image.naturalHeight);
  const width = Math.max(1, Math.round(image.naturalWidth * factor * state.zoom));
  const height = Math.max(1, Math.round(image.naturalHeight * factor * state.zoom));
  image.style.width = `${width}px`; image.style.height = `${height}px`;
  wrap.style.width = `${Math.max(stage.clientWidth, width + padding)}px`;
  wrap.style.height = `${Math.max(stage.clientHeight, height + padding)}px`;
  $("#zoom-level").textContent = `${Math.round(state.zoom * 100)}%`;
  $("#zoom-out").disabled = state.zoom <= .5;
  $("#zoom-in").disabled = state.zoom >= 3;
}
function selectKind(kind) {
  state.kind = kind; state.zoom = 1; showPreview();
}
function showPreview() {
  const batch = state.batch, file = batch?.files[state.kind];
  $$("[data-kind]").forEach((button) => {
    const selected = button.dataset.kind === state.kind;
    if (button.getAttribute("role") === "tab") { button.setAttribute("aria-selected", selected); button.tabIndex = selected ? 0 : -1; }
    else button.classList.toggle("selected", selected);
  });
  const image = $("#document-image"); image.hidden = !file;
  $("#empty-preview").hidden = Boolean(file);
  $("#preview-filename").textContent = file ? file.name : kinds[state.kind];
  $("#image-dimensions").textContent = file ? `${file.size[0]} x ${file.size[1]} px / PNG` : "PNG";
  $("#expand-preview").disabled = !file;
  $("#zoom-fit").disabled = !file; $("#zoom-in").disabled = !file; $("#zoom-out").disabled = !file;
  downloadLink($("#download-image"), file ? `${file.url}?download=1` : null);
  if (file && image.getAttribute("src") !== file.url) {
    image.src = file.url; image.alt = `${kinds[state.kind]} for fictional student ${batch.profile.full_name}`;
  }
  if (!file) {
    image.removeAttribute("src");
    $("#empty-preview strong").textContent = batch?.status === "failed" ? "Generation incomplete" : state.activeTask ? "Generating documents" : "No document selected";
    $("#empty-preview span").textContent = `${batch?.outputs_done || 0} of 3 documents`;
  }
  fitImage();
}
function showBatch(batch) {
  state.batch = batch;
  if (batch) {
    const profile = state.profiles.find((p) => p.student_id === batch.profile.student_id && p.full_name === batch.profile.full_name);
    if (profile) { $("#profile-select").value = profile.id; showProfile(); }
  }
  const modeBadge = $("#batch-mode");
  modeBadge.textContent = batch ? batch.render_mode === "ai" ? "AI assets" : "Local preview" : "No batch selected";
  modeBadge.classList.toggle("ai", batch?.render_mode === "ai");
  $("#batch-reference").textContent = batch ? `Batch ${batch.id}` : "No batch selected";
  $("#batch-sources").disabled = !batch;
  downloadLink($("#download-set"), batch?.status === "complete" ? `/api/batches/${batch.id}/download` : null);
  const status = $("#preview-status"); status.replaceChildren();
  status.append(node("span", `status-dot${batch?.status === "complete" ? "" : " neutral"}`),
    document.createTextNode(batch ? batch.status === "complete" ? "Complete" : `${batch.outputs_done}/3 ready` : "Waiting"));
  const strip = $("#thumbnail-strip"); strip.replaceChildren();
  Object.entries(kinds).forEach(([kind, title], index) => {
    const button = node("button", "thumbnail"); button.dataset.kind = kind; button.setAttribute("aria-label", `Preview ${title}`);
    button.addEventListener("click", () => selectKind(kind));
    const picture = node("div", "thumbnail-image"); picture.append(node("span", "index", `0${index + 1}`));
    if (batch?.files[kind]) { const img = node("img"); img.src = batch.files[kind].url; img.alt = ""; picture.append(img); }
    else picture.append(icon(kindIcons[kind]));
    const caption = node("div", "thumbnail-caption"); caption.append(node("span", "", title));
    if (batch?.files[kind]) caption.append(icon("circle-check"));
    button.append(picture, caption); strip.append(button);
  });
  const message = $("#batch-message"), failed = batch && ["failed", "interrupted"].includes(batch.status);
  const running = batch && ["running", "created"].includes(batch.status);
  message.hidden = !(failed || running); message.classList.toggle("running", Boolean(running));
  $("#batch-message-title").textContent = failed ? "Batch needs attention" : "Generation in progress";
  $("#batch-message-detail").textContent = failed ? batch.error || "The previous run was interrupted. Check the batch before retrying." : `${batch?.assets_done || 0}/2 assets and ${batch?.outputs_done || 0}/3 documents ready.`;
  $("#retry-batch").hidden = !failed; $("#retry-batch").disabled = Boolean(state.activeTask);
  icons(); showPreview(); generationState();
}
function showView(view) {
  state.view = view;
  $("#workspace-view").hidden = view !== "workspace";
  $("#history-view").hidden = view !== "history";
  $("#page-title").textContent = view === "workspace" ? "Document workspace" : "Batch history";
  $("#breadcrumb-current").textContent = view === "workspace" ? "Workspace" : "Batch history";
  $("#download-set").hidden = view !== "workspace";
  $$("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  if (view === "workspace") requestAnimationFrame(fitImage);
}
function renderHistory() {
  $("#history-count").textContent = String(state.batches.length);
  $("#history-summary").textContent = `${state.batches.length} BATCH${state.batches.length === 1 ? "" : "ES"}`;
  const filter = $("#history-filter").value;
  const filtered = state.batches.filter((batch) => filter === "all" || (filter === "failed" ? ["failed", "interrupted"].includes(batch.status) : batch.status === filter));
  const body = $("#history-body"); body.replaceChildren();
  $("#history-empty").hidden = Boolean(filtered.length);
  for (const batch of filtered) {
    const row = node("tr");
    const created = node("td", "", dateText(batch.created)); created.append(node("small", "", batch.id.slice(-8)));
    const person = node("td", "", batch.profile.full_name); person.append(node("small", "", batch.profile.student_id));
    const rendering = node("td", "", batch.render_mode === "ai" ? "AI assets" : "Local preview");
    if (batch.render_mode === "ai") rendering.append(node("small", "", batch.model));
    const status = node("td"); status.append(node("span", `badge ${batch.status}`, batch.status[0].toUpperCase() + batch.status.slice(1)));
    const count = node("td", "", `${batch.outputs_done} / 3`);
    const actions = node("td");
    if (["failed", "interrupted"].includes(batch.status)) {
      const retry = node("button", "icon-button"); retry.title = "Retry batch"; retry.setAttribute("aria-label", `Retry batch ${batch.id}`); retry.append(icon("rotate-cw")); retry.disabled = Boolean(state.activeTask);
      retry.addEventListener("click", () => startGeneration(batch.id)); actions.append(retry);
    }
    const open = node("button", "icon-button"); open.title = "Open batch"; open.setAttribute("aria-label", `Open batch ${batch.id}`); open.append(icon("arrow-up-right"));
    open.addEventListener("click", () => { showBatch(batch); showView("workspace"); }); actions.append(open);
    row.append(created, person, rendering, status, count, actions); body.append(row);
  }
  icons();
}
async function refreshBatches() {
  state.batches = await api("/api/batches"); renderHistory();
}
async function load() {
  const data = await api("/api/bootstrap");
  clearTimeout(state.pollTimer);
  state.activeTask = data.active_task || null;
  if (!state.token) $('input[name="render-mode"][value="ai"]').checked = true;
  state.token = data.token; state.profiles = data.profiles; state.resources = data.resources;
  state.batches = data.batches; state.sources = data.sources; state.keyConfigured = data.key_configured;
  $("#base-url").value = data.settings.base_url; $("#model").value = data.settings.model; $("#timeout").value = data.settings.timeout;
  $("#key-status").textContent = state.keyConfigured ? "Key configured" : "No API key";
  $("#key-status").classList.toggle("ready", state.keyConfigured);
  fillProfiles(); fillResources($("#resource-select").value || (state.resources[0]?.id ?? ""));
  $("#session-term").textContent = data.sources.session.term;
  const formatDate = (value, year) => new Date(value + "T12:00:00Z").toLocaleDateString("en-US", {month: "short", day: "numeric", ...(year ? {year: "numeric"} : {}), timeZone: "UTC"});
  $("#session-dates").textContent = `${formatDate(data.sources.session.start, false)} - ${formatDate(data.sources.session.end, true)}`;
  $("#source-date").textContent = data.sources.verified_on;
  const previous = state.batches.find((b) => b.id === state.batch?.id);
  showBatch(previous || state.batches.find((b) => b.status === "complete") || state.batches[0] || null);
  renderHistory(); generationState(); $("#connection-alert").hidden = true;
  $("#generation-progress").hidden = !state.activeTask;
  if (state.activeTask) pollTask();
}
async function startGeneration(resumeId = null) {
  if (state.activeTask) return;
  $("#generate").disabled = true;
  try {
    state.pendingRegeneration = !resumeId && state.batch?.status === "complete";
    const body = resumeId ? {resume_id: resumeId, settings: settings()} : {
      fresh_profile: true, profile_id: $("#profile-select").value, resource_id: $("#resource-select").value,
      render_mode: mode(), settings: settings()
    };
    const task = await api("/api/tasks", {method: "POST", body: JSON.stringify(body)});
    if (task.profile) { state.profiles.unshift(task.profile); fillProfiles(task.profile.id); }
    state.activeTask = task.id; showView("workspace");
    if (!resumeId) showBatch(null);
    else { const previous = state.batches.find((b) => b.id === resumeId); if (previous) showBatch({...previous, status: "running", error: ""}); }
    generationState(); $("#generation-progress").hidden = false;
    pollTask();
  } catch (error) { state.pendingRegeneration = false; toast(error.message, true); generationState(); }
}
async function pollTask(failures = 0) {
  clearTimeout(state.pollTimer);
  if (!state.activeTask) return;
  const taskId = state.activeTask;
  try {
    const task = await api(`/api/tasks/${taskId}`);
    if (state.activeTask !== taskId) return;
    if (task.batch) showBatch(task.batch);
    const progress = $("#generation-progress"); progress.hidden = false;
    const assetsTotal = task.batch?.assets_total ?? 1;
    const outputsTotal = task.batch?.outputs_total ?? 3;
    $("#generation-progress progress").max = assetsTotal + outputsTotal;
    $("#generation-progress progress").value = (task.batch?.assets_done || 0) + (task.batch?.outputs_done || 0);
    $("#generation-progress span").textContent = task.batch
      ? `${task.batch.assets_done}/${assetsTotal} assets / ${task.batch.outputs_done}/${outputsTotal} documents`
      : "Queued";
    if (["complete", "failed"].includes(task.status)) {
      state.activeTask = null; generationState(); progress.hidden = true;
      if (task.batch) showBatch(task.batch);
      const message = task.status === "complete"
        ? state.pendingRegeneration ? "New three-image set saved to history." : "Three images are ready."
        : task.error || "Generation failed.";
      state.pendingRegeneration = false;
      const updated = await api("/api/bootstrap");
      state.profiles = updated.profiles; fillProfiles();
      if (task.batch) showBatch(task.batch);
      toast(message, task.status === "failed");
      await refreshBatches(); return;
    }
    state.pollTimer = setTimeout(() => pollTask(), 800);
  } catch (error) {
    if (state.activeTask !== taskId) return;
    if (failures < 4) state.pollTimer = setTimeout(() => pollTask(failures + 1), 1800);
    else { $("#connection-alert").textContent = error.message; $("#connection-alert").hidden = false; }
  }
}
function showSources() {
  const target = $("#sources-content"); target.replaceChildren();
  for (const [name, source] of Object.entries(state.sources.sources || {})) {
    const section = node("section", "source-record");
    section.append(node("h3", "", name), node("p", "", source.evidence));
    const link = node("a", "", source.url); link.href = source.url; link.target = "_blank"; link.rel = "noreferrer"; section.append(link); target.append(section);
  }
  const list = node("ul", "source-assumptions");
  for (const assumption of state.sources.assumptions || []) list.append(node("li", "", assumption));
  target.append(list); $("#sources-dialog").showModal();
}

$$("[data-view]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.view)));
$$(".document-tabs [data-kind]").forEach((button) => {
  button.addEventListener("click", () => selectKind(button.dataset.kind));
  button.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault(); const keys = Object.keys(kinds), index = keys.indexOf(state.kind);
    const next = event.key === "Home" ? 0 : event.key === "End" ? keys.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + keys.length) % keys.length;
    selectKind(keys[next]); $(`.document-tabs [data-kind="${keys[next]}"]`).focus();
  });
});
$("#profile-select").addEventListener("change", showProfile);
$$("input[name=render-mode]").forEach((input) => input.addEventListener("change", generationState));
$("#history-filter").addEventListener("change", renderHistory);
$("#generate").addEventListener("click", () => startGeneration());
$("#retry-batch").addEventListener("click", () => { if (state.batch) startGeneration(state.batch.id); });
$("#document-image").addEventListener("load", fitImage);
$("#document-image").addEventListener("error", () => { toast("Preview could not be loaded. Refresh the batch.", true); });
$("#zoom-in").addEventListener("click", () => { state.zoom = Math.min(3, state.zoom + .25); fitImage(); });
$("#zoom-out").addEventListener("click", () => { state.zoom = Math.max(.5, state.zoom - .25); fitImage(); });
$("#zoom-fit").addEventListener("click", () => { state.zoom = 1; fitImage(); });
new ResizeObserver(fitImage).observe($("#preview-stage"));
$("#expand-preview").addEventListener("click", () => {
  const file = state.batch?.files[state.kind]; if (!file) return;
  $("#expanded-image").src = file.url; $("#expanded-title").textContent = kinds[state.kind]; $("#image-dialog").showModal();
});
$("#sources-open").addEventListener("click", showSources);
$("#batch-sources").addEventListener("click", () => { if (state.batch) window.location.assign(`/api/batches/${state.batch.id}/sources`); });
$$("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
$("#refresh").addEventListener("click", async () => {
  $("#refresh").disabled = true;
  try { await load(); toast("Workspace refreshed."); } catch (error) { toast(error.message, true); }
  finally { $("#refresh").disabled = false; }
});
$("#new-profile").addEventListener("click", async () => {
  $("#new-profile").disabled = true;
  try {
    const profile = await api("/api/profiles", {method: "POST", body: "{}"});
    state.profiles.unshift(profile); fillProfiles(profile.id); toast("New fictional profile created.");
  } catch (error) { toast(error.message, true); }
  finally { $("#new-profile").disabled = false; }
});
$("#edit-profile").addEventListener("click", () => {
  const profile = currentProfile(); if (!profile) return;
  $("#edit-name").value = profile.full_name; $("#edit-dob").value = profile.date_of_birth;
  $("#profile-error").hidden = true; $("#profile-dialog").showModal();
});
$("#generate-profile-image").addEventListener("click", async () => {
  const profile = currentProfile(); if (!profile) return;
  const button = $("#generate-profile-image"); button.disabled = true; button.classList.add("spin");
  try {
    const updated = await api(`/api/profiles/${profile.id}/portrait`, {method: "POST", body: JSON.stringify({settings: settings()})});
    state.profiles = state.profiles.map((item) => item.id === updated.id ? updated : item);
    fillProfiles(updated.id); toast("Student image generated.");
  } catch (error) { toast(error.message, true); }
  finally { button.classList.remove("spin"); profileImageState(); }
});
$("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const button = $('#profile-form button[type="submit"]'); button.disabled = true;
  try {
    const profile = await api("/api/profiles", {method: "POST", body: JSON.stringify({full_name: $("#edit-name").value, date_of_birth: $("#edit-dob").value})});
    state.profiles.unshift(profile); fillProfiles(profile.id); $("#profile-dialog").close(); toast("Profile copy saved.");
  } catch (error) { $("#profile-error").textContent = error.message; $("#profile-error").hidden = false; }
  finally { button.disabled = false; }
});
$("#upload-trigger").addEventListener("click", () => $("#resource-file").click());
$("#resource-file").addEventListener("change", async () => {
  const file = $("#resource-file").files[0]; if (!file) return;
  if (file.size > 10 * 1024 * 1024) { toast("The ZIP package must be 10 MB or smaller.", true); $("#resource-file").value = ""; return; }
  $("#upload-trigger").disabled = true;
  try {
    const body = new FormData(); body.append("file", file);
    const resource = await api("/api/resources", {method: "POST", body});
    state.resources.push(resource); fillResources(resource.id); toast("Resource package uploaded.");
  } catch (error) { toast(error.message, true); }
  finally { $("#upload-trigger").disabled = false; $("#resource-file").value = ""; }
});
$("#save-settings").addEventListener("click", async () => {
  $("#save-settings").disabled = true;
  try { await api("/api/settings", {method: "POST", body: JSON.stringify(settings())}); toast("Connection settings saved."); }
  catch (error) { toast(error.message, true); }
  finally { $("#save-settings").disabled = false; }
});
icons(); showBatch(null);
load().catch((error) => { $("#connection-alert").textContent = error.message; $("#connection-alert").hidden = false; });
