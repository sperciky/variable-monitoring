/* ===================================================================
   GTM Variable Monitor — Content script (ISOLATED world)
   Runs on tagmanager.google.com pages.
   1. Detects container parameters from the URL hash
   2. Listens for intercepted export data from the MAIN world script
      (via postMessage) and stores it in chrome.storage.local
   =================================================================== */

(function () {
  const TAG = "[GTM Monitor ISOLATED]";
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
      console.log(TAG, "Parsed container data, storing in chrome.storage.local");

      // Store in chrome.storage so popup can access it
      chrome.storage.local.set({
        interceptedExport: containerData,
        interceptedAt: Date.now(),
      }, function () {
        console.log(TAG, "Data stored in chrome.storage.local successfully");
      });

      // Notify popup (if open)
      chrome.runtime.sendMessage({
        type: "export-intercepted",
        timestamp: Date.now(),
      }).catch(function () {
        // Popup not open, that's fine
        console.log(TAG, "Popup not open, will pick up data when opened");
      });
    } catch (err) {
      console.error(TAG, "Error processing export data:", err);
    }
  });

  console.log(TAG, "All listeners registered, waiting for export data...");
})();
