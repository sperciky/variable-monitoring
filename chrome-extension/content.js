/* ===================================================================
   GTM Variable Monitor — Content script
   Runs on tagmanager.google.com pages.
   Detects container parameters from the URL hash and notifies
   the background script.
   =================================================================== */

(function () {
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

  // Send initial detection
  const params = detectParams();
  if (params) {
    chrome.runtime.sendMessage({ type: "gtm-params-detected", params });
  }

  // GTM uses hash-based routing — watch for changes
  window.addEventListener("hashchange", () => {
    const p = detectParams();
    if (p) {
      chrome.runtime.sendMessage({ type: "gtm-params-detected", params: p });
    }
  });
})();
