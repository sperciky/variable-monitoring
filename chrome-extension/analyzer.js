/**
 * GTM Variable Analyzer — ported from gtm-analyzer.py
 *
 * Detects:
 *  1. Unused variables
 *  2. Duplicate variables
 *  3. Unused custom templates
 */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract {{Variable Name}} references from a string. */
function getVariableRefsInValue(value) {
  const refs = new Set();
  if (typeof value === "string") {
    const re = /\{\{([^}]+)\}\}/g;
    let m;
    while ((m = re.exec(value)) !== null) {
      refs.add(m[1]);
    }
  }
  return refs;
}

/** Recursively collect all {{…}} references inside any object/array/string. */
function getVariableRefsInObject(obj) {
  const refs = new Set();
  if (typeof obj === "string") {
    for (const r of getVariableRefsInValue(obj)) refs.add(r);
  } else if (Array.isArray(obj)) {
    for (const item of obj) {
      for (const r of getVariableRefsInObject(item)) refs.add(r);
    }
  } else if (obj && typeof obj === "object") {
    for (const val of Object.values(obj)) {
      for (const r of getVariableRefsInObject(val)) refs.add(r);
    }
  }
  return refs;
}

// ---------------------------------------------------------------------------
// Variable type display names
// ---------------------------------------------------------------------------
const VARIABLE_TYPE_NAMES = {
  v: "Data Layer Variable",
  k: "Cookie",
  u: "URL",
  f: "Referrer",
  e: "Event",
  j: "JavaScript Variable",
  jsm: "Custom JavaScript",
  d: "DOM Element",
  c: "Constant",
  gas: "Google Analytics Settings",
  r: "Random Number",
  aev: "Auto-Event Variable",
  vis: "Element Visibility",
  ctv: "Container Version",
  dbg: "Debug Mode",
  cid: "Container ID",
  hid: "HTML ID",
  smm: "Lookup Table",
  remm: "Regex Table",
  ed: "Event Data",
  t: "Environment Name",
  awec: "User Provided Data",
  uv: "Undefined Value",
  fs: "Firestore Lookup",
  rh: "Request Header",
  sgtmk: "Request - Cookie Value",
};

function getVariableTypeName(varType) {
  if (varType && varType.startsWith("cvt_")) return "Custom Template Variable";
  return VARIABLE_TYPE_NAMES[varType] || `Unknown (${varType})`;
}

// ---------------------------------------------------------------------------
// 1. Find unused variables
// ---------------------------------------------------------------------------
function findUnusedVariables(cv, includePausedTags = true) {
  const variables = cv.variable || [];
  const tags = cv.tag || [];
  const triggers = cv.trigger || [];
  const transformations = cv.transformation || [];
  const clients = cv.client || [];
  const customTemplates = cv.customTemplate || [];

  const referenced = new Set();

  const componentSets = [
    { type: "tag", list: tags },
    { type: "trigger", list: triggers },
    { type: "variable", list: variables },
    { type: "transformation", list: transformations },
    { type: "client", list: clients },
    { type: "customTemplate", list: customTemplates },
  ];

  for (const { type, list } of componentSets) {
    for (const component of list) {
      if (type === "tag" && component.paused && !includePausedTags) continue;

      const refs = getVariableRefsInObject(component);

      // Don't count self-references for variables
      if (type === "variable" && component.name) {
        refs.delete(component.name);
      }

      for (const r of refs) referenced.add(r);
    }
  }

  const unused = [];
  for (const v of variables) {
    if (!referenced.has(v.name)) {
      unused.push({
        name: v.name,
        variableId: v.variableId,
        type: v.type,
        typeName: getVariableTypeName(v.type),
      });
    }
  }
  return unused;
}

// ---------------------------------------------------------------------------
// 2. Find duplicate variables
// ---------------------------------------------------------------------------

function extractFormatValueInfo(fv) {
  if (!fv) return null;
  const info = {};
  const keys = [
    "convertNullToValue",
    "convertUndefinedToValue",
    "convertTrueToValue",
    "convertFalseToValue",
    "caseConversionType",
    "convertNaNToValue",
    "convertEmptyToValue",
  ];
  for (const k of keys) {
    if (k in fv) {
      const val = fv[k];
      info[k] = val && typeof val === "object" && "value" in val ? val.value : val;
    }
  }
  return Object.keys(info).length ? info : null;
}

function findDuplicateVariables(cv) {
  const variables = cv.variable || [];

  // category -> groupingKey -> [vars]
  const groups = {};

  for (const v of variables) {
    const varType = v.type;
    const params = v.parameter || [];
    const formatValue = v.formatValue || {};

    const keyInfo = {};
    for (const p of params) keyInfo[p.key] = p.value;

    const formatInfo = extractFormatValueInfo(formatValue);
    let category = null;
    let key = null;
    let extra = {};

    if (varType === "v" && "name" in keyInfo) {
      category = "data_layer_duplicates";
      key = `datalayer|${keyInfo.name}|v${keyInfo.dataLayerVersion || "2"}`;
      extra = { path: keyInfo.name, version: keyInfo.dataLayerVersion || "2", defaultValue: keyInfo.defaultValue || "" };
    } else if (varType === "ed" && "keyPath" in keyInfo) {
      category = "event_data_duplicates";
      key = `eventdata|${keyInfo.keyPath}`;
      extra = { keyPath: keyInfo.keyPath, defaultValue: keyInfo.defaultValue || "" };
    } else if (varType === "k" && "name" in keyInfo) {
      category = "cookie_duplicates";
      key = `cookie|${keyInfo.name}`;
      extra = { cookieName: keyInfo.name };
    } else if (varType === "j" && "name" in keyInfo) {
      category = "js_variable_duplicates";
      key = `jsvar|${keyInfo.name}`;
      extra = { jsVarName: keyInfo.name };
    } else if (varType === "u") {
      category = "url_duplicates";
      const component = keyInfo.component || "UNSPECIFIED";
      const queryKey = keyInfo.queryKey || "";
      const customUrlSource = keyInfo.customUrlSource || "";
      if (queryKey) {
        key = `url|${component}|${queryKey}`;
      } else if (customUrlSource) {
        key = `url|${component}|${customUrlSource}`;
      } else {
        key = `url|${component}`;
      }
      extra = { component, queryKey };
    } else if (varType && varType.startsWith("cvt_")) {
      const templateKeyParams = [];
      for (const p of ["queryParamName", "pageLocation", "keyPath", "name", "key"]) {
        if (p in keyInfo) templateKeyParams.push(`${p}:${keyInfo[p]}`);
      }
      if (templateKeyParams.length) {
        category = "custom_template_duplicates";
        key = `custom|${varType}|${templateKeyParams.sort().join("|")}`;
        extra = { parameters: keyInfo };
      }
    }

    if (category && key) {
      if (!groups[category]) groups[category] = {};
      if (!groups[category][key]) groups[category][key] = [];
      groups[category][key].push({
        name: v.name,
        variableId: v.variableId,
        type: varType,
        typeName: getVariableTypeName(varType),
        formatValue: formatInfo,
        ...extra,
      });
    }
  }

  // Collect only groups with > 1 variable
  const duplicates = {};
  for (const [cat, keyMap] of Object.entries(groups)) {
    duplicates[cat] = [];
    for (const vars of Object.values(keyMap)) {
      if (vars.length > 1) duplicates[cat].push(vars);
    }
  }
  return duplicates;
}

// ---------------------------------------------------------------------------
// 3. Find unused custom templates
// ---------------------------------------------------------------------------
function findUnusedCustomTemplates(cv) {
  const customTemplates = cv.customTemplate || [];
  const variables = cv.variable || [];
  const tags = cv.tag || [];
  const clients = cv.client || [];

  // Build template usage map: typeId -> info
  const templateUsage = {};

  for (const tpl of customTemplates) {
    const containerId = tpl.containerId || "";
    const templateId = tpl.templateId || "";
    const galleryRef = tpl.galleryReference || {};
    const galleryTemplateId = galleryRef.galleryTemplateId || "";
    const isGallery = !!galleryTemplateId;

    const templateType = `cvt_${containerId}_${templateId}`;

    // Parse templateData for category and ID
    const templateData = tpl.templateData || "";
    let templateCategory = "UNKNOWN";
    let templateDataId = null;

    if (typeof templateData === "string") {
      const typeMatch = templateData.match(/"type"\s*:\s*"(TAG|MACRO|CLIENT)"/);
      if (typeMatch) templateCategory = typeMatch[1];
      const idMatch = templateData.match(/"id"\s*:\s*"([^"]+)"/);
      if (idMatch) templateDataId = idMatch[1];
    }

    const info = {
      template: tpl,
      category: templateCategory,
      isGallery,
      galleryId: galleryTemplateId,
      used: false,
    };

    templateUsage[templateType] = info;

    if (galleryTemplateId) {
      const galleryType = `cvt_${galleryTemplateId}`;
      if (galleryType !== templateType) templateUsage[galleryType] = info;
    }

    if (templateDataId && templateDataId !== templateType) {
      templateUsage[templateDataId] = info;
    }
  }

  // Check variables (MACRO)
  for (const v of variables) {
    const vt = v.type || "";
    if (vt in templateUsage && templateUsage[vt].category === "MACRO") {
      templateUsage[vt].used = true;
    }
  }

  // Check tags (TAG)
  for (const tag of tags) {
    const tt = tag.type || "";
    if (tt in templateUsage && templateUsage[tt].category === "TAG") {
      templateUsage[tt].used = true;
    }
  }

  // Check clients (CLIENT)
  for (const client of clients) {
    const ct = client.type || "";
    if (ct in templateUsage && templateUsage[ct].category === "CLIENT") {
      templateUsage[ct].used = true;
    }
  }

  // Collect unused, dedup by fingerprint
  const seen = new Set();
  const unused = [];
  for (const [typeId, info] of Object.entries(templateUsage)) {
    if (!info.used) {
      const fp = info.template.fingerprint || "";
      if (!seen.has(fp)) {
        seen.add(fp);
        unused.push({
          name: info.template.name || "Unnamed Template",
          templateId: info.template.templateId || "",
          type: typeId,
          category: info.category,
          isGallery: info.isGallery,
          galleryId: info.galleryId,
          fingerprint: fp,
        });
      }
    }
  }
  return unused;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Run full analysis on a parsed GTM container JSON.
 * @param {object} gtmData - The parsed GTM export JSON (must contain containerVersion)
 * @param {boolean} includePausedTags - Whether to count paused-tag references
 * @returns {{ unusedVariables, duplicateVariables, unusedTemplates, summary }}
 */
function analyzeContainer(gtmData, includePausedTags = true) {
  const cv = gtmData.containerVersion || {};

  const unusedVariables = findUnusedVariables(cv, includePausedTags);
  const duplicateVariables = findDuplicateVariables(cv);
  const unusedTemplates = findUnusedCustomTemplates(cv);

  // Summary counts
  const totalVars = (cv.variable || []).length;
  const totalTags = (cv.tag || []).length;
  const totalTriggers = (cv.trigger || []).length;
  const totalTemplates = (cv.customTemplate || []).length;

  let totalDupGroups = 0;
  let totalDupVars = 0;
  for (const groups of Object.values(duplicateVariables)) {
    totalDupGroups += groups.length;
    for (const g of groups) totalDupVars += g.length;
  }

  return {
    unusedVariables,
    duplicateVariables,
    unusedTemplates,
    summary: {
      totalVariables: totalVars,
      totalTags,
      totalTriggers,
      totalCustomTemplates: totalTemplates,
      unusedVariableCount: unusedVariables.length,
      duplicateGroups: totalDupGroups,
      duplicateVariableCount: totalDupVars,
      unusedTemplateCount: unusedTemplates.length,
    },
  };
}

// Make available to other extension scripts
if (typeof window !== "undefined") {
  window.GTMAnalyzer = { analyzeContainer, getVariableTypeName };
}
