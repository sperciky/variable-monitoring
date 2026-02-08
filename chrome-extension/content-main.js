/* ===================================================================
   GTM Variable Monitor — MAIN world network interceptor
   Runs in the page's JS context (world: "MAIN" in manifest).
   Intercepts both fetch() and XMLHttpRequest to capture partialexport
   responses when the user clicks Export/Preview in GTM.

   NOTE: GTM is an AngularJS app which uses XMLHttpRequest, not fetch.
   =================================================================== */

(function () {
  const TAG = "[GTM Monitor MAIN]";

  // ---- Prevent duplicate initialization -----------------------------
  // MAIN world scripts persist in the page JS context even after extension
  // reload. If ensureContentScripts() re-injects this file, skip to avoid
  // duplicate XHR patches and message listeners.
  if (window.__gtm_monitor_main_initialized) {
    console.log(TAG, "Already initialized, skipping duplicate injection");
    return;
  }
  window.__gtm_monitor_main_initialized = true;

  console.log(TAG, "Interceptor script loaded at", window.location.href);

  // ---- Pending export buffer (survives ISOLATED world invalidation) ---
  // MAIN world persists as long as the page is alive, even if the extension
  // reloads and the ISOLATED content script loses its context.
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
        // "Export Default Workspace" → "Default Workspace"
        return text.replace(/^Export\s+/i, "") || text;
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  // ---- Extract account/container/workspace IDs from the API URL -----
  function parseExportUrl(url) {
    // .../api/accounts/218461/containers/55831269/workspaces/678/partialexport?hl=en
    // .../api/accounts/218461/containers/55831269/versions/123/partialexport?hl=en
    const m = url.match(/\/api\/accounts\/(\d+)\/containers\/(\d+)\/(workspaces|versions)\/(\d+)\/partialexport/);
    if (!m) return {};
    return {
      accountId: m[1],
      containerId: m[2],
      sourceType: m[3],   // "workspaces" or "versions"
      sourceId: m[4],
    };
  }

  // ---- Intercept XMLHttpRequest (AngularJS uses this) ---------------
  const _origXHROpen = XMLHttpRequest.prototype.open;
  const _origXHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url) {
    this.__gtmMonUrl = url || "";
    this.__gtmMonMethod = method || "";

    // Log all GTM API calls for debugging
    if (url && typeof url === "string" && url.includes("tagmanager.google.com/api")) {
      console.log(TAG, "GTM API call:", method, url.substring(0, 150));
    }

    return _origXHROpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function () {
    const url = this.__gtmMonUrl;

    if (url.includes("/partialexport")) {
      console.log(TAG, "XHR partialexport intercepted:", this.__gtmMonMethod, url);

      this.addEventListener("load", function () {
        console.log(TAG, "XHR response status:", this.status, "length:", (this.responseText || "").length);
        try {
          processExportResponse(this.responseText, url, "XHR");
        } catch (e) {
          console.error(TAG, "XHR processing error:", e);
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
      console.log(TAG, "fetch() partialexport intercepted:", url);

      return _origFetch.apply(this, arguments).then(function (response) {
        const clone = response.clone();
        clone.text().then(function (text) {
          console.log(TAG, "fetch response status:", response.status, "length:", text.length);
          try {
            processExportResponse(text, url, "fetch");
          } catch (e) {
            console.error(TAG, "fetch processing error:", e);
          }
        });
        return response;
      });
    }
    return _origFetch.apply(this, arguments);
  };

  // ---- Common response processor ------------------------------------
  function processExportResponse(text, requestUrl, source) {
    // Google APIs prefix with )]}',\n — strip it
    const jsonStr = text.replace(/^\)\]\}',?\s*/, "");
    console.log(TAG, "Stripped prefix, parsing JSON from", source, "first 200 chars:", jsonStr.substring(0, 200));

    const parsed = JSON.parse(jsonStr);
    console.log(TAG, "Parsed top-level keys:", Object.keys(parsed));

    const wrapper = parsed.default || parsed;
    console.log(TAG, "Wrapper keys:", Object.keys(wrapper));

    const exportedJson = wrapper.exportedContainerJson;
    if (!exportedJson) {
      console.warn(TAG, "No exportedContainerJson found in response");
      return;
    }

    console.log(TAG, "exportedContainerJson length:", exportedJson.length);
    const containerData = JSON.parse(exportedJson);
    console.log(TAG, "Parsed container data, keys:", Object.keys(containerData));

    // Gather metadata
    const urlInfo = parseExportUrl(requestUrl);
    const workspaceName = getWorkspaceName();
    console.log(TAG, "URL info:", urlInfo, "Workspace name:", workspaceName);

    // Build the message payload
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

    // Buffer in global array so a freshly-injected ISOLATED script can recover it
    window.__gtm_monitor_pending_exports.push(exportMsg);
    // Keep buffer bounded (max 20)
    if (window.__gtm_monitor_pending_exports.length > 20) {
      window.__gtm_monitor_pending_exports.shift();
    }
    console.log(TAG, "Buffered export, pending count:", window.__gtm_monitor_pending_exports.length);

    // Use postMessage to cross the MAIN→ISOLATED world boundary
    window.postMessage(exportMsg, "*");
    console.log(TAG, "Posted message to ISOLATED world via postMessage");
  }

  // ==================================================================
  // Navigate + select & flush: triggered from ISOLATED world content script
  // ==================================================================

  window.addEventListener("message", function (e) {
    if (e.source !== window) return;
    if (!e.data) return;

    // ---- Flush pending exports to a freshly-loaded ISOLATED script ----
    if (e.data.type === "__gtm_monitor_flush_pending") {
      var pending = window.__gtm_monitor_pending_exports || [];
      console.log(TAG, "Flush requested, sending", pending.length, "pending exports");
      for (var i = 0; i < pending.length; i++) {
        window.postMessage(pending[i], "*");
      }
      // Clear buffer after flushing
      window.__gtm_monitor_pending_exports = [];
      return;
    }

    if (e.data.type === "__gtm_monitor_navigate_and_select") {
      console.log(TAG, "Navigate-and-select received, hash:", e.data.hash,
        "variables:", e.data.variableNames.length);
      navigateAndSelect(e.data.hash, e.data.variableNames);
    }
  });

  function navigateAndSelect(hash, variableNames) {
    var path = hash.replace(/^#/, "");
    console.log(TAG, "Navigating AngularJS to:", path);

    // 1. Close any open GTM dialog/sheet that may block navigation
    closeGtmDialogs();

    // 2. Small delay for dialog close animation, then navigate
    setTimeout(function () {
      doNavigate(path, hash);

      // 3. Wait for the URL to actually reflect the target path, then select
      waitForUrlChange(path, 10000).then(function () {
        console.log(TAG, "URL confirmed, waiting for page render...");
        setTimeout(function () {
          selectVariablesOnPage(variableNames);
        }, 250);
      }).catch(function () {
        console.warn(TAG, "URL did not change, retrying navigation...");
        // Fallback: force hash change directly
        window.location.hash = hash;
        setTimeout(function () {
          selectVariablesOnPage(variableNames);
        }, 2000);
      });
    }, 150);
  }

  function closeGtmDialogs() {
    // Close export sheet / any open GTM overlay
    var closeBtn = document.querySelector(
      ".gtm-sheet-header__close-button, " +
      ".gtm-dialog-header__close-button, " +
      "gtm-selective-export .gtm-sheet-header button"
    );
    if (closeBtn) {
      console.log(TAG, "Closing open GTM dialog/sheet");
      closeBtn.click();
      return;
    }
    // Fallback: press Escape to close any modal
    document.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Escape", keyCode: 27, bubbles: true
    }));
  }

  function doNavigate(path, hash) {
    if (typeof angular !== "undefined") {
      try {
        var $injector = angular.element(document.body).injector();
        if ($injector) {
          $injector.invoke(["$location", "$timeout", function ($location, $timeout) {
            $timeout(function () {
              $location.url(path);
            });
          }]);
          console.log(TAG, "Navigation triggered via AngularJS $timeout + $location.url()");
          return;
        }
      } catch (err) {
        console.warn(TAG, "AngularJS navigation failed, falling back to hash:", err);
      }
    }
    window.location.hash = hash;
  }

  function waitForUrlChange(targetPath, timeout) {
    return new Promise(function (resolve, reject) {
      var elapsed = 0;
      var interval = setInterval(function () {
        var currentHash = window.location.hash || "";
        // Check if the current hash contains the target path
        if (currentHash.indexOf("/variables") >= 0 && currentHash.indexOf(targetPath) >= 0) {
          clearInterval(interval);
          resolve();
        }
        elapsed += 200;
        if (elapsed >= timeout) {
          clearInterval(interval);
          reject(new Error("URL did not change to target path"));
        }
      }, 200);
    });
  }

  async function selectVariablesOnPage(names) {
    const nameSet = new Set(names);
    try {
      // 1. Wait for the variables table to appear
      console.log(TAG, "Waiting for variables table...");
      await waitForElement("tr[gtm-table-row]", 15000);
      console.log(TAG, "Table rows found");

      // 2. Set pagination to ALL so every variable is visible
      await setPaginationToAll();

      // 3. Wait for row count to stabilize (all rows rendered)
      const totalRows = await waitForStableRowCount(8000);
      console.log(TAG, "Row count stabilized at", totalRows);

      // 4. Click checkboxes for matching variable names
      let selected = 0;
      const rows = document.querySelectorAll("tr[gtm-table-row]");
      for (const row of rows) {
        const nameLink = row.querySelector("a.wd-variable-name");
        if (!nameLink) continue;
        const varName = nameLink.textContent.trim();
        if (nameSet.has(varName)) {
          const checkbox = row.querySelector("gtm-table-row-checkbox i");
          if (checkbox && !checkbox.classList.contains("gtm-check-box-icon")) {
            checkbox.click();
            selected++;
          }
        }
      }
      console.log(TAG, "Selected", selected, "of", names.length, "unused variables");
    } catch (err) {
      console.error(TAG, "Variable selection failed:", err);
    }
  }

  function setPaginationToAll() {
    return new Promise(function (resolve) {
      const select = document.querySelector("gtm-pagination select");
      if (!select) { console.warn(TAG, "Pagination select not found"); resolve(); return; }

      // Already ALL?
      if (select.value === "string:ALL") { console.log(TAG, "Pagination already ALL"); resolve(); return; }

      console.log(TAG, "Setting pagination to ALL (current:", select.value, ")");

      // Use AngularJS scope if available for reliable model update
      if (typeof angular !== "undefined") {
        try {
          var scope = angular.element(select).scope();
          if (scope && scope.ctrl) {
            scope.$apply(function () {
              scope.ctrl.itemsPerPage = "ALL";
              scope.ctrl.onPageSizeSelect();
            });
            console.log(TAG, "Pagination set via AngularJS scope");
            // Give AngularJS time to re-render
            setTimeout(resolve, 500);
            return;
          }
        } catch (e) {
          console.warn(TAG, "AngularJS scope approach failed, using DOM fallback:", e);
        }
      }

      // DOM fallback
      select.value = "string:ALL";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      console.log(TAG, "Pagination set via DOM event");
      setTimeout(resolve, 500);
    });
  }

  function waitForElement(selector, timeout) {
    return new Promise(function (resolve, reject) {
      var el = document.querySelector(selector);
      if (el) { resolve(el); return; }

      var observer = new MutationObserver(function () {
        var found = document.querySelector(selector);
        if (found) { observer.disconnect(); resolve(found); }
      });
      observer.observe(document.body, { childList: true, subtree: true });

      setTimeout(function () {
        observer.disconnect();
        reject(new Error("Timeout waiting for " + selector));
      }, timeout);
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
