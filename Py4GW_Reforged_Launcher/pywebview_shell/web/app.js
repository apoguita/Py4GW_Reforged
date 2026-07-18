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
// RELAY 041: the profile whose real game window currently owns OS focus,
// or null if nothing tracked does (this app's own window included --
// deliberately not special-cased, see bridge.py's _run_focus_poll).
// Genuinely separate from checkedIds -- that means "checked for a bulk
// action," this means "this card's window is the one you're looking at
// right now." Reusing one mechanism for both would corrupt whichever
// wasn't the most recent click.
let focusedProfileId = null;
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
  document.getElementById("team-rename-btn").style.display = activeTeamId === "ALL" ? "none" : "grid";
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
    card.className = "card" + (checkedIds.has(p.id) ? " selected" : "") + (p.id === focusedProfileId ? " card-focused" : "");
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
    // RELAY 041, direction 1: the card <div> itself has no click handler
    // of its own before this -- only its children do, each already
    // stopping propagation, so this only fires on a genuine click
    // elsewhere on the card (avatar, name, badges, empty space).
    card.onclick = () => onCardClick(p.id);
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
  } else if (st.phase === "error-running") {
    // RELAY 040: a real, orphaned, still-alive Gw.exe from a failed
    // injection (bridge.py's _run_launch confirmed this via a real
    // psutil liveness check, not a guess) -- error text stays visible
    // (same rendering as plain "error" below) AND Stop actually reaches
    // the orphaned process, since bridge.py tracked its pid. Deliberately
    // NOT "Launch" here -- that would spawn a second, duplicate process
    // for the same account instead of doing anything to the first one.
    card.classList.add("state-error");
    sub.textContent = st.error || "Launch failed";
    sub.title = st.error || "";
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

// ---------- Two-way card <-> game-window focus sync (RELAY 041) ----------

// Targeted DOM update, not a full renderCards() -- this can fire every
// ~500ms from the background poll (direction 2), and re-rendering the
// whole grid on a tick where nothing the user asked for changed would be
// real, unnecessary churn (a re-render mid-drag/scroll/edit would also be
// actively disruptive, unlike a plain class toggle).
function setFocusedProfile(profileId) {
  if (focusedProfileId === profileId) return;
  if (focusedProfileId !== null) {
    const prev = document.querySelector('[data-card="' + focusedProfileId + '"]');
    if (prev) prev.classList.remove("card-focused");
  }
  focusedProfileId = profileId;
  if (focusedProfileId !== null) {
    const next = document.querySelector('[data-card="' + focusedProfileId + '"]');
    if (next) next.classList.add("card-focused");
  }
}

async function onCardClick(id) {
  const res = await window.pywebview.api.focus_profile_window(id);
  // Optimistic -- don't make a deliberate click wait up to ~500ms for the
  // background poll's own next tick to confirm what just happened.
  // bridge.py's own poll will independently re-confirm (or correct, if
  // Windows refused the foreground request) this on its next tick either
  // way, via the same setFocusedProfile call the push handler below uses.
  if (res && res.ok) setFocusedProfile(id);
}

// ---------- Launch-time prerequisite gate (RELAY 037) ----------
// Ported from launcher.py's _try_launch_with_prereq_gate exactly, not
// reinvented -- a real, already-proven design (see that function's own
// docstring): never a hard block. Gates ONLY when all three hold: this
// specific launch actually uses Py4GW injection (computed per-launch, not
// app-wide -- a GW1-only profile/team has nothing to check), the prereq
// check has definitively finished AND found something missing (still-
// checking, i.e. cachedPrereqsResult still null, never blocks), and the
// user hasn't already clicked "Launch anyway" earlier this session
// (session-scoped -- resets every app restart, on purpose, matching the
// old app; NOT settings_store-backed).

let cachedPrereqsResult = null; // last real "prereqs_result" push, or null before the first one arrives
let prereqLaunchAcknowledged = false;

function missingPrereqNames() {
  if (!cachedPrereqsResult) return null; // still checking -- never gate on this
  const names = [];
  for (const component of PREREQ_COMPONENTS) {
    const result = cachedPrereqsResult[component];
    if (!result || !result.is_ok) names.push(PREREQ_INFO[component].label);
  }
  return names;
}

async function tryLaunchWithPrereqGate(launchAction, needsPy4gw) {
  const missing = needsPy4gw ? missingPrereqNames() : [];
  if (!missing || missing.length === 0 || prereqLaunchAcknowledged) {
    launchAction();
    return;
  }
  const count = missing.length;
  // Real copy, quoted verbatim from _try_launch_with_prereq_gate's own
  // popup (_show_prereq_launch_confirm_popup) -- don't paraphrase.
  const result = await openConfirmModal({
    title: "Prerequisites missing",
    message: `Py4GW injection needs ${count} prerequisite${count !== 1 ? "s" : ""} that aren't installed yet:\n${missing.join(", ")}`,
    confirmLabel: "Launch anyway",
    secondaryLabel: "Open App Settings",
  });
  if (result === "secondary") {
    document.getElementById("settings-drawer-content").style.display = "flex";
    document.getElementById("edit-drawer-content").style.display = "none";
    document.body.classList.add("drawer-open");
    selectSettingsTab("setup"); // where Prerequisites actually lives (RELAY 036)
    return;
  }
  if (result === true) {
    prereqLaunchAcknowledged = true;
    launchAction();
  }
}

async function launchProfile(id) {
  const p = profiles.find((x) => x.id === id);
  tryLaunchWithPrereqGate(() => reallyLaunchProfile(id), !!(p && p.py4gw_enabled));
}

async function reallyLaunchProfile(id) {
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
  const needsPy4gw = ids.some((id) => {
    const p = profiles.find((x) => x.id === id);
    return !!(p && p.py4gw_enabled);
  });
  await tryLaunchWithPrereqGate(async () => {
    checkedIds = new Set();
    updateAddToTeamBtn();
    const res = await window.pywebview.api.launch_profiles_bulk(ids);
    if (res && res.ok) setBulkLaunchActive(true);
    renderCards();
  }, needsPy4gw);
}

async function onLaunchTeamClick() {
  if (activeTeamId === "ALL" || bulkLaunchActive) return;
  const members = membersOfActiveTeam();
  const ids = members.map((p) => p.id);
  if (ids.length === 0) return;
  const needsPy4gw = members.some((p) => p.py4gw_enabled);
  await tryLaunchWithPrereqGate(async () => {
    const res = await window.pywebview.api.launch_profiles_bulk(ids);
    if (res && res.ok) setBulkLaunchActive(true);
  }, needsPy4gw);
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
      // RELAY 037: cached for the launch-time gate (tryLaunchWithPrereqGate)
      // -- a fresh check_prereqs() call at click time would be slower and
      // pointless (032 already checks automatically at startup and pushes
      // here whenever a real check finishes, install included).
      cachedPrereqsResult = data;
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
    if (event === "run_as_admin_relaunching") {
      // A real elevated copy just started (bridge.save_run_as_admin_enabled's
      // background worker) -- this (non-elevated) instance's job is done.
      // Same close path as the titlebar's own close button, not a teardown
      // special-cased for this event.
      window.pywebview.api.close_clicked();
      return;
    }
    if (event === "run_as_admin_relaunch_failed") {
      openConfirmModal({ title: "Elevation failed", message: data.error, confirmLabel: "OK" });
      return;
    }
    if (event === "focused_profile_changed") {
      // data.profile_id is legitimately null here (nothing tracked is
      // OS-focused) -- placed before the `!data.profile_id` guard below
      // for exactly that reason; every other event past this point
      // requires a real profile_id.
      setFocusedProfile(data.profile_id);
      return;
    }
    if (event === "profile_exited") {
      // RELAY 042: a client closed OUTSIDE the app (its own Exit, closing
      // the window directly) -- bridge.py's focus-poll loop already
      // confirmed via a real liveness check the pid is actually gone, not
      // a guess. Reuses stopProfile's own success-path shape exactly
      // (same state transition, just triggered externally instead of by a
      // click), not a second, parallel way to revert a card to idle.
      delete launchState[data.profile_id];
      refreshCard(data.profile_id);
      return;
    }
    if (event === "launcher_update_result") {
      // No profile_id -- placed before the guard below for exactly that
      // reason, same as focused_profile_changed/run_as_admin_relaunch_failed.
      renderLauncherUpdateResult(data);
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
      // RELAY 040: still_running (real, from bridge.py's own psutil
      // liveness check) means the launch failed but the game process is
      // genuinely still alive and orphaned -- error-running gets a
      // working Stop instead of Launch (applyCardLaunchVisual), so
      // clicking the only available action doesn't spawn a duplicate
      // process for the same account.
      launchState[id] = data.success
        ? { phase: "running", pid: data.pid }
        : data.still_running
        ? { phase: "error-running", error: data.error || "Launch failed", pid: data.pid }
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

function openConfirmModal({ title, message, warningLine, inputPlaceholder, inputValue, confirmLabel = "Confirm", secondaryLabel, danger = false }) {
  const scrim = document.getElementById("confirm-scrim");
  const modal = document.getElementById("confirm-modal");
  const titleEl = document.getElementById("confirm-title");
  const messageEl = document.getElementById("confirm-message");
  const warningEl = document.getElementById("confirm-warning");
  const inputEl = document.getElementById("confirm-input");
  const confirmBtn = document.getElementById("confirm-btn");
  const cancelBtn = document.getElementById("confirm-cancel-btn");
  const secondaryBtn = document.getElementById("confirm-secondary-btn");
  const hasInput = inputPlaceholder !== undefined;
  const hasSecondary = secondaryLabel !== undefined;

  titleEl.textContent = title;
  messageEl.textContent = message || "";
  messageEl.style.display = message ? "block" : "none";
  // RELAY 032: optional quoted-verbatim warning line, own color, distinct
  // from the main message (e.g. the DirectX runtime install confirm).
  warningEl.textContent = warningLine || "";
  warningEl.style.display = warningLine ? "block" : "none";
  inputEl.style.display = hasInput ? "block" : "none";
  // RELAY 057: rename team pre-fills the current name (edit, not create-
  // from-blank) -- every prior caller left inputValue unset, so this
  // defaults to the same "" every other input-modal caller already gets.
  inputEl.value = inputValue || "";
  inputEl.placeholder = inputPlaceholder || "";
  confirmBtn.textContent = confirmLabel;
  confirmBtn.className = danger ? "danger-btn" : "primary-btn";
  // RELAY 037: optional third action (e.g. the prereq launch gate's real
  // "Open App Settings" button) -- resolves the promise with the string
  // "secondary", distinct from true (confirm)/false or null (cancel), so a
  // caller can tell all three outcomes apart. Every other call site leaves
  // secondaryLabel unset and never sees this value.
  secondaryBtn.textContent = secondaryLabel || "";
  secondaryBtn.style.display = hasSecondary ? "inline-block" : "none";

  return new Promise((resolve) => {
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      document.body.classList.remove("confirm-open");
      scrim.onclick = null;
      confirmBtn.onclick = null;
      cancelBtn.onclick = null;
      secondaryBtn.onclick = null;
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
    secondaryBtn.onclick = () => finish("secondary");
    document.addEventListener("keydown", onKeydown);

    document.body.classList.add("confirm-open");
    if (hasInput) setTimeout(() => inputEl.select(), 0);
  });
}

// ---------- Import result modal (RELAY 034) ----------
// A genuinely different shape from openConfirmModal above -- informational,
// "Close"-only, variable-length content -- so it's its own small function
// rather than stretching openConfirmModal's yes/no semantics to also cover
// this. One shared renderer backs both Restore's and Old Launcher Import's
// result display (ported from the old imgui app's _render_import_result_
// body real copy, line for line).

function showImportResultModal(result) {
  const body = document.getElementById("result-body");
  let html = `<div class="line">Profiles: ${result.added_profiles} added, ${result.skipped_profiles} already present.</div>`;
  html += `<div class="line">Teams: ${result.added_teams} added, ${result.skipped_teams} already present.</div>`;
  if (result.warnings && result.warnings.length > 0) {
    html += `<div class="line warning">Some old-launcher settings weren't carried over:</div>`;
    for (const w of result.warnings) html += `<div class="line muted">${escapeHtml(w)}</div>`;
  }
  if (result.path_warnings && result.path_warnings.length > 0) {
    html += `<div class="line warning">Some imported paths don't exist on this machine:</div>`;
    for (const w of result.path_warnings) html += `<div class="line muted">${escapeHtml(w)}</div>`;
    html += `<div class="line muted">Fix these in each profile's Settings on this machine.</div>`;
  }
  body.innerHTML = html;
  document.getElementById("result-title").textContent = "Import Result";
  document.body.classList.add("result-open");
}

function closeResultModal() {
  document.body.classList.remove("result-open");
}

document.getElementById("result-close-btn").onclick = closeResultModal;
document.getElementById("result-scrim").onclick = closeResultModal;

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
      schedulePaletteSave();
    };
    row.appendChild(el);
  }
}

// RELAY 038: every swatch/hex-field pair this drawer edits, field name ->
// {swatch element id, hex-text element id}. Iterated by syncPaletteControls/
// wirePaletteControls instead of 7 near-identical blocks each -- accent/bg/
// surface/text plus (new this entry) good/warn/bad, the exact fields
// theme.js's buildTheme already applies as real --good/--warn/--bad CSS vars
// (RELAY 030's console coloring, card running/error states) but that had no
// direct-edit UI before this.
const PALETTE_FIELDS = {
  accent: { swatch: "pal-accent", hex: "pal-accent-hex" },
  bg: { swatch: "pal-bg", hex: "pal-bg-hex" },
  surface: { swatch: "pal-surface", hex: "pal-surface-hex" },
  text: { swatch: "pal-text", hex: "pal-text-hex" },
  good: { swatch: "pal-good", hex: "pal-good-hex" },
  warn: { swatch: "pal-warn", hex: "pal-warn-hex" },
  bad: { swatch: "pal-bad", hex: "pal-bad-hex" },
};
const HEX_COLOR_RE = /^#[0-9a-fA-F]{6}$/;

function syncPaletteControls() {
  for (const [field, ids] of Object.entries(PALETTE_FIELDS)) {
    document.getElementById(ids.swatch).value = palette[field];
    const hexEl = document.getElementById(ids.hex);
    hexEl.value = palette[field];
    hexEl.classList.remove("invalid");
  }
  document.getElementById("pal-radius").value = palette.radius;
  document.getElementById("pal-radius-val").textContent = palette.radius + "px";
  document.getElementById("pal-font").value = palette.font;
  renderPresetRow();
}

// Debounced (RELAY 038): a dragged native color-picker swatch fires oninput
// once per drag frame, and this same helper backs every palette mutation
// (preset click, reset, hex onchange, radius drag, font select too) for one
// consistent save path rather than special-casing which ones need it --
// writing to disk on every frame would be real, pointless I/O for a purely
// visual live-preview value.
let paletteSaveTimeout = null;
function schedulePaletteSave() {
  if (paletteSaveTimeout) clearTimeout(paletteSaveTimeout);
  paletteSaveTimeout = setTimeout(() => {
    window.pywebview.api.save_custom_palette(palette);
  }, 400);
}

async function loadPalette() {
  const saved = await window.pywebview.api.get_custom_palette();
  if (saved) {
    palette = { ...THEME_PRESETS[0], ...saved };
    applyTheme(palette);
    syncPaletteControls();
  }
}

function wirePaletteControls() {
  for (const [field, ids] of Object.entries(PALETTE_FIELDS)) {
    document.getElementById(ids.swatch).oninput = (e) => {
      palette[field] = e.target.value;
      document.getElementById(ids.hex).value = e.target.value;
      document.getElementById(ids.hex).classList.remove("invalid");
      applyTheme(palette);
      renderPresetRow();
      schedulePaletteSave();
    };
    // onchange (fires on blur/Enter), not oninput -- don't apply a
    // half-typed hex value on every keystroke, same reasoning as any other
    // free-text input elsewhere in this app that feeds something visual.
    document.getElementById(ids.hex).onchange = (e) => {
      const value = e.target.value.trim();
      if (!HEX_COLOR_RE.test(value)) {
        e.target.classList.add("invalid");
        e.target.value = palette[field]; // revert to the last real value
        return;
      }
      e.target.classList.remove("invalid");
      palette[field] = value;
      document.getElementById(ids.swatch).value = value;
      applyTheme(palette);
      renderPresetRow();
      schedulePaletteSave();
    };
  }
  document.getElementById("pal-radius").oninput = (e) => {
    palette.radius = Number(e.target.value);
    document.getElementById("pal-radius-val").textContent = palette.radius + "px";
    applyTheme(palette);
    schedulePaletteSave();
  };
  document.getElementById("pal-font").onchange = (e) => {
    palette.font = e.target.value;
    applyTheme(palette);
    schedulePaletteSave();
  };
}

function onResetThemeClick() {
  // Functionally identical to clicking the first preset swatch -- reuses
  // the exact same sequence renderPresetRow's own onclick already proves,
  // not a second code path for the same effect.
  palette = { ...THEME_PRESETS[0] };
  applyTheme(palette);
  syncPaletteControls();
  schedulePaletteSave();
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

// ---------- Run as administrator (RELAY 035) ----------

const adminState = { enabled: false, elevated: false };

function renderRunAsAdminUI() {
  document.getElementById("admin-badge").style.display = adminState.elevated ? "inline-block" : "none";
  document.getElementById("settings-run-as-admin").checked = adminState.enabled;
  const statusEl = document.getElementById("run-as-admin-status");
  let text = "";
  if (adminState.elevated) {
    text = "Currently running as Administrator.";
    if (!adminState.enabled) text += " Turning this off takes effect next restart.";
  } else if (adminState.enabled) {
    text = "Will run elevated the next time the launcher starts.";
  }
  statusEl.textContent = text;
  statusEl.style.display = text ? "block" : "none";
}

async function loadRunAsAdminState() {
  const s = await window.pywebview.api.get_run_as_admin_state();
  adminState.enabled = !!s.enabled;
  adminState.elevated = !!s.elevated;
  renderRunAsAdminUI();
}

function wireRunAsAdminControl() {
  document.getElementById("settings-run-as-admin").onchange = async (e) => {
    const checked = e.target.checked;
    const res = await window.pywebview.api.save_run_as_admin_enabled(checked);
    adminState.enabled = checked;
    if (res && res.elevated !== undefined) adminState.elevated = res.elevated;
    renderRunAsAdminUI();
  };
}

// ---------- Launcher self-update check (RELAY 048) ----------
// Ported from the old imgui app's real UpdateCheckState + App Settings
// render block, onto push_event instead of that class's per-frame polling
// (this app has no render loop to poll from) -- same real copy/behavior:
// silent on a failed check (no internet, GitHub down, rate-limited --
// never shown as an error), auto-checked once at startup in addition to
// the explicit button click.

function setLauncherUpdateChecking(checking) {
  document.getElementById("launcher-update-check-btn").style.display = checking ? "none" : "inline-block";
  const statusEl = document.getElementById("launcher-update-status");
  if (checking) {
    statusEl.style.display = "inline";
    statusEl.className = "prereq-status busy";
    statusEl.textContent = "Checking for updates...";
  }
}

async function loadLauncherVersion() {
  const v = await window.pywebview.api.get_launcher_version();
  document.getElementById("launcher-version-text").textContent = v;
}

function onLauncherUpdateCheckClick() {
  setLauncherUpdateChecking(true);
  window.pywebview.api.check_launcher_update();
}

function onViewReleasesClick(e) {
  e.preventDefault();
  window.pywebview.api.open_releases_page();
}

function renderLauncherUpdateResult(data) {
  setLauncherUpdateChecking(false);
  const statusEl = document.getElementById("launcher-update-status");
  // ok is false (no internet, GitHub down, rate-limited, unexpected
  // response shape) or never-checked-yet: show nothing at all, matching
  // the old app's own real behavior exactly -- this is an informational
  // notice, not something worth surfacing as an error.
  if (!data || !data.ok) {
    statusEl.style.display = "none";
    return;
  }
  statusEl.style.display = "inline";
  if (data.is_newer) {
    statusEl.className = "prereq-status missing";
    statusEl.innerHTML = `A newer version is available: ${escapeHtml(data.latest_tag)} <a href="#" onclick="onViewReleasesClick(event)" style="color:inherit;text-decoration:underline">View releases</a>`;
  } else {
    statusEl.className = "prereq-status ok";
    statusEl.textContent = "You're up to date.";
  }
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

// ---------- Backup/Restore accounts + Old Launcher Import (RELAY 034) ----------
// Ported from the old imgui app's _show_export_import_section, real copy
// reused verbatim (both confirm-popup warning strings, quoted not
// paraphrased -- what they're warning about is a real plaintext secret).

async function onBackupAccountsClick() {
  const includePasswords = document.getElementById("roster-include-passwords").checked;
  const ok = await openConfirmModal({
    title: "Back up accounts?",
    message: includePasswords
      ? "This file will contain your saved account passwords in plain text.\n\nStore it securely and delete it once you're done restoring it elsewhere."
      : "Back up your profiles and teams to a file.\n\nPasswords are not included -- restored profiles will need their passwords re-entered.",
    confirmLabel: "Choose file and back up…",
  });
  if (!ok) return;
  // Real Save-As only runs after the warning is confirmed -- mirrors the
  // old app's own deferred-browse shape (_export_browse_pending), just
  // expressed as sequential awaits instead of a next-frame flag.
  const chosen = await window.pywebview.api.browse_for_save_file("py4gw_reforged_roster.json", "JSON files", "*.json");
  if (!chosen) return;
  const res = await window.pywebview.api.export_roster(chosen, includePasswords);
  const statusEl = document.getElementById("roster-status-message");
  statusEl.style.display = "block";
  statusEl.textContent = res.ok ? `Backed up to ${chosen}` : `Backup failed: ${res.error}`;
}

async function onRestoreAccountsClick() {
  const chosen = await window.pywebview.api.browse_for_file("JSON files", "*.json");
  if (!chosen) return;
  const res = await window.pywebview.api.import_roster(chosen);
  document.getElementById("roster-status-message").style.display = "none";
  if (res.ok) {
    showImportResultModal(res.result);
    await loadData(); // newly-added profiles/teams should show up immediately
  } else {
    await openConfirmModal({ title: "Import failed", message: res.error, confirmLabel: "OK" });
  }
}

async function onLegacyImportClick() {
  const chosen = await window.pywebview.api.browse_for_file("JSON files", "*.json");
  if (!chosen) return;
  const res = await window.pywebview.api.import_legacy_accounts(chosen);
  document.getElementById("roster-status-message").style.display = "none";
  if (res.ok) {
    showImportResultModal(res.result);
    await loadData();
  } else {
    await openConfirmModal({ title: "Import failed", message: res.error, confirmLabel: "OK" });
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
  document.getElementById("edit-script-path").value = p ? p.script_path || "" : "";
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
    script_path: document.getElementById("edit-script-path").value.trim(),
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

async function onRenameTeamClick() {
  if (activeTeamId === "ALL") return;
  const currentName = teamName(activeTeamId);
  const newName = await openConfirmModal({
    title: "Rename team",
    inputPlaceholder: "Team name",
    inputValue: currentName,
    confirmLabel: "Save",
  });
  if (!newName || newName === currentName) return;
  await window.pywebview.api.rename_team(activeTeamId, newName);
  await loadData();
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

// ---------- Cross-team search (RELAY 057) ----------
// Entirely client-side -- profiles/teams are already loaded via loadData(),
// confirmed via source there's no need for a new bridge call.

function onSearchClick() {
  document.body.classList.add("search-open");
  const input = document.getElementById("search-input");
  input.value = "";
  renderSearchResults("");
  setTimeout(() => input.focus(), 0);
}

function closeSearch() {
  document.body.classList.remove("search-open");
}

function onSearchInput() {
  renderSearchResults(document.getElementById("search-input").value);
}

function renderSearchResults(query) {
  const results = document.getElementById("search-results");
  const q = query.trim().toLowerCase();

  // Grouped by team, in the same order teams appear in the rail -- a
  // profile with no team membership at all is grouped under "No team"
  // (matches the ALL view's own real possibility: team_ids can be empty).
  const groups = [];
  for (const t of teams) {
    const rows = profiles.filter(
      (p) => (p.team_ids || []).includes(t.id) && (!q || (p.name || "").toLowerCase().includes(q))
    );
    if (rows.length) groups.push({ teamName: t.name, rows });
  }
  const noTeamRows = profiles.filter(
    (p) => (p.team_ids || []).length === 0 && (!q || (p.name || "").toLowerCase().includes(q))
  );
  if (noTeamRows.length) groups.push({ teamName: "No team", rows: noTeamRows });

  if (!groups.length) {
    results.innerHTML = `<div id="search-empty">No matches</div>`;
    return;
  }

  results.innerHTML = groups
    .map(
      (g) => `
        <div class="search-group-label">${escapeHtml(g.teamName)}</div>
        ${g.rows
          .map(
            (p) => `
              <div class="search-row" data-search-row="${p.id}">
                <div class="card-avatar" style="background:${avatarColor(p.name)}">${initials(p.name)}</div>
                <div style="min-width:0">
                  <div class="search-row-name">${escapeHtml(p.name || "(unnamed)")}</div>
                  <div class="search-row-sub">${escapeHtml(clientFolderLabel(p.executable_path))}</div>
                </div>
                <span class="search-row-team">${escapeHtml(g.teamName)}</span>
              </div>`
          )
          .join("")}`
    )
    .join("");

  for (const el of results.querySelectorAll("[data-search-row]")) {
    el.onclick = () => onSearchResultClick(el.getAttribute("data-search-row"));
  }
}

// Jumps to the FIRST team the clicked profile belongs to (a profile can be
// in several) and focuses its card -- matches "search finds it, take me
// there" rather than just closing the modal with no follow-through.
function onSearchResultClick(profileId) {
  const p = profiles.find((x) => x.id === profileId);
  closeSearch();
  if (!p) return;
  const teamId = (p.team_ids || [])[0] || "ALL";
  selectTeam(teamId);
  focusedProfileId = profileId;
  renderCards();
  const card = document.querySelector(`[data-card="${profileId}"]`);
  if (card) card.scrollIntoView({ block: "center", behavior: "smooth" });
}

document.getElementById("search-scrim").addEventListener("click", closeSearch);
document.getElementById("search-close-btn").addEventListener("click", closeSearch);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && document.body.classList.contains("search-open")) closeSearch();
});

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
  // RELAY 038: real persisted palette, once it arrives -- `palette` above
  // starts as THEME_PRESETS[0] (an instant first paint, same as before this
  // entry) and gets swapped for the real saved one moments later, same
  // fire-and-don't-block pattern loadAppSettings/loadRunAsAdminState below
  // already use for their own startup values.
  loadPalette();
  loadData();
  loadConsoleHistory();
  loadAppSettings();
  wireAppSettingsControls();
  loadRunAsAdminState();
  wireRunAsAdminControl();
  loadLauncherVersion();
  // RELAY 048: same eager-once-at-startup pattern as 032/033 below --
  // matches the old app's own UpdateCheckState.run_check_async, "safe to
  // call unconditionally" (never raises, silent on failure).
  window.pywebview.api.check_launcher_update();
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
