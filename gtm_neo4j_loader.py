#!/usr/bin/env python3
"""
Neo4j Loader for GTM Analysis Dataset (output2.json format)
Loads nodes and relationships from the standardized dataset
"""

import json
import sys
import os
from neo4j import GraphDatabase
from typing import Dict, List, Any
import argparse
from datetime import datetime

class GTMContainerGraphLoader:
    def __init__(self, uri: str, user: str, password: str):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        """Close the database connection"""
        self.driver.close()
    
    def clear_database(self):
        """Clear all existing data"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Database cleared successfully")
    
    def create_constraints_and_indexes(self):
        """Create constraints and indexes for better performance"""
        with self.driver.session() as session:
            # Constraints for unique IDs
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Variable) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Tag) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Trigger) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Client) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Transformation) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:CustomTemplate) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Container) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:DuplicateGroup) REQUIRE n.id IS UNIQUE"
            ]
            
            # Indexes for common queries
            indexes = [
                "CREATE INDEX IF NOT EXISTS FOR (n:Variable) ON (n.name)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Variable) ON (n.type)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Variable) ON (n.is_used)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Tag) ON (n.name)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Trigger) ON (n.name)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Client) ON (n.name)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Transformation) ON (n.name)",
                "CREATE INDEX IF NOT EXISTS FOR (n:CustomTemplate) ON (n.name)"
            ]
            
            # Create constraints
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        print(f"Note: {e}")
            
            # Create indexes
            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        print(f"Note: {e}")
            
            print("✓ Created constraints and indexes")
    
    def load_dataset(self, dataset: Dict[str, Any], clear_existing: bool = False):
        """Load the output2.json format dataset into Neo4j"""
        
        if clear_existing:
            print("Clearing existing data...")
            self.clear_database()
        
        print("Creating constraints and indexes...")
        self.create_constraints_and_indexes()
        
        # Load nodes and relationships
        nodes = dataset.get('nodes', [])
        relationships = dataset.get('relationships', [])
        
        print(f"\nLoading {len(nodes)} nodes...")
        self._load_nodes(nodes)
        
        print(f"\nLoading {len(relationships)} relationships...")
        self._load_relationships(relationships)
        
        print("\n✓ Dataset loaded successfully!")
        
        # Run validation
        self._validate_import()
    
    def _load_nodes(self, nodes: List[Dict[str, Any]], batch_size: int = 100):
        """Load nodes in batches"""
        with self.driver.session() as session:
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i:i + batch_size]
                
                # Process each node in the batch
                for node_data in batch:
                    node_id = node_data['id']
                    labels = ':'.join(node_data['labels'])
                    properties = node_data['properties']
                    
                    # Build property string
                    prop_strings = []
                    for key, value in properties.items():
                        if isinstance(value, str):
                            # Escape single quotes in strings
                            value = value.replace("'", "\\'")
                            prop_strings.append(f"{key}: '{value}'")
                        elif isinstance(value, bool):
                            prop_strings.append(f"{key}: {str(value).lower()}")
                        elif value is None:
                            prop_strings.append(f"{key}: null")
                        else:
                            prop_strings.append(f"{key}: {value}")
                    
                    prop_string = '{' + ', '.join(prop_strings) + '}'
                    
                    # Create node with all labels
                    query = f"CREATE (n:{labels} {prop_string})"
                    
                    try:
                        session.run(query)
                    except Exception as e:
                        print(f"Error creating node {node_id}: {e}")
                
                print(f"  Loaded {min(i + batch_size, len(nodes))}/{len(nodes)} nodes...", end='\r')
            
            print()  # New line after progress
    
    def _load_relationships(self, relationships: List[Dict[str, Any]], batch_size: int = 100):
        """Load relationships in batches"""
        with self.driver.session() as session:
            # Group by relationship type for efficiency
            rels_by_type = {}
            for rel in relationships:
                rel_type = rel['type']
                if rel_type not in rels_by_type:
                    rels_by_type[rel_type] = []
                rels_by_type[rel_type].append(rel)
            
            total_created = 0
            for rel_type, rels in rels_by_type.items():
                print(f"  Loading {rel_type} relationships...")
                
                for i in range(0, len(rels), batch_size):
                    batch = rels[i:i + batch_size]
                    
                    for rel_data in batch:
                        start_id = rel_data['startNode']
                        end_id = rel_data['endNode']
                        properties = rel_data.get('properties', {})
                        
                        # Build property string
                        if properties:
                            prop_strings = []
                            for key, value in properties.items():
                                if isinstance(value, str):
                                    value = value.replace("'", "\\'")
                                    prop_strings.append(f"{key}: '{value}'")
                                else:
                                    prop_strings.append(f"{key}: {value}")
                            prop_string = '{' + ', '.join(prop_strings) + '}'
                        else:
                            prop_string = ''
                        
                        # Create relationship
                        query = f"""
                        MATCH (a {{id: '{start_id}'}}), (b {{id: '{end_id}'}})
                        CREATE (a)-[:{rel_type} {prop_string}]->(b)
                        """
                        
                        try:
                            session.run(query)
                            total_created += 1
                        except Exception as e:
                            print(f"Error creating relationship {start_id} -> {end_id}: {e}")
                
            print(f"  Created {total_created} relationships")
    
    def _validate_import(self):
        """Validate the import by running some checks"""
        with self.driver.session() as session:
            print("\nValidation Results:")
            
            # Count nodes by label
            query = """
            MATCH (n)
            UNWIND labels(n) AS label
            WITH label, count(DISTINCT n) as count
            RETURN label, count
            ORDER BY count DESC
            """
            result = session.run(query)
            print("\nNode counts by label:")
            for record in result:
                print(f"  - {record['label']}: {record['count']}")
            
            # Count relationships
            query = """
            MATCH ()-[r]->()
            RETURN type(r) as type, count(r) as count
            ORDER BY count DESC
            """
            result = session.run(query)
            print("\nRelationship counts:")
            for record in result:
                print(f"  - {record['type']}: {record['count']}")
    
    def _categorize_variable(self, var_name: str) -> str:
        """Categorize variables based on naming patterns"""
        var_lower = var_name.lower()
        
        if 'session' in var_lower:
            return 'Session'
        elif 'transaction' in var_lower or 'purchase' in var_lower or 'revenue' in var_lower:
            return 'Ecommerce'
        elif 'item' in var_lower:
            return 'Item'
        elif 'currency' in var_lower:
            return 'Currency'
        elif 'firestore' in var_lower:
            return 'Firestore'
        elif 'cookie' in var_lower or '_fb' in var_lower or '_ga' in var_lower:
            return 'Cookie'
        elif 'page_' in var_lower or 'hostname' in var_lower:
            return 'Page'
        elif 'user' in var_lower or 'client_id' in var_lower:
            return 'User'
        elif 'cd' in var_lower or 'dimension' in var_lower:
            return 'Custom Dimension'
        elif 'cg' in var_lower:
            return 'Custom Group'
        elif 'event' in var_lower:
            return 'Event'
        elif 'campaign' in var_lower:
            return 'Campaign'
        elif 'fb' in var_lower or 'facebook' in var_lower:
            return 'Facebook'
        elif 'tiktok' in var_lower or 'ttclid' in var_lower or '_ttp' in var_lower:
            return 'TikTok'
        elif 'bing' in var_lower or '_uet' in var_lower:
            return 'Bing'
        elif 'meiro' in var_lower:
            return 'Meiro'
        elif 'const' in var_lower or 'undefined' in var_lower:
            return 'Constant'
        elif 'header' in var_lower:
            return 'Header'
        elif 'domain' in var_lower:
            return 'Domain'
        elif 'test' in var_lower:
            return 'Test'
        else:
            return 'Other'
    
    def _create_tag_nodes(self, json_data: List[Dict[str, Any]]):
        """Create tag nodes"""
        with self.driver.session() as session:
            for tag in json_data:
                query = """
                CREATE (t:Tag {
                    name: $name,
                    type: $type,
                    template_name: $template_name,
                    template_id: $template_id,
                    direct_variable_count: $direct_count,
                    total_variable_count: $total_count
                })
                """
                
                template_info = tag.get('custom_template_info', {}) or {}
                
                session.run(query, 
                    name=tag['name'],
                    type=tag['type'],
                    template_name=template_info.get('name'),
                    template_id=template_info.get('template_id'),
                    direct_count=len(tag.get('direct_variables', [])),
                    total_count=len(tag.get('all_variables', {}))
                )
            print(f"Created {len(json_data)} tag nodes")
    
    def _create_variable_nodes(self, variables: set, categories: dict):
        """Create variable nodes"""
        with self.driver.session() as session:
            for var_name in variables:
                query = """
                CREATE (v:Variable {
                    name: $name,
                    category: $category
                })
                """
                session.run(query, 
                    name=var_name,
                    category=categories.get(var_name, 'Other')
                )
            print(f"Created {len(variables)} variable nodes")
    
    def _create_category_nodes(self, categories: set):
        """Create category nodes"""
        with self.driver.session() as session:
            for category in categories:
                query = "CREATE (c:Category {name: $name})"
                session.run(query, name=category)
            print(f"Created {len(categories)} category nodes")
    
    def _create_template_nodes(self, json_data: List[Dict[str, Any]]):
        """Create template nodes"""
        templates = set()
        with self.driver.session() as session:
            for tag in json_data:
                template_info = tag.get('custom_template_info')
                if template_info:
                    template_key = (template_info['name'], template_info['template_id'])
                    if template_key not in templates:
                        templates.add(template_key)
                        query = """
                        CREATE (template:Template {
                            name: $name,
                            id: $id
                        })
                        """
                        session.run(query, 
                            name=template_info['name'],
                            id=template_info['template_id']
                        )
            print(f"Created {len(templates)} template nodes")
    
    def _create_tag_type_nodes(self, json_data: List[Dict[str, Any]]):
        """Create tag type nodes"""
        tag_types = set(tag['type'] for tag in json_data)
        with self.driver.session() as session:
            for tag_type in tag_types:
                query = "CREATE (tt:TagType {name: $name})"
                session.run(query, name=tag_type)
            print(f"Created {len(tag_types)} tag type nodes")
    
    def _create_tag_variable_relationships(self, json_data: List[Dict[str, Any]]):
        """Create relationships between tags and variables"""
        with self.driver.session() as session:
            relationship_count = 0
            
            for tag in json_data:
                tag_name = tag['name']
                
                # Direct variable relationships
                for var_name in tag.get('direct_variables', []):
                    query = """
                    MATCH (t:Tag {name: $tag_name}), (v:Variable {name: $var_name})
                    CREATE (t)-[:USES_DIRECTLY]->(v)
                    """
                    session.run(query, tag_name=tag_name, var_name=var_name)
                    relationship_count += 1
                
                # All variable relationships with usage count
                for var_name, usage_count in tag.get('all_variables', {}).items():
                    if var_name not in tag.get('direct_variables', []):
                        query = """
                        MATCH (t:Tag {name: $tag_name}), (v:Variable {name: $var_name})
                        CREATE (t)-[:USES {count: $usage_count}]->(v)
                        """
                        session.run(query, 
                            tag_name=tag_name, 
                            var_name=var_name, 
                            usage_count=usage_count
                        )
                        relationship_count += 1
            
            print(f"Created {relationship_count} tag-variable relationships")
    
    def _create_variable_dependencies(self, json_data: List[Dict[str, Any]]):
        """Create dependency relationships between variables"""
        dependencies = [
            ("BASE DECODE - heureka_gtm_ga_info", "ED - cookies.heureka_gtm_ga_info"),
            ("GA4 - session_id - heureka_gtm_ga_info - CZ/SK mp1", "BASE DECODE - heureka_gtm_ga_info"),
            ("FB Contents - items - item_id", "ED - items"),
            ("get Main domain from page_location (Frontend)", "ED - page_location"),
            ("LT - currency for domain", "get Main domain from page_location (Frontend)"),
            ("Item category CZ/SK for MPv1", "ED - items.0.item_category"),
            ("Item category 2 CZ/SK for MPv1", "ED - items.0.item_category"),
            ("Item category 3 CZ/SK for MPv1", "ED - items.0.item_category"),
            ("Item category 4 CZ/SK for MPv1", "ED - items.0.item_category"),
            ("Item category 5 CZ/SK for MPv1", "ED - items.0.item_category"),
            ("UA - transaction revenue 'x-ga-mp1-tr'", "ED - value"),
        ]
        
        with self.driver.session() as session:
            dependency_count = 0
            for dependent, dependency in dependencies:
                query = """
                MATCH (v1:Variable {name: $dependent}), (v2:Variable {name: $dependency})
                CREATE (v1)-[:DEPENDS_ON]->(v2)
                """
                try:
                    session.run(query, dependent=dependent, dependency=dependency)
                    dependency_count += 1
                except Exception as e:
                    print(f"Could not create dependency {dependent} -> {dependency}: {e}")
            
            print(f"Created {dependency_count} variable dependency relationships")
    
    def _create_template_relationships(self, json_data: List[Dict[str, Any]]):
        """Create relationships between tags and templates"""
        with self.driver.session() as session:
            relationship_count = 0
            for tag in json_data:
                template_info = tag.get('custom_template_info')
                if template_info:
                    query = """
                    MATCH (t:Tag {name: $tag_name}), (template:Template {name: $template_name, id: $template_id})
                    CREATE (t)-[:USES_TEMPLATE]->(template)
                    """
                    session.run(query,
                        tag_name=tag['name'],
                        template_name=template_info['name'],
                        template_id=template_info['template_id']
                    )
                    relationship_count += 1
            print(f"Created {relationship_count} tag-template relationships")
    
    def _create_category_relationships(self):
        """Create relationships between variables and categories"""
        with self.driver.session() as session:
            query = """
            MATCH (v:Variable), (c:Category)
            WHERE v.category = c.name
            CREATE (v)-[:BELONGS_TO]->(c)
            """
            result = session.run(query)
            print("Created variable-category relationships")
    
    def _create_tag_type_relationships(self, json_data: List[Dict[str, Any]]):
        """Create relationships between tags and tag types"""
        with self.driver.session() as session:
            for tag in json_data:
                query = """
                MATCH (t:Tag {name: $tag_name}), (tt:TagType {name: $tag_type})
                CREATE (t)-[:IS_TYPE]->(tt)
                """
                session.run(query, tag_name=tag['name'], tag_type=tag['type'])
            print("Created tag-type relationships")
    
    def run_analysis_query(self, query: str, description: str = ""):
        """Run an analysis query and return results"""
        with self.driver.session() as session:
            result = session.run(query)
            records = [record.data() for record in result]
            if description:
                print(f"\n{description}")
                print("-" * len(description))
            return records

# Main function for command line usage
def main():
    """Main function for loading output2.json dataset into Neo4j"""
    parser = argparse.ArgumentParser(description='Load GTM Analysis Dataset into Neo4j')
    parser.add_argument('dataset', nargs='?', default='output2.json', 
                       help='Path to dataset file (default: output2.json)')
    parser.add_argument('--uri', default='bolt://localhost:7687',
                       help='Neo4j URI (default: bolt://localhost:7687)')
    parser.add_argument('--user', default='neo4j',
                       help='Neo4j username (default: neo4j)')
    parser.add_argument('--password', required=True,
                       help='Neo4j password')
    parser.add_argument('--clear', action='store_true',
                       help='Clear existing data before loading')
    
    args = parser.parse_args()
    
    # Check if dataset file exists
    if not os.path.exists(args.dataset):
        print(f"Error: Dataset file '{args.dataset}' not found.")
        sys.exit(1)
    
    # Load dataset
    print(f"Loading dataset from {args.dataset}...")
    with open(args.dataset, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    
    # Initialize loader
    loader = GTMContainerGraphLoader(args.uri, args.user, args.password)
    
    try:
        # Load the dataset
        loader.load_dataset(dataset, clear_existing=args.clear)
        
        # Run some example queries
        print("\n" + "="*60)
        print("EXAMPLE QUERIES")
        print("="*60)
        
        # Most connected variables
        most_connected = loader.run_analysis_query("""
            MATCH (v:Variable)
            OPTIONAL MATCH (v)<-[r:USES_VARIABLE|REFERENCES_VARIABLE]-()
            WITH v, count(r) as connections
            WHERE connections > 0
            RETURN v.name as variable, v.type as type, connections
            ORDER BY connections DESC
            LIMIT 10
        """, "\nTop 10 Most Connected Variables:")
        
        for record in most_connected:
            print(f"  {record['variable']} ({record['type']}): {record['connections']} connections")
        
        # Unused variables count
        unused_count = loader.run_analysis_query("""
            MATCH (v:Variable)
            WHERE v.is_used = false
            RETURN count(v) as count
        """, "\nUnused Variables:")
        
        for record in unused_count:
            print(f"  Total: {record['count']} unused variables")
        
        # Container health
        health = loader.run_analysis_query("""
            MATCH (c:Container)
            RETURN c.name as name, c.health_score as score, c.total_variables as vars
        """, "\nContainer Health:")
        
        for record in health:
            print(f"  {record['name']}: Health Score {record['score']}/100 ({record['vars']} variables)")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        loader.close()
    
    print("\n✅ Done! You can now explore the graph in Neo4j Browser.")
    print("\nUseful Cypher queries:")
    print("1. Find all dependencies of a variable:")
    print("   MATCH (v:Variable {name: 'Your Variable'})<-[:USES_VARIABLE]-(n)")
    print("   RETURN v, n")
    print("\n2. Show duplicate variable groups:")
    print("   MATCH (v:Variable)-[:DUPLICATE_OF]->(g:DuplicateGroup)")
    print("   RETURN v, g")
    print("\n3. Find trigger-tag relationships:")
    print("   MATCH (t:Trigger)-[:FIRES_TAG]->(tag:Tag)")
    print("   RETURN t, tag LIMIT 50")

if __name__ == '__main__':
    main()