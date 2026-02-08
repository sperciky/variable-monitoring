#!/usr/bin/env python3
"""
GTM Container Analysis - Streamlit Dashboard
Upload a GTM export JSON, run analysis, and view interactive dashboard.

Usage:
    streamlit run gtm_streamlit_app.py
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import json
import re
import os
import importlib.util
from datetime import datetime

# ---------------------------------------------------------------------------
# Helper: import gtm-analyzer.py (hyphen in filename requires importlib)
# ---------------------------------------------------------------------------
@st.cache_resource
def _load_analyzer_module():
    analyzer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gtm-analyzer.py")
    spec = importlib.util.spec_from_file_location("gtm_analyzer", analyzer_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# ---------------------------------------------------------------------------
# Color scheme (same as static dashboard)
# ---------------------------------------------------------------------------
COLORS = {
    "primary": "#1f77b4",
    "success": "#2ca02c",
    "warning": "#ff7f0e",
    "danger": "#d62728",
    "info": "#17a2b8",
    "light": "#f8f9fa",
    "dark": "#343a40",
}

# ---------------------------------------------------------------------------
# Functions ported from gtm_dashboard_static.py
# ---------------------------------------------------------------------------
def get_variable_type_name(var_type: str) -> str:
    type_names = {
        "v": "Data Layer Variable",
        "k": "Cookie",
        "u": "URL",
        "f": "Referrer",
        "e": "Event",
        "j": "JavaScript Variable",
        "jsm": "Custom JavaScript",
        "d": "DOM Element",
        "c": "Constant",
        "gas": "Google Analytics Settings",
        "r": "Random Number",
        "aev": "Auto-Event Variable",
        "vis": "Element Visibility",
        "ctv": "Container Version",
        "dbg": "Debug Mode",
        "cid": "Container ID",
        "hid": "HTML ID",
        "smm": "Lookup Table",
        "remm": "Regex Table",
        "ed": "Event Data",
        "t": "Environment Name",
        "awec": "User Provided Data",
        "uv": "Undefined Value",
        "fs": "Firestore Lookup",
        "rh": "Request Header",
        "sgtmk": "Request - Cookie Value",
    }
    if var_type.startswith("cvt_"):
        return "Custom Template Variable"
    return type_names.get(var_type, f"Unknown ({var_type})")


_BUILTIN_NAMES = {
    "Event Name", "Page URL", "Page Hostname", "Page Path", "Referrer",
    "Click Element", "Click Classes", "Click ID", "Click URL", "Click Text",
    "Container ID", "Container Version", "Debug Mode", "Random Number",
    "HTML ID", "Environment Name", "Client Name", "Client ID", "IP Address",
    "User Agent", "Event", "Error Message", "Error Line", "Error URL",
    "Form Element", "Form Classes", "Form ID", "Form Target", "Form URL",
    "Form Text", "History Source", "New History Fragment", "New History State",
    "New History URL", "Old History Fragment", "Old History State",
    "Old History URL", "Video Current Time", "Video Duration", "Video Percent",
    "Video Provider", "Video Status", "Video Title", "Video URL",
    "Video Visible", "Scroll Depth Threshold", "Scroll Depth Units",
    "Scroll Direction", "Element Visibility Ratio", "Element Visibility Time",
    "Element Visibility First Time", "Element Visibility Recent Time",
    "Percent Visible", "On Screen Duration",
}


def get_variable_type_for_name(var_name: str, usage_data: dict) -> str:
    if var_name in usage_data:
        var_info = usage_data[var_name].get("variable", {})
        return get_variable_type_name(var_info.get("type", "Unknown"))
    if var_name.startswith("_"):
        return "GTM Internal Variable"
    if var_name in _BUILTIN_NAMES:
        return "Built-in Variable"
    return "Unknown"


def prepare_variable_impact_data(data: dict) -> pd.DataFrame:
    trigger_data = data.get("trigger_evaluation_impact", {})
    tag_data = data.get("tag_evaluation_impact", {})
    usage_counts = data.get("variable_usage_counts", {})

    combined = {}
    for var, count in trigger_data.get("evaluations_by_variable", {}).items():
        combined[var] = {"triggers": count, "tags": 0, "total_evaluations": count, "locations": 0, "type": "Unknown"}
    for var, count in tag_data.get("evaluations_by_variable", {}).items():
        if var in combined:
            combined[var]["tags"] = count
            combined[var]["total_evaluations"] += count
        else:
            combined[var] = {"triggers": 0, "tags": count, "total_evaluations": count, "locations": 0, "type": "Unknown"}
    for var in combined:
        if var in usage_counts:
            combined[var]["locations"] = usage_counts[var].get("evaluation_contexts", 0)
        combined[var]["type"] = get_variable_type_for_name(var, usage_counts)

    df = pd.DataFrame.from_dict(combined, orient="index").reset_index()
    df.columns = ["Variable", "Trigger Evals", "Tag Evals", "Total Evals", "Locations", "Type"]
    return df.sort_values("Total Evals", ascending=False)


def calculate_health_score(data: dict) -> float:
    summary = data.get("summary", {})
    total_vars = summary.get("total_variables", 0)
    unused_vars = summary.get("unused_variables", 0)
    unused_ratio = unused_vars / total_vars if total_vars > 0 else 0
    score = 100.0
    score -= unused_ratio * 30
    score -= min(summary.get("duplicate_groups", 0) * 2, 20)
    if total_vars > 200:
        score -= 10
    if total_vars > 300:
        score -= 10
    return max(0.0, min(100.0, score))


def create_improvement_recommendations(data: dict) -> list:
    recommendations = []

    # Unused variables
    unused_vars = data.get("unused_variables", [])
    if unused_vars:
        items = [f"{v['name']} (ID: {v['variableId']}, Type: {v['type']})" for v in unused_vars]
        recommendations.append({
            "priority": "HIGH", "category": "Cleanup",
            "title": f"Remove {len(unused_vars)} Unused Variables",
            "impact": "Reduces container size and complexity",
            "action": "The following variables can be safely removed:",
            "items": items,
        })

    # Unused custom templates
    unused_templates = data.get("unused_custom_templates", [])
    if unused_templates:
        items = [f"{t['name']} (ID: {t['templateId']}, Type: {t.get('category', 'UNKNOWN')})" for t in unused_templates]
        if items:
            recommendations.append({
                "priority": "HIGH", "category": "Cleanup",
                "title": f"Remove {len(items)} Unused Custom Templates",
                "impact": "Reduces container complexity",
                "action": "The following custom templates are not used:",
                "items": items,
            })

    # Duplicates
    duplicates = data.get("duplicate_variables", {})
    dup_items = []
    total_dup = 0
    for dup_type, groups in duplicates.items():
        for group in groups:
            total_dup += len(group)
            names = [v["name"] for v in group]
            clean_type = dup_type.replace("_duplicates", "").replace("_", " ").title()
            dup_items.append(f"{clean_type}: {', '.join(names)}")
    if dup_items:
        recommendations.append({
            "priority": "MEDIUM", "category": "Consolidation",
            "title": f"Consolidate {total_dup} Duplicate Variables in {len(dup_items)} Groups",
            "impact": "Improves performance and reduces re-evaluations",
            "action": "Review and consolidate these duplicate variable groups:",
            "items": dup_items,
        })

    # High re-evaluation
    trigger_data = data.get("trigger_evaluation_impact", {})
    tag_data = data.get("tag_evaluation_impact", {})
    all_evals = {}
    for var, count in trigger_data.get("evaluations_by_variable", {}).items():
        all_evals[var] = count
    for var, count in tag_data.get("evaluations_by_variable", {}).items():
        all_evals[var] = all_evals.get(var, 0) + count
    high_eval = sorted([(v, c) for v, c in all_evals.items() if c > 100], key=lambda x: x[1], reverse=True)
    if high_eval:
        items = [f"{v} ({c} evaluations)" for v, c in high_eval[:20]]
        if len(high_eval) > 20:
            items.append(f"... and {len(high_eval) - 20} more high-impact variables")
        recommendations.append({
            "priority": "MEDIUM", "category": "Performance",
            "title": f"Optimize {len(high_eval)} High-Impact Variables",
            "impact": "Significant performance improvement",
            "action": "Consider caching or optimizing these frequently evaluated variables:",
            "items": items,
        })

    # Container size
    total_vars = data.get("summary", {}).get("total_variables", 0)
    total_tags = data.get("summary", {}).get("total_tags", 0)
    if total_vars > 200 or total_tags > 100:
        recommendations.append({
            "priority": "LOW", "category": "Architecture",
            "title": "Consider Container Split",
            "impact": "Better maintainability and performance",
            "action": f"Your container has {total_vars} variables and {total_tags} tags.",
            "items": ["Consider splitting into multiple containers by function or domain"],
        })

    return recommendations


# ---------------------------------------------------------------------------
# Run analysis
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Running GTM analysis...")
def run_analysis(file_bytes: bytes, include_paused: bool) -> dict:
    gtm_data = json.loads(file_bytes)
    mod = _load_analyzer_module()
    analyzer = mod.GTMAnalyzer(gtm_data, include_paused_tags=include_paused)
    report = analyzer.generate_detailed_report()
    trigger_impact = analyzer.analyze_trigger_evaluation_impact()
    tag_impact = analyzer.analyze_tag_evaluation_impact()
    report["trigger_evaluation_impact"] = trigger_impact
    report["tag_evaluation_impact"] = tag_impact
    return report


# ---------------------------------------------------------------------------
# Dashboard rendering
# ---------------------------------------------------------------------------
def _esc_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_js(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


# JavaScript for clipboard copy — runs inside st.components.v1.html iframe
_COPY_JS = """\
<script>
function copyVar(text, el) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() {
            _ok(el);
        }).catch(function() { _fallbackCopy(text, el); });
    } else {
        _fallbackCopy(text, el);
    }
}
function _fallbackCopy(text, el) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px';
    document.body.appendChild(ta);
    ta.focus(); ta.select();
    try { document.execCommand('copy'); _ok(el); } catch(e) {}
    document.body.removeChild(ta);
}
function _ok(el) {
    el.textContent = '\\u2705';
    setTimeout(function(){ el.textContent = '\\ud83d\\udccb'; }, 1200);
}
// Auto-resize iframe to fit content
(function(){
    function resize(){
        try {
            if (window.frameElement)
                window.frameElement.style.height = document.documentElement.scrollHeight + 'px';
        } catch(e){}
    }
    resize(); setTimeout(resize, 50); setTimeout(resize, 200);
})();
</script>"""


def _render_copyable_html(body_html: str, fallback_height: int = 200):
    """Render HTML with working copy-to-clipboard JS via an iframe component."""
    import streamlit.components.v1 as stc
    page = (
        '<html><head><style>'
        'body{font-family:"Source Sans Pro",sans-serif;font-size:14px;'
        'margin:0;padding:0;color:#262730;}'
        '</style></head><body>'
        f'{body_html}{_COPY_JS}'
        '</body></html>'
    )
    stc.html(page, height=fallback_height, scrolling=False)


def _copy_span(name: str) -> str:
    """Render a variable name with an inline copy-to-clipboard icon."""
    h = _esc_html(name)
    j = _esc_js(name)
    clipboard_icon = "\U0001f4cb"
    return (
        f'<code style="background:#f0f2f6;padding:1px 6px;border-radius:4px;font-size:0.9em;">{h}</code>'
        f"<span onclick=\"copyVar('{j}',this)\""
        f' style="cursor:pointer;margin-left:3px;font-size:0.9em;user-select:none;"'
        f' title="Copy variable name">{clipboard_icon}</span>'
    )


def _make_copyable_item(item_text: str) -> str:
    """Convert a recommendation list item to HTML with copy icons next to variable names."""
    import re as _re

    # Pattern: "VarName (ID: 123, Type: v)" — unused vars / templates
    m = _re.match(r'^(.+?)\s*\(ID:\s*', item_text)
    if m:
        name = m.group(1).strip()
        rest = _esc_html(item_text[len(name):])
        return f"<li>{_copy_span(name)}{rest}</li>"

    # Pattern: "Type: name1, name2, name3" — duplicate groups
    m = _re.match(r'^([^:]+):\s*(.+)$', item_text)
    if m and ", " in m.group(2):
        prefix = _esc_html(m.group(1))
        names = [n.strip() for n in m.group(2).split(",")]
        names_html = ", ".join(_copy_span(n) for n in names)
        return f"<li>{prefix}: {names_html}</li>"

    # Pattern: "name (N evaluations)" — high-impact vars
    m = _re.match(r'^(.+?)\s*\(\d+\s+evaluations?\)', item_text)
    if m:
        name = m.group(1).strip()
        rest = _esc_html(item_text[len(name):])
        return f"<li>{_copy_span(name)}{rest}</li>"

    # Fallback — plain text (e.g. "... and N more", architectural advice)
    return f"<li>{_esc_html(item_text)}</li>"


def render_dashboard(data: dict):
    summary = data.get("summary", {})
    trigger_impact = data.get("trigger_evaluation_impact", {})
    tag_impact = data.get("tag_evaluation_impact", {})
    total_evaluations = trigger_impact.get("total_evaluations", 0) + tag_impact.get("total_evaluations", 0)

    # ---- Summary metrics row ----
    st.markdown("## Container Overview")
    cols = st.columns(4)
    cols[0].metric("Total Variables", summary.get("total_variables", 0))
    cols[1].metric("Unused Variables", summary.get("unused_variables", 0))
    cols[2].metric("Total Tags", f"{summary.get('total_tags', 0)}  ({summary.get('paused_tags', 0)} paused)")
    cols[3].metric("Total Evaluations", f"{total_evaluations:,}")

    extra = st.columns(4)
    extra[0].metric("Total Triggers", summary.get("total_triggers", 0))
    extra[1].metric("Duplicate Groups", summary.get("duplicate_groups", 0))
    extra[2].metric("Custom Templates", summary.get("total_custom_templates", 0))
    extra[3].metric("Built-in Variables", summary.get("total_builtin_variables", 0))

    # ---- Health score gauge ----
    health_score = calculate_health_score(data)
    bar_color = COLORS["success"] if health_score >= 80 else COLORS["warning"] if health_score >= 60 else COLORS["danger"]
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=health_score,
        title={"text": "Container Health Score"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": bar_color},
            "steps": [
                {"range": [0, 60], "color": "lightgray"},
                {"range": [60, 80], "color": "gray"},
            ],
            "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 90},
        },
    ))
    fig_gauge.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_gauge, width="stretch")

    # ---- Recommendations ----
    recommendations = create_improvement_recommendations(data)
    if recommendations:
        st.markdown("## Container Improvement Guide")
        for rec in recommendations:
            icon = {"HIGH": "\U0001f534", "MEDIUM": "\U0001f7e0", "LOW": "\U0001f535"}[rec["priority"]]
            with st.expander(f"{icon} [{rec['priority']}] {rec['title']} \u2014 {rec['impact']}", expanded=True):
                st.write(rec.get("action", ""))
                items_html = "<ul style='padding-left:20px;'>" + "".join(
                    _make_copyable_item(item) for item in rec["items"]
                ) + "</ul>"
                _render_copyable_html(items_html, fallback_height=len(rec["items"]) * 38 + 20)

    # ---- Charts ----
    st.markdown("## Variable Evaluation Impact")
    df_impact = prepare_variable_impact_data(data)

    # Top 20 bar chart
    df_top20 = df_impact.head(20)
    fig_impact = px.bar(
        df_top20, x="Variable", y=["Trigger Evals", "Tag Evals"],
        title="Top 20 Variables by Evaluation Impact",
        labels={"value": "Evaluations", "Variable": "Variable Name"},
        color_discrete_map={"Trigger Evals": COLORS["primary"], "Tag Evals": COLORS["warning"]},
    )
    fig_impact.update_xaxes(categoryorder="array", categoryarray=df_top20["Variable"].tolist())
    fig_impact.update_layout(
        xaxis_tickangle=-45, height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_impact, width="stretch")

    # Pie charts side-by-side
    col_a, col_b = st.columns(2)
    with col_a:
        used = summary.get("total_variables", 0) - summary.get("unused_variables", 0)
        unused = summary.get("unused_variables", 0)
        fig_usage = go.Figure(data=[go.Pie(
            labels=["Used Variables", "Unused Variables"],
            values=[used, unused], hole=0.3,
            marker_colors=[COLORS["success"], COLORS["danger"]],
        )])
        fig_usage.update_layout(title="Variable Usage Status", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_usage, width="stretch")

    with col_b:
        type_counts = df_impact["Type"].value_counts()
        fig_types = px.pie(values=type_counts.values, names=type_counts.index, title="Variable Distribution by Type")
        fig_types.update_layout(paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_types, width="stretch")

    # ---- Tag type statistics ----
    tag_stats = tag_impact.get("tag_type_statistics", {})
    if tag_stats:
        st.markdown("## Tag Type Statistics")
        rows = []
        for tag_type, stats in tag_stats.items():
            avg = stats["total_evaluations"] / stats["count"] if stats["count"] else 0
            rows.append({
                "Tag Type": tag_type,
                "Count": stats["count"],
                "Total Evaluations": stats["total_evaluations"],
                "Unique Variables": stats.get("unique_variables", 0),
                "Avg Evals / Tag": round(avg, 1),
            })
        df_tags = pd.DataFrame(rows).sort_values("Total Evaluations", ascending=False)
        st.dataframe(df_tags, hide_index=True, width="stretch")

    # ---- High impact variables table ----
    st.markdown("## High Impact Variables")
    df_table = df_impact.head(30)

    def color_evals(val):
        if isinstance(val, (int, float)):
            if val > 1000:
                return "background-color: #f8d7da"
            if val > 500:
                return "background-color: #fff3cd"
        return ""

    styled = df_table.style.map(color_evals, subset=["Total Evals"])
    st.dataframe(styled, hide_index=True, width="stretch")

    # ---- Unused variables detail ----
    unused_vars = data.get("unused_variables", [])
    if unused_vars:
        st.markdown("## Unused Variables Detail")
        # Build HTML table with copy icons next to variable names
        tbl = (
            '<table style="width:100%;border-collapse:collapse;font-size:0.9em;">'
            '<thead><tr style="border-bottom:2px solid #ddd;text-align:left;">'
            '<th style="padding:6px;">Name</th>'
            '<th style="padding:6px;">Variable ID</th>'
            '<th style="padding:6px;">Type</th>'
            '</tr></thead><tbody>'
        )
        for v in unused_vars:
            type_name = get_variable_type_name(v.get("type", ""))
            tbl += (
                f'<tr style="border-bottom:1px solid #eee;">'
                f'<td style="padding:6px;">{_copy_span(v["name"])}</td>'
                f'<td style="padding:6px;">{_esc_html(str(v.get("variableId", "")))}</td>'
                f'<td style="padding:6px;">{_esc_html(type_name)}</td>'
                f'</tr>'
            )
        tbl += '</tbody></table>'
        _render_copyable_html(tbl, fallback_height=len(unused_vars) * 36 + 50)

    # ---- Duplicate variables detail ----
    duplicates = data.get("duplicate_variables", {})
    has_dups = any(groups for groups in duplicates.values())
    if has_dups:
        st.markdown("## Duplicate Variables Detail")
        for dup_type, groups in duplicates.items():
            if not groups:
                continue
            clean_type = dup_type.replace("_duplicates", "").replace("_", " ").title()
            for i, group in enumerate(groups, 1):
                with st.expander(f"{clean_type} \u2014 Group {i}: {', '.join(v['name'] for v in group)}", expanded=True):
                    # Build HTML table with copy icons
                    cols = [k for k in group[0].keys() if k != "formatValue"]
                    header = "".join(f'<th style="padding:6px;text-align:left;">{_esc_html(c)}</th>' for c in cols)
                    rows = ""
                    for v in group:
                        cells = ""
                        for c in cols:
                            val = v.get(c, "")
                            if c == "name":
                                cells += f'<td style="padding:6px;">{_copy_span(str(val))}</td>'
                            else:
                                cells += f'<td style="padding:6px;">{_esc_html(str(val))}</td>'
                        rows += f'<tr style="border-bottom:1px solid #eee;">{cells}</tr>'
                    tbl = (
                        f'<table style="width:100%;border-collapse:collapse;font-size:0.9em;">'
                        f'<thead><tr style="border-bottom:2px solid #ddd;">{header}</tr></thead>'
                        f'<tbody>{rows}</tbody></table>'
                    )
                    _render_copyable_html(tbl, fallback_height=len(group) * 36 + 50)

    # ---- Download JSON report ----
    st.markdown("---")
    st.download_button(
        label="Download Full Analysis Report (JSON)",
        data=json.dumps(data, indent=2),
        file_name="gtm_analysis_report.json",
        mime="application/json",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="GTM Container Analyzer", page_icon="📊", layout="wide")
    st.title("📊 GTM Container Analysis Dashboard")

    # ---- Sidebar options ----
    with st.sidebar:
        st.header("Options")
        include_paused = not st.checkbox("Exclude paused tags", value=False)

    # ---- Step 1: Upload ----
    st.markdown("### Step 1: Upload the GTM Export File")
    uploaded = st.file_uploader(
        "Select a GTM container export JSON file",
        type=["json"],
        help="Export your container from GTM workspace and upload the .json file here.",
    )

    if uploaded is None:
        st.info("Upload a GTM container JSON export to get started.")
        return

    file_bytes = uploaded.getvalue()

    # Quick JSON sanity check
    try:
        preview = json.loads(file_bytes)
        if "containerVersion" not in preview:
            st.warning("This JSON does not appear to contain a `containerVersion` key. It may not be a valid GTM export.")
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON file: {exc}")
        return

    # ---- Step 2: Run Analysis ----
    st.markdown("### Step 2: Run Analysis")
    run_clicked = st.button("Run Analysis", type="primary")

    if run_clicked:
        st.session_state["report"] = run_analysis(file_bytes, include_paused)

    if "report" not in st.session_state:
        st.info("Click **Run Analysis** to start.")
        return

    # ---- Step 3: Dashboard ----
    st.markdown("---")
    render_dashboard(st.session_state["report"])


if __name__ == "__main__":
    main()
