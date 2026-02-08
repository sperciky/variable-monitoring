/* ===================================================================
   GTM Variable Monitor — Background service worker
   =================================================================== */

// Update extension icon badge based on enabled state
chrome.storage.local.get("gtmMonitorEnabled", ({ gtmMonitorEnabled = true }) => {
  updateBadge(gtmMonitorEnabled);
});

chrome.storage.onChanged.addListener((changes) => {
  if (changes.gtmMonitorEnabled) {
    updateBadge(changes.gtmMonitorEnabled.newValue);
  }
});

function updateBadge(enabled) {
  if (enabled) {
    chrome.action.setBadgeText({ text: "" });
  } else {
    chrome.action.setBadgeText({ text: "OFF" });
    chrome.action.setBadgeBackgroundColor({ color: "#d93025" });
  }
}

// Listen for messages from content script or popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "gtm-params-detected") {
    // Content script detected GTM parameters — store them
    chrome.storage.local.set({ detectedGtmParams: msg.params });
  }
  return false;
});
