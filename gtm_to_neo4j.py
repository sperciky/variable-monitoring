#!/usr/bin/env python3
"""
Convert GTM Analysis Report to Neo4j-compatible JSON dataset
Creates nodes and relationships for graph database import
"""

import json
import sys
import hashlib
from datetime import datetime

def generate_id(prefix, name):
    """Generate a unique ID for a node"""
    return f"{prefix}_{hashlib.md5(name.encode()).hexdigest()[:8]}"

def create_neo4j_dataset(analysis_data):
    """Convert GTM analysis data to Neo4j format"""
    nodes = []
    relationships = []
    
    # Track processed nodes to avoid duplicates
    processed_nodes = set()
    
    # Get data from analysis report
    usage_counts = analysis_data.get('variable_usage_counts', {})
    usage_details = analysis_data.get('variable_usage_details', {})
    summary = analysis_data.get('summary', {})
    
    # Container metadata node
    container_id = "container_main"
    nodes.append({
        "id": container_id,
        "labels": ["Container"],
        "properties": {
            "name": "GTM Container",
            "type": summary.get('container_type', 'Unknown'),
            "total_variables": summary.get('total_variables', 0),
            "total_tags": summary.get('total_tags', 0),
            "total_triggers": summary.get('total_triggers', 0),
            "health_score": 100 - summary.get('unused_variables', 0) - (summary.get('duplicate_groups', 0) * 2)
        }
    })
    
    # Process variables and their usage
    for var_name, var_data in usage_counts.items():
        var_info = var_data.get('variable', {})
        var_id = generate_id("var", var_name)
        
        if var_id not in processed_nodes:
            # Determine variable type for categorization
            var_type = var_info.get('type', 'unknown')
            if var_type.startswith('cvt_'):
                var_category = 'Custom Template Variable'
            elif var_name.startswith('_'):
                var_category = 'GTM Internal Variable'
            else:
                var_category = get_variable_category(var_type)
            
            nodes.append({
                "id": var_id,
                "labels": ["Variable", var_category.replace(' ', '')],
                "properties": {
                    "name": var_name,
                    "type": var_type,
                    "category": var_category,
                    "total_references": var_data.get('total_references', 0),
                    "evaluation_contexts": var_data.get('evaluation_contexts', 0),
                    "is_used": var_data.get('total_references', 0) > 0
                }
            })
            processed_nodes.add(var_id)
        
        # Create relationships to components using this variable
        components = var_data.get('usage_components', {})
        
        # Tags
        for tag_name in components.get('tags', []):
            tag_id = generate_id("tag", tag_name)
            if tag_id not in processed_nodes:
                nodes.append({
                    "id": tag_id,
                    "labels": ["Tag"],
                    "properties": {
                        "name": tag_name
                    }
                })
                processed_nodes.add(tag_id)
            
            relationships.append({
                "type": "USES_VARIABLE",
                "startNode": tag_id,
                "endNode": var_id,
                "properties": {
                    "usage_type": "direct"
                }
            })
        
        # Triggers
        for trigger_name in components.get('triggers', []):
            trigger_id = generate_id("trigger", trigger_name)
            if trigger_id not in processed_nodes:
                nodes.append({
                    "id": trigger_id,
                    "labels": ["Trigger"],
                    "properties": {
                        "name": trigger_name
                    }
                })
                processed_nodes.add(trigger_id)
            
            relationships.append({
                "type": "USES_VARIABLE",
                "startNode": trigger_id,
                "endNode": var_id,
                "properties": {
                    "usage_type": "condition"
                }
            })
        
        # Variables (variable-to-variable dependencies)
        for ref_var_name in components.get('variables', []):
            ref_var_id = generate_id("var", ref_var_name)
            if ref_var_id != var_id:  # Avoid self-references
                relationships.append({
                    "type": "REFERENCES_VARIABLE",
                    "startNode": ref_var_id,
                    "endNode": var_id,
                    "properties": {
                        "reference_type": "nested"
                    }
                })
        
        # Clients (SGTM)
        for client_name in components.get('clients', []):
            client_id = generate_id("client", client_name)
            if client_id not in processed_nodes:
                nodes.append({
                    "id": client_id,
                    "labels": ["Client"],
                    "properties": {
                        "name": client_name
                    }
                })
                processed_nodes.add(client_id)
            
            relationships.append({
                "type": "USES_VARIABLE",
                "startNode": client_id,
                "endNode": var_id,
                "properties": {
                    "usage_type": "parameter"
                }
            })
        
        # Transformations (SGTM)
        for trans_name in components.get('transformations', []):
            trans_id = generate_id("trans", trans_name)
            if trans_id not in processed_nodes:
                nodes.append({
                    "id": trans_id,
                    "labels": ["Transformation"],
                    "properties": {
                        "name": trans_name
                    }
                })
                processed_nodes.add(trans_id)
            
            relationships.append({
                "type": "USES_VARIABLE",
                "startNode": trans_id,
                "endNode": var_id,
                "properties": {
                    "usage_type": "transform"
                }
            })
        
        # Custom Templates
        for template_name in components.get('custom_templates', []):
            template_id = generate_id("template", template_name)
            if template_id not in processed_nodes:
                nodes.append({
                    "id": template_id,
                    "labels": ["CustomTemplate"],
                    "properties": {
                        "name": template_name
                    }
                })
                processed_nodes.add(template_id)
            
            relationships.append({
                "type": "USES_VARIABLE",
                "startNode": template_id,
                "endNode": var_id,
                "properties": {
                    "usage_type": "template_code"
                }
            })
    
    # Process trigger-to-tag relationships from evaluation impact data
    trigger_impact = analysis_data.get('trigger_evaluation_impact', {})
    if 'trigger_details' in trigger_impact:
        for trigger_detail in trigger_impact['trigger_details']:
            trigger_name = trigger_detail.get('name', 'Unknown Trigger')
            trigger_id = generate_id("trigger", trigger_name)
            
            for tag_info in trigger_detail.get('attached_tags', []):
                tag_name = tag_info.get('name', 'Unknown Tag')
                tag_id = generate_id("tag", tag_name)
                
                relationships.append({
                    "type": "FIRES_TAG",
                    "startNode": trigger_id,
                    "endNode": tag_id,
                    "properties": {
                        "tag_type": tag_info.get('type', 'Unknown')
                    }
                })
    
    # Process unused variables
    for unused_var in analysis_data.get('unused_variables', []):
        var_name = unused_var['name']
        var_id = generate_id("var", var_name)
        
        if var_id not in processed_nodes:
            var_type = unused_var.get('type', 'unknown')
            nodes.append({
                "id": var_id,
                "labels": ["Variable", "UnusedVariable"],
                "properties": {
                    "name": var_name,
                    "type": var_type,
                    "category": get_variable_category(var_type),
                    "total_references": 0,
                    "is_used": False,
                    "variable_id": unused_var.get('variableId', '')
                }
            })
            processed_nodes.add(var_id)
    
    # Process duplicate variables
    duplicates = analysis_data.get('duplicate_variables', {})
    dup_group_id = 0
    for dup_type, dup_groups in duplicates.items():
        for group in dup_groups:
            dup_group_id += 1
            group_node_id = f"dupgroup_{dup_group_id}"
            
            nodes.append({
                "id": group_node_id,
                "labels": ["DuplicateGroup"],
                "properties": {
                    "type": dup_type,
                    "size": len(group)
                }
            })
            
            for dup_var in group:
                var_id = generate_id("var", dup_var['name'])
                relationships.append({
                    "type": "DUPLICATE_OF",
                    "startNode": var_id,
                    "endNode": group_node_id,
                    "properties": {
                        "duplicate_type": dup_type
                    }
                })
    
    # Create Neo4j import format
    neo4j_data = {
        "nodes": nodes,
        "relationships": relationships,
        "metadata": {
            "generated": datetime.now().isoformat(),
            "total_nodes": len(nodes),
            "total_relationships": len(relationships),
            "node_types": count_node_types(nodes),
            "relationship_types": count_relationship_types(relationships)
        },
        "cypher_import": generate_cypher_commands(nodes, relationships)
    }
    
    return neo4j_data

def get_variable_category(var_type):
    """Categorize variable by type"""
    categories = {
        'v': 'Data Layer Variable',
        'k': 'Cookie',
        'u': 'URL Variable',
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
        't': 'Environment Name'
    }
    
    if var_type.startswith('cvt_'):
        return 'Custom Template Variable'
    
    return categories.get(var_type, 'Other Variable')

def count_node_types(nodes):
    """Count nodes by label"""
    counts = {}
    for node in nodes:
        for label in node['labels']:
            counts[label] = counts.get(label, 0) + 1
    return counts

def count_relationship_types(relationships):
    """Count relationships by type"""
    counts = {}
    for rel in relationships:
        rel_type = rel['type']
        counts[rel_type] = counts.get(rel_type, 0) + 1
    return counts

def generate_cypher_commands(nodes, relationships):
    """Generate Cypher commands for Neo4j import"""
    commands = []
    
    # Create constraint commands
    commands.append("// Create constraints for better performance")
    commands.append("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Variable) REQUIRE n.id IS UNIQUE;")
    commands.append("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Tag) REQUIRE n.id IS UNIQUE;")
    commands.append("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Trigger) REQUIRE n.id IS UNIQUE;")
    commands.append("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Client) REQUIRE n.id IS UNIQUE;")
    commands.append("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Transformation) REQUIRE n.id IS UNIQUE;")
    commands.append("")
    
    # Create nodes
    commands.append("// Create nodes")
    for node in nodes[:5]:  # Show first 5 as examples
        labels = ':'.join(node['labels'])
        props = json.dumps(node['properties'])
        commands.append(f"CREATE (n:{labels} {props});")
    commands.append("// ... more node creation commands")
    commands.append("")
    
    # Create relationships
    commands.append("// Create relationships")
    for rel in relationships[:5]:  # Show first 5 as examples
        commands.append(
            f"MATCH (a {{id: '{rel['startNode']}'}}), (b {{id: '{rel['endNode']}'}}) "
            f"CREATE (a)-[:{rel['type']} {json.dumps(rel['properties'])}]->(b);"
        )
    commands.append("// ... more relationship creation commands")
    
    return commands

def main():
    if len(sys.argv) < 2:
        print("Usage: python gtm_to_neo4j.py <analysis_report.json>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = "output2.json"
    
    # Load analysis report
    print(f"Loading analysis report from {input_file}...")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
    except Exception as e:
        print(f"Error loading file: {e}")
        sys.exit(1)
    
    # Convert to Neo4j format
    print("Converting to Neo4j dataset...")
    neo4j_data = create_neo4j_dataset(analysis_data)
    
    # Save output
    print(f"Saving Neo4j dataset to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(neo4j_data, f, indent=2)
    
    # Print summary
    print("\n✅ Neo4j dataset created successfully!")
    print(f"\nSummary:")
    print(f"- Total nodes: {neo4j_data['metadata']['total_nodes']}")
    print(f"- Total relationships: {neo4j_data['metadata']['total_relationships']}")
    print(f"\nNode types:")
    for node_type, count in neo4j_data['metadata']['node_types'].items():
        print(f"  - {node_type}: {count}")
    print(f"\nRelationship types:")
    for rel_type, count in neo4j_data['metadata']['relationship_types'].items():
        print(f"  - {rel_type}: {count}")
    
    print(f"\nOutput saved to: {output_file}")
    print("\nTo import into Neo4j:")
    print("1. Use Neo4j Desktop or Aura")
    print("2. Import the JSON using APOC procedures or")
    print("3. Use the generated Cypher commands in 'cypher_import'")

if __name__ == '__main__':
    main()