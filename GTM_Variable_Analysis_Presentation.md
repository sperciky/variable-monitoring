# GTM Variable Analysis & Optimization
## 20-Minute Presentation Structure

---

## 🎯 Presentation Overview (1 minute)

**Title:** "GTM Variable Analysis: Finding Dependencies, Duplicates, and Performance Bottlenecks"

**Key Takeaways:**
- How to analyze GTM variable usage programmatically
- Identify unused variables and duplicates
- Measure performance impact through re-evaluation analysis
- Actionable optimization strategies

---

## 📊 Part 1: The Problem (3 minutes)

### Why Variable Analysis Matters

**Common GTM Container Issues:**
- 🗑️ **Unused Variables** accumulating over time (20-30% typical)
- 🔄 **Duplicate Variables** referencing same data
- 🐌 **Performance Impact** from excessive re-evaluations
- 📈 **Container Bloat** affecting load times

**Real Example:**
```
Container Stats:
- 150 total variables
- 35 unused (23%)
- 12 duplicates
- Some variables evaluated 400+ times per page
```

**Impact:**
- Slower page load times
- Harder maintenance
- Increased debugging complexity
- Risk of errors

---

## 🔍 Part 2: Understanding GTM Export Structure (4 minutes)

### GTM JSON Export Anatomy

**Key Structure:**
```json
{
  "containerVersion": {
    "variable": [...],      // All variables
    "tag": [...],          // All tags
    "trigger": [...],      // All triggers
    "customTemplate": [...] // Custom templates
  }
}
```

### Variable Reference Pattern

**How GTM References Variables:**
```json
{
  "parameter": [
    {
      "key": "eventName",
      "value": "{{Event Name}}"  // Variable reference
    }
  ]
}
```

**Key Pattern:** `{{Variable Name}}` anywhere in the JSON

### Where Variables Hide

1. **Direct References:**
   - Tag parameters
   - Trigger conditions
   - Variable definitions

2. **Nested References:**
   - Custom JavaScript
   - Lookup/Regex tables
   - Default values
   - Format values

3. **Hidden References:**
   - Custom template code (`templateData`)
   - Transformation rules
   - Client configurations (SGTM)

---

## 🛠️ Part 3: Analysis Approach (5 minutes)

### Step 1: Recursive Variable Detection

**Core Algorithm:**
```python
def find_variable_references(obj):
    # Recursively search for {{Variable}} pattern
    if isinstance(obj, str):
        return re.findall(r'\{\{([^}]+)\}\}', obj)
    elif isinstance(obj, dict):
        # Check all values
    elif isinstance(obj, list):
        # Check all items
```

### Step 2: Usage Mapping

**Track Where Each Variable is Used:**
```python
usage_map = {
  "Page URL": {
    "tags": ["GA4 - Page View", "GA4 - Scroll"],
    "triggers": ["All Pages", "Product Pages"],
    "variables": ["Page Path"],
    "total_references": 23
  }
}
```

### Step 3: Re-evaluation Analysis

**Count How Many Times Variables Execute:**

1. **Trigger Evaluation:**
   - Variable in trigger → evaluated for each tag using trigger
   - Example: `{{Page Type}}` in 5 triggers → 45 evaluations

2. **Tag Evaluation:**
   - Direct usage in tags
   - Custom template processing
   - Transformation chains

### Step 4: Duplicate Detection

**Identify Variables with Same Data Source:**
```python
# Example duplicates:
"Cookie - User ID": {"cookie": "uid"}
"User Cookie": {"cookie": "uid"}
# Both read same cookie!
```

---

## 📈 Part 4: Analysis Results & Dashboard (4 minutes)

### Static HTML Dashboard Features

**1. Container Health Score**
- Overall health rating (0-100)
- Based on: unused ratio, duplicates, size

**2. Visual Analytics**
- Bar chart: Most evaluated variables
- Pie charts: Usage distribution
- Heatmap: Evaluation patterns

**3. Actionable Recommendations**

**HIGH Priority (Red):**
- Remove 25 unused variables
- Remove 3 unused custom templates

**MEDIUM Priority (Orange):**
- Consolidate 7 duplicate variables
- Optimize 5 high-impact variables

**LOW Priority (Blue):**
- Architecture improvements
- Container splitting suggestions

### Key Metrics Display

```
Summary:
- Total Variables: 150
- Unused: 35 (23%)
- Duplicates: 12 (8%)
- Total Evaluations: 1,770 per page
  - From Triggers: 523 (29.5%)
  - From Tags: 1,247 (70.5%)
```

---

## 💡 Part 5: Optimization Strategies (3 minutes)

### 1. Remove Unused Variables

**Safe Removal Process:**
1. Export container backup
2. Remove variables with 0 references
3. Test in Preview mode
4. Publish with confidence

**Impact:** Reduces container size by ~20%

### 2. Consolidate Duplicates

**Example:**
```
Before: 3 variables reading same cookie
After: 1 variable referenced by all
Result: 67% reduction in cookie reads
```

### 3. Cache Heavy Custom Templates

**For Variables Evaluated 100+ Times:**
```javascript
// Before: Complex calculation every time
function() {
  return complexCalculation();
}

// After: Cache result
function() {
  if (!window.myCache) {
    window.myCache = complexCalculation();
  }
  return window.myCache;
}
```

**Performance Gain:** 10-50ms per page

### 4. Variable Architecture

**Best Practices:**
- Group related variables
- Use consistent naming
- Document dependencies
- Regular audits (monthly)

---

## 🎯 Key Takeaways & Demo (2-3 minutes)

### Tools Provided

1. **GTM Analyzer (`gtm-analyzer.py`)**
   - Complete variable analysis
   - Re-evaluation counting
   - Duplicate detection

2. **Static Dashboard (`gtm_dashboard_static.py`)**
   - No server required
   - Shareable HTML file
   - Visual insights

3. **Dependency Graph (`gtm_dependency_graph.py`)**
   - Network visualization
   - Impact analysis

### Quick Demo

```bash
# 1. Export GTM container (JSON)

# 2. Run analysis
python gtm-analyzer.py container_export.json

# 3. Generate dashboard
python gtm_dashboard_static.py container_export_analysis_report.json

# 4. Open dashboard in browser
```

### Results You Can Expect

- **20-30% container size reduction**
- **Faster page loads** (50-200ms improvement)
- **Easier maintenance** and debugging
- **Clear optimization roadmap**

---

## 📋 Q&A Topics to Prepare

1. **How to handle paused tags?**
   - Include by default (they might be re-enabled)

2. **What about external dependencies?**
   - Manual review needed
   - Document external systems

3. **Automation possibilities?**
   - CI/CD integration
   - Scheduled audits
   - GTM API automation

4. **Custom template handling?**
   - Special parsing for templateData
   - Gallery vs custom templates

5. **Server-side containers?**
   - Full support for clients, transformations
   - Same analysis approach

---

## 🎤 Presentation Tips

1. **Start with Impact** - Show real numbers from actual container
2. **Live Examples** - Show actual JSON snippets
3. **Visual Focus** - Use dashboard screenshots
4. **Practical Takeaways** - Provide scripts and process

**Time Management:**
- 1 min: Introduction
- 3 min: Problem statement
- 4 min: Technical explanation
- 5 min: Solution approach
- 4 min: Results & dashboard
- 3 min: Optimization strategies
- Allow overflow for Q&A

**Key Message:** "Variable hygiene is not just cleanup - it's performance optimization and risk reduction"