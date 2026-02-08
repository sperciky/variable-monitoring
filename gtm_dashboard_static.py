#!/usr/bin/env python3
"""
GTM Container Analysis Dashboard - Static HTML Generator
Generates a standalone HTML file that can be opened in any browser
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import json
import sys
from datetime import datetime
import os

# Color scheme
COLORS = {
    'primary': '#1f77b4',
    'success': '#2ca02c',
    'warning': '#ff7f0e',
    'danger': '#d62728',
    'info': '#17a2b8',
    'light': '#f8f9fa',
    'dark': '#343a40'
}

def load_analysis_data(filename):
    """Load the GTM analysis JSON report"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file. {e}")
        sys.exit(1)

def prepare_variable_impact_data(data):
    """Prepare variable impact data for visualization"""
    trigger_data = data.get('trigger_evaluation_impact', {})
    tag_data = data.get('tag_evaluation_impact', {})
    usage_counts = data.get('variable_usage_counts', {})
    
    combined = {}
    
    # Add trigger evaluation data
    for var, count in trigger_data.get('evaluations_by_variable', {}).items():
        combined[var] = {
            'triggers': count,
            'tags': 0,
            'total_evaluations': count,
            'locations': 0,
            'type': 'Unknown'
        }
    
    # Add tag evaluation data
    for var, count in tag_data.get('evaluations_by_variable', {}).items():
        if var in combined:
            combined[var]['tags'] = count
            combined[var]['total_evaluations'] += count
        else:
            combined[var] = {
                'triggers': 0,
                'tags': count,
                'total_evaluations': count,
                'locations': 0,
                'type': 'Unknown'
            }
    
    # Add usage location data and variable types
    for var, var_data in usage_counts.items():
        if var in combined:
            combined[var]['locations'] = var_data.get('evaluation_contexts', 0)
            combined[var]['type'] = get_variable_type_for_name(var, usage_counts)
        
    # For variables not in usage_counts, try to determine their type
    for var in combined:
        if combined[var]['type'] == 'Unknown':
            combined[var]['type'] = get_variable_type_for_name(var, usage_counts)
        
    return pd.DataFrame.from_dict(combined, orient='index').reset_index()

def get_variable_type_name(var_type):
    """Get human-readable variable type name"""
    type_names = {
        'v': 'Data Layer Variable',
        'k': 'Cookie',
        'u': 'URL',
        'f': 'Referrer',
        'e': 'Event',
        'j': 'JavaScript Variable',
        'jsm': 'Custom JavaScript',
        'd': 'DOM Element',
        'c': 'Constant',
        'gas': 'Google Analytics Settings',
        'r': 'Random Number',
        'aev': 'Auto-Event Variable',
        'vis': 'Element Visibility',
        'ctv': 'Container Version',
        'dbg': 'Debug Mode',
        'cid': 'Container ID',
        'hid': 'HTML ID',
        'smm': 'Lookup Table',
        'remm': 'Regex Table',
        'ed': 'Event Data',
        't': 'Environment Name',
        'awec': 'User Provided Data',
        'uv': 'Undefined Value',
        'fs': 'Firestore Lookup',
        'rh': 'Request Header'
    }
    
    if var_type.startswith('cvt_'):
        return 'Custom Template Variable'
    
    return type_names.get(var_type, f'Unknown ({var_type})')

def get_variable_type_for_name(var_name, usage_data):
    """Get the variable type display name for a given variable name"""
    # Check if we have the variable in usage data
    if var_name in usage_data:
        var_info = usage_data[var_name].get('variable', {})
        var_type = var_info.get('type', 'Unknown')
        return get_variable_type_name(var_type)
    
    # Check if it's a GTM internal variable
    gtm_internal_vars = {
        '_event': 'GTM Internal Variable',
        '_triggers_fired': 'GTM Internal Variable',
        '_tags_fired': 'GTM Internal Variable', 
        '_container': 'GTM Internal Variable',
        '_html_id': 'GTM Internal Variable',
        '_debug_mode': 'GTM Internal Variable',
        '_random': 'GTM Internal Variable',
        '_container_version': 'GTM Internal Variable'
    }
    
    if var_name in gtm_internal_vars:
        return gtm_internal_vars[var_name]
    elif var_name.startswith('_'):
        return 'GTM Internal Variable'
    
    # Check if it matches a known built-in variable name pattern
    builtin_name_map = {
        'Event Name': 'Built-in Variable',
        'Page URL': 'Built-in Variable',
        'Page Hostname': 'Built-in Variable', 
        'Page Path': 'Built-in Variable',
        'Referrer': 'Built-in Variable',
        'Click Element': 'Built-in Variable',
        'Click Classes': 'Built-in Variable',
        'Click ID': 'Built-in Variable',
        'Click URL': 'Built-in Variable',
        'Click Text': 'Built-in Variable',
        'Container ID': 'Built-in Variable',
        'Container Version': 'Built-in Variable',
        'Debug Mode': 'Built-in Variable',
        'Random Number': 'Built-in Variable',
        'HTML ID': 'Built-in Variable',
        'Environment Name': 'Built-in Variable',
        'Client Name': 'Built-in Variable',
        'Client ID': 'Built-in Variable',
        'IP Address': 'Built-in Variable',
        'User Agent': 'Built-in Variable',
        'Event': 'Built-in Variable',
        'Error Message': 'Built-in Variable',
        'Error Line': 'Built-in Variable',
        'Error URL': 'Built-in Variable',
        'Form Element': 'Built-in Variable',
        'Form Classes': 'Built-in Variable',
        'Form ID': 'Built-in Variable',
        'Form Target': 'Built-in Variable',
        'Form URL': 'Built-in Variable',
        'Form Text': 'Built-in Variable',
        'History Source': 'Built-in Variable',
        'New History Fragment': 'Built-in Variable',
        'New History State': 'Built-in Variable',
        'New History URL': 'Built-in Variable',
        'Old History Fragment': 'Built-in Variable',
        'Old History State': 'Built-in Variable',
        'Old History URL': 'Built-in Variable',
        'Video Current Time': 'Built-in Variable',
        'Video Duration': 'Built-in Variable',
        'Video Percent': 'Built-in Variable',
        'Video Provider': 'Built-in Variable',
        'Video Status': 'Built-in Variable',
        'Video Title': 'Built-in Variable',
        'Video URL': 'Built-in Variable',
        'Video Visible': 'Built-in Variable',
        'Scroll Depth Threshold': 'Built-in Variable',
        'Scroll Depth Units': 'Built-in Variable',
        'Scroll Direction': 'Built-in Variable',
        'Element Visibility Ratio': 'Built-in Variable',
        'Element Visibility Time': 'Built-in Variable',
        'Element Visibility First Time': 'Built-in Variable',
        'Element Visibility Recent Time': 'Built-in Variable',
        'Percent Visible': 'Built-in Variable',
        'On Screen Duration': 'Built-in Variable'
    }
    
    if var_name in builtin_name_map:
        return builtin_name_map[var_name]
    
    return 'Unknown'

def create_improvement_recommendations(data):
    """Generate actionable improvement recommendations"""
    recommendations = []
    
    # 1. Unused variables - SHOW ALL
    unused_vars = data.get('unused_variables', [])
    if unused_vars:
        items = [f"{var['name']} (ID: {var['variableId']}, Type: {var['type']})" 
                 for var in unused_vars]
        recommendations.append({
            'priority': 'HIGH',
            'category': 'Cleanup',
            'title': f'Remove {len(unused_vars)} Unused Variables',
            'impact': 'Reduces container size and complexity',
            'action': 'The following variables can be safely removed:',
            'items': items,  # Show ALL items
            'show_all': True
        })
    
    # 2. Unused custom templates - SHOW ALL
    unused_templates = data.get('unused_custom_templates', [])
    if unused_templates:
        # Filter to only show truly unused templates (not TAG or CLIENT templates in use)
        items = []
        for template in unused_templates:
            category = template.get('category', 'UNKNOWN')
            items.append(f"{template['name']} (ID: {template['templateId']}, Type: {category})")
        
        if items:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Cleanup',
                'title': f'Remove {len(items)} Unused Custom Templates',
                'impact': 'Reduces container complexity',
                'action': 'The following custom templates are not used:',
                'items': items,  # Show ALL items
                'show_all': True
            })
    
    # 3. Duplicate variables - SHOW ALL GROUPS
    duplicates = data.get('duplicate_variables', {})
    items = []
    total_duplicate_vars = 0
    
    # Count individual variables in duplicate groups
    for dup_type, groups in duplicates.items():
        if groups:
            for group in groups:
                total_duplicate_vars += len(group)
                vars_in_group = [var['name'] for var in group]
                # Clean up the duplicate type name
                clean_type = dup_type.replace('_duplicates', '').replace('_', ' ').title()
                items.append(f"{clean_type}: {', '.join(vars_in_group)}")
    
    if items:
        recommendations.append({
            'priority': 'MEDIUM',
            'category': 'Consolidation',
            'title': f'Consolidate {total_duplicate_vars} Duplicate Variables in {len(items)} Groups',
            'impact': 'Improves performance and reduces re-evaluations',
            'action': 'Review and consolidate these duplicate variable groups:',
            'items': items,  # Show ALL groups
            'show_all': True
        })
    
    # 4. High re-evaluation variables
    trigger_data = data.get('trigger_evaluation_impact', {})
    tag_data = data.get('tag_evaluation_impact', {})
    
    all_evals = {}
    for var, count in trigger_data.get('evaluations_by_variable', {}).items():
        all_evals[var] = count
    for var, count in tag_data.get('evaluations_by_variable', {}).items():
        all_evals[var] = all_evals.get(var, 0) + count
    
    high_eval_vars = [(var, count) for var, count in all_evals.items() if count > 100]
    if high_eval_vars:
        high_eval_vars.sort(key=lambda x: x[1], reverse=True)
        items = [f"{var} ({count} evaluations)" for var, count in high_eval_vars]
        recommendations.append({
            'priority': 'MEDIUM',
            'category': 'Performance',
            'title': f'Optimize {len(high_eval_vars)} High-Impact Variables',
            'impact': 'Significant performance improvement',
            'action': 'Consider caching or optimizing these frequently evaluated variables:',
            'items': items[:20],  # Show top 20 for performance
            'show_all': False
        })
        if len(high_eval_vars) > 20:
            recommendations[-1]['items'].append(f"... and {len(high_eval_vars) - 20} more high-impact variables")
    
    # 5. Container size warning
    total_vars = data.get('summary', {}).get('total_variables', 0)
    total_tags = data.get('summary', {}).get('total_tags', 0)
    
    if total_vars > 200 or total_tags > 100:
        recommendations.append({
            'priority': 'LOW',
            'category': 'Architecture',
            'title': 'Consider Container Split',
            'impact': 'Better maintainability and performance',
            'action': f'Your container has {total_vars} variables and {total_tags} tags.',
            'items': ['Consider splitting into multiple containers by function or domain'],
            'show_all': True
        })
    
    return recommendations

def calculate_health_score(data):
    """Calculate container health score (0-100)"""
    summary = data.get('summary', {})
    
    total_vars = summary.get('total_variables', 0)
    unused_vars = summary.get('unused_variables', 0)
    unused_ratio = unused_vars / total_vars if total_vars > 0 else 0
    
    score = 100
    score -= unused_ratio * 30
    score -= min(summary.get('duplicate_groups', 0) * 2, 20)
    
    if total_vars > 200:
        score -= 10
    if total_vars > 300:
        score -= 10
    
    return max(0, min(100, score))

def generate_static_dashboard(data, output_filename='gtm_dashboard.html'):
    """Generate a static HTML dashboard"""
    
    # Prepare data
    df_impact = prepare_variable_impact_data(data)
    df_impact.columns = ['Variable', 'Trigger Evals', 'Tag Evals', 'Total Evals', 'Locations', 'Type']
    df_impact = df_impact.sort_values('Total Evals', ascending=False)
    
    print(df_impact.head(20))
    
    recommendations = create_improvement_recommendations(data)
    health_score = calculate_health_score(data)
    
    # Summary data
    summary = data.get('summary', {})
    trigger_impact = data.get('trigger_evaluation_impact', {})
    tag_impact = data.get('tag_evaluation_impact', {})
    total_evaluations = trigger_impact.get('total_evaluations', 0) + tag_impact.get('total_evaluations', 0)
    
    # Create figures
    # 1. Variable Impact Bar Chart
    # Get top 20 variables
    df_top20 = df_impact.head(20)
    print(df_top20)
    
    fig_impact = px.bar(
        df_top20,
        x='Variable',
        y=['Trigger Evals', 'Tag Evals'],
        title='Top 20 Variables by Evaluation Impact',
        labels={'value': 'Evaluations', 'Variable': 'Variable Name'},
        color_discrete_map={'Trigger Evals': COLORS['primary'], 'Tag Evals': COLORS['warning']}
    )
    
    # Fix the x-axis ordering to match the dataframe order
    fig_impact.update_xaxes(
        categoryorder='array', 
        categoryarray=df_top20['Variable'].tolist()
    )
    
    fig_impact.update_layout(
        xaxis_tickangle=-45,
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    
    # 2. Variable Type Distribution
    type_counts = df_impact['Type'].value_counts()
    fig_types = px.pie(
        values=type_counts.values,
        names=type_counts.index,
        title='Variable Distribution by Type'
    )
    fig_types.update_layout(paper_bgcolor='white')
    
    # 3. Usage Status Donut Chart
    used_vars = summary.get('total_variables', 0) - summary.get('unused_variables', 0)
    unused_vars = summary.get('unused_variables', 0)
    
    fig_usage = go.Figure(data=[go.Pie(
        labels=['Used Variables', 'Unused Variables'],
        values=[used_vars, unused_vars],
        hole=.3,
        marker_colors=[COLORS['success'], COLORS['danger']]
    )])
    fig_usage.update_layout(
        title='Variable Usage Status',
        paper_bgcolor='white'
    )
    
    # 4. Health Score Gauge
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=health_score,
        title={'text': "Container Health Score"},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': COLORS['success'] if health_score >= 80 else COLORS['warning'] if health_score >= 60 else COLORS['danger']},
            'steps': [
                {'range': [0, 60], 'color': "lightgray"},
                {'range': [60, 80], 'color': "gray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    fig_gauge.update_layout(height=300, paper_bgcolor='white')
    
    # Create recommendations HTML
    recommendations_html = ""
    for rec in recommendations:
        priority_color = {'HIGH': 'danger', 'MEDIUM': 'warning', 'LOW': 'info'}[rec['priority']]
        
        # For long lists, create scrollable container
        if rec.get('show_all', False) and len(rec['items']) > 10:
            items_html = '<div class="recommendation-list" style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 4px;">'
            items_html += '<ul class="mb-0">'
            for item in rec['items']:
                items_html += f'<li>{item}</li>'
            items_html += '</ul></div>'
        else:
            items_html = '<ul class="mb-0">'
            for item in rec['items']:
                items_html += f'<li>{item}</li>'
            items_html += '</ul>'
        
        action_text = rec.get('action', '')
        if action_text:
            action_html = f'<p>{action_text}</p>'
        else:
            action_html = ''
        
        recommendations_html += f"""
        <div class="card mb-3 border-{priority_color}">
            <div class="card-body">
                <span class="badge badge-{priority_color} float-right">{rec['priority']}</span>
                <h5 class="card-title">{rec['title']}</h5>
                <p class="text-muted small">{rec['impact']}</p>
                {action_html}
                {items_html}
            </div>
        </div>
        """
    
    # Create high impact table
    table_data = df_impact.head(30)
    table_html = """
    <table class="table table-striped table-hover">
        <thead>
            <tr>
                <th>Variable</th>
                <th>Type</th>
                <th>Trigger Evals</th>
                <th>Tag Evals</th>
                <th>Total Evals</th>
            </tr>
        </thead>
        <tbody>
    """
    for _, row in table_data.iterrows():
        row_class = 'table-danger' if row['Total Evals'] > 1000 else 'table-warning' if row['Total Evals'] > 500 else ''
        table_html += f"""
            <tr class="{row_class}">
                <td>{row['Variable']}</td>
                <td>{row['Type']}</td>
                <td>{row['Trigger Evals']}</td>
                <td>{row['Tag Evals']}</td>
                <td><strong>{row['Total Evals']}</strong></td>
            </tr>
        """
    table_html += "</tbody></table>"
    
    # Generate HTML
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GTM Container Analysis Dashboard</title>
    <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            background-color: #f8f9fa;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        .metric-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
            margin-bottom: 20px;
        }}
        .metric-card h3 {{
            font-size: 2.5rem;
            margin: 10px 0;
            font-weight: 300;
        }}
        .metric-card p {{
            color: #6c757d;
            text-transform: uppercase;
            font-size: 0.875rem;
            letter-spacing: 0.5px;
            margin: 0;
        }}
        .card {{
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .card.border-danger {{ border-left: 4px solid #dc3545; }}
        .card.border-warning {{ border-left: 4px solid #ffc107; }}
        .card.border-info {{ border-left: 4px solid #17a2b8; }}
        .plotly-graph-div {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .badge {{ padding: 0.375rem 0.75rem; }}
        h1, h2 {{ color: #343a40; }}
        .table-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            overflow-x: auto;
        }}
        .recommendation-list {{
            font-size: 0.9rem;
        }}
        .recommendation-list ul {{
            padding-left: 20px;
        }}
        .recommendation-list li {{
            margin-bottom: 5px;
            line-height: 1.4;
        }}
        .card-columns {{
            column-count: 1;
        }}
        @media (min-width: 768px) {{
            .card-columns {{
                column-count: 2;
            }}
        }}
        @media (min-width: 1200px) {{
            .card-columns {{
                column-count: 3;
            }}
        }}
    </style>
</head>
<body>
    <div class="container-fluid mt-4">
        <h1 class="text-center mb-4">GTM Container Analysis Dashboard</h1>
        <p class="text-center text-muted">Analysis Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
        
        <!-- Summary Metrics -->
        <div class="row mt-4">
            <div class="col-md-3">
                <div class="metric-card">
                    <p>Total Variables</p>
                    <h3 class="text-primary">{summary.get('total_variables', 0)}</h3>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <p>Unused Variables</p>
                    <h3 class="text-danger">{summary.get('unused_variables', 0)}</h3>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <p>Total Tags</p>
                    <h3 class="text-info">{summary.get('total_tags', 0)}</h3>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <p>Total Evaluations</p>
                    <h3 class="text-warning">{total_evaluations:,}</h3>
                </div>
            </div>
        </div>
        
        <!-- Health Score -->
        <div class="row mt-4">
            <div class="col-12">
                <div id="healthGauge"></div>
            </div>
        </div>
        
        <!-- Improvement Recommendations -->
        <div class="row mt-4">
            <div class="col-12">
                <h2>Container Improvement Guide</h2>
                <div class="card-columns">
                    {recommendations_html}
                </div>
            </div>
        </div>
        
        <!-- Charts -->
        <div class="row mt-4">
            <div class="col-12">
                <div id="impactChart"></div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-md-6">
                <div id="usageChart"></div>
            </div>
            <div class="col-md-6">
                <div id="typesChart"></div>
            </div>
        </div>
        
        <!-- High Impact Variables Table -->
        <div class="row mt-4">
            <div class="col-12">
                <h2>High Impact Variables</h2>
                <div class="table-container">
                    {table_html}
                </div>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="row mt-5 mb-3">
            <div class="col-12 text-center text-muted">
                <hr>
                <p>Generated by GTM Container Analyzer | 
                   <a href="#" onclick="window.print()">Print Report</a> | 
                   <a href="#" onclick="downloadData()">Download JSON Data</a>
                </p>
            </div>
        </div>
    </div>
    
    <script>
        // Render charts
        Plotly.newPlot('healthGauge', {fig_gauge.to_json()});
        Plotly.newPlot('impactChart', {fig_impact.to_json()});
        Plotly.newPlot('usageChart', {fig_usage.to_json()});
        Plotly.newPlot('typesChart', {fig_types.to_json()});
        
        // Download function
        function downloadData() {{
            const data = {json.dumps(data, indent=2)};
            const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'gtm_analysis_data.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>
"""
    
    # Write to file
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(html_template)
    
    print(f"✅ Static dashboard generated: {output_filename}")
    print(f"📂 File location: {os.path.abspath(output_filename)}")
    print(f"🌐 Open in browser: file:///{os.path.abspath(output_filename).replace(os.sep, '/')}")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python gtm_dashboard_static.py <path_to_analysis_report.json> [output_filename.html]")
        sys.exit(1)
    
    # Load data
    input_filename = sys.argv[1]
    data = load_analysis_data(input_filename)
    
    # Generate output filename based on input filename
    if len(sys.argv) > 2:
        output_filename = sys.argv[2]
    else:
        # Extract base name without path and .json extension
        base_name = os.path.basename(input_filename)
        if base_name.endswith('_analysis_report.json'):
            # Remove _analysis_report.json suffix
            base_name = base_name[:-21]
        elif base_name.endswith('.json'):
            # Remove .json suffix
            base_name = base_name[:-5]
        
        # Create output filename as gtm_dashboard_<base_name>.html
        output_filename = f'gtm_dashboard_{base_name}.html'
    
    # Generate dashboard
    generate_static_dashboard(data, output_filename)

if __name__ == '__main__':
    main()