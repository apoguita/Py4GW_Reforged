// Phase B/C real UI (RELAY 010) -- structure + theme + one real data slice.
// No framework: the mockup this is built from uses a small proprietary
// component/templating system (DCLogic/sc-for/sc-if) that isn't portable outside
// Claude Design's own export tooling, so this is hand-written vanilla JS doing the
// same job (render from state, re-render on change) without that dependency.
//
// Explicitly NOT wired here (RELAY 010's own out-of-scope list): Add/Edit/Delete
// profile actions, GW1 launch, console/log, App Settings' real prerequisite
// checks/mod repo/accounts sections, auto-login fields, edit-dialog tabs, cross-team
// search, checkbox/subset launch, click-to-focus tracking. Cards render real data
// read-only; the Launch button is present for visual structure but intentionally
// does nothing yet.

let palette = { ...THEME_PRESETS[0] };
let profiles = [];
let teams = [];
let activeTeamId = "ALL";
let filterText = "";

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
}

function badgeHtml(label, on) {
  return `<span class="badge${on ? " on" : ""}" title="${label} — ${on ? "on" : "off"} for this profile">${label}</span>`;
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
    noResults.textContent = `No profiles match "${filterText}"`;
  }

  grid.innerHTML = "";
  for (const p of visible) {
    const card = document.createElement("div");
    card.className = "card";
    const midText = p.executable_path ? p.executable_path : "no client path set";
    card.innerHTML = `
      <div class="card-top">
        <div class="card-avatar" style="background:${avatarColor(p.name)}">${initials(p.name)}</div>
        <div class="card-name-block">
          <div class="card-name">${escapeHtml(p.name || "(unnamed)")}</div>
          <div class="card-sub">${escapeHtml(midText)}</div>
        </div>
        <span class="card-dot"></span>
      </div>
      <div class="card-badges">
        ${badgeHtml("P4", !!p.py4gw_enabled)}
        ${badgeHtml("gM", !!p.gmod_enabled)}
        ${p.auto_login_enabled ? badgeHtml("AUTO", true) : ""}
      </div>
      <button class="card-action" disabled>&#9654; Launch</button>
    `;
    grid.appendChild(card);
  }
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function selectTeam(teamId) {
  activeTeamId = teamId;
  filterText = "";
  document.getElementById("filter-input").value = "";
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

// ---------- Settings drawer / theme ----------

function openDrawer() {
  document.body.classList.add("drawer-open");
}

function closeDrawer() {
  document.body.classList.remove("drawer-open");
}

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

// ---------- Window controls (carried over from Phase A) ----------

function startResize(edge) {
  window.pywebview.api.start_resize(edge);
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && document.body.classList.contains("drawer-open")) {
    closeDrawer();
  }
});

window.addEventListener("pywebviewready", () => {
  applyTheme(palette);
  syncPaletteControls();
  wirePaletteControls();
  loadData();
});
