# GTM Variable Monitor

A Chrome extension that analyzes Google Tag Manager containers to find unused variables, duplicate variables, and unused custom templates.

## Features

### Export Interception
The extension automatically intercepts GTM container export data when you use the **Export Container** or **Preview JSON** feature in Tag Manager. Up to 20 exports are cached for later analysis.

A green checkmark badge appears on the extension icon when new export data is captured and ready for analysis.

### Three-Part Analysis

**Unused Variables** — Detects variables not referenced by any tag, trigger, variable, transformation, client, or template. Supports toggling whether paused tags are included.

**Duplicate Variables** — Groups variables by type and configuration to find redundant definitions. Grouping accounts for variable type, key parameters, default values, and format settings across all supported types (Data Layer, Event Data, Cookie, JavaScript, URL, Custom Template).

**Unused Custom Templates** — Identifies custom template definitions (`cvt_*`) not used by any variable, tag, or client.

### Select Unused Variables in GTM
Automatically navigates to the variables overview page and checks the checkboxes of all detected unused variables, making bulk cleanup straightforward. Handles pagination, batch selection, and GTM's AngularJS routing.

### Export Analysis Results
Downloads a `.txt` report containing all findings — unused variables, duplicate groups, and unused templates — along with the container name, workspace, and export date.

### Detached Window
Pop the extension out into a standalone window to keep analysis results visible while working in GTM.

### Tutorial
Built-in 8-step visual guide accessible via the **?** button in the header.

## Installation

1. Clone or download this repository
2. Open `chrome://extensions/` in Chrome
3. Enable **Developer mode** (toggle in the top-right corner)
4. Click **Load unpacked** and select the `chrome-extension` folder
5. Navigate to [tagmanager.google.com](https://tagmanager.google.com) to start using the extension

## How It Works

1. **Navigate** to your GTM container at [tagmanager.google.com](https://tagmanager.google.com)
2. **Export** your container data using GTM's Export Container feature (Admin > Export Container) or Preview JSON
3. The extension **intercepts** the export response automatically — look for the green checkmark badge
4. Click the extension icon and select the captured export from the dropdown
5. Click **Run Analysis** to detect unused variables, duplicates, and unused templates
6. Use **Select Unused Variables in GTM** to auto-check them in the GTM UI for deletion
7. Use **Export Analysis Results** to download a text report

## Architecture

The extension uses Chrome's Manifest V3 with a three-world content script model:

| Component | World | Purpose |
|-----------|-------|---------|
| `content-main.js` | MAIN | Intercepts XHR/fetch to GTM's `partialexport` API, handles in-page navigation and checkbox selection |
| `content.js` | ISOLATED | Bridges MAIN world data to Chrome extension APIs, manages storage |
| `background.js` | Service Worker | Badge updates and message routing |
| `popup.js` | Popup | UI controller, analysis orchestration, export |
| `analyzer.js` | Popup | Core analysis engine (unused, duplicates, templates) |

```
GTM Page
  └─ content-main.js (MAIN) ──postMessage──► content.js (ISOLATED)
                                                  │
                                      chrome.storage.local
                                                  │
                                    chrome.runtime.sendMessage
                                                  │
                              ┌────────────────────┴────────────────────┐
                              ▼                                         ▼
                      background.js                                popup.js
                      (badge updates)                          (UI + analyzer.js)
```

## Permissions

| Permission | Reason |
|------------|--------|
| `storage` + `unlimitedStorage` | Cache up to 20 GTM exports locally |
| `activeTab` | Detect whether the user is on a GTM page |
| `scripting` | Recover buffered exports after extension reloads |
| `host_permissions: tagmanager.google.com` | Intercept export API responses and interact with GTM UI |

## Files

```
chrome-extension/
├── manifest.json          # Extension configuration
├── popup.html             # Popup UI markup + tutorial
├── popup.js               # Popup controller
├── analyzer.js            # Analysis engine
├── background.js          # Service worker
├── content-main.js        # MAIN world interceptor
├── content.js             # ISOLATED world bridge
├── styles.css             # Popup styles
├── icons/                 # Extension icons (16, 48, 128px)
└── tutorial/              # Tutorial screenshot images
    ├── tutorial-step1.png
    ├── ...
    └── tutorial-step8.png
```

## Requirements

- Google Chrome (Manifest V3 compatible)
- Access to a Google Tag Manager container
- No external dependencies — the extension is fully self-contained
