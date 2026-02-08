#!/usr/bin/env python3
"""
GTM Container Analysis Dashboard
Interactive dashboard for visualizing GTM container analysis results
"""

import dash
from dash import dcc, html, dash_table, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import json
import sys
from datetime import datetime

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
    
    # Combine all data sources
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
            var_type = var_data.get('variable', {}).get('type', 'Unknown')
            combined[var]['type'] = get_variable_type_name(var_type)
        
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
        'ed': 'Event Data',
        't': 'Environment Name'
    }
    
    if var_type.startswith('cvt_'):
        return 'Custom Template Variable'
    
    return type_names.get(var_type, f'Unknown ({var_type})')

def create_improvement_recommendations(data):
    """Generate actionable improvement recommendations"""
    recommendations = []
    
    # 1. Unused variables
    unused_vars = data.get('unused_variables', [])
    if unused_vars:
        rec = {
            'priority': 'HIGH',
            'category': 'Cleanup',
            'title': f'Remove {len(unused_vars)} Unused Variables',
            'impact': 'Reduces container size and complexity',
            'action': 'The following variables can be safely removed:',
            'items': [f"• {var['name']} (ID: {var['variableId']}, Type: {var['type']})" 
                     for var in unused_vars[:10]]  # Show first 10
        }
        if len(unused_vars) > 10:
            rec['items'].append(f"• ... and {len(unused_vars) - 10} more variables")
        recommendations.append(rec)
    
    # 2. Unused custom templates
    unused_templates = data.get('unused_custom_templates', [])
    if unused_templates:
        rec = {
            'priority': 'HIGH',
            'category': 'Cleanup',
            'title': f'Remove {len(unused_templates)} Unused Custom Templates',
            'impact': 'Reduces container complexity',
            'action': 'The following custom templates can be removed:',
            'items': [f"• {template['name']} (ID: {template['templateId']})" 
                     for template in unused_templates]
        }
        recommendations.append(rec)
    
    # 3. Duplicate variables
    duplicates = data.get('duplicate_variables', {})
    total_duplicates = sum(len(groups) for groups in duplicates.values() if groups)
    if total_duplicates > 0:
        rec = {
            'priority': 'MEDIUM',
            'category': 'Consolidation',
            'title': f'Consolidate {total_duplicates} Duplicate Variables',
            'impact': 'Improves performance and reduces re-evaluations',
            'action': 'Review and consolidate these duplicate variable groups:',
            'items': []
        }
        
        for dup_type, groups in duplicates.items():
            if groups:
                for group in groups[:3]:  # Show first 3 groups
                    vars_in_group = [var['name'] for var in group]
                    rec['items'].append(f"• {dup_type}: {', '.join(vars_in_group)}")
        recommendations.append(rec)
    
    # 4. High re-evaluation variables
    trigger_data = data.get('trigger_evaluation_impact', {})
    tag_data = data.get('tag_evaluation_impact', {})
    
    # Combine evaluations
    all_evals = {}
    for var, count in trigger_data.get('evaluations_by_variable', {}).items():
        all_evals[var] = count
    for var, count in tag_data.get('evaluations_by_variable', {}).items():
        all_evals[var] = all_evals.get(var, 0) + count
    
    high_eval_vars = [(var, count) for var, count in all_evals.items() if count > 100]
    if high_eval_vars:
        high_eval_vars.sort(key=lambda x: x[1], reverse=True)
        rec = {
            'priority': 'MEDIUM',
            'category': 'Performance',
            'title': f'Optimize {len(high_eval_vars)} High-Impact Variables',
            'impact': 'Significant performance improvement',
            'action': 'Consider caching or optimizing these frequently evaluated variables:',
            'items': [f"• {var} ({count} evaluations)" 
                     for var, count in high_eval_vars[:5]]
        }
        recommendations.append(rec)
    
    # 5. Container size warning
    total_vars = data.get('summary', {}).get('total_variables', 0)
    total_tags = data.get('summary', {}).get('total_tags', 0)
    
    if total_vars > 200 or total_tags > 100:
        rec = {
            'priority': 'LOW',
            'category': 'Architecture',
            'title': 'Consider Container Split',
            'impact': 'Better maintainability and performance',
            'action': f'Your container has {total_vars} variables and {total_tags} tags.',
            'items': ['• Consider splitting into multiple containers by function or domain']
        }
        recommendations.append(rec)
    
    return recommendations

def create_dashboard(data):
    """Create the Dash application"""
    app = dash.Dash(__name__, external_stylesheets=[
        'https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'
    ])
    
    # Prepare data
    df_impact = prepare_variable_impact_data(data)
    df_impact.columns = ['Variable', 'Trigger Evals', 'Tag Evals', 'Total Evals', 'Locations', 'Type']
    df_impact = df_impact.sort_values('Total Evals', ascending=False)
    
    recommendations = create_improvement_recommendations(data)
    
    # Calculate summary metrics
    summary = data.get('summary', {})
    trigger_impact = data.get('trigger_evaluation_impact', {})
    tag_impact = data.get('tag_evaluation_impact', {})
    
    total_evaluations = trigger_impact.get('total_evaluations', 0) + tag_impact.get('total_evaluations', 0)
    
    # Create visualizations
    # 1. Variable Impact Bar Chart
    fig_impact = px.bar(
        df_impact.head(20),
        x='Variable',
        y=['Trigger Evals', 'Tag Evals'],
        title='Top 20 Variables by Evaluation Impact',
        labels={'value': 'Evaluations', 'Variable': 'Variable Name'},
        color_discrete_map={'Trigger Evals': COLORS['primary'], 'Tag Evals': COLORS['warning']}
    )
    fig_impact.update_layout(
        xaxis_tickangle=-45,
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    # 2. Variable Type Distribution
    type_counts = df_impact['Type'].value_counts()
    fig_types = px.pie(
        values=type_counts.values,
        names=type_counts.index,
        title='Variable Distribution by Type'
    )
    
    # 3. Usage Status Donut Chart
    used_vars = summary.get('total_variables', 0) - summary.get('unused_variables', 0)
    unused_vars = summary.get('unused_variables', 0)
    
    fig_usage = go.Figure(data=[go.Pie(
        labels=['Used Variables', 'Unused Variables'],
        values=[used_vars, unused_vars],
        hole=.3,
        marker_colors=[COLORS['success'], COLORS['danger']]
    )])
    fig_usage.update_layout(title='Variable Usage Status')
    
    # 4. Performance Impact Heatmap
    top_vars = df_impact.head(15)
    heatmap_data = []
    for _, row in top_vars.iterrows():
        heatmap_data.append({
            'Variable': row['Variable'],
            'Component': 'Triggers',
            'Evaluations': row['Trigger Evals']
        })
        heatmap_data.append({
            'Variable': row['Variable'],
            'Component': 'Tags',
            'Evaluations': row['Tag Evals']
        })
    
    df_heatmap = pd.DataFrame(heatmap_data)
    fig_heatmap = px.density_heatmap(
        df_heatmap,
        x='Component',
        y='Variable',
        z='Evaluations',
        title='Variable Evaluation Heatmap',
        color_continuous_scale='Reds'
    )
    fig_heatmap.update_layout(height=600)
    
    # App layout
    app.layout = html.Div([
        # Header
        html.Div([
            html.H1('GTM Container Analysis Dashboard', className='text-center mb-4'),
            html.P(f'Analysis Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 
                   className='text-center text-muted')
        ], className='container mt-4'),
        
        # Summary Cards
        html.Div([
            html.Div([
                create_metric_card('Total Variables', summary.get('total_variables', 0), 'primary'),
                create_metric_card('Unused Variables', summary.get('unused_variables', 0), 'danger'),
                create_metric_card('Total Tags', summary.get('total_tags', 0), 'info'),
                create_metric_card('Total Evaluations', f'{total_evaluations:,}', 'warning'),
            ], className='row')
        ], className='container mb-4'),
        
        # Container Health Score
        html.Div([
            html.Div([
                html.H2('Container Health Score', className='text-center'),
                create_health_score_gauge(data)
            ], className='col-12')
        ], className='container mb-4'),
        
        # Improvement Recommendations
        html.Div([
            html.H2('Container Improvement Guide', className='mb-4'),
            html.Div(id='recommendations-container', children=[
                create_recommendation_card(rec) for rec in recommendations
            ])
        ], className='container mb-4'),
        
        # Charts
        html.Div([
            html.Div([
                dcc.Graph(figure=fig_impact)
            ], className='col-12 mb-4'),
            
            html.Div([
                html.Div([
                    dcc.Graph(figure=fig_usage)
                ], className='col-md-6'),
                html.Div([
                    dcc.Graph(figure=fig_types)
                ], className='col-md-6')
            ], className='row mb-4'),
            
            html.Div([
                dcc.Graph(figure=fig_heatmap)
            ], className='col-12 mb-4')
        ], className='container'),
        
        # Detailed Tables
        html.Div([
            html.H2('Detailed Analysis', className='mb-4'),
            
            # High Impact Variables Table
            html.H3('High Impact Variables'),
            dash_table.DataTable(
                id='impact-table',
                columns=[
                    {'name': col, 'id': col} for col in df_impact.columns
                ],
                data=df_impact.head(50).to_dict('records'),
                style_cell={'textAlign': 'left'},
                style_data_conditional=[
                    {
                        'if': {'column_id': 'Total Evals'},
                        'backgroundColor': '#ffcccc',
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {
                            'filter_query': '{Total Evals} > 1000',
                            'column_id': 'Total Evals'
                        },
                        'backgroundColor': '#ff6666',
                        'color': 'white',
                    }
                ],
                filter_action="native",
                sort_action="native",
                page_size=20,
                style_table={'overflowX': 'auto'}
            )
        ], className='container mb-4'),
        
        # Export Section
        html.Div([
            html.Hr(),
            html.Div([
                html.Button('Export Full Report', id='export-btn', className='btn btn-primary'),
                dcc.Download(id="download-report")
            ], className='text-center mb-4')
        ], className='container')
    ])
    
    # Callback for export
    @app.callback(
        Output("download-report", "data"),
        Input("export-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def export_report(n_clicks):
        # Create a detailed report
        report = {
            'analysis_date': datetime.now().isoformat(),
            'summary': data.get('summary', {}),
            'recommendations': recommendations,
            'high_impact_variables': df_impact.head(50).to_dict('records'),
            'unused_variables': data.get('unused_variables', []),
            'duplicate_variables': data.get('duplicate_variables', {})
        }
        
        return dict(
            content=json.dumps(report, indent=2),
            filename=f"gtm_improvement_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
    
    return app

def create_metric_card(title, value, color='primary'):
    """Create a Bootstrap-style metric card"""
    return html.Div([
        html.Div([
            html.H5(title, className='card-title text-muted'),
            html.H2(str(value), className=f'text-{color}')
        ], className='card-body text-center')
    ], className='col-md-3 mb-3')

def create_recommendation_card(recommendation):
    """Create a recommendation card with action items"""
    priority_colors = {
        'HIGH': 'danger',
        'MEDIUM': 'warning',
        'LOW': 'info'
    }
    
    color = priority_colors.get(recommendation['priority'], 'secondary')
    
    return html.Div([
        html.Div([
            html.Div([
                html.Span(recommendation['priority'], 
                         className=f'badge badge-{color} float-right'),
                html.H5(recommendation['title'], className='card-title'),
                html.P(recommendation['impact'], className='text-muted small'),
                html.P(recommendation['action']),
                html.Div([
                    html.P(item, className='mb-1 small') 
                    for item in recommendation['items']
                ])
            ], className='card-body')
        ], className=f'card border-{color} mb-3')
    ])

def create_health_score_gauge(data):
    """Create a gauge chart for container health score"""
    # Calculate health score (0-100)
    summary = data.get('summary', {})
    
    # Factors for health score
    total_vars = summary.get('total_variables', 0)
    unused_vars = summary.get('unused_variables', 0)
    unused_ratio = unused_vars / total_vars if total_vars > 0 else 0
    
    # Score calculation (higher is better)
    score = 100
    score -= unused_ratio * 30  # Up to -30 points for unused variables
    score -= min(summary.get('duplicate_groups', 0) * 2, 20)  # Up to -20 points for duplicates
    
    # Penalty for container size
    if total_vars > 200:
        score -= 10
    if total_vars > 300:
        score -= 10
    
    score = max(0, min(100, score))  # Ensure 0-100 range
    
    # Determine color based on score
    if score >= 80:
        color = COLORS['success']
    elif score >= 60:
        color = COLORS['warning']
    else:
        color = COLORS['danger']
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={'text': "Container Health Score"},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': color},
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
    
    fig.update_layout(height=300)
    return dcc.Graph(figure=fig)

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python gtm_dashboard.py <path_to_analysis_report.json>")
        sys.exit(1)
    
    # Load data
    data = load_analysis_data(sys.argv[1])
    
    # Create and run dashboard
    app = create_dashboard(data)
    
    print("Starting GTM Analysis Dashboard...")
    print("Open http://127.0.0.1:8050 in your browser")
    print("Press CTRL+C to stop the server")
    
    try:
        app.run(debug=True, host='127.0.0.1', port=8050)
    except Exception as e:
        print(f"Error starting dashboard: {e}")
        print("\nTrying alternative port 8051...")
        try:
            app.run(debug=True, host='127.0.0.1', port=8051)
            print("Dashboard running on http://127.0.0.1:8051")
        except Exception as e2:
            print(f"Error: {e2}")
            print("\nPlease check if:")
            print("1. All dependencies are installed: pip install -r requirements.txt")
            print("2. No other application is using port 8050/8051")
            print("3. Your firewall is not blocking the connection")

if __name__ == '__main__':
    main()