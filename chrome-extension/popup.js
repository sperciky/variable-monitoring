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
const panelIds   = ["unused-vars", "duplicates", "unused-tpl"];

// ---- State ----------------------------------------------------------
let currentTab  = null;    // active chrome tab
let gtmParams   = null;    // { accountId, containerId, containerDraftId | containerVersionId }
let analysisResult = null; // result from analyzeContainer()

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
    setStatus(`GTM container detected`, "success");
    $ctrInfo.textContent = `Account: ${gtmParams.accountId}  |  Container: ${gtmParams.containerId}`;
    $ctrInfo.classList.remove("hidden");
    $btnRun.disabled = false;
  } else {
    setStatus("Navigate to a GTM container page first", "error");
    $btnRun.disabled = true;
  }

  // If we have a cached result for this container, show it
  const { cachedResult, cachedParams } = await chrome.storage.local.get(["cachedResult", "cachedParams"]);
  if (cachedResult && cachedParams && gtmParams &&
      cachedParams.accountId === gtmParams.accountId &&
      cachedParams.containerId === gtmParams.containerId) {
    analysisResult = cachedResult;
    renderResults(analysisResult);
  }
})();

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
  if (!gtmParams) return;
  $btnRun.disabled = true;
  setStatus("Fetching container data...", "");

  try {
    const gtmJson = await fetchContainerJson(gtmParams);
    setStatus("Analyzing...", "");
    analysisResult = window.GTMAnalyzer.analyzeContainer(gtmJson, true);

    // Cache for detached window
    chrome.storage.local.set({ cachedResult: analysisResult, cachedParams: gtmParams });

    renderResults(analysisResult);
    setStatus("Analysis complete", "success");
  } catch (err) {
    console.error("Analysis error:", err);
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    $btnRun.disabled = false;
  }
}

// ---- Fetch container JSON via GTM internal API ----------------------
async function fetchContainerJson(params) {
  // Build the partial-export URL
  let apiUrl;
  if (params.containerDraftId) {
    apiUrl = `https://tagmanager.google.com/api/accounts/${params.accountId}/containers/${params.containerId}/workspaces/${params.containerDraftId}/partialexport`;
  } else if (params.containerVersionId) {
    apiUrl = `https://tagmanager.google.com/api/accounts/${params.accountId}/containers/${params.containerId}/versions/${params.containerVersionId}/partialexport`;
  } else {
    throw new Error("No workspace draft or version ID found in URL");
  }

  // POST with empty key list = export everything
  const resp = await fetch(apiUrl, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: [], retainFolderStructure: true }),
  });

  if (!resp.ok) {
    if (resp.status === 401 || resp.status === 403) {
      throw new Error("Not authorized. Make sure you are logged in to GTM.");
    }
    throw new Error(`API returned ${resp.status}`);
  }

  const data = await resp.json();
  // The response wraps the JSON string in data.default.exportedContainerJson
  const jsonStr = (data.default || data).exportedContainerJson;
  if (!jsonStr) throw new Error("No exportedContainerJson in API response");
  return JSON.parse(jsonStr);
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
