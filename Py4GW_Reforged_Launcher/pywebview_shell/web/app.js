// Phase B/C/D real UI (RELAY 010/011) -- structure + theme + real profile CRUD.
// No framework: the mockup this is built from uses a small proprietary
// component/templating system (DCLogic/sc-for/sc-if) that isn't portable outside
// Claude Design's own export tooling, so this is hand-written vanilla JS doing the
// same job (render from state, re-render on change) without that dependency.
//
// RELAY 011 wires real writes (Add/Edit/Delete profiles, team membership) onto the
// read-only structure RELAY 010 built. Still explicitly NOT wired: GW1 launch,
// console/log, App Settings' real prerequisite checks/mod repo/accounts sections,
// edit-dialog tabs decision, cross-team search, checkbox/subset launch,
// click-to-focus tracking. The Launch button remains disabled -- present for visual
// structure only.
//
// No `run_as_admin` field/control anywhere here -- deliberate (RELAY 011):
// GameProfile has no such field, and the real UAC/elevation mechanism is still
// undesigned, so a toggle with nothing behind it would just lie about what it does.

let palette = { ...THEME_PRESETS[0] };
let profiles = [];
let teams = [];
let activeTeamId = "ALL";
let filterText = "";
let checkedIds = new Set();
let editingProfileId = null; // null while the edit drawer is closed or adding new
// RELAY 024: gMod plugin list is an array field, not a simple form control --
// held here while the drawer's open, same lifecycle as editingProfileId, and
// written back into save_profile's data on Save.
let editPluginPaths = [];
let bulkLaunchActive = false; // Phase F -- a team/bulk launch sequence is currently running
// Console (RELAY 021). consoleLines mirrors bridge.py's own bounded deque --
// entries are {id, text, err}, appended/replaced one at a time via the
// 'console_line' push (see window.shellBridge.on) rather than resending the
// whole history on every line.
let consoleLines = [];
let consoleSelected = new Set();
let consoleNextId = 0;
const CONSOLE_MAX_LINES = 500; // mirrors bridge.py's deque(maxlen=500)

// Mod Repository (RELAY 033) -- mirrors the old imgui app's ModRepoState
// property names closely on purpose, not renamed/combined, so this stays
// easy to compare against that real, proven reference.
let modRepoPath = "";
let modRepoUrl = "";
let modRepoDetection = null; // null while checking, else {status, path}
let modRepoCheckingUpdates = false;
let modRepoUpdateCheck = null; // null until "Check for updates" resolves once
let modRepoCloneInProgress = false;
let modRepoUpdateInProgress = false;
let modRepoOpStatusText = "";
let modRepoOpDoneMessage = null;

function teamName(teamId) {
  if (teamId === "ALL") return "All Profiles";
  const t = teams.find((x) => x.id === teamId);
  return t ? t.name : "";
}

// RELAY 029: alphabetical-by-name is the only ordering model this app will
// ever have -- no drag-and-drop reorder exists or is planned (Chris, having
// lived with the old imgui app's real custom-order feature through real
// multi-account use: "it really turned out to be unnecessary fluff"), so
// there's no toggle here, just a permanent sort. Case-insensitive, matching
// the old app's own sort(key=lambda p: p.name.lower()) convention. Sorts a
// copy -- never mutates the shared `profiles` array itself.
function membersOfActiveTeam() {
  const members = activeTeamId === "ALL" ? profiles : profiles.filter((p) => (p.team_ids || []).includes(activeTeamId));
  return [...members].sort((a, b) => (a.name || "").localeCompare(b.name || "", undefined, { sensitivity: "base" }));
}

function renderRail() {
  document.getElementById("rail-all-count").textContent = String(profiles.length);
  document.getElementById("rail-all").classList.toggle("active", activeTeamId === "ALL");

  const container = document.getElementById("rail-teams");
  container.innerHTML = "";
  for (const t of teams) {
    const el = document.createElement("div");
    el.className = "rail-team" + (t.id === activeTeamId ? " active" : "");
    el.style.background = avatarColor(t.name);
    el.title = t.name;
    el.textContent = initials(t.name);
    el.onclick = () => selectTeam(t.id);
    container.appendChild(el);
  }
}

function renderHeader() {
  const members = membersOfActiveTeam();
  document.getElementById("team-name").textContent = teamName(activeTeamId);
  document.getElementById("team-count").textContent = `${members.length} profile${members.length === 1 ? "" : "s"}`;
  document.getElementById("remove-team-btn").style.display = activeTeamId === "ALL" ? "none" : "inline-block";
  // "Launch Team" only makes sense for a real team, not the ALL pseudo-view
  // (same visibility rule remove-team-btn already uses).
  document.getElementById("launch-team-btn").style.display =
    activeTeamId === "ALL" || bulkLaunchActive ? "none" : "inline-block";
  updateAddToTeamBtn();
}

// Add to Team (RELAY 023): ALL view only -- redundant on a team-scoped view
// since a profile shown there is already in that team; reassigning between
// teams is ALL's job.
// RELAY 027: within the ALL view, always visible rather than hidden until
// checked -- disabled (real attribute) when there's nothing selected, same
// reversal as updateLaunchSelectedBtn above.
function updateAddToTeamBtn() {
  const btn = document.getElementById("add-to-team-btn");
  const onAll = activeTeamId === "ALL";
  btn.style.display = onAll ? "inline-block" : "none";
  btn.disabled = !onAll || checkedIds.size === 0;
}

function badgeHtml(label, on) {
  return `<span class="badge${on ? " on" : ""}" title="${label} — ${on ? "on" : "off"} for this profile">${label}</span>`;
}

// Cards are too narrow for a real Gw.exe path -- CSS ellipsis just chops it
// mid-string ("C:\Games\Guild Wars 1\Client_..."), which reads as broken, not
// truncated. The folder immediately containing Gw.exe is what actually tells
// two profiles apart (e.g. "Client 02"), so show that short label instead and
// keep the full path as a hover tooltip.
function clientFolderLabel(execPath) {
  if (!execPath) return "no client path set";
  const parts = execPath.split(/[\\/]/).filter(Boolean);
  if (parts.length < 2) return execPath;
  return parts[parts.length - 2];
}

function renderCards() {
  const members = membersOfActiveTeam();
  const q = filterText.toLowerCase().trim();
  const visible = q ? members.filter((p) => (p.name || "").toLowerCase().includes(q)) : members;

  const grid = document.getElementById("card-grid");
  const noProfiles = document.getElementById("no-profiles");
  const noResults = document.getElementById("no-results");

  noProfiles.style.display = profiles.length === 0 ? "block" : "none";
  noResults.style.display = profiles.length > 0 && visible.length === 0 ? "block" : "none";
  if (noResults.style.display === "block") {
    noResults.textContent = q ? `No profiles match "${filterText}"` : "No profiles in this team yet";
  }

  grid.innerHTML = "";
  for (const p of visible) {
    const card = document.createElement("div");
    card.className = "card" + (checkedIds.has(p.id) ? " selected" : "");
    card.setAttribute("data-card", p.id);
    const midText = clientFolderLabel(p.executable_path);
    card.innerHTML = `
      <div class="card-top">
        <div class="card-check${checkedIds.has(p.id) ? " checked" : ""}" data-check="${p.id}">${checkedIds.has(p.id) ? "&#10003;" : ""}</div>
        <div class="card-avatar" style="background:${avatarColor(p.name)}">${initials(p.name)}</div>
        <div class="card-name-block">
          <div class="card-name">${escapeHtml(p.name || "(unnamed)")}</div>
          <div class="card-sub" title="${escapeHtml(p.executable_path || "")}">${escapeHtml(midText)}</div>
        </div>
        <span class="card-dot"></span>
      </div>
      <div class="card-badges">
        ${badgeHtml("P4", !!p.py4gw_enabled)}
        ${badgeHtml("gM", !!p.gmod_enabled)}
        ${p.auto_login_enabled ? badgeHtml("AUTO", true) : ""}
      </div>
      <div class="card-bottom-row">
        <button class="card-action">&#9654; Launch</button>
        <button class="card-edit-btn" data-edit="${p.id}" title="Edit profile">&#9998;</button>
      </div>
    `;
    card.querySelector("[data-check]").onclick = (e) => {
      e.stopPropagation();
      toggleCheck(p.id);
    };
    card.querySelector("[data-edit]").onclick = (e) => {
      e.stopPropagation();
      openEditDrawer(p.id);
    };
    applyCardLaunchVisual(card, p); // Launch/Stop button + dot + status per launchState
    grid.appendChild(card);
  }
}

// ---------- Individual launch (Phase E) ----------
// launchState[profileId] = { phase, status, pid, error }. Kept separate from
// `profiles` so a re-render (team switch, filter, CRUD) preserves a launch in
// progress, and so live push updates can target one card without a full
// re-render. Python (bridge.launch_profile) runs the real pipeline on a thread
// and pushes 'launch_log'/'launch_done' back here via window.shellBridge.on.
const launchState = {};

function applyCardLaunchVisual(card, p) {
  const st = launchState[p.id] || { phase: "idle" };
  const dot = card.querySelector(".card-dot");
  const sub = card.querySelector(".card-sub");
  const action = card.querySelector(".card-action");
  card.classList.remove("state-launching", "state-running", "state-error", "state-queued");

  if (st.phase === "queued") {
    card.classList.add("state-queued");
    sub.textContent = st.status || "Queued...";
    sub.removeAttribute("title");
    action.innerHTML = "&#8987; Queued";
    action.disabled = true;
    action.onclick = null;
  } else if (st.phase === "launching") {
    card.classList.add("state-launching");
    sub.textContent = st.status || "Launching...";
    sub.removeAttribute("title");
    action.innerHTML = "&#8987; " + escapeHtml(st.status || "Launching...");
    action.disabled = true;
    action.onclick = null;
  } else if (st.phase === "running") {
    card.classList.add("state-running");
    sub.textContent = "Running · PID " + st.pid;
    sub.removeAttribute("title");
    action.textContent = "■ Stop";
    action.disabled = false;
    action.onclick = (e) => { e.stopPropagation(); stopProfile(p.id); };
  } else {
    // idle or error: button offers Launch either way; error shows why.
    if (st.phase === "error") {
      card.classList.add("state-error");
      sub.textContent = st.error || "Launch failed";
      sub.title = st.error || "";
    } else {
      sub.textContent = clientFolderLabel(p.executable_path);
      sub.title = p.executable_path || "";
    }
    action.innerHTML = "&#9654; Launch";
    action.disabled = false;
    action.onclick = (e) => { e.stopPropagation(); launchProfile(p.id); };
  }
}

function refreshCard(id) {
  const card = document.querySelector('[data-card="' + id + '"]');
  if (!card) return; // not currently on screen (other team / filtered out)
  const p = profiles.find((x) => x.id === id);
  if (p) applyCardLaunchVisual(card, p);
}

async function launchProfile(id) {
  launchState[id] = { phase: "launching", status: "Launching..." };
  refreshCard(id);
  const res = await window.pywebview.api.launch_profile(id);
  if (!res || !res.ok) {
    launchState[id] = { phase: "error", error: (res && res.error) || "Could not start launch" };
    refreshCard(id);
  }
  // On success, the launch_log / launch_done pushes drive the rest.
}

async function stopProfile(id) {
  const res = await window.pywebview.api.stop_profile(id);
  if (res && res.ok) {
    delete launchState[id];
  } else {
    launchState[id] = { phase: "error", error: (res && res.error) || "Could not stop the client" };
  }
  refreshCard(id);
}

// ---------- Team/bulk launch (Phase F) ----------
// "Launch Selected" and "Launch Team" both call the same bridge method,
// bulk_launch_profiles -- they only differ in which profile ids they pass
// (checkedIds vs. every member of the active team). Pacing/sequencing/
// readiness all live on the Python side (bridge._run_bulk_launch); this
// side just triggers it and reflects the per-card 'launch_queued' pushes
// it drives (see applyCardLaunchVisual's "queued" branch and
// window.shellBridge.on above/below).

function setBulkLaunchActive(active) {
  bulkLaunchActive = active;
  document.getElementById("bulk-stop-btn").style.display = active ? "inline-block" : "none";
  updateLaunchSelectedBtn();
  renderHeader(); // launch-team-btn's own visibility depends on bulkLaunchActive too
}

async function onLaunchSelectedClick() {
  if (checkedIds.size === 0 || bulkLaunchActive) return;
  const ids = Array.from(checkedIds);
  checkedIds = new Set();
  updateAddToTeamBtn();
  const res = await window.pywebview.api.launch_profiles_bulk(ids);
  if (res && res.ok) setBulkLaunchActive(true);
  renderCards();
}

async function onLaunchTeamClick() {
  if (activeTeamId === "ALL" || bulkLaunchActive) return;
  const ids = membersOfActiveTeam().map((p) => p.id);
  if (ids.length === 0) return;
  const res = await window.pywebview.api.launch_profiles_bulk(ids);
  if (res && res.ok) setBulkLaunchActive(true);
}

async function onBulkStopClick() {
  await window.pywebview.api.cancel_bulk_launch();
  // bulk_launch_done (pushed once the sequence's loop actually exits)
  // is what flips bulkLaunchActive back off -- not this call itself,
  // since cancelling only stops queuing further accounts, it doesn't
  // instantly end the sequence (an in-flight readiness wait/pacing tick
  // still finishes its own current step first).
}

// Python -> JS push target (bridge.push_event -> window.shellBridge.on).
window.shellBridge = {
  on(event, data) {
    if (event === "console_line") {
      // RELAY 030: category comes from the server (classify_progress_
      // category, launcher_core/launch_progress.py) -- no client-side
      // regex guess anymore, that old .err-only heuristic is fully
      // replaced, not run alongside this.
      if (data.replace_last && consoleLines.length > 0) {
        consoleLines[consoleLines.length - 1] = { ...consoleLines[consoleLines.length - 1], text: data.line, category: data.category };
      } else {
        consoleLines.push({ id: consoleNextId++, text: data.line, category: data.category });
        if (consoleLines.length > CONSOLE_MAX_LINES) consoleLines.shift();
      }
      renderConsole();
      return;
    }
    if (event === "bulk_launch_done") {
      // Whatever never got started (mid-sequence cancel) goes back to
      // idle instead of being left showing "Queued" forever.
      setBulkLaunchActive(false);
      for (const id of (data && data.reset_profile_ids) || []) {
        delete launchState[id];
        refreshCard(id);
      }
      return;
    }
    if (event === "prereqs_result") {
      for (const component of PREREQ_COMPONENTS) {
        updatePrereqRow(component, data[component]);
      }
      return;
    }
    if (event === "prereq_install_status") {
      // Busy text takes over the row's status slot in place of the Install
      // button, same swap the old imgui app did (text_colored(_PREREQ_
      // BUSY_COLOR, ...) same_line() instead of the button).
      const statusEl = document.getElementById(`prereq-status-${data.component}`);
      statusEl.textContent = data.text;
      statusEl.className = "prereq-status busy";
      return;
    }
    if (event === "prereq_install_done") {
      const doneEl = document.getElementById("prereq-done-message");
      doneEl.textContent = data.message;
      doneEl.style.display = "block";
      // No restart needed to see the result -- the bridge already re-runs
      // check_prereqs() right after this event, so the rows themselves
      // refresh on their own via the next "prereqs_result" push.
      return;
    }
    if (event === "mod_repo_result") {
      modRepoDetection = data;
      renderModRepoSection();
      return;
    }
    if (event === "mod_repo_update_result") {
      modRepoCheckingUpdates = false;
      modRepoUpdateCheck = data;
      renderModRepoSection();
      return;
    }
    if (event === "mod_repo_op_status") {
      modRepoOpStatusText = data.text;
      renderModRepoSection();
      return;
    }
    if (event === "mod_repo_op_done") {
      modRepoCloneInProgress = false;
      modRepoUpdateInProgress = false;
      modRepoOpDoneMessage = data.message;
      renderModRepoSection();
      // Bridge already re-runs detect (and, for update, check-updates too)
      // right after this event -- the section refreshes itself via the
      // next mod_repo_result/mod_repo_update_result push.
      return;
    }
    if (!data || !data.profile_id) return;
    const id = data.profile_id;
    if (event === "launch_log") {
      // Always authoritative for "this profile is actively launching" --
      // not gated on an already-"launching" phase, since a bulk-launched
      // card never went through launchProfile()'s own client-side
      // pre-set (individual clicks do; this covers both paths the same
      // way). Log events for a given attempt are always pushed strictly
      // before that attempt's own launch_done, so this can't stomp a
      // later running/error state with stale text.
      launchState[id] = { phase: "launching", status: data.status };
      refreshCard(id);
    } else if (event === "launch_done") {
      launchState[id] = data.success
        ? { phase: "running", pid: data.pid }
        : { phase: "error", error: data.error || "Launch failed" };
      refreshCard(id);
      // Auto-expand on error (TODO.md's console spec, confirmed against the
      // approved mockup's own everError->consoleOpen behavior) -- a launch
      // failing is exactly the "something actually went wrong" moment the
      // panel should surface itself for, not wait for the user to notice.
      if (!data.success) openConsole();
    } else if (event === "launch_queued") {
      launchState[id] = { phase: "queued", status: data.status };
      refreshCard(id);
    }
  },
};

// ---------- Console/log panel (RELAY 021) ----------

function openConsole() {
  document.body.classList.add("console-open");
}

function toggleConsole() {
  document.body.classList.toggle("console-open");
}

function renderConsole() {
  const body = document.getElementById("console-body");
  const wasAtBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 12;
  body.innerHTML = "";
  for (const entry of consoleLines) {
    const row = document.createElement("div");
    row.className = "console-line" + (entry.category ? " " + entry.category : "") + (consoleSelected.has(entry.id) ? " selected" : "");
    row.innerHTML = `<span>${escapeHtml(entry.text)}</span>`;
    row.onclick = () => toggleConsoleLineSelection(entry.id);
    body.appendChild(row);
  }
  if (wasAtBottom) body.scrollTop = body.scrollHeight;

  document.getElementById("console-count").textContent = `${consoleLines.length} line${consoleLines.length === 1 ? "" : "s"}`;
  document.getElementById("console-latest").textContent =
    consoleLines.length > 0 ? consoleLines[consoleLines.length - 1].text : "No activity yet";
  updateConsoleSelectedText();
}

function toggleConsoleLineSelection(id) {
  if (consoleSelected.has(id)) consoleSelected.delete(id);
  else consoleSelected.add(id);
  renderConsole();
}

function updateConsoleSelectedText() {
  const el = document.getElementById("console-selected-text");
  const n = consoleSelected.size;
  el.textContent = n > 0 ? `${n} line${n === 1 ? "" : "s"} selected · click lines to toggle` : "Tip: click log lines to select, then Copy";
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    // Clipboard permission can be denied in some WebView2 configurations --
    // fail quietly rather than throwing into an onclick handler.
  }
}

function copyAllLog() {
  copyToClipboard(consoleLines.map((l) => l.text).join("\n"));
}

function copySelectedLog() {
  const selected = consoleLines.filter((l) => consoleSelected.has(l.id));
  if (selected.length === 0) return;
  copyToClipboard(selected.map((l) => l.text).join("\n"));
}

async function clearLog() {
  await window.pywebview.api.clear_console();
  consoleLines = [];
  consoleSelected = new Set();
  renderConsole();
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function toggleCheck(profileId) {
  if (checkedIds.has(profileId)) checkedIds.delete(profileId);
  else checkedIds.add(profileId);
  updateAddToTeamBtn();
  updateLaunchSelectedBtn();
  renderCards();
}

// RELAY 027: always visible (on any view it appears on), disabled rather
// than hidden when there's nothing to act on -- Chris's reversal of 020/023's
// hide-until-checked call ("the missing disabled buttons remove the feedback
// needed to prompt a user... steering them towards the profile checkbox").
function updateLaunchSelectedBtn() {
  const btn = document.getElementById("launch-selected-btn");
  btn.disabled = checkedIds.size === 0 || bulkLaunchActive;
  btn.textContent = `▶ Launch Selected${checkedIds.size > 0 ? ` (${checkedIds.size})` : ""}`;
}

function selectTeam(teamId) {
  activeTeamId = teamId;
  filterText = "";
  checkedIds = new Set();
  document.getElementById("filter-input").value = "";
  updateAddToTeamBtn();
  updateLaunchSelectedBtn();
  renderRail();
  renderHeader();
  renderCards();
}

function onFilterInput() {
  filterText = document.getElementById("filter-input").value;
  renderCards();
}

function renderAll() {
  renderRail();
  renderHeader();
  renderCards();
  updateLaunchSelectedBtn();
  updateFirstRunCues();
}

// RELAY 028: reactive first-run guidance, not a one-time flag -- re-evaluated
// on every renderAll() so the cue disappears the moment its condition stops
// being true (first profile/team created), same lifecycle as everything else
// in this function. Only one cue is ever active: Add Profile is the real
// first step for a brand-new user; Add Team only matters once a profile
// already exists. Settings deliberately gets no cue (two competing accented
// buttons would dilute which one is the actual recommended first step).
function updateFirstRunCues() {
  document.getElementById("add-profile-btn").classList.toggle("accent-cue", profiles.length === 0);
  document.getElementById("rail-add-team-btn").classList.toggle("accent-cue", profiles.length > 0 && teams.length === 0);
}

async function loadData() {
  const result = await window.pywebview.api.list_profiles();
  profiles = result.profiles || [];
  teams = result.teams || [];
  renderAll();
}

// ---------- Drawer (shared shell -- settings vs edit content) ----------

function openSettingsDrawer() {
  document.getElementById("settings-drawer-content").style.display = "flex";
  document.getElementById("edit-drawer-content").style.display = "none";
  document.body.classList.add("drawer-open");
  selectSettingsTab("theme");
}

// ---------- App Settings drawer tabs (RELAY 036) ----------
// Deliberately separate from selectEditTab/.edit-tab* despite the
// identical visual shape (see style.css's comment on the shared CSS
// rules) -- both functions use an unscoped querySelectorAll, so sharing
// the exact same classes would have one drawer's tab switch silently
// hide the other drawer's panels.

function selectSettingsTab(tab) {
  for (const btn of document.querySelectorAll(".settings-tab")) {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  }
  for (const panel of document.querySelectorAll(".settings-tab-panel")) {
    panel.style.display = panel.id === `settings-tab-${tab}` ? "flex" : "none";
  }
}

function closeDrawer() {
  document.body.classList.remove("drawer-open");
  editingProfileId = null;
}

// ---------- Themed confirm/prompt modal (RELAY 016) ----------
// Replaces native prompt()/confirm() -- one component covers both shapes:
// an input variant (New Team) and a message-only variant (Remove from
// Team/Remove Team/Delete). Promise-based so call sites keep the same
// early-return shape the native calls had (`const name = await
// openConfirmModal(...); if (!name) return;`).

function openConfirmModal({ title, message, warningLine, inputPlaceholder, confirmLabel = "Confirm", danger = false }) {
  const scrim = document.getElementById("confirm-scrim");
  const modal = document.getElementById("confirm-modal");
  const titleEl = document.getElementById("confirm-title");
  const messageEl = document.getElementById("confirm-message");
  const warningEl = document.getElementById("confirm-warning");
  const inputEl = document.getElementById("confirm-input");
  const confirmBtn = document.getElementById("confirm-btn");
  const cancelBtn = document.getElementById("confirm-cancel-btn");
  const hasInput = inputPlaceholder !== undefined;

  titleEl.textContent = title;
  messageEl.textContent = message || "";
  messageEl.style.display = message ? "block" : "none";
  // RELAY 032: optional quoted-verbatim warning line, own color, distinct
  // from the main message (e.g. the DirectX runtime install confirm).
  warningEl.textContent = warningLine || "";
  warningEl.style.display = warningLine ? "block" : "none";
  inputEl.style.display = hasInput ? "block" : "none";
  inputEl.value = "";
  inputEl.placeholder = inputPlaceholder || "";
  confirmBtn.textContent = confirmLabel;
  confirmBtn.className = danger ? "danger-btn" : "primary-btn";

  return new Promise((resolve) => {
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      document.body.classList.remove("confirm-open");
      scrim.onclick = null;
      confirmBtn.onclick = null;
      cancelBtn.onclick = null;
      document.removeEventListener("keydown", onKeydown);
      resolve(result);
    };
    const onKeydown = (e) => {
      if (e.key === "Escape") finish(hasInput ? null : false);
      else if (e.key === "Enter" && (!hasInput || document.activeElement === inputEl)) {
        finish(hasInput ? inputEl.value.trim() : true);
      }
    };

    scrim.onclick = () => finish(hasInput ? null : false);
    cancelBtn.onclick = () => finish(hasInput ? null : false);
    confirmBtn.onclick = () => finish(hasInput ? inputEl.value.trim() : true);
    document.addEventListener("keydown", onKeydown);

    document.body.classList.add("confirm-open");
    if (hasInput) setTimeout(() => inputEl.focus(), 0);
  });
}

// ---------- Settings / theme (RELAY 010) ----------

function renderPresetRow() {
  const row = document.getElementById("preset-row");
  row.innerHTML = "";
  for (const preset of THEME_PRESETS) {
    const el = document.createElement("div");
    const isActive = preset.accent === palette.accent && preset.bg === palette.bg;
    el.className = "preset-swatch" + (isActive ? " active" : "");
    el.title = preset.name;
    el.style.background = `linear-gradient(135deg, ${preset.accent} 0 50%, ${preset.surface} 50% 100%)`;
    el.onclick = () => {
      palette = { ...preset };
      applyTheme(palette);
      syncPaletteControls();
    };
    row.appendChild(el);
  }
}

function syncPaletteControls() {
  document.getElementById("pal-accent").value = palette.accent;
  document.getElementById("pal-bg").value = palette.bg;
  document.getElementById("pal-surface").value = palette.surface;
  document.getElementById("pal-text").value = palette.text;
  document.getElementById("pal-radius").value = palette.radius;
  document.getElementById("pal-radius-val").textContent = palette.radius + "px";
  document.getElementById("pal-font").value = palette.font;
  renderPresetRow();
}

function wirePaletteControls() {
  document.getElementById("pal-accent").oninput = (e) => {
    palette.accent = e.target.value;
    applyTheme(palette);
    renderPresetRow();
  };
  document.getElementById("pal-bg").oninput = (e) => {
    palette.bg = e.target.value;
    applyTheme(palette);
    renderPresetRow();
  };
  document.getElementById("pal-surface").oninput = (e) => {
    palette.surface = e.target.value;
    applyTheme(palette);
    renderPresetRow();
  };
  document.getElementById("pal-text").oninput = (e) => {
    palette.text = e.target.value;
    applyTheme(palette);
    renderPresetRow();
  };
  document.getElementById("pal-radius").oninput = (e) => {
    palette.radius = Number(e.target.value);
    document.getElementById("pal-radius-val").textContent = palette.radius + "px";
    applyTheme(palette);
  };
  document.getElementById("pal-font").onchange = (e) => {
    palette.font = e.target.value;
    applyTheme(palette);
  };
}

// ---------- App Settings, part 1 (RELAY 029) ----------
// The cheap settings_store-backed controls -- loaded eagerly at startup
// (same pattern as palette/profiles/console above) rather than lazily on
// drawer-open, so the drawer never shows a flash of stale/default values.

async function loadAppSettings() {
  const s = await window.pywebview.api.get_app_settings();
  document.getElementById("settings-multiclient").checked = !!s.multiclient_enabled;
  document.getElementById("settings-py4gw-injection").checked = !!s.py4gw_injection_enabled;
  document.getElementById("settings-gmod-injection").checked = !!s.gmod_injection_enabled;
  document.getElementById("settings-pacing").value = s.bulk_launch_pacing_seconds;
}

function wireAppSettingsControls() {
  document.getElementById("settings-multiclient").onchange = (e) => {
    window.pywebview.api.save_multiclient_enabled(e.target.checked);
  };
  document.getElementById("settings-py4gw-injection").onchange = (e) => {
    window.pywebview.api.save_py4gw_injection_enabled(e.target.checked);
  };
  document.getElementById("settings-gmod-injection").onchange = (e) => {
    window.pywebview.api.save_gmod_injection_enabled(e.target.checked);
  };
  // Deliberately no JS-side clamp on this field beyond the native min/max
  // attributes -- bulk_launch.clamp_pacing_seconds() already enforces the
  // real floor/ceiling at use time regardless of what's stored here.
  document.getElementById("settings-pacing").onchange = (e) => {
    window.pywebview.api.save_bulk_launch_pacing_seconds(Number(e.target.value));
  };
}

async function onReloadDataClick() {
  await loadData();
}

// ---------- Prerequisites (RELAY 032) ----------
// Ported from the old imgui app's PrereqState/_draw_prereq_row/
// _show_prereq_install_confirm_popup, onto push_event instead of that
// class's polling design (see bridge.py's check_prereqs/install_prereq).

const PREREQ_COMPONENTS = ["python", "vcredist_x86", "vcredist_x64", "directx_runtime"];
// Labels/URLs mirrored from launcher_core/prereqs.py's own real constants
// (PYTHON_DOWNLOAD_URL, VCREDIST_2013_X86_URL, VCREDIST_2013_X64_URL,
// DIRECTX_RUNTIME_DOWNLOAD_URL) -- JS can't import that module directly,
// so keep these in sync by hand if the Python side's URLs ever change.
const PREREQ_INFO = {
  python: { label: "Python 3.13.0 (32-bit)", url: "https://www.python.org/ftp/python/3.13.0/python-3.13.0.exe" },
  vcredist_x86: { label: "VC++ Redistributable (x86)", url: "https://aka.ms/highdpimfc2013x86enu" },
  vcredist_x64: { label: "VC++ Redistributable (x64)", url: "https://aka.ms/highdpimfc2013x64enu" },
  directx_runtime: {
    label: "DirectX End-User Runtime",
    url: "https://download.microsoft.com/download/8/4/a/84a35bf1-dafe-4ae8-82af-ad2ae20b6b14/directx_Jun2010_redist.exe",
  },
};
// Quoted verbatim from Microsoft's own download page (id=8109), same
// reasoning as any other quoted-source text in this app -- don't paraphrase.
const DIRECTX_RUNTIME_CANNOT_UNINSTALL_NOTICE = "The DirectX runtime cannot be uninstalled.";

function onCheckPrereqsClick() {
  for (const component of PREREQ_COMPONENTS) {
    const statusEl = document.getElementById(`prereq-status-${component}`);
    statusEl.textContent = "Checking...";
    statusEl.className = "prereq-status";
    document.getElementById(`prereq-install-${component}`).style.display = "none";
  }
  window.pywebview.api.check_prereqs();
}

function updatePrereqRow(component, result) {
  const statusEl = document.getElementById(`prereq-status-${component}`);
  const installBtn = document.getElementById(`prereq-install-${component}`);
  if (result.is_ok) {
    // RELAY 033: Python/DirectX's real diagnostic text ends "...detected
    // at <path>"/"...found at <path>" -- a real path has no spaces to
    // wrap on, so it ran off the drawer's edge instead of wrapping
    // (Chris, live). Break it onto its own line right before the path
    // (style.css's .prereq-status has white-space:pre-line to render
    // this \n as a real line break).
    statusEl.textContent = `OK -- ${result.diagnostic_text.replace(" at ", " at\n")}`;
    statusEl.className = "prereq-status ok";
    installBtn.style.display = "none";
  } else {
    statusEl.textContent = "NOT FOUND";
    statusEl.className = "prereq-status missing";
    installBtn.style.display = "inline-block";
  }
}

async function onPrereqInstallClick(component) {
  const info = PREREQ_INFO[component];
  const ok = await openConfirmModal({
    title: "Install prerequisite?",
    message: `This will download and run the installer for:\n${info.label}\n\n${info.url}`,
    warningLine: component === "directx_runtime" ? DIRECTX_RUNTIME_CANNOT_UNINSTALL_NOTICE : undefined,
    confirmLabel: "Install",
  });
  if (!ok) return;
  document.getElementById("prereq-install-" + component).style.display = "none";
  const res = await window.pywebview.api.install_prereq(component);
  if (!res || !res.ok) {
    const statusEl = document.getElementById(`prereq-status-${component}`);
    statusEl.textContent = (res && res.error) || "Could not start install";
    statusEl.className = "prereq-status missing";
  }
}

// ---------- Mod Repository (RELAY 033) ----------
// Ported from the old imgui app's ModRepoState/_show_mod_repo_section,
// branch-for-branch, onto push_event instead of that class's polling.

async function loadModRepoInfo() {
  const info = await window.pywebview.api.get_mod_repo_info();
  modRepoPath = info.path;
  modRepoUrl = info.url;
  document.getElementById("modrepo-path").value = modRepoPath;
}

function renderModRepoSection() {
  const area = document.getElementById("modrepo-status-area");

  if (modRepoDetection === null) {
    area.innerHTML = `<div class="prereq-status">Checking...</div>`;
    return;
  }

  let html = "";
  if (modRepoDetection.status === "not_found") {
    html += `<div class="prereq-status missing">No Py4GW_Reforged checkout found at this location.</div>`;
    if (modRepoCloneInProgress) {
      html += `<div class="prereq-status busy" style="margin-top:4px">${escapeHtml(modRepoOpStatusText)}</div>`;
    } else {
      html += `<button class="small-btn" style="margin-top:6px" onclick="onModRepoCloneClick()">Clone Py4GW_Reforged</button>`;
    }
  } else if (modRepoDetection.status === "not_a_git_repo") {
    html += `<div class="prereq-status missing">Found a folder here, but it isn't a git checkout -- can't check for updates.</div>`;
  } else {
    // ok
    html += `<div class="prereq-status-row">`;
    if (modRepoCheckingUpdates) {
      html += `<span class="prereq-status busy">Checking for updates...</span>`;
    } else {
      html += `<button class="small-btn" onclick="onModRepoCheckUpdatesClick()">Check for updates</button>`;
    }
    html += `<span class="prereq-status ok">Checkout found.</span>`;
    html += `</div>`;

    if (modRepoUpdateCheck !== null) {
      const check = modRepoUpdateCheck;
      if (check.status === "up_to_date") {
        html += `<div class="prereq-status ok" style="margin-top:4px">${escapeHtml(check.message)}</div>`;
      } else if (check.status === "behind") {
        html += `<div class="prereq-status-row" style="margin-top:4px">`;
        html += `<span class="prereq-status missing">${escapeHtml(check.message)}</span>`;
        if (modRepoUpdateInProgress) {
          html += `<span class="prereq-status busy">${escapeHtml(modRepoOpStatusText)}</span>`;
        } else {
          html += `<button class="small-btn" onclick="onModRepoUpdateClick()">Update now</button>`;
        }
        html += `</div>`;
      } else {
        // ahead or error -- informational only, no fast-forward possible/needed.
        html += `<div class="prereq-status" style="margin-top:4px">${escapeHtml(check.message)}</div>`;
      }
    }
  }

  if (modRepoOpDoneMessage && !modRepoCloneInProgress && !modRepoUpdateInProgress) {
    html += `<div class="prereq-status" style="margin-top:6px">${escapeHtml(modRepoOpDoneMessage)}</div>`;
  }

  area.innerHTML = html;
}

async function onBrowseModRepoFolderClick() {
  const chosen = await window.pywebview.api.browse_for_folder();
  if (!chosen) return;
  modRepoPath = chosen;
  document.getElementById("modrepo-path").value = chosen;
  // Any earlier update-check result was about the OLD location -- clear it
  // rather than leave it showing a stale answer for a path no longer in
  // effect, same reasoning ModRepoState.set_configured_path uses.
  modRepoDetection = null;
  modRepoUpdateCheck = null;
  renderModRepoSection();
  await window.pywebview.api.save_mod_repo_path(chosen);
}

async function onModRepoCheckUpdatesClick() {
  if (modRepoCheckingUpdates) return;
  modRepoCheckingUpdates = true;
  renderModRepoSection();
  await window.pywebview.api.check_mod_repo_updates();
}

async function onModRepoCloneClick() {
  const ok = await openConfirmModal({
    title: "Clone Py4GW_Reforged?",
    message: `This will clone the full Py4GW_Reforged repository from:\n${modRepoUrl}\n\ninto:\n${modRepoPath}\n\nThis is the full mod repository (roughly 600MB) and can take a minute or two depending on your connection.`,
    confirmLabel: "Clone",
  });
  if (!ok) return;
  modRepoCloneInProgress = true;
  modRepoOpStatusText = "Starting...";
  renderModRepoSection();
  const res = await window.pywebview.api.start_mod_repo_clone();
  if (!res || !res.ok) {
    modRepoCloneInProgress = false;
    modRepoOpDoneMessage = (res && res.error) || "Could not start clone";
    renderModRepoSection();
  }
}

async function onModRepoUpdateClick() {
  const behindText = modRepoUpdateCheck ? ` (${modRepoUpdateCheck.message})` : "";
  const ok = await openConfirmModal({
    title: "Update Py4GW_Reforged?",
    message:
      `This will fast-forward the checkout at:\n${modRepoPath}\nto the latest Py4GW_Reforged${behindText}.\n\n` +
      // Real behavior per update_mod_repo's own docstring (RELAY 033
      // verify-before-building read), not the old imgui app's slightly
      // broader popup wording ("refused... if the checkout has any
      // uncommitted changes") -- confirmed directly against dulwich's own
      // pull() that only a file the incoming update actually touches can
      // ever cause a refusal, so this says that precisely instead of
      // repeating the old app's looser claim.
      "Only ever fast-forwards -- refused automatically if the update would overwrite a file you've changed locally, so nothing local is silently discarded.",
    confirmLabel: "Update",
  });
  if (!ok) return;
  modRepoUpdateInProgress = true;
  modRepoOpStatusText = "Starting...";
  renderModRepoSection();
  const res = await window.pywebview.api.start_mod_repo_update();
  if (!res || !res.ok) {
    modRepoUpdateInProgress = false;
    modRepoOpDoneMessage = (res && res.error) || "Could not start update";
    renderModRepoSection();
  }
}

// ---------- Add/Edit profile (RELAY 011) ----------

function openEditDrawer(profileId) {
  editingProfileId = profileId;
  const p = profileId ? profiles.find((x) => x.id === profileId) : null;

  document.getElementById("edit-drawer-title").textContent = p ? "Edit Profile" : "Add Profile";
  document.getElementById("edit-name").value = p ? p.name || "" : "";
  document.getElementById("edit-email").value = p ? p.email || "" : "";
  document.getElementById("edit-password").value = "";
  document.getElementById("edit-path").value = p ? p.executable_path || "" : "";
  document.getElementById("edit-args").value = p ? p.launch_arguments || "" : "";
  document.getElementById("edit-py4gw").checked = p ? !!p.py4gw_enabled : false;
  document.getElementById("edit-gmod").checked = p ? !!p.gmod_enabled : false;
  document.getElementById("edit-autologin").checked = p ? !!p.auto_login_enabled : false;
  document.getElementById("edit-autoselect").checked = p ? !!p.auto_select_character_enabled : false;
  document.getElementById("edit-charname").value = p ? p.character_name || "" : "";

  // RELAY 024: Mods/Window tab fields.
  document.getElementById("edit-py4gw-dll-path").value = p ? p.py4gw_dll_path || "" : "";
  document.getElementById("edit-gmod-dll-path").value = p ? p.gmod_dll_path || "" : "";
  editPluginPaths = p ? [...(p.gmod_plugin_paths || [])] : [];
  renderPluginList();
  // GameProfile.windowed_mode_enabled defaults to True -- match that default
  // for a brand-new profile too, not false.
  document.getElementById("edit-windowed").checked = p ? !!p.windowed_mode_enabled : true;
  selectEditTab("general");

  // Delete button: hidden entirely for a brand-new (unsaved) profile -- there's
  // nothing to delete/remove yet. Label is context-aware per RELAY 011's spec:
  // viewing a specific team -> "Remove from Team" (profile survives elsewhere);
  // viewing ALL -> real "Delete" (removes the profile everywhere).
  const deleteBtn = document.getElementById("edit-delete-btn");
  if (!p) {
    deleteBtn.style.display = "none";
  } else {
    deleteBtn.style.display = "inline-block";
    deleteBtn.textContent = activeTeamId === "ALL" ? "Delete" : "Remove from Team";
  }

  document.getElementById("settings-drawer-content").style.display = "none";
  document.getElementById("edit-drawer-content").style.display = "flex";
  document.body.classList.add("drawer-open");
}

// ---------- Edit drawer tabs (RELAY 024) ----------

function selectEditTab(tab) {
  for (const btn of document.querySelectorAll(".edit-tab")) {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  }
  for (const panel of document.querySelectorAll(".edit-tab-panel")) {
    panel.style.display = panel.id === `edit-tab-${tab}` ? "flex" : "none";
  }
}

// ---------- Mods tab: DLL path browse + gMod plugin list (RELAY 024) ----------

async function onBrowsePathClick(inputId, typeLabel, pattern) {
  const chosen = await window.pywebview.api.browse_for_file(typeLabel, pattern);
  if (chosen) document.getElementById(inputId).value = chosen;
}

function renderPluginList() {
  const list = document.getElementById("gmod-plugin-list");
  if (editPluginPaths.length === 0) {
    list.innerHTML = `<div class="plugin-list-empty">No plugins added</div>`;
    return;
  }
  list.innerHTML = "";
  editPluginPaths.forEach((path, i) => {
    // Basename, no extension -- matches GWxLauncher's own
    // Path.GetFileNameWithoutExtension(path) display (same convention
    // launcher.py's own Mods tab uses); full path is the hover tooltip.
    const parts = path.split(/[\\/]/).filter(Boolean);
    const base = parts.length ? parts[parts.length - 1] : path;
    const nameNoExt = base.replace(/\.[^.]+$/, "");
    const row = document.createElement("div");
    row.className = "plugin-row";
    row.title = path;
    row.innerHTML = `
      <span class="plugin-name">${escapeHtml(nameNoExt)}</span>
      <button class="plugin-remove" title="Remove">&#10005;</button>
    `;
    row.querySelector(".plugin-remove").onclick = () => onRemovePlugin(i);
    list.appendChild(row);
  });
}

function onRemovePlugin(index) {
  editPluginPaths.splice(index, 1);
  renderPluginList();
}

async function onAddPluginClick() {
  const chosen = await window.pywebview.api.browse_for_file("TPF files", "*.tpf");
  if (chosen && !editPluginPaths.includes(chosen)) {
    editPluginPaths.push(chosen);
    renderPluginList();
  }
}

async function onSaveProfileClick() {
  const data = {
    id: editingProfileId || undefined,
    name: document.getElementById("edit-name").value.trim(),
    email: document.getElementById("edit-email").value.trim(),
    executable_path: document.getElementById("edit-path").value.trim(),
    launch_arguments: document.getElementById("edit-args").value.trim(),
    py4gw_enabled: document.getElementById("edit-py4gw").checked,
    gmod_enabled: document.getElementById("edit-gmod").checked,
    auto_login_enabled: document.getElementById("edit-autologin").checked,
    auto_select_character_enabled: document.getElementById("edit-autoselect").checked,
    character_name: document.getElementById("edit-charname").value.trim(),
    py4gw_dll_path: document.getElementById("edit-py4gw-dll-path").value.trim(),
    gmod_dll_path: document.getElementById("edit-gmod-dll-path").value.trim(),
    gmod_plugin_paths: editPluginPaths.slice(),
    windowed_mode_enabled: document.getElementById("edit-windowed").checked,
  };
  const newPassword = document.getElementById("edit-password").value;
  if (newPassword) data.new_password = newPassword;

  // New profile scoped to whatever's currently being viewed -- "the + you
  // clicked is scoped to what you're looking at" (RELAY 011's spec).
  if (!editingProfileId) {
    data.team_ids = activeTeamId === "ALL" ? [] : [activeTeamId];
  }

  await window.pywebview.api.save_profile(data);
  closeDrawer();
  await loadData();
}

async function onEditDeleteClick() {
  if (!editingProfileId) return;
  const p = profiles.find((x) => x.id === editingProfileId);
  const name = p ? p.name : "this profile";

  if (activeTeamId === "ALL") {
    const ok = await openConfirmModal({
      title: "Delete profile",
      message: `Permanently delete "${name}"? This removes it from every team.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    await window.pywebview.api.delete_profile(editingProfileId);
  } else {
    const tn = teamName(activeTeamId);
    const ok = await openConfirmModal({
      title: "Remove from team",
      message: `Remove "${name}" from "${tn}"? The profile stays in ALL and any other teams.`,
      confirmLabel: "Remove",
    });
    if (!ok) return;
    await window.pywebview.api.remove_profile_from_team(editingProfileId, activeTeamId);
  }
  closeDrawer();
  await loadData();
}

// ---------- Add to Team (bulk, RELAY 011) ----------

function onAddToTeamClick() {
  const existing = document.getElementById("add-to-team-menu");
  if (existing) {
    existing.remove();
    return;
  }
  if (teams.length === 0) {
    alert("No teams exist yet -- create one with the rail's + button first.");
    return;
  }
  const btn = document.getElementById("add-to-team-btn");
  const menu = document.createElement("div");
  menu.id = "add-to-team-menu";
  menu.style.cssText =
    "position:absolute;z-index:70;background:var(--surface,#14162b);border:1px solid var(--border,#2a2f55);" +
    "border-radius:10px;box-shadow:0 16px 42px rgba(0,0,0,.45);padding:6px;min-width:180px;";
  const rect = btn.getBoundingClientRect();
  menu.style.top = rect.bottom + 6 + "px";
  menu.style.left = rect.left + "px";

  for (const t of teams) {
    const row = document.createElement("div");
    row.textContent = t.name;
    row.style.cssText = "padding:8px 10px;border-radius:7px;cursor:pointer;font-size:12.5px;font-weight:600;";
    row.onmouseenter = () => (row.style.background = "var(--panel2, #1f2340)");
    row.onmouseleave = () => (row.style.background = "");
    row.onclick = async () => {
      await window.pywebview.api.add_profiles_to_team(Array.from(checkedIds), t.id);
      menu.remove();
      checkedIds = new Set();
      updateAddToTeamBtn();
      await loadData();
    };
    menu.appendChild(row);
  }
  document.body.appendChild(menu);

  const closeOnOutsideClick = (e) => {
    if (!menu.contains(e.target) && e.target !== btn) {
      menu.remove();
      document.removeEventListener("mousedown", closeOnOutsideClick);
    }
  };
  setTimeout(() => document.addEventListener("mousedown", closeOnOutsideClick), 0);
}

// ---------- Teams (new / remove, RELAY 011) ----------

async function onNewTeamClick() {
  const name = await openConfirmModal({
    title: "New team",
    inputPlaceholder: "Team name",
    confirmLabel: "Create",
  });
  if (!name) return;
  const newTeam = await window.pywebview.api.add_team(name);
  await loadData();
  selectTeam(newTeam.id);
}

async function onRemoveTeamClick() {
  if (activeTeamId === "ALL") return;
  const tn = teamName(activeTeamId);
  const ok = await openConfirmModal({
    title: "Remove team",
    message: `Remove team "${tn}"? Profiles are kept -- they just lose membership in this team.`,
    confirmLabel: "Remove",
  });
  if (!ok) return;
  await window.pywebview.api.remove_team(activeTeamId);
  selectTeam("ALL");
  await loadData();
}

// ---------- Window controls (carried over from Phase A) ----------
// Resize is handled entirely by Windows' native WS_THICKFRAME border (no JS
// resize zones -- see index.html). This supersedes RELAY 018's stopPropagation
// patch on the old startResize(): with the resize-zone divs gone there's no
// zone-click left to race pywebview's move-tracking, so that fix is moot here.

// Title-bar drag + hand-rolled Aero Snap (dev_notes/AERO_SNAP_INVESTIGATION.md).
// We move the window ourselves (easy_drag=False) so only the title bar drags it
// and there's no WS_THICKFRAME-border jump -- see bridge.on_drag_start/drag_tick.
// on_drag_start latches the cursor offset; each mousemove asks Python to move
// the window to follow (Python reads the real cursor, so no coords cross the
// bridge); mouseup runs the snap. Listeners are added on mousedown and removed
// on mouseup so a plain click elsewhere never moves the window.
(function () {
  let dragging = false;
  function onMove() {
    if (dragging) window.pywebview.api.drag_tick();
  }
  function onUp() {
    if (!dragging) return;
    dragging = false;
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
    window.pywebview.api.on_drag_end();
  }
  document.getElementById("titlebar").addEventListener("mousedown", (e) => {
    if (e.button !== 0) return; // left button only
    if (e.target.closest("button")) return; // let the window-control buttons through
    dragging = true;
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    window.pywebview.api.on_drag_start();
  });
})();

document.addEventListener("keydown", (e) => {
  // confirm-open is deliberately excluded here -- the confirm modal can open
  // on top of the drawer (Delete lives in the edit drawer's footer), and its
  // own keydown listener (openConfirmModal) already handles Escape for
  // itself. Without this guard, Escape while the modal is open would close
  // both layers in one press instead of just the topmost one.
  if (e.key === "Escape" && document.body.classList.contains("drawer-open") && !document.body.classList.contains("confirm-open")) {
    closeDrawer();
  }
});

window.addEventListener("pywebviewready", () => {
  applyTheme(palette);
  syncPaletteControls();
  wirePaletteControls();
  loadData();
  loadConsoleHistory();
  loadAppSettings();
  wireAppSettingsControls();
  // RELAY 032: checked once automatically at startup, same as the old
  // imgui app's PREREQS.run_check_async() at module load -- not gated
  // behind opening the Settings drawer, so results are usually already
  // there by the time someone looks.
  window.pywebview.api.check_prereqs();
  // RELAY 033: same eager-detect pattern -- MOD_REPO_STATE.run_detect_async()
  // also fires at the old app's module load, not gated behind the drawer.
  // check_mod_repo_updates() is deliberately NOT called here (real network
  // fetch, only ever on the explicit button click).
  loadModRepoInfo().then(() => window.pywebview.api.check_mod_repo());
});

async function loadConsoleHistory() {
  // The console itself never survives a full app restart (bridge.py's
  // store is in-memory only, matching launcher.py's own console_lines --
  // never persisted to disk), but this still guards against showing a
  // stale-looking empty panel if the page itself ever reloads while the
  // same Python process keeps running.
  // RELAY 030: each entry is now {line, category} (bridge.py classifies
  // once, at write time), not a bare string -- so history reload shows
  // the same coloring a live push would have, not a re-guessed one.
  const lines = await window.pywebview.api.get_console_lines();
  consoleLines = (lines || []).map((entry) => ({ id: consoleNextId++, text: entry.line, category: entry.category }));
  renderConsole();
}
