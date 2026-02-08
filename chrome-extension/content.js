/* ===================================================================
   GTM Variable Monitor — Content script (ISOLATED world)
   Runs on tagmanager.google.com pages.
   1. Detects container parameters from the URL hash
   2. Listens for intercepted export data from the MAIN world script
      (via postMessage) and accumulates exports in chrome.storage.local
   =================================================================== */

(function () {
  const TAG = "[GTM Monitor ISOLATED]";
  const MAX_EXPORTS = 20;

  console.log(TAG, "Content script loaded at", window.location.href);

  // ---- URL param detection ------------------------------------------
  function detectParams() {
    const hash = window.location.hash || "";
    const qIndex = hash.indexOf("?");
    if (qIndex < 0) return null;

    const sp = new URLSearchParams(hash.slice(qIndex + 1));
    const accountId = sp.get("accountId");
    const containerId = sp.get("containerId");
    const containerDraftId = sp.get("containerDraftId");
    const containerVersionId = sp.get("containerVersionId");

    if (!accountId || !containerId) return null;
    return { accountId, containerId, containerDraftId, containerVersionId };
  }

  const params = detectParams();
  if (params) {
    console.log(TAG, "GTM params detected:", params);
    chrome.runtime.sendMessage({ type: "gtm-params-detected", params });
  } else {
    console.log(TAG, "No GTM params found in hash:", window.location.hash);
  }

  window.addEventListener("hashchange", () => {
    const p = detectParams();
    if (p) {
      console.log(TAG, "GTM params updated on hashchange:", p);
      chrome.runtime.sendMessage({ type: "gtm-params-detected", params: p });
    }
  });

  // ---- Listen for intercepted data from MAIN world via postMessage --
  window.addEventListener("message", function (e) {
    // Only accept messages from the same window (our MAIN world script)
    if (e.source !== window) return;
    if (!e.data || e.data.type !== "__gtm_monitor_export") return;

    console.log(TAG, "Received export data via postMessage, length:", (e.data.containerData || "").length);

    try {
      const containerData = JSON.parse(e.data.containerData);
      const meta = e.data.meta || {};
      console.log(TAG, "Parsed container data, meta:", meta);

      // Build a label for this export
      const label = buildLabel(meta, containerData);

      const entry = {
        id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
        label: label,
        accountId: meta.accountId || "",
        containerId: meta.containerId || "",
        sourceType: meta.sourceType || "",
        sourceId: meta.sourceId || "",
        workspaceName: meta.workspaceName || "",
        timestamp: Date.now(),
        containerData: containerData,
      };

      // Accumulate in storage (newest first, capped at MAX_EXPORTS)
      chrome.storage.local.get({ exportHistory: [] }, function (result) {
        const history = result.exportHistory;
        history.unshift(entry);
        if (history.length > MAX_EXPORTS) history.length = MAX_EXPORTS;

        chrome.storage.local.set({ exportHistory: history }, function () {
          console.log(TAG, "Export stored. History size:", history.length);
        });

        // Notify popup (if open)
        chrome.runtime.sendMessage({
          type: "export-intercepted",
          entryId: entry.id,
          label: entry.label,
          timestamp: entry.timestamp,
        }).catch(function () {
          console.log(TAG, "Popup not open, will pick up data when opened");
        });
      });
    } catch (err) {
      console.error(TAG, "Error processing export data:", err);
    }
  });

  // ---- Build a human-readable label for the export ------------------
  function buildLabel(meta, containerData) {
    const parts = [];

    // Workspace or version name
    if (meta.workspaceName) {
      parts.push(meta.workspaceName);
    } else if (meta.sourceType === "versions") {
      parts.push("Version " + meta.sourceId);
    } else if (meta.sourceType === "workspaces") {
      parts.push("Workspace " + meta.sourceId);
    }

    // Container name from containerVersion.container.name
    const cv = containerData && containerData.containerVersion;
    const containerName = cv && cv.container && cv.container.name;
    if (containerName) {
      parts.push(containerName);
    } else if (meta.containerId) {
      parts.push("CTR-" + meta.containerId);
    }

    return parts.length > 0 ? parts.join(" | ") : "Export";
  }

  console.log(TAG, "All listeners registered, waiting for export data...");
})();
