/* ===================================================================
   GTM Variable Monitor — MAIN world network interceptor
   Runs in the page's JS context (world: "MAIN" in manifest).
   Intercepts both fetch() and XMLHttpRequest to capture partialexport
   responses when the user clicks Export/Preview in GTM.

   NOTE: GTM is an AngularJS app which uses XMLHttpRequest, not fetch.
   =================================================================== */

(function () {
  const TAG = "[GTM Monitor MAIN]";
  var _scriptStart = performance.now();
  function _ts() { return "[" + Math.round(performance.now() - _scriptStart) + "ms]"; }
  function log() { console.log.apply(console, [TAG, _ts()].concat(Array.prototype.slice.call(arguments))); }
  function warn() { console.warn.apply(console, [TAG, _ts()].concat(Array.prototype.slice.call(arguments))); }
  function err() { console.error.apply(console, [TAG, _ts()].concat(Array.prototype.slice.call(arguments))); }

  // ---- Prevent duplicate initialization -----------------------------
  if (window.__gtm_monitor_main_initialized) {
    log("Already initialized, skipping duplicate injection");
    return;
  }
  window.__gtm_monitor_main_initialized = true;

  log("Interceptor script loaded at", window.location.href);

  // ---- Pending export buffer (survives ISOLATED world invalidation) ---
  if (!window.__gtm_monitor_pending_exports) {
    window.__gtm_monitor_pending_exports = [];
  }

  // ---- Extract workspace name from the export dialog DOM ------------
  function getWorkspaceName() {
    try {
      const el = document.querySelector(
        "gtm-selective-export > div > div.gtm-sheet-header > div.gtm-sheet-header__title > div"
      );
      if (el) {
        const text = el.innerText.trim();
        return text.replace(/^Export\s+/i, "") || text;
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  // ---- Extract account/container/workspace IDs from the API URL -----
  function parseExportUrl(url) {
    const m = url.match(/\/api\/accounts\/(\d+)\/containers\/(\d+)\/(workspaces|versions)\/(\d+)\/partialexport/);
    if (!m) return {};
    return {
      accountId: m[1],
      containerId: m[2],
      sourceType: m[3],
      sourceId: m[4],
    };
  }

  // ---- Intercept XMLHttpRequest (AngularJS uses this) ---------------
  const _origXHROpen = XMLHttpRequest.prototype.open;
  const _origXHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url) {
    this.__gtmMonUrl = url || "";
    this.__gtmMonMethod = method || "";

    if (url && typeof url === "string" && url.includes("tagmanager.google.com/api")) {
      log("GTM API call:", method, url.substring(0, 150));
    }

    return _origXHROpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function () {
    const url = this.__gtmMonUrl;

    if (url.includes("/partialexport")) {
      log("XHR partialexport intercepted:", this.__gtmMonMethod, url);

      this.addEventListener("load", function () {
        log("XHR response status:", this.status, "length:", (this.responseText || "").length);
        try {
          processExportResponse(this.responseText, url, "XHR");
        } catch (e) {
          err("XHR processing error:", e);
        }
      });
    }

    return _origXHRSend.apply(this, arguments);
  };

  // ---- Intercept fetch (in case GTM switches to it) -----------------
  const _origFetch = window.fetch;
  window.fetch = function () {
    const req = arguments[0];
    const url = typeof req === "string" ? req : (req && req.url) || "";

    if (url.includes("/partialexport")) {
      log("fetch() partialexport intercepted:", url);

      return _origFetch.apply(this, arguments).then(function (response) {
        const clone = response.clone();
        clone.text().then(function (text) {
          log("fetch response status:", response.status, "length:", text.length);
          try {
            processExportResponse(text, url, "fetch");
          } catch (e) {
            err("fetch processing error:", e);
          }
        });
        return response;
      });
    }
    return _origFetch.apply(this, arguments);
  };

  // ---- Common response processor ------------------------------------
  function processExportResponse(text, requestUrl, source) {
    const jsonStr = text.replace(/^\)\]\}',?\s*/, "");
    log("Stripped prefix, parsing JSON from", source, "first 200 chars:", jsonStr.substring(0, 200));

    const parsed = JSON.parse(jsonStr);
    log("Parsed top-level keys:", Object.keys(parsed));

    const wrapper = parsed.default || parsed;
    log("Wrapper keys:", Object.keys(wrapper));

    const exportedJson = wrapper.exportedContainerJson;
    if (!exportedJson) {
      warn("No exportedContainerJson found in response");
      return;
    }

    log("exportedContainerJson length:", exportedJson.length);
    const containerData = JSON.parse(exportedJson);
    log("Parsed container data, keys:", Object.keys(containerData));

    const urlInfo = parseExportUrl(requestUrl);
    const workspaceName = getWorkspaceName();
    log("URL info:", urlInfo, "Workspace name:", workspaceName);

    var exportMsg = {
      type: "__gtm_monitor_export",
      containerData: JSON.stringify(containerData),
      meta: {
        accountId: urlInfo.accountId || "",
        containerId: urlInfo.containerId || "",
        sourceType: urlInfo.sourceType || "",
        sourceId: urlInfo.sourceId || "",
        workspaceName: workspaceName || "",
      },
    };

    window.__gtm_monitor_pending_exports.push(exportMsg);
    if (window.__gtm_monitor_pending_exports.length > 20) {
      window.__gtm_monitor_pending_exports.shift();
    }
    log("Buffered export, pending count:", window.__gtm_monitor_pending_exports.length);

    window.postMessage(exportMsg, "*");
    log("Posted message to ISOLATED world via postMessage");
  }

  // ==================================================================
  // Navigate + select & flush: triggered from ISOLATED world content script
  // ==================================================================

  window.addEventListener("message", function (e) {
    if (e.source !== window) return;
    if (!e.data) return;

    if (e.data.type === "__gtm_monitor_flush_pending") {
      var pending = window.__gtm_monitor_pending_exports || [];
      log("Flush requested, sending", pending.length, "pending exports");
      for (var i = 0; i < pending.length; i++) {
        window.postMessage(pending[i], "*");
      }
      window.__gtm_monitor_pending_exports = [];
      return;
    }

    if (e.data.type === "__gtm_monitor_navigate_and_select") {
      log("Navigate-and-select received, hash:", e.data.hash,
        "variables:", e.data.variableNames.length);
      navigateAndSelect(e.data.hash, e.data.variableNames);
    }
  });

  function navigateAndSelect(hash, variableNames) {
    log("Navigate-and-select START");
    var targetPath = hash.replace(/^#/, "");

    // Check if a dialog/sheet is open (export dialog, etc.)
    var hasDialog = !!document.querySelector(
      "gtm-selective-export, .gtm-sheet, .gtm-dialog"
    );

    if (hasDialog) {
      // Dialog is open — hash navigation won't work reliably while Angular
      // is managing the dialog. Skip all the close/wait/navigate complexity
      // and go straight to a full page reload at the target URL.
      log("Dialog detected, saving selection and forcing full page reload");
      saveAndReload(hash, variableNames);
      return;
    }

    // No dialog — try in-page hash navigation
    log("No dialog, attempting in-page navigation");
    log("Setting window.location.hash");
    window.location.hash = hash;

    log("Verifying URL change, target:", targetPath);
    waitForUrlToContain(targetPath, 3000).then(function () {
      log("URL confirmed, waiting for variables page elements...");
      return waitForElement("a.wd-variable-name", 15000);
    }).then(function () {
      log("Variables page detected, starting selection");
      selectVariablesOnPage(variableNames);
    }).catch(function (e) {
      warn("In-page navigation failed:", e.message, "— forcing full page reload");
      saveAndReload(hash, variableNames);
    });
  }

  function saveAndReload(hash, variableNames) {
    try {
      sessionStorage.setItem("__gtm_monitor_pending_selection", JSON.stringify({
        variableNames: variableNames,
      }));
      log("Saved", variableNames.length, "variable names to sessionStorage");
    } catch (e) {
      err("Failed to save to sessionStorage:", e);
    }
    // Set the hash first, then force a real page reload.
    // Just setting href to the same origin + different hash does NOT reload.
    window.location.hash = hash;
    log("Hash set, forcing page reload...");
    window.location.reload();
  }

  function waitForUrlToContain(targetPath, timeout) {
    return new Promise(function (resolve, reject) {
      // Check immediately
      if (window.location.hash.indexOf(targetPath) >= 0) {
        resolve();
        return;
      }
      var elapsed = 0;
      var interval = setInterval(function () {
        if (window.location.hash.indexOf(targetPath) >= 0) {
          clearInterval(interval);
          resolve();
          return;
        }
        elapsed += 100;
        if (elapsed >= timeout) {
          clearInterval(interval);
          reject(new Error("URL did not change to " + targetPath + " within " + timeout + "ms (current: " + window.location.hash + ")"));
        }
      }, 100);
    });
  }

  // Check for pending selection after page load (survives forced reload via sessionStorage)
  try {
    var pendingJson = sessionStorage.getItem("__gtm_monitor_pending_selection");
    if (pendingJson) {
      sessionStorage.removeItem("__gtm_monitor_pending_selection");
      var pending = JSON.parse(pendingJson);
      log("Found pending selection from before reload, resuming with", pending.variableNames.length, "variables...");
      // Wait for the variables page to fully render after reload
      waitForElement("a.wd-variable-name", 15000).then(function () {
        log("Variables page ready after reload, starting selection");
        selectVariablesOnPage(pending.variableNames);
      }).catch(function (e) {
        err("Failed to find variables page after reload:", e.message);
      });
    }
  } catch (e) { /* ignore */ }

  async function selectVariablesOnPage(names) {
    const nameSet = new Set(names);
    try {
      // 1. Wait for the variables table to appear
      log("Waiting for variables table...");
      await waitForElement("tr[gtm-table-row]", 15000);
      log("Table rows found");

      // 2. Set pagination to ALL so every variable is visible
      log("Setting pagination to ALL...");
      await setPaginationToAll();
      log("Pagination done");

      // 3. Wait for row count to stabilize (all rows rendered)
      log("Waiting for row count to stabilize...");
      const totalRows = await waitForStableRowCount(8000);
      log("Row count stabilized at", totalRows);

      // 4. Collect all checkboxes to click, then click in batches
      log("Finding checkboxes to click...");
      log("Target variable names:", Array.from(nameSet).slice(0, 5), "... (" + nameSet.size + " total)");
      const toClick = [];
      const rows = document.querySelectorAll("tr[gtm-table-row]");
      var rowsWithLink = 0;
      var nameMatches = 0;
      var checkboxIssues = 0;
      var sampleDomNames = [];
      for (const row of rows) {
        const nameLink = row.querySelector("a.wd-variable-name");
        if (!nameLink) continue;
        rowsWithLink++;
        const varName = nameLink.textContent.trim();
        if (sampleDomNames.length < 5) sampleDomNames.push(varName);
        if (nameSet.has(varName)) {
          nameMatches++;
          const checkbox = row.querySelector("gtm-table-row-checkbox i");
          if (!checkbox) {
            checkboxIssues++;
            log("No checkbox <i> found for matched variable:", varName);
          } else {
            toClick.push(checkbox);
          }
        }
      }
      log("Rows with a.wd-variable-name:", rowsWithLink, "of", rows.length);
      log("Sample DOM variable names:", sampleDomNames);
      log("Name matches:", nameMatches, "Checkbox issues:", checkboxIssues);
      log("Found", toClick.length, "checkboxes to click");

      // Click in batches of 10 with a small yield between batches
      const BATCH = 10;
      for (let i = 0; i < toClick.length; i += BATCH) {
        for (let j = i; j < Math.min(i + BATCH, toClick.length); j++) {
          toClick[j].click();
        }
        if (i + BATCH < toClick.length) {
          await new Promise(function (r) { setTimeout(r, 0); });
        }
      }
      log("DONE — Selected", toClick.length, "of", names.length, "unused variables");
    } catch (e) {
      err("Variable selection failed:", e);
    }
  }

  function setPaginationToAll() {
    return new Promise(function (resolve) {
      const select = document.querySelector("gtm-pagination select");
      if (!select) { warn("Pagination select not found"); resolve(); return; }

      if (select.value === "string:ALL") { log("Pagination already ALL"); resolve(); return; }

      log("Setting pagination to ALL (current:", select.value, ")");

      if (typeof angular !== "undefined") {
        try {
          var scope = angular.element(select).scope();
          if (scope && scope.ctrl) {
            scope.$apply(function () {
              scope.ctrl.itemsPerPage = "ALL";
              scope.ctrl.onPageSizeSelect();
            });
            log("Pagination set via AngularJS scope");
            setTimeout(resolve, 500);
            return;
          }
        } catch (e) {
          warn("AngularJS scope approach failed, using DOM fallback:", e);
        }
      }

      select.value = "string:ALL";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      log("Pagination set via DOM event");
      setTimeout(resolve, 500);
    });
  }

  function waitForElement(selector, timeout) {
    return new Promise(function (resolve, reject) {
      var el = document.querySelector(selector);
      if (el) { resolve(el); return; }

      var timedOut = false;
      var timer = setTimeout(function () {
        timedOut = true;
        if (observer) observer.disconnect();
        reject(new Error("Timeout waiting for " + selector));
      }, timeout);

      var observer;
      function startObserving() {
        if (timedOut) return;
        // Re-check after waiting for body
        var found = document.querySelector(selector);
        if (found) { clearTimeout(timer); resolve(found); return; }

        observer = new MutationObserver(function () {
          var found = document.querySelector(selector);
          if (found) { observer.disconnect(); clearTimeout(timer); resolve(found); }
        });
        var root = document.body || document.documentElement;
        observer.observe(root, { childList: true, subtree: true });
      }

      if (document.body) {
        startObserving();
      } else {
        log("document.body not ready, waiting for DOMContentLoaded...");
        document.addEventListener("DOMContentLoaded", startObserving);
      }
    });
  }

  function waitForStableRowCount(timeout) {
    return new Promise(function (resolve) {
      var lastCount = 0;
      var stableTime = 0;

      var interval = setInterval(function () {
        var count = document.querySelectorAll("tr[gtm-table-row]").length;
        if (count === lastCount && count > 0) {
          stableTime += 200;
          if (stableTime >= 600) {
            clearInterval(interval);
            resolve(count);
          }
        } else {
          lastCount = count;
          stableTime = 0;
        }
      }, 200);

      setTimeout(function () {
        clearInterval(interval);
        resolve(lastCount);
      }, timeout);
    });
  }
})();
