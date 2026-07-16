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

function teamName(teamId) {
  if (teamId === "ALL") return "All Profiles";
  const t = teams.find((x) => x.id === teamId);
  return t ? t.name : "";
}

function membersOfActiveTeam() {
  if (activeTeamId === "ALL") return profiles;
  return profiles.filter((p) => (p.team_ids || []).includes(activeTeamId));
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
        <button class="card-action" disabled>&#9654; Launch</button>
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
    grid.appendChild(card);
  }
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function toggleCheck(profileId) {
  if (checkedIds.has(profileId)) checkedIds.delete(profileId);
  else checkedIds.add(profileId);
  document.getElementById("add-to-team-btn").style.display = checkedIds.size > 0 ? "inline-block" : "none";
  renderCards();
}

function selectTeam(teamId) {
  activeTeamId = teamId;
  filterText = "";
  checkedIds = new Set();
  document.getElementById("filter-input").value = "";
  document.getElementById("add-to-team-btn").style.display = "none";
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

function openConfirmModal({ title, message, inputPlaceholder, confirmLabel = "Confirm", danger = false }) {
  const scrim = document.getElementById("confirm-scrim");
  const modal = document.getElementById("confirm-modal");
  const titleEl = document.getElementById("confirm-title");
  const messageEl = document.getElementById("confirm-message");
  const inputEl = document.getElementById("confirm-input");
  const confirmBtn = document.getElementById("confirm-btn");
  const cancelBtn = document.getElementById("confirm-cancel-btn");
  const hasInput = inputPlaceholder !== undefined;

  titleEl.textContent = title;
  messageEl.textContent = message || "";
  messageEl.style.display = message ? "block" : "none";
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
      document.getElementById("add-to-team-btn").style.display = "none";
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

function startResize(edge, event) {
  // pywebview's own easy_drag attaches a window-level mousedown listener
  // that arms JS-side window-MOVE tracking on every mousedown, anywhere in
  // the window (DRAG_REGION_DIRECT_TARGET_ONLY defaults to False and this
  // app never overrides it -- confirmed in webview/js/customize.js/util.py).
  // Without stopping propagation here, a resize-zone click both starts our
  // own native resize handoff (async, over the JS<->Python bridge) AND
  // arms that same move-tracking in parallel -- if the user moves the
  // mouse before the async handoff completes, pywebview's own synchronous
  // move-tracking could win the race and move the window instead of
  // resizing it. A real, confirmed race condition (RELAY 018) -- fixed
  // here regardless, though it turned out NOT to be the main cause of the
  // move-instead-of-resize bug Chris reported; that one's still open, see
  // RELAY.md 018's summary.
  if (event) event.stopPropagation();
  window.pywebview.api.start_resize(edge);
}

// Hand-rolled Aero Snap (dev_notes/AERO_SNAP_INVESTIGATION.md). easy_drag still
// does the actual moving; we only tell Python when a title-bar drag starts (so
// it can show the snap preview / restore a snapped window) and when it ends (so
// it can snap into whatever zone the cursor was released over). Python reads the
// real cursor itself, so no coordinates need to cross the bridge.
document.getElementById("titlebar").addEventListener("mousedown", (e) => {
  if (e.button !== 0) return; // left button only
  if (e.target.closest("button")) return; // let the window-control buttons through
  window.pywebview.api.on_drag_start();
});

window.addEventListener("mouseup", () => {
  window.pywebview.api.on_drag_end();
});

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
});
