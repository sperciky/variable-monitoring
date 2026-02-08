#!/usr/bin/env python3
"""
GTM Variable Dependency Network Graph
Visualizes relationships between variables and GTM components
"""

import plotly.graph_objects as go
import json
import sys
import os
from datetime import datetime
import networkx as nx
import numpy as np

# Color scheme for different component types
COMPONENT_COLORS = {
    'variable': '#1f77b4',          # Blue for variables
    'tag': '#ff7f0e',              # Orange for tags
    'trigger': '#2ca02c',          # Green for triggers
    'client': '#d62728',           # Red for clients
    'transformation': '#9467bd',    # Purple for transformations
    'custom_template': '#8c564b',   # Brown for custom templates
    'builtin': '#e377c2',          # Pink for built-in variables
    'internal': '#7f7f7f',         # Gray for internal variables
    'unknown': '#bcbd22'           # Yellow-green for unknown
}

# Node sizes
NODE_SIZES = {
    'variable': 20,
    'tag': 25,
    'trigger': 25,
    'client': 25,
    'transformation': 20,
    'custom_template': 22,
    'builtin': 18,
    'internal': 18,
    'unknown': 15
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

def get_variable_type(var_name, usage_data):
    """Determine the type of variable"""
    if var_name.startswith('_'):
        return 'internal'
    
    # Check in usage data
    if var_name in usage_data:
        var_info = usage_data[var_name].get('variable', {})
        var_type = var_info.get('type', '')
        if var_type.startswith('cvt_'):
            return 'custom_template'
        elif var_type:
            return 'variable'
    
    # Check for built-in variable names
    builtin_names = {
        'Event Name', 'Page URL', 'Page Hostname', 'Page Path', 'Referrer',
        'Click Element', 'Click Classes', 'Click ID', 'Click URL', 'Click Text',
        'Container ID', 'Container Version', 'Debug Mode', 'Random Number',
        'HTML ID', 'Environment Name', 'Client Name', 'Client ID', 'IP Address',
        'User Agent', 'Event', 'Error Message', 'Error Line', 'Error URL'
    }
    
    if var_name in builtin_names:
        return 'builtin'
    
    return 'other'

def build_dependency_graph(data, min_connections=0, max_nodes=500):
    """Build a network graph from the analysis data
    
    Args:
        data: Analysis data from GTM analyzer
        min_connections: Minimum number of connections for a variable to be included
        max_nodes: Maximum number of nodes to include (top by connection count)
    """
    G = nx.Graph()
    
    usage_counts = data.get('variable_usage_counts', {})
    variable_usage_details = data.get('variable_usage_details', {})
    
    # Filter variables by minimum connections if specified
    if min_connections > 0:
        filtered_counts = {
            var: data for var, data in usage_counts.items()
            if data.get('total_references', 0) >= min_connections
        }
        usage_counts = filtered_counts
    
    # If still too many, take top N by total references
    if len(usage_counts) > max_nodes:
        sorted_vars = sorted(
            usage_counts.items(),
            key=lambda x: x[1].get('total_references', 0),
            reverse=True
        )
        usage_counts = dict(sorted_vars[:max_nodes])
    
    # Track all nodes to avoid duplicates
    nodes_added = set()
    
    # Add variable nodes and their connections
    for var_name, var_data in usage_counts.items():
        if var_data.get('total_references', 0) == 0:
            continue
            
        # Add variable node if not already added
        var_type = get_variable_type(var_name, usage_counts)
        if var_name not in nodes_added:
            G.add_node(var_name, 
                      node_type=var_type,
                      label=var_name,
                      size=NODE_SIZES.get(var_type, 15))
            nodes_added.add(var_name)
        
        # Add connections to components
        components = var_data.get('usage_components', {})
        
        # Tags
        for tag_name in components.get('tags', []):
            node_id = f"tag:{tag_name}"
            if node_id not in nodes_added:
                G.add_node(node_id, 
                          node_type='tag',
                          label=tag_name,
                          size=NODE_SIZES['tag'])
                nodes_added.add(node_id)
            G.add_edge(var_name, node_id)
        
        # Triggers
        for trigger_name in components.get('triggers', []):
            node_id = f"trigger:{trigger_name}"
            if node_id not in nodes_added:
                G.add_node(node_id,
                          node_type='trigger', 
                          label=trigger_name,
                          size=NODE_SIZES['trigger'])
                nodes_added.add(node_id)
            G.add_edge(var_name, node_id)
        
        # Variables (variable-to-variable dependencies)
        for ref_var_name in components.get('variables', []):
            if ref_var_name != var_name:  # Avoid self-references
                ref_var_type = get_variable_type(ref_var_name, usage_counts)
                if ref_var_name not in nodes_added:
                    G.add_node(ref_var_name,
                              node_type=ref_var_type,
                              label=ref_var_name,
                              size=NODE_SIZES.get(ref_var_type, 15))
                    nodes_added.add(ref_var_name)
                G.add_edge(var_name, ref_var_name)
        
        # Clients
        for client_name in components.get('clients', []):
            node_id = f"client:{client_name}"
            if node_id not in nodes_added:
                G.add_node(node_id,
                          node_type='client',
                          label=client_name,
                          size=NODE_SIZES['client'])
                nodes_added.add(node_id)
            G.add_edge(var_name, node_id)
        
        # Transformations
        for trans_name in components.get('transformations', []):
            node_id = f"transformation:{trans_name}"
            if node_id not in nodes_added:
                G.add_node(node_id,
                          node_type='transformation',
                          label=trans_name,
                          size=NODE_SIZES['transformation'])
                nodes_added.add(node_id)
            G.add_edge(var_name, node_id)
        
        # Custom Templates
        for template_name in components.get('custom_templates', []):
            node_id = f"template:{template_name}"
            if node_id not in nodes_added:
                G.add_node(node_id,
                          node_type='custom_template',
                          label=template_name,
                          size=NODE_SIZES['custom_template'])
                nodes_added.add(node_id)
            G.add_edge(var_name, node_id)
    
    # Also check variable-to-variable references from usage details
    for var_name, details in variable_usage_details.items():
        if var_name in nodes_added and isinstance(details, dict):
            # Check variables that use this variable
            for ref_var_name in details.get('used_in_variables', []):
                if ref_var_name != var_name and ref_var_name not in nodes_added:
                    ref_var_type = get_variable_type(ref_var_name, usage_counts)
                    G.add_node(ref_var_name,
                              node_type=ref_var_type,
                              label=ref_var_name,
                              size=NODE_SIZES.get(ref_var_type, 15))
                    nodes_added.add(ref_var_name)
                # Add edge from referencing variable to referenced variable
                if ref_var_name != var_name and not G.has_edge(ref_var_name, var_name):
                    G.add_edge(ref_var_name, var_name)
    
    return G

def create_network_visualization(G, output_filename):
    """Create an interactive network graph visualization"""
    # Calculate optimal layout based on graph size
    num_nodes = len(G.nodes())
    
    # Adjust layout parameters based on graph size
    if num_nodes > 100:
        # For large graphs, use Kamada-Kawai layout which handles large graphs better
        pos = nx.kamada_kawai_layout(G, scale=5)
    elif num_nodes > 50:
        # For medium graphs, use spring layout with adjusted parameters
        pos = nx.spring_layout(G, k=5/np.sqrt(num_nodes), iterations=100, scale=3)
    else:
        # For small graphs, standard spring layout works well
        pos = nx.spring_layout(G, k=3, iterations=50, scale=2)
    
    # Extract node information
    node_x = []
    node_y = []
    node_labels = []
    node_colors = []
    node_sizes = []
    node_types = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        node_data = G.nodes[node]
        node_labels.append(node_data['label'])
        node_type = node_data['node_type']
        node_types.append(node_type)
        node_colors.append(COMPONENT_COLORS.get(node_type, COMPONENT_COLORS['unknown']))
        node_sizes.append(node_data.get('size', 15))
    
    # Adjust text visibility based on graph size
    show_text = num_nodes < 50  # Only show labels for smaller graphs
    
    # Create node trace
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text' if show_text else 'markers',
        text=node_labels if show_text else None,
        textposition="top center",
        textfont=dict(size=8),
        hoverinfo='text',
        marker=dict(
            showscale=False,
            color=node_colors,
            size=[s * (0.7 if num_nodes > 100 else 1.0) for s in node_sizes],  # Scale down for large graphs
            line=dict(width=1, color='white')
        )
    )
    
    # Create hover text with component type
    hover_texts = []
    for i, node in enumerate(G.nodes()):
        node_data = G.nodes[node]
        connections = list(G.neighbors(node))
        hover_text = f"<b>{node_data['label']}</b><br>"
        hover_text += f"Type: {node_data['node_type'].replace('_', ' ').title()}<br>"
        hover_text += f"Connections: {len(connections)}"
        hover_texts.append(hover_text)
    
    node_trace.hovertext = hover_texts
    
    # Extract edge information
    edge_x = []
    edge_y = []
    
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    
    # Create edge trace
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines'
    )
    
    # Create legend traces
    legend_traces = []
    for comp_type, color in COMPONENT_COLORS.items():
        legend_traces.append(
            go.Scatter(
                x=[None], y=[None],
                mode='markers',
                marker=dict(size=10, color=color),
                showlegend=True,
                name=comp_type.replace('_', ' ').title()
            )
        )
    
    # Create the figure
    fig = go.Figure(data=[edge_trace, node_trace] + legend_traces)
    
    # Update layout with better controls
    fig.update_layout(
        title={
            'text': f'GTM Variable Dependencies Network ({num_nodes} nodes, {len(G.edges())} connections)',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20}
        },
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="Black",
            borderwidth=1,
            font=dict(size=10)
        ),
        hovermode='closest',
        margin=dict(b=40, l=40, r=180, t=80),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='#fafafa',
        width=1600,
        height=1000,
        dragmode='pan',  # Default to pan mode for easier navigation
        modebar=dict(
            bgcolor='rgba(255, 255, 255, 0.9)',
            orientation='v'
        )
    )
    
    # Add custom modebar buttons for better control
    config = {
        'toImageButtonOptions': {
            'format': 'png',
            'filename': 'gtm_dependencies',
            'height': 1600,
            'width': 2000,
            'scale': 2
        },
        'modeBarButtonsToAdd': ['toggleHover', 'toggleSpikelines'],
        'displaylogo': False
    }
    
    # Add annotations for statistics
    total_nodes = len(G.nodes())
    total_edges = len(G.edges())
    node_type_counts = {}
    for node in G.nodes():
        node_type = G.nodes[node]['node_type']
        node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
    
    stats_text = f"Total Nodes: {total_nodes} | Total Connections: {total_edges}"
    fig.add_annotation(
        text=stats_text,
        xref="paper", yref="paper",
        x=0, y=-0.05,
        showarrow=False,
        font=dict(size=12)
    )
    
    # Generate HTML with the plot
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GTM Variable Dependencies Network</title>
        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 1500px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #333;
                text-align: center;
            }}
            .stats {{
                margin: 20px 0;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
            }}
            .stat-item {{
                padding: 10px;
                background-color: white;
                border-radius: 5px;
                border: 1px solid #dee2e6;
            }}
            .stat-label {{
                font-size: 12px;
                color: #6c757d;
                text-transform: uppercase;
                margin-bottom: 5px;
            }}
            .stat-value {{
                font-size: 24px;
                font-weight: bold;
                color: #333;
            }}
            .info {{
                margin-top: 20px;
                padding: 15px;
                background-color: #e9ecef;
                border-radius: 5px;
                font-size: 14px;
                line-height: 1.6;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>GTM Variable Dependencies Network</h1>
            
            <div class="stats">
                <h3>Network Statistics</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">Total Nodes</div>
                        <div class="stat-value">{total_nodes}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Total Connections</div>
                        <div class="stat-value">{total_edges}</div>
                    </div>
                    {node_type_stats}
                </div>
            </div>
            
            <div id="myDiv">{plot_div}</div>
            
            <div class="info">
                <h3>How to Navigate This Network</h3>
                <ul>
                    <li><strong>🖱️ Pan</strong>: Click and drag to move around the graph</li>
                    <li><strong>🔍 Zoom</strong>: Use mouse wheel or pinch to zoom in/out</li>
                    <li><strong>👆 Hover</strong>: Move mouse over nodes to see details and connections</li>
                    <li><strong>📦 Box Select</strong>: Click the box select tool to select multiple nodes</li>
                    <li><strong>🏠 Reset</strong>: Double-click to reset the view</li>
                    <li><strong>💾 Save</strong>: Use the camera icon to save as PNG</li>
                </ul>
                <h3>Understanding the Network</h3>
                <ul>
                    <li><strong>Nodes</strong> = GTM components (variables, tags, triggers, etc.)</li>
                    <li><strong>Lines</strong> = Dependencies (component uses the connected variable)</li>
                    <li><strong>Colors</strong> = Component types (see legend on the right)</li>
                    <li><strong>Node Size</strong> = Component importance (tags/triggers are larger)</li>
                    <li><strong>Dense Areas</strong> = Highly interconnected components</li>
                    <li><strong>Isolated Nodes</strong> = Components with few dependencies</li>
                </ul>
                <p><strong>Tip for Large Graphs:</strong> Zoom in to specific areas to see details. Labels only appear for graphs with less than 50 nodes to maintain readability.</p>
            </div>
            
            <div class="info">
                <p><em>Generated: {timestamp}</em></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Generate node type statistics HTML
    node_type_stats_html = ""
    for node_type, count in sorted(node_type_counts.items()):
        node_type_display = node_type.replace('_', ' ').title()
        color = COMPONENT_COLORS.get(node_type, COMPONENT_COLORS['unknown'])
        node_type_stats_html += f"""
        <div class="stat-item">
            <div class="stat-label" style="color: {color};">{node_type_display}</div>
            <div class="stat-value">{count}</div>
        </div>
        """
    
    # Generate plot HTML with config
    plot_html = fig.to_html(include_plotlyjs=False, div_id="myDiv", config=config)
    
    # Fill template
    html_content = html_template.format(
        total_nodes=total_nodes,
        total_edges=total_edges,
        node_type_stats=node_type_stats_html,
        plot_div=plot_html,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # Write to file
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Network graph generated: {output_filename}")
    print(f"📊 Graph contains {total_nodes} nodes and {total_edges} connections")
    print(f"📂 File location: {os.path.abspath(output_filename)}")
    print(f"🌐 Open in browser: file:///{os.path.abspath(output_filename).replace(os.sep, '/')}")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python gtm_dependency_graph.py <path_to_analysis_report.json> [output_filename.html]")
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
            base_name = base_name[:-21]
        elif base_name.endswith('.json'):
            base_name = base_name[:-5]
        
        output_filename = f'gtm_dependency_graph_{base_name}.html'
    
    # Check data size and provide options for large containers
    total_vars = len(data.get('variable_usage_counts', {}))
    print(f"Found {total_vars} variables in the analysis...")
    
    # For very large containers, apply filtering
    min_connections = 0
    max_nodes = 500
    
    if total_vars > 200:
        print(f"\n⚠️  Large container detected ({total_vars} variables)")
        print("Applying filters for better visualization:")
        print("- Including only top 200 most connected variables")
        print("- Filtering out variables with less than 2 connections")
        min_connections = 2
        max_nodes = 200
    elif total_vars > 100:
        print("Optimizing layout for medium-sized container...")
        min_connections = 1
    
    # Build and visualize the graph
    print("\nBuilding dependency graph...")
    G = build_dependency_graph(data, min_connections=min_connections, max_nodes=max_nodes)
    
    if len(G.nodes()) == 0:
        print("❌ No dependencies found to visualize.")
        sys.exit(1)
    
    print(f"Creating visualization with {len(G.nodes())} nodes and {len(G.edges())} connections...")
    if total_vars > len(G.nodes()):
        print(f"(Filtered from {total_vars} total variables for clarity)")
    
    create_network_visualization(G, output_filename)

if __name__ == '__main__':
    main()