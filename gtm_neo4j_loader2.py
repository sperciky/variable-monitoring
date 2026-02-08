import json
from neo4j import GraphDatabase
from typing import Dict, List, Any

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
    
    def create_indexes(self):
        """Create indexes for better performance"""
        with self.driver.session() as session:
            indexes = [
                "CREATE INDEX tag_name_index IF NOT EXISTS FOR (t:Tag) ON (t.name)",
                "CREATE INDEX variable_name_index IF NOT EXISTS FOR (v:Variable) ON (v.name)",
                "CREATE INDEX category_name_index IF NOT EXISTS FOR (c:Category) ON (c.name)",
                "CREATE INDEX template_name_index IF NOT EXISTS FOR (template:Template) ON (template.name)"
            ]
            
            for index in indexes:
                try:
                    session.run(index)
                    print(f"Index created: {index.split('_index')[0].split()[-1]}")
                except Exception as e:
                    print(f"Index creation failed or already exists: {e}")
    
    def load_gtm_data(self, json_data: List[Dict[str, Any]]):
        """Load GTM container data into Neo4j"""
        
        # Extract all unique variables and their metadata
        all_variables = set()
        variable_categories = {}
        
        for tag in json_data:
            for var_name in tag.get('all_variables', {}):
                all_variables.add(var_name)
                # Categorize variables based on naming patterns
                category = self._categorize_variable(var_name)
                variable_categories[var_name] = category
        
        # Create nodes
        self._create_tag_nodes(json_data)
        self._create_variable_nodes(all_variables, variable_categories)
        self._create_category_nodes(set(variable_categories.values()))
        self._create_template_nodes(json_data)
        self._create_tag_type_nodes(json_data)
        
        # Create relationships
        self._create_tag_variable_relationships(json_data)
        self._create_variable_dependencies(json_data)
        self._create_template_relationships(json_data)
        self._create_category_relationships()
        self._create_tag_type_relationships(json_data)
        
        print("GTM container data loaded successfully!")
    
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

# Usage example
def load_gtm_container(json_file_path: str, neo4j_uri: str, username: str, password: str):
    """Load GTM container data from JSON file into Neo4j"""
    
    # Load JSON data
    with open(json_file_path, 'r') as f:
        gtm_data = json.load(f)
    
    # Initialize loader
    loader = GTMContainerGraphLoader(neo4j_uri, username, password)
    
    try:
        # Clear existing data (optional)
        # loader.clear_database()
        
        # Create indexes
        loader.create_indexes()
        
        # Load data
        loader.load_gtm_data(gtm_data)
        
        print("\nData loading complete!")
        
        # Run some basic analysis
        print("\n=== BASIC ANALYSIS ===")
        
        # Most used variables
        most_used = loader.run_analysis_query("""
            MATCH (v:Variable)<-[:USES_DIRECTLY]-(t:Tag)
            WITH v, count(t) as usage_count
            RETURN v.name as variable, v.category as category, usage_count
            ORDER BY usage_count DESC
            LIMIT 10
        """, "Top 10 Most Used Variables:")
        
        for record in most_used:
            print(f"  {record['variable']} ({record['category']}): {record['usage_count']} tags")
        
        # Template usage
        template_usage = loader.run_analysis_query("""
            MATCH (template:Template)<-[:USES_TEMPLATE]-(t:Tag)
            RETURN template.name as template, count(t) as usage_count
            ORDER BY usage_count DESC
        """, "\nTemplate Usage:")
        
        for record in template_usage:
            print(f"  {record['template']}: {record['usage_count']} tags")
        
    finally:
        loader.close()

# Example usage (uncomment and modify as needed):
# load_gtm_container('output.json', 'bolt://localhost:7687', 'neo4j', 'password')