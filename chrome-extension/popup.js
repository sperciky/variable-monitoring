/* ===================================================================
   GTM Variable Monitor — Popup controller
   =================================================================== */

// ---- DOM refs -------------------------------------------------------
const $toggle    = document.getElementById("toggle-enabled");
const $btnRun    = document.getElementById("btn-run");
const $btnDetach = document.getElementById("btn-detach");
const $statusBar = document.getElementById("status-bar");
const $statusTxt = document.getElementById("status-text");
const $ctrInfo   = document.getElementById("container-info");
const $results   = document.getElementById("results");
const $summary   = document.getElementById("summary-cards");
const $overlay   = document.getElementById("disabled-overlay");
const $exportSel = document.getElementById("export-selector");
const $select    = document.getElementById("select-export");
const $btnClear  = document.getElementById("btn-clear-history");
const $resActs   = document.getElementById("results-actions");
const $btnSelUnused = document.getElementById("btn-select-unused");
const panelIds   = ["unused-vars", "duplicates", "unused-tpl"];

// ---- State ----------------------------------------------------------
let currentTab  = null;    // active chrome tab
let gtmParams   = null;    // { accountId, containerId, containerDraftId | containerVersionId }
let analysisResult = null; // result from analyzeContainer()
let exportHistory  = [];   // array of export entries from storage

// ---- Init -----------------------------------------------------------
(async function init() {
  // Restore enabled state
  const { gtmMonitorEnabled = true } = await chrome.storage.local.get("gtmMonitorEnabled");
  $toggle.checked = gtmMonitorEnabled;
  applyEnabledState(gtmMonitorEnabled);

  // Detect if we're running in a detached window (has search params)
  const params = new URLSearchParams(window.location.search);
  if (params.get("detached") === "1") {
    document.body.classList.add("detached");
    $btnDetach.classList.add("hidden");
    // Restore cached result if any
    const { cachedResult } = await chrome.storage.local.get("cachedResult");
    if (cachedResult) {
      analysisResult = cachedResult;
      renderResults(analysisResult);
    }
  }

  // Get current tab and check if it's a GTM page
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTab = tab;

  if (tab && tab.url) {
    gtmParams = parseGTMUrl(tab.url);
  }

  if (gtmParams) {
    $ctrInfo.textContent = `Account: ${gtmParams.accountId}  |  Container: ${gtmParams.containerId}`;
    $ctrInfo.classList.remove("hidden");
  } else {
    setStatus("Navigate to a GTM container page first", "error");
    $btnRun.disabled = true;
  }

  // Load export history
  await loadExportHistory();

  // If we have a cached analysis result for this container, show it
  const { cachedResult, cachedParams } = await chrome.storage.local.get(["cachedResult", "cachedParams"]);
  if (cachedResult && cachedParams && gtmParams &&
      cachedParams.accountId === gtmParams.accountId &&
      cachedParams.containerId === gtmParams.containerId) {
    analysisResult = cachedResult;
    renderResults(analysisResult);
    setStatus("Showing cached results (click Run Analysis to refresh)", "success");
  }
})();

// ---- Load and render export history ---------------------------------
async function loadExportHistory() {
  const result = await chrome.storage.local.get({ exportHistory: [] });
  exportHistory = result.exportHistory;
  renderExportSelector();
}

function renderExportSelector() {
  $select.innerHTML = "";

  if (exportHistory.length === 0) {
    $exportSel.classList.add("hidden");
    $btnRun.disabled = true;
    if (gtmParams) {
      setStatus("GTM container detected \u2014 click Export in GTM, then Run Analysis", "");
    }
    return;
  }

  $exportSel.classList.remove("hidden");
  $btnRun.disabled = false;

  for (const entry of exportHistory) {
    const opt = document.createElement("option");
    opt.value = entry.id;
    opt.textContent = formatEntryLabel(entry);
    $select.appendChild(opt);
  }

  // Auto-select newest (first)
  $select.selectedIndex = 0;
  updateStatusFromSelection();
}

function formatEntryLabel(entry) {
  const age = timeAgo(entry.timestamp);
  return `${entry.label}  (${age})`;
}

function timeAgo(ts) {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return mins + "m ago";
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + "h ago";
  const days = Math.floor(hrs / 24);
  return days + "d ago";
}

function updateStatusFromSelection() {
  const entry = getSelectedEntry();
  if (entry) {
    const age = timeAgo(entry.timestamp);
    setStatus(`Selected: ${entry.label} (${age}) \u2014 click Run Analysis`, "success");
  }
}

function getSelectedEntry() {
  const id = $select.value;
  return exportHistory.find(e => e.id === id) || null;
}

// ---- Listen for new intercepted data while popup is open -------------
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "export-intercepted") {
    // Reload history to pick up the new entry
    loadExportHistory();
  }
});

// ---- Clear export history -------------------------------------------
$btnClear.addEventListener("click", async () => {
  await chrome.storage.local.set({ exportHistory: [] });
  exportHistory = [];
  renderExportSelector();
  $results.classList.add("hidden");
  analysisResult = null;
  setStatus("Export history cleared", "");
});

// ---- Export selector change -----------------------------------------
$select.addEventListener("change", updateStatusFromSelection);

// ---- URL Parsing ----------------------------------------------------
function parseGTMUrl(url) {
  try {
    const u = new URL(url);
    if (u.hostname !== "tagmanager.google.com") return null;

    // Hash-based routing: #/admin/?accountId=…&containerId=…&containerDraftId=…
    const hash = u.hash || "";
    const qIndex = hash.indexOf("?");
    if (qIndex < 0) return null;

    const sp = new URLSearchParams(hash.slice(qIndex + 1));
    const accountId = sp.get("accountId");
    const containerId = sp.get("containerId");
    const containerDraftId = sp.get("containerDraftId");
    const containerVersionId = sp.get("containerVersionId");

    if (!accountId || !containerId) return null;
    return { accountId, containerId, containerDraftId, containerVersionId };
  } catch { return null; }
}

// ---- Enable / Disable -----------------------------------------------
$toggle.addEventListener("change", () => {
  const on = $toggle.checked;
  chrome.storage.local.set({ gtmMonitorEnabled: on });
  applyEnabledState(on);
});

function applyEnabledState(enabled) {
  if (enabled) {
    $overlay.classList.add("hidden");
  } else {
    $overlay.classList.remove("hidden");
  }
}

// ---- Detach ---------------------------------------------------------
$btnDetach.addEventListener("click", () => {
  // Cache current result so detached window can pick it up
  if (analysisResult) {
    chrome.storage.local.set({ cachedResult: analysisResult, cachedParams: gtmParams });
  }
  chrome.windows.create({
    url: chrome.runtime.getURL("popup.html?detached=1"),
    type: "popup",
    width: 620,
    height: 750,
  });
  window.close();
});

// ---- Run Analysis ---------------------------------------------------
$btnRun.addEventListener("click", runAnalysis);

async function runAnalysis() {
  $btnRun.disabled = true;
  setStatus("Looking for container data...", "");

  try {
    const entry = getSelectedEntry();
    if (!entry) {
      throw new Error(
        "No export selected. In GTM, go to Admin > Export Container, " +
        "select all items, then click \"Export\" or \"Preview\"."
      );
    }

    setStatus("Analyzing " + entry.label + "...", "");
    analysisResult = window.GTMAnalyzer.analyzeContainer(entry.containerData, true);

    // Cache for detached window
    chrome.storage.local.set({ cachedResult: analysisResult, cachedParams: gtmParams });

    renderResults(analysisResult);
    setStatus("Analysis complete \u2014 " + entry.label, "success");
  } catch (err) {
    console.error("Analysis error:", err);
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    $btnRun.disabled = false;
  }
}

// ---- Status helpers -------------------------------------------------
function setStatus(msg, type) {
  $statusTxt.textContent = msg;
  $statusBar.className = "status-bar" + (type ? ` ${type}` : "");
}

// ---- Render results -------------------------------------------------
function renderResults(result) {
  const { unusedVariables, duplicateVariables, unusedTemplates, summary } = result;
  $results.classList.remove("hidden");

  // Summary cards
  $summary.innerHTML = `
    <div class="card card--danger">
      <div class="card__number">${summary.unusedVariableCount}</div>
      <div class="card__label">Unused Variables</div>
    </div>
    <div class="card card--warning">
      <div class="card__number">${summary.duplicateGroups}</div>
      <div class="card__label">Duplicate Groups</div>
    </div>
    <div class="card card--info">
      <div class="card__number">${summary.unusedTemplateCount}</div>
      <div class="card__label">Unused Templates</div>
    </div>
  `;

  // Show/hide "Select Unused Variables" button
  if (unusedVariables.length > 0) {
    $resActs.classList.remove("hidden");
  } else {
    $resActs.classList.add("hidden");
  }

  // Render tab panels
  renderUnusedVars(unusedVariables);
  renderDuplicates(duplicateVariables);
  renderUnusedTemplates(unusedTemplates);

  // Activate first tab
  activateTab("unused-vars");
}

// ---- Tab switching --------------------------------------------------
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => activateTab(btn.dataset.tab));
});

function activateTab(tabId) {
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("tab--active", t.dataset.tab === tabId));
  panelIds.forEach(id => {
    document.getElementById(`panel-${id}`).classList.toggle("panel--active", id === tabId);
  });
}

// ---- Render: Unused Variables ---------------------------------------
function renderUnusedVars(vars) {
  const $el = document.getElementById("panel-unused-vars");
  if (!vars.length) {
    $el.innerHTML = emptyState("No unused variables found.");
    return;
  }
  let html = `<table class="result-table"><thead><tr>
    <th>Name</th><th>ID</th><th>Type</th>
  </tr></thead><tbody>`;
  for (const v of vars) {
    html += `<tr>
      <td>${copyableSpan(v.name)}</td>
      <td class="text-muted">${esc(v.variableId)}</td>
      <td>${esc(v.typeName)}</td>
    </tr>`;
  }
  html += "</tbody></table>";
  $el.innerHTML = html;
  attachCopyListeners($el);
}

// ---- Render: Duplicates ---------------------------------------------
function renderDuplicates(dups) {
  const $el = document.getElementById("panel-duplicates");
  const allGroups = [];
  const categoryLabels = {
    data_layer_duplicates: "Data Layer",
    event_data_duplicates: "Event Data",
    cookie_duplicates: "Cookie",
    js_variable_duplicates: "JavaScript",
    url_duplicates: "URL",
    custom_template_duplicates: "Custom Template",
    other_duplicates: "Other",
  };

  for (const [cat, groups] of Object.entries(dups)) {
    for (const group of groups) {
      allGroups.push({ category: categoryLabels[cat] || cat, group });
    }
  }

  if (!allGroups.length) {
    $el.innerHTML = emptyState("No duplicate variables found.");
    return;
  }

  let html = "";
  for (const { category, group } of allGroups) {
    const names = group.map(v => v.name).join(", ");
    html += `<div class="dup-group">
      <div class="dup-group__header">${esc(category)}: ${esc(names)}</div>
      <table class="result-table"><thead><tr>
        <th>Name</th><th>ID</th><th>Detail</th>
      </tr></thead><tbody>`;
    for (const v of group) {
      const detail = dupDetail(v);
      html += `<tr>
        <td>${copyableSpan(v.name)}</td>
        <td class="text-muted">${esc(v.variableId)}</td>
        <td class="text-muted">${esc(detail)}</td>
      </tr>`;
    }
    html += "</tbody></table></div>";
  }
  $el.innerHTML = html;
  attachCopyListeners($el);
}

function dupDetail(v) {
  if (v.path) return `DL: ${v.path} (v${v.version})`;
  if (v.keyPath) return `Key: ${v.keyPath}`;
  if (v.cookieName) return `Cookie: ${v.cookieName}`;
  if (v.jsVarName) return `JS: ${v.jsVarName}`;
  if (v.component) return `URL ${v.component}${v.queryKey ? " ?" + v.queryKey : ""}`;
  return v.typeName || "";
}

// ---- Render: Unused Templates ---------------------------------------
function renderUnusedTemplates(tpls) {
  const $el = document.getElementById("panel-unused-tpl");
  if (!tpls.length) {
    $el.innerHTML = emptyState("No unused custom templates found.");
    return;
  }
  let html = `<table class="result-table"><thead><tr>
    <th>Name</th><th>ID</th><th>Category</th><th>Gallery</th>
  </tr></thead><tbody>`;
  for (const t of tpls) {
    html += `<tr>
      <td>${copyableSpan(t.name)}</td>
      <td class="text-muted">${esc(t.templateId)}</td>
      <td>${esc(t.category)}</td>
      <td>${t.isGallery ? "Yes" : "No"}</td>
    </tr>`;
  }
  html += "</tbody></table>";
  $el.innerHTML = html;
  attachCopyListeners($el);
}

// ---- Select Unused Variables in GTM ---------------------------------
$btnSelUnused.addEventListener("click", async () => {
  if (!analysisResult || !analysisResult.unusedVariables.length) return;

  const entry = getSelectedEntry();
  if (!entry || !entry.accountId || !entry.containerId || !entry.sourceId) {
    setStatus("Missing workspace info \u2014 re-export the container first", "error");
    return;
  }

  // Build variables overview URL
  const sourceType = entry.sourceType || "workspaces";
  const varsUrl = `https://tagmanager.google.com/#/container/accounts/${entry.accountId}/containers/${entry.containerId}/${sourceType}/${entry.sourceId}/variables`;

  // Collect unused variable names
  const variableNames = analysisResult.unusedVariables.map(v => v.name);

  // Send message to content script to navigate and select
  // (chrome.tabs.update with hash-only change doesn't trigger SPA navigation)
  if (currentTab) {
    const hash = new URL(varsUrl).hash;
    chrome.tabs.sendMessage(currentTab.id, {
      type: "navigate-and-select",
      hash: hash,
      variableNames: variableNames,
    });
  }

  setStatus(`Navigating to select ${variableNames.length} variables...`, "success");
  setTimeout(() => window.close(), 400);
});

// ---- Utility --------------------------------------------------------
function esc(s) {
  if (s == null) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function copyableSpan(name) {
  return `<span class="var-name" data-copy="${esc(name)}" title="Click to copy">${esc(name)}</span>`;
}

function emptyState(msg) {
  return `<div class="empty-state"><div class="empty-state__icon">&#x2705;</div><p>${msg}</p></div>`;
}

function attachCopyListeners(container) {
  container.querySelectorAll(".var-name").forEach(el => {
    el.addEventListener("click", () => {
      const text = el.dataset.copy;
      navigator.clipboard.writeText(text).then(() => {
        el.classList.add("copied");
        setTimeout(() => el.classList.remove("copied"), 1000);
      }).catch(() => {
        // Fallback
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.cssText = "position:fixed;left:-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        el.classList.add("copied");
        setTimeout(() => el.classList.remove("copied"), 1000);
      });
    });
  });
}
