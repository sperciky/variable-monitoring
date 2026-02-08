import json
import networkx as nx
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict, Counter
import pandas as pd

class GTMGraphVisualizer:
    def __init__(self, json_file_path: str):
        """Initialize with GTM container JSON data"""
        with open(json_file_path, 'r') as f:
            self.data = json.load(f)
        
        self.graph = nx.DiGraph()
        self.variable_usage = defaultdict(int)
        self.tag_complexity = {}
        self.build_graph()
    
    def build_graph(self):
        """Build NetworkX graph from GTM data"""
        # Add tag nodes
        for tag in self.data:
            tag_name = tag['name']
            self.graph.add_node(tag_name, 
                               node_type='tag',
                               tag_type=tag['type'],
                               template=tag.get('custom_template_info', {}).get('name', 'None'))
            
            # Track tag complexity
            self.tag_complexity[tag_name] = len(tag.get('all_variables', {}))
            
            # Add variable nodes and edges
            for var_name, usage_count in tag.get('all_variables', {}).items():
                if not self.graph.has_node(var_name):
                    self.graph.add_node(var_name, 
                                      node_type='variable',
                                      category=self._categorize_variable(var_name))
                
                # Add edge with usage count
                self.graph.add_edge(tag_name, var_name, weight=usage_count)
                self.variable_usage[var_name] += usage_count
    
    def _categorize_variable(self, var_name: str) -> str:
        """Categorize variables based on naming patterns"""
        var_lower = var_name.lower()
        
        categories = {
            'session': 'Session',
            'transaction': 'Ecommerce', 'purchase': 'Ecommerce', 'revenue': 'Ecommerce',
            'item': 'Item',
            'currency': 'Currency',
            'firestore': 'Firestore',
            'cookie': 'Cookie', '_fb': 'Cookie', '_ga': 'Cookie',
            'page_': 'Page', 'hostname': 'Page',
            'user': 'User', 'client_id': 'User',
            'cd': 'Custom Dimension', 'dimension': 'Custom Dimension',
            'cg': 'Custom Group',
            'event': 'Event',
            'campaign': 'Campaign',
            'facebook': 'Facebook', 'fb ': 'Facebook',
            'tiktok': 'TikTok', 'ttclid': 'TikTok', '_ttp': 'TikTok',
            'bing': 'Bing', '_uet': 'Bing',
            'meiro': 'Meiro',
            'const': 'Constant', 'undefined': 'Constant',
            'header': 'Header',
            'domain': 'Domain',
            'test': 'Test'
        }
        
        for keyword, category in categories.items():
            if keyword in var_lower:
                return category
        return 'Other'
    
    def get_network_stats(self):
        """Calculate network statistics"""
        stats = {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'tag_nodes': len([n for n, d in self.graph.nodes(data=True) if d['node_type'] == 'tag']),
            'variable_nodes': len([n for n, d in self.graph.nodes(data=True) if d['node_type'] == 'variable']),
            'density': nx.density(self.graph),
            'avg_degree': sum(dict(self.graph.degree()).values()) / len(self.graph.nodes()),
        }
        
        return stats
    
    def analyze_variable_usage(self, top_n=20):
        """Analyze most used variables"""
        top_variables = sorted(self.variable_usage.items(), 
                             key=lambda x: x[1], reverse=True)[:top_n]
        
        df = pd.DataFrame(top_variables, columns=['Variable', 'Usage Count'])
        df['Category'] = df['Variable'].apply(self._categorize_variable)
        
        return df
    
    def analyze_tag_complexity(self, top_n=20):
        """Analyze tag complexity by variable count"""
        top_complex = sorted(self.tag_complexity.items(), 
                           key=lambda x: x[1], reverse=True)[:top_n]
        
        df = pd.DataFrame(top_complex, columns=['Tag', 'Variable Count'])
        
        # Add tag type information
        tag_types = {}
        for tag in self.data:
            tag_types[tag['name']] = tag['type']
        
        df['Tag Type'] = df['Tag'].map(tag_types)
        
        return df
    
    def find_shared_variables(self, min_shared=5):
        """Find tags that share many variables"""
        shared_vars = []
        
        tag_vars = {}
        for tag in self.data:
            tag_vars[tag['name']] = set(tag.get('all_variables', {}).keys())
        
        tag_names = list(tag_vars.keys())
        for i, tag1 in enumerate(tag_names):
            for tag2 in tag_names[i+1:]:
                shared = tag_vars[tag1] & tag_vars[tag2]
                if len(shared) >= min_shared:
                    shared_vars.append({
                        'Tag 1': tag1,
                        'Tag 2': tag2,
                        'Shared Variables': len(shared),
                        'Variables': list(shared)[:5]  # Show first 5
                    })
        
        return sorted(shared_vars, key=lambda x: x['Shared Variables'], reverse=True)
    
    def analyze_categories(self):
        """Analyze variable categories"""
        categories = defaultdict(list)
        
        for var_name, usage in self.variable_usage.items():
            category = self._categorize_variable(var_name)
            categories[category].append(usage)
        
        category_stats = {}
        for category, usages in categories.items():
            category_stats[category] = {
                'count': len(usages),
                'total_usage': sum(usages),
                'avg_usage': sum(usages) / len(usages),
                'max_usage': max(usages)
            }
        
        df = pd.DataFrame.from_dict(category_stats, orient='index')
        return df.sort_values('total_usage', ascending=False)
    
    def create_summary_report(self):
        """Create a comprehensive summary report"""
        print("=" * 60)
        print("GTM CONTAINER DEPENDENCY ANALYSIS REPORT")
        print("=" * 60)
        
        # Network Statistics
        stats = self.get_network_stats()
        print(f"\nNETWORK OVERVIEW:")
        print(f"  Total Nodes: {stats['total_nodes']}")
        print(f"  Total Edges: {stats['total_edges']}")
        print(f"  Tags: {stats['tag_nodes']}")
        print(f"  Variables: {stats['variable_nodes']}")
        print(f"  Network Density: {stats['density']:.4f}")
        print(f"  Average Degree: {stats['avg_degree']:.2f}")
        
        # Top Variables
        print(f"\nTOP 10 MOST USED VARIABLES:")
        top_vars = self.analyze_variable_usage(10)
        for _, row in top_vars.iterrows():
            print(f"  {row['Variable'][:50]}... ({row['Category']}): {row['Usage Count']}")
        
        # Most Complex Tags
        print(f"\nMOST COMPLEX TAGS (by variable count):")
        complex_tags = self.analyze_tag_complexity(10)
        for _, row in complex_tags.iterrows():
            print(f"  {row['Tag'][:50]}... ({row['Tag Type']}): {row['Variable Count']} vars")
        
        # Category Analysis
        print(f"\nVARIABLE CATEGORIES:")
        categories = self.analyze_categories()
        for category, stats in categories.head(10).iterrows():
            print(f"  {category}: {stats['count']} vars, {stats['total_usage']} total usage")
        
        # Shared Variables
        print(f"\nTAGS WITH MANY SHARED VARIABLES:")
        shared = self.find_shared_variables(5)
        for item in shared[:5]:
            tag1 = item['Tag 1'][:30] + "..." if len(item['Tag 1']) > 30 else item['Tag 1']
            tag2 = item['Tag 2'][:30] + "..." if len(item['Tag 2']) > 30 else item['Tag 2']
            print(f"  {tag1} <-> {tag2}: {item['Shared Variables']} shared")
        
        print("\n" + "=" * 60)
    
    def create_visualizations(self):
        """Create visualization plots"""
        plt.style.use('default')
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. Variable Usage Distribution
        top_vars = self.analyze_variable_usage(15)
        axes[0,0].barh(range(len(top_vars)), top_vars['Usage Count'])
        axes[0,0].set_yticks(range(len(top_vars)))
        axes[0,0].set_yticklabels([v[:30] + '...' if len(v) > 30 else v 
                                  for v in top_vars['Variable']], fontsize=8)
        axes[0,0].set_xlabel('Usage Count')
        axes[0,0].set_title('Top 15 Most Used Variables')
        axes[0,0].invert_yaxis()
        
        # 2. Tag Complexity Distribution
        complexities = list(self.tag_complexity.values())
        axes[0,1].hist(complexities, bins=20, alpha=0.7, color='skyblue')
        axes[0,1].set_xlabel('Number of Variables')
        axes[0,1].set_ylabel('Number of Tags')
        axes[0,1].set_title('Tag Complexity Distribution')
        
        # 3. Category Analysis
        categories = self.analyze_categories()
        axes[1,0].bar(range(len(categories.head(10))), categories.head(10)['total_usage'])
        axes[1,0].set_xticks(range(len(categories.head(10))))
        axes[1,0].set_xticklabels(categories.head(10).index, rotation=45, ha='right')
        axes[1,0].set_ylabel('Total Usage')
        axes[1,0].set_title('Variable Categories by Usage')
        
        # 4. Tag Type Distribution
        tag_types = [tag['type'] for tag in self.data]
        type_counts = Counter(tag_types)
        axes[1,1].pie(type_counts.values(), labels=type_counts.keys(), autopct='%1.1f%%')
        axes[1,1].set_title('Tag Type Distribution')
        
        plt.tight_layout()
        plt.show()
        
        return fig

# Usage example
def analyze_gtm_container(json_file_path: str):
    """Complete analysis of GTM container"""
    
    visualizer = GTMGraphVisualizer(json_file_path)
    
    # Create summary report
    visualizer.create_summary_report()
    
    # Create visualizations
    visualizer.create_visualizations()
    
    # Export detailed data
    print("\nDetailed Analysis Data:")
    print("\n1. Variable Usage Analysis:")
    var_analysis = visualizer.analyze_variable_usage(20)
    print(var_analysis)
    
    print("\n2. Tag Complexity Analysis:")
    complexity_analysis = visualizer.analyze_tag_complexity(15)
    print(complexity_analysis)
    
    print("\n3. Shared Variables Analysis:")
    shared_analysis = visualizer.find_shared_variables(3)
    for item in shared_analysis[:10]:
        print(f"Tags: {item['Tag 1']} <-> {item['Tag 2']}")
        print(f"Shared: {item['Shared Variables']} variables")
        print(f"Examples: {', '.join(item['Variables'])}")
        print("-" * 50)
    
    return visualizer

# Example usage:
# analyzer = analyze_gtm_container('output.json')