/* ===================================================================
   GTM Variable Monitor — Content script (ISOLATED world)
   Runs on tagmanager.google.com pages.
   1. Detects container parameters from the URL hash
   2. Listens for intercepted export data from the MAIN world script
      and stores it in chrome.storage.local for the popup to use
   =================================================================== */

(function () {
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
    chrome.runtime.sendMessage({ type: "gtm-params-detected", params });
  }

  window.addEventListener("hashchange", () => {
    const p = detectParams();
    if (p) {
      chrome.runtime.sendMessage({ type: "gtm-params-detected", params: p });
    }
  });

  // ---- Listen for intercepted data from the MAIN world script ------
  window.addEventListener("__gtm_monitor_export", function (e) {
    try {
      const containerData = JSON.parse(e.detail.containerData);
      // Store in chrome.storage so popup can access it
      chrome.storage.local.set({
        interceptedExport: containerData,
        interceptedAt: Date.now(),
      });
      // Notify popup (if open)
      chrome.runtime.sendMessage({
        type: "export-intercepted",
        timestamp: Date.now(),
      });
    } catch (err) {
      // ignore
    }
  });
})();
