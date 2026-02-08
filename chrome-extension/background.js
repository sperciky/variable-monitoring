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

  if (msg.type === "export-intercepted" && sender.tab) {
    // Export data successfully stored — show checkmark badge on that tab
    showReadyBadge(sender.tab.id);
  }

  return false;
});

// Show a white checkmark on green background badge for the given tab
function showReadyBadge(tabId) {
  chrome.action.setBadgeText({ tabId: tabId, text: "\u2713" });
  chrome.action.setBadgeBackgroundColor({ tabId: tabId, color: "#34a853" });
  chrome.action.setBadgeTextColor({ tabId: tabId, color: "#ffffff" });
  console.log("[GTM Monitor BG] Badge set to ready (checkmark) for tab", tabId);
}

// Clear badge when popup is opened (user has seen the notification)
chrome.runtime.onConnect.addListener((port) => {
  if (port.name === "popup") {
    // Popup opened — clear the ready badge for the active tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.action.setBadgeText({ tabId: tabs[0].id, text: "" });
      }
    });
  }
});
