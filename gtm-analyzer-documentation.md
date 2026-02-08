# GTM Analyzer - Project Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Core Capabilities](#core-capabilities)
3. [Development Journey](#development-journey)
4. [Usage Guide](#usage-guide)
5. [Technical Architecture](#technical-architecture)
6. [Output Examples](#output-examples)

## Project Overview

The GTM Analyzer is a Python tool designed to analyze Google Tag Manager (GTM) export files to identify:
- Unused variables
- Duplicate variables
- Unused custom templates
- Variable usage across all container components

It supports both web containers and server-side (SGTM) containers, providing comprehensive analysis for GTM container optimization and maintenance.

## Core Capabilities

### 1. Unused Variable Detection
- Identifies variables not referenced anywhere in the container
- Checks all component types: tags, triggers, variables, transformations, clients, and custom templates
- Includes variables used only in paused tags (configurable)
- Shows origin template for custom template variables

### 2. Duplicate Variable Detection
Identifies variables referencing the same data source:
- **Data Layer Variables**: Same path and version
- **Event Data Variables**: Same keyPath
- **Cookie Variables**: Same cookie name
- **JavaScript Variables**: Same JS variable path
- **URL Variables**: Same URL component
- **Custom Template Variables**: Same template and parameters

Shows formatValue differences between duplicates for informed decision-making.

### 3. Custom Template Analysis
- Detects unused custom templates (variable, tag, and client templates)
- Distinguishes between custom templates and gallery templates
- Tracks template usage across appropriate component types
- Shows which variables/tags/clients use each template

### 4. Comprehensive Variable Reference Detection
- Finds `{{Variable Name}}` patterns at any nesting level
- Checks within:
  - Tag parameters
  - Trigger conditions
  - Variable configurations
  - Transformation rules
  - Client settings
  - Custom template code (templateData)
  - Default values and format values

### 5. Variable Usage Location Counts
- Calculates how many times each variable is referenced in different component types
- Shows usage breakdown by component type (tags, triggers, variables, clients, transformations, templates)
- Counts total number of references across all components
- Includes component names (e.g., "Tags: 3 [GA4 - Purchase, GA4 - Page View, Custom HTML]")
- Helps identify heavily used variables and optimization opportunities

### 6. Re-evaluation Analysis
- **Phase 1 - Trigger Evaluation Impact**: Analyzes how many times variables need to be evaluated for triggers
  - Counts variable evaluations for all triggers attached to non-paused tags
  - Shows recursive evaluation counts (variables referencing other variables)
  - Breaks down by variable type and tag type
- **Phase 2 - Tag Evaluation Impact**: Analyzes variable evaluations within tags
  - Includes transformations and custom template processing
  - Tracks direct and recursive variable references
  - Provides tag-by-tag evaluation counts
- **Combined Report**: Shows total evaluations from both triggers and tags

### 7. Dashboard Visualization
- Interactive Plotly dashboard for analysis results
- Static HTML generator for offline viewing
- Visual representations include:
  - Container health score gauge
  - Variable impact bar charts
  - Usage distribution pie charts
  - Evaluation heatmaps
- Improvement recommendations with priority levels
- Export functionality for detailed reports

### 8. Unknown Type Detection
- **NEW**: Automatically tracks component types without translations
- Logs unknown tag, variable, trigger, and client types
- Provides formatted output ready for adding to translation dictionaries
- Helps maintain complete type coverage as GTM adds new features

### 9. Container Type Support
- **Web Containers**: Full support for all standard components
- **Server-Side Containers**: Includes transformations, clients, and server-specific features
- Automatic detection of container type

## Development Journey

### Phase 1: Basic Foundation
**Initial Goal**: Find unused variables in web containers

**Implementation**:
- Created recursive parser for finding `{{Variable}}` references
- Built basic structure for loading GTM exports
- Initial support for tags and triggers only

**Challenge**: Variables were incorrectly marked as unused when referenced in nested structures

### Phase 2: Comprehensive Coverage
**Goal**: Check all possible locations for variable references

**Added**:
- Support for transformations (server-side)
- Support for custom templates
- Support for clients (server-side)
- Recursive checking of all nested structures

**Key Learning**: Variables can be referenced anywhere, not just in obvious places

### Phase 3: Paused Tag Handling
**Challenge**: Variables used only in paused tags were marked as unused

**Solution**:
- Default includes paused tags (important for maintenance)
- Added `--exclude-paused` option for flexibility
- Clear marking of paused tags in output

**Rationale**: Removing variables breaks paused tags when re-enabled

### Phase 4: Duplicate Detection Enhancement
**Initial**: Only checked data layer variables

**Expanded to**:
- Event Data variables
- Cookie variables
- JavaScript variables
- URL variables
- Custom template variables

**Added**: formatValue comparison to show differences between duplicates

### Phase 5: Custom Template Support
**Challenge**: Custom templates weren't properly detected as used/unused

**Discoveries**:
- Templates can be for variables (MACRO), tags (TAG), or clients (CLIENT)
- Gallery templates use different ID patterns
- Some templates have placeholder IDs in templateData

**Solution**: Parse templateData to determine type and proper ID handling

### Phase 6: Template Variable References
**Final Enhancement**: Check for variable references within custom template code

**Implementation**:
- Parse templateData string for `{{Variable}}` patterns
- Track which templates use which variables
- Show template origin for unused custom template variables

### Phase 7: Variable Usage Location Counts
**Enhancement**: Count variable usage by component type with component names

**Goal**: Provide detailed analytics on where and how often variables are used

**Implementation**:
- Count usage in each component type (tags, triggers, etc.)
- Track total reference count across all components
- Include component names alongside counts
- Sort variables by usage frequency in report

### Phase 8: Re-evaluation Analysis
**Goal**: Understand performance impact of variable evaluations

**Phase 1 - Trigger Impact**:
- Analyze triggers attached to non-paused tags
- Count direct and recursive variable evaluations
- Group by variable type and tag type

**Phase 2 - Tag Impact**:
- Process tags, transformations, and custom templates
- Track evaluation counts per tag
- Include custom template variable processing

**Result**: Complete picture of variable evaluation overhead

### Phase 9: Dashboard Development
**Challenge**: Make analysis results accessible to non-technical users

**Solutions**:
- Created Plotly Dash interactive dashboard
- Added static HTML generator for portability
- Implemented visual health scoring
- Added prioritized improvement recommendations

**Key Features**:
- No server required for static version
- Complete lists of items to remove (no truncation)
- Proper duplicate counting (individual variables, not groups)

### Phase 10: Gallery Template Support
**Discovery**: Gallery templates use different ID patterns

**Example**: `"type": "cvt_WVXBK"` with `"galleryTemplateId": "WVXBK"`

**Solution**: Updated template detection to handle both patterns:
- Standard: `cvt_<containerId>_<templateId>`
- Gallery: `cvt_<galleryTemplateId>`

### Phase 11: Unknown Type Logging
**Latest Enhancement**: Track component types needing translation

**Implementation**:
- Added tracking sets for unknown types
- Log types in get_*_type_name() methods
- Print formatted report at end of analysis
- Include in JSON output under `unknown_types`

## Usage Guide

### Basic Usage
```bash
python gtm_analyzer.py <path_to_gtm_export.json>
```

### Command Line Options
```bash
# Show debug information with detailed usage tracking
python gtm_analyzer.py export.json --debug

# Exclude paused tags from analysis
python gtm_analyzer.py export.json --exclude-paused

# Combine options
python gtm_analyzer.py export.json --debug --exclude-paused
```

### Output Files
- Console report (human-readable)
- JSON report file: `<filename>_analysis_report.json`

## Technical Architecture

### Main Components

#### 1. GTMAnalyzer Class
Core analyzer with methods for:
- `find_unused_variables()` - Main unused variable detection
- `find_duplicate_variables()` - Duplicate detection across all types
- `find_unused_custom_templates()` - Template usage analysis (supports gallery templates)
- `get_variable_references_in_object()` - Recursive reference finder
- `get_variable_usage_counts()` - Count usage by component type with names
- `count_variable_occurrences_in_object()` - Count total references
- `analyze_trigger_evaluation_impact()` - Phase 1 re-evaluation analysis
- `analyze_tag_evaluation_impact()` - Phase 2 re-evaluation analysis
- `get_all_variable_references_recursive()` - Recursive variable dependency resolution
- `get_tag_type_name()` - Human-readable tag type with unknown tracking
- `get_variable_type_name()` - Human-readable variable type with unknown tracking
- `get_trigger_type_name()` - Human-readable trigger type with unknown tracking
- `get_client_type_name()` - Human-readable client type with unknown tracking
- `print_unknown_types_report()` - Display unknown types needing translation

#### 2. Detection Logic
```python
# Recursive variable reference detection
def get_variable_references_in_object(self, obj):
    if isinstance(obj, str):
        # Extract {{Variable Name}} patterns
    elif isinstance(obj, dict):
        # Recursively check all values
    elif isinstance(obj, list):
        # Check all list items
```

#### 3. Template ID Handling
- Custom templates: `cvt_<containerId>_<templateId>`
- Gallery templates: `cvt_<code>` (e.g., `cvt_WVXBK`)
- Placeholder IDs ignored (e.g., `cvt_temp_public_id`)

## Output Examples

### Summary Section
```
SUMMARY:
  Container Type: Server-side
  Total Variables: 150
  Total Tags: 100 (15 paused)
  Paused Tags Included: Yes
  Total Triggers: 50
  Total Transformations: 10
  Total Custom Templates: 20
  Unused Variables: 25
  Unused Custom Templates: 3
  Duplicate Groups: 5
  Total Duplicate Variables: 12
```

### Unused Variables
```
UNUSED VARIABLES:
--------------------------------------------------------------------------------

  STANDARD VARIABLES:
    - ED - item_name (ID: 459, Type: ed)
    - CONST - API Key (ID: 282, Type: c)

  CUSTOM TEMPLATE VARIABLES:
    - Bot-score (ID: 404, Type: cvt_55831269_403) [Template: Bot Detection]
    - Cookie Parser (ID: 482, Type: cvt_55831269_481) [Template: Cookie Reader]
```

### Duplicate Variables
```
EVENT DATA VARIABLE DUPLICATES:

  Duplicate Group 1 (Key Path: 'x-ga-mp1-heureka_gtm_ga_info'):
    - UA - session id (ID: 84)
      Default: {{= undefined}}
      Format Value Options:
        - Convert undefined to: {{Fallback Value}}
    - ED - cookies.heureka_gtm_ga_info (ID: 946)
      Default: No default
```

### Unused Custom Templates
```
UNUSED CUSTOM TEMPLATES:
--------------------------------------------------------------------------------

  CUSTOM TEMPLATES:
    
    Variable Templates:
      - Query Parser (Template ID: 123, Type: cvt_55831269_123)
    
    Tag Templates:
      - Custom Pixel (Template ID: 456, Type: cvt_55831269_456)

  GALLERY TEMPLATES:
    
    Variable Templates:
      - Unused Gallery Tool (Type: cvt_ABCDE)
```

### Variable Usage Location Counts
```
VARIABLE USAGE LOCATION COUNTS:
--------------------------------------------------------------------------------

  Variable: ED - page_type1 (ed)
    - Tags: 1 [GA4 - Purchase]
    - Triggers: 3 [Event - Purchase Page Type PD, Event - Cart Page Type, Event - Checkout Page Type]
    - Custom Template Variables: 3 [Product Data Parser, Cart Validator, Checkout Handler]
    - Clients: 1 [Main HTTP Client]
    - Transformations: 1 [Normalize Page Type]
    Total References: 9

  Variable: Page URL (u)
    - Tags: 15 [GA4 - Page View, GA4 - Scroll, GA4 - Time on Page, ... and 12 more]
    - Triggers: 8 [All Pages, Product Pages, Category Pages, ... and 5 more]
    Total References: 23

  ... and 47 more variables with usage
```

### Re-evaluation Analysis
```
TRIGGER EVALUATION IMPACT
================================================================================

SUMMARY:
  Triggers Analyzed: 45 (attached to non-paused tags)
  Total Variable Evaluations: 523

VARIABLE TYPE BREAKDOWN:
  Data Layer Variable: 245 evaluations
  Constant: 120 evaluations
  Event Data Variable: 98 evaluations
  Custom Template Variable: 60 evaluations

TAG TYPE BREAKDOWN (tags using these triggers):
  Google Analytics: GA4: 65 tags
  Custom HTML: 23 tags
  Google Ads Conversion: 15 tags

================================================================================
TAG EVALUATION IMPACT
================================================================================

SUMMARY:
  Tags Analyzed: 85 (non-paused tags)
  Total Variable Evaluations: 1,247
  Custom Template Tags Processed: 12
  Transformations Processed: 8

TAG TYPE STATISTICS:
  Google Analytics: GA4 - 35 tags, 523 evaluations
  Custom HTML - 20 tags, 412 evaluations
  Custom Template Tag - 12 tags, 198 evaluations

================================================================================
COMBINED TOTALS:
Grand Total Variable Evaluations: 1,770
  From Triggers: 523 (29.5%)
  From Tags: 1,247 (70.5%)
```

### Unknown Types Report
```
🔍 UNKNOWN VARIABLE TYPES FOUND (Add to translations):
--------------------------------------------------
  'awec': 'Description Here',
  'fs': 'Description Here',
  'rh': 'Description Here',
  'uv': 'Description Here',

🔍 UNKNOWN TAG TYPES FOUND (Add to translations):
--------------------------------------------------
  'googtag': 'Description Here',

✅ All component types have translations!
```

## Key Features Summary

1. **Comprehensive Detection**: Checks every possible location for variable references
2. **Smart Template Handling**: Properly identifies custom vs gallery templates
3. **Detailed Reporting**: Shows exactly where variables are used and why they're duplicates
4. **Maintenance-Friendly**: Considers paused tags by default
5. **Debug Support**: Extensive debugging output for troubleshooting
6. **Format Value Awareness**: Shows transformation differences in duplicates
7. **Template Origin Tracking**: Shows which template created unused variables
8. **Usage Analytics**: Shows usage counts by component type with component names
9. **Re-evaluation Analysis**: Complete trigger and tag evaluation impact analysis
10. **Dashboard Support**: Interactive and static HTML dashboards for results
11. **Gallery Template Support**: Handles both custom and gallery template ID patterns
12. **Unknown Type Tracking**: Automatically logs types needing translation
13. **Performance Insights**: Shows where variables are evaluated most frequently

## Limitations

1. Cannot detect dynamic variable references (e.g., string concatenation)
2. Cannot know if variables are used by external systems
3. Static analysis only - no runtime information
4. No optimization for extremely large containers (loads entire JSON)

## Conclusion

The GTM Analyzer evolved from a simple unused variable finder to a comprehensive container analysis tool. Through iterative development and addressing real-world edge cases, it now provides reliable detection of unused resources and duplicates across all GTM container types. The tool significantly simplifies GTM container maintenance and optimization tasks.