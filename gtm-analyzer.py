import json
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple

class GTMAnalyzer:
    def __init__(self, gtm_data: dict, include_paused_tags: bool = True):
        self.gtm_data = gtm_data
        self.container_version = gtm_data.get('containerVersion', {})
        self.variables = self.container_version.get('variable', [])
        self.tags = self.container_version.get('tag', [])
        self.triggers = self.container_version.get('trigger', [])
        self.transformations = self.container_version.get('transformation', [])
        self.clients = self.container_version.get('client', [])
        self.custom_templates = self.container_version.get('customTemplate', [])
        self.folders = self.container_version.get('folder', [])
        self.built_in_variables = self.container_version.get('builtInVariable', [])
        self.include_paused_tags = include_paused_tags
        
        # Track unknown component types for translation
        self.unknown_tag_types = set()
        self.unknown_variable_types = set()
        self.unknown_trigger_types = set()
        self.unknown_client_types = set()
        self.unknown_builtin_types = set()
        
    def get_variable_references_in_value(self, value: str) -> Set[str]:
        """Extract variable references from a string value (e.g., {{Variable Name}})"""
        references = set()
        if isinstance(value, str):
            import re
            # Match {{Variable Name}} pattern
            matches = re.findall(r'\{\{([^}]+)\}\}', value)
            references.update(matches)
        return references
    
    def get_variable_references_in_object(self, obj) -> Set[str]:
        """Recursively find all variable references in any object (dict, list, or string)"""
        references = set()
        
        if isinstance(obj, str):
            references.update(self.get_variable_references_in_value(obj))
        elif isinstance(obj, dict):
            # Check all values in the dictionary
            for key, value in obj.items():
                references.update(self.get_variable_references_in_object(value))
        elif isinstance(obj, list):
            # Check all items in the list
            for item in obj:
                references.update(self.get_variable_references_in_object(item))
        
        return references
    
    def test_variable_detection(self):
        """Test function to verify variable detection is working"""
        print("Testing variable reference detection...")
        
        # Test string with variable reference
        test_cases = [
            ("Simple reference", "{{ED - offer_id}}"),
            ("Multiple refs", "Value is {{Var1}} and {{Var2}}"),
            ("Nested in dict", {"value": "{{ED - offer_id}}"}),
            ("Nested in list", [{"value": "{{ED - offer_id}}"}]),
            ("Deep nesting", {"list": [{"map": [{"value": "{{ED - offer_id}}"}]}]})
        ]
        
        for name, test_case in test_cases:
            refs = self.get_variable_references_in_object(test_case)
            print(f"  {name}: {refs}")
        
        print()
    
    def find_unused_custom_templates(self) -> List[Dict]:
        """Find custom templates that are not used by any variable, tag, or client"""
        unused_templates = []
        
        # Get all custom template IDs and their types
        template_usage = {}
        for template in self.custom_templates:
            container_id = template.get('containerId', '')
            template_id = template.get('templateId', '')
            
            # Check if it's a gallery template
            gallery_ref = template.get('galleryReference', {})
            gallery_template_id = gallery_ref.get('galleryTemplateId', '')
            
            # Determine the template type ID used by variables/tags/clients
            # ALWAYS use the standard format as primary (variables/tags/clients use this)
            template_type = f"cvt_{container_id}_{template_id}"

            # Check if it's a gallery template
            if gallery_template_id:
                is_gallery = True
            else:
                is_gallery = False
            
            # Parse templateData to determine template category and get ID from templateData
            template_data = template.get('templateData', '')
            template_category = 'UNKNOWN'
            template_data_id = None
            
            if isinstance(template_data, str):
                import re
                # Get category (TAG/MACRO/CLIENT)
                type_match = re.search(r'"type"\s*:\s*"(TAG|MACRO|CLIENT)"', template_data)
                if type_match:
                    template_category = type_match.group(1)
                
                # Get ID from templateData
                id_match = re.search(r'"id"\s*:\s*"([^"]+)"', template_data)
                if id_match:
                    template_data_id = id_match.group(1)
            
            # Add both possible IDs to track usage
            template_info = {
                'template': template,
                'category': template_category,
                'is_gallery': is_gallery,
                'gallery_id': gallery_template_id,
                'used': False,
                'used_by': []
            }

            # Track by primary ID (standard format)
            template_usage[template_type] = template_info

            # For gallery templates, also track by gallery ID (in case variables use that format)
            if gallery_template_id:
                gallery_type = f"cvt_{gallery_template_id}"
                if gallery_type != template_type:
                    template_usage[gallery_type] = template_info

            # Also track by templateData ID if different
            if template_data_id and template_data_id != template_type:
                template_usage[template_data_id] = template_info
        
        # Check variables for MACRO template usage
        for var in self.variables:
            var_type = var.get('type', '')
            if var_type in template_usage and template_usage[var_type]['category'] == 'MACRO':
                template_usage[var_type]['used'] = True
                if {
                    'type': 'variable',
                    'name': var['name'],
                    'id': var['variableId']
                } not in template_usage[var_type]['used_by']:
                    template_usage[var_type]['used_by'].append({
                        'type': 'variable',
                        'name': var['name'],
                        'id': var['variableId']
                    })
        
        # Check tags for TAG template usage
        for tag in self.tags:
            tag_type = tag.get('type', '')
            if tag_type in template_usage and template_usage[tag_type]['category'] == 'TAG':
                template_usage[tag_type]['used'] = True
                if {
                    'type': 'tag',
                    'name': tag['name'],
                    'id': tag['tagId']
                } not in template_usage[tag_type]['used_by']:
                    template_usage[tag_type]['used_by'].append({
                        'type': 'tag',
                        'name': tag['name'],
                        'id': tag['tagId']
                    })
        
        # Check clients for CLIENT template usage
        for client in self.clients:
            client_type = client.get('type', '')
            if client_type in template_usage and template_usage[client_type]['category'] == 'CLIENT':
                template_usage[client_type]['used'] = True
                if {
                    'type': 'client',
                    'name': client['name'],
                    'id': client.get('clientId', 'Unknown')
                } not in template_usage[client_type]['used_by']:
                    template_usage[client_type]['used_by'].append({
                        'type': 'client',
                        'name': client['name'],
                        'id': client.get('clientId', 'Unknown')
                    })
        
        # Collect unused templates (avoid duplicates from same template tracked by multiple IDs)
        seen_templates = set()
        for template_type, usage_info in template_usage.items():
            if not usage_info['used']:
                template = usage_info['template']
                template_fingerprint = template.get('fingerprint', '')
                
                # Use fingerprint to avoid duplicate entries
                if template_fingerprint not in seen_templates:
                    seen_templates.add(template_fingerprint)
                    unused_templates.append({
                        'name': template.get('name', 'Unnamed Template'),
                        'templateId': template.get('templateId', ''),
                        'type': template_type,
                        'category': usage_info['category'],
                        'is_gallery': usage_info['is_gallery'],
                        'gallery_id': usage_info['gallery_id'],
                        'fingerprint': template_fingerprint
                    })
        
        return unused_templates
    
    def find_unused_variables(self, debug=False) -> List[Dict]:
        """Find all variables that are not referenced anywhere in the container"""
        # Create a map of variable names
        variable_map = {var['name']: var for var in self.variables}
        
        # Find all variable references
        referenced_variables = set()
        reference_locations = defaultdict(list)  # Track where each variable is referenced
        
        # Check ALL components for variable references
        components_to_check = [
            ('tag', self.tags),
            ('trigger', self.triggers),
            ('variable', self.variables),
            ('transformation', self.transformations),
            ('client', self.clients),
            ('customTemplate', self.custom_templates)
        ]
        
        for component_type, components in components_to_check:
            for component in components:
                # Handle paused tags based on configuration
                if component_type == 'tag' and component.get('paused', False):
                    if not self.include_paused_tags:
                        continue
                    # If including paused tags, mark them in the reference location
                
                # Get all variable references in this component
                component_refs = self.get_variable_references_in_object(component)
                
                # For variables, don't count self-references
                if component_type == 'variable' and component.get('name') in component_refs:
                    component_refs.discard(component['name'])
                
                # Track where each variable is referenced
                for ref in component_refs:
                    component_id = (component.get(f'{component_type}Id') or 
                                  component.get('tagId') or 
                                  component.get('triggerId') or 
                                  component.get('variableId') or 
                                  component.get('transformationId') or 
                                  component.get('clientId') or 
                                  component.get('templateId') or 
                                  'Unknown')
                    
                    paused_status = " (PAUSED)" if component_type == 'tag' and component.get('paused', False) else ""
                    
                    reference_locations[ref].append({
                        'type': component_type,
                        'name': component.get('name', 'Unnamed') + paused_status,
                        'id': component_id,
                        'paused': component.get('paused', False) if component_type == 'tag' else False
                    })
                
                referenced_variables.update(component_refs)
        
        if debug:
            print("DEBUG: Referenced variables found:")
            for var_name in sorted(referenced_variables):
                print(f"  - {var_name}")
                for loc in reference_locations[var_name]:
                    print(f"    Used in {loc['type']}: {loc['name']} (ID: {loc['id']})")
        
        # Find unused variables
        unused_variables = []
        for var in self.variables:
            if var['name'] not in referenced_variables:
                unused_variables.append({
                    'name': var['name'],
                    'variableId': var['variableId'],
                    'type': var['type']
                })
        
        return unused_variables
    
    def extract_format_value_info(self, format_value: dict) -> dict:
        """Extract and summarize formatValue settings"""
        if not format_value:
            return None
        
        info = {}
        
        # Check for value conversions
        conversions = [
            ('convertNullToValue', 'Convert NULL to'),
            ('convertUndefinedToValue', 'Convert undefined to'),
            ('convertTrueToValue', 'Convert true to'),
            ('convertFalseToValue', 'Convert false to'),
            ('caseConversionType', 'Case conversion'),
            ('convertNaNToValue', 'Convert NaN to'),
            ('convertEmptyToValue', 'Convert empty to')
        ]
        
        for key, label in conversions:
            if key in format_value:
                value = format_value[key]
                if isinstance(value, dict) and 'value' in value:
                    info[label] = value['value']
                else:
                    info[label] = value
        
        return info if info else None
    
    def find_duplicate_variables(self) -> Dict[str, List[List[Dict]]]:
        """Find variables that reference the same data source"""
        duplicates = {
            'data_layer_duplicates': [],
            'event_data_duplicates': [],
            'cookie_duplicates': [],
            'js_variable_duplicates': [],
            'url_duplicates': [],
            'custom_template_duplicates': [],
            'other_duplicates': []
        }
        
        # Group variables by their type and key data
        variable_groups = defaultdict(lambda: defaultdict(list))
        
        for var in self.variables:
            var_type = var.get('type')
            parameters = var.get('parameter', [])
            format_value = var.get('formatValue', {})
            
            # Extract key information based on variable type
            key_info = {}
            for param in parameters:
                key_info[param.get('key')] = param.get('value')
            
            # Extract formatValue info
            format_info = self.extract_format_value_info(format_value)
            
            # Data Layer Variable (type 'v')
            if var_type == 'v' and 'name' in key_info:
                key = f"datalayer|{key_info['name']}|v{key_info.get('dataLayerVersion', '2')}"
                variable_groups['data_layer_duplicates'][key].append({
                    'name': var['name'],
                    'variableId': var['variableId'],
                    'type': var_type,
                    'path': key_info['name'],
                    'version': key_info.get('dataLayerVersion', '2'),
                    'defaultValue': key_info.get('defaultValue', ''),
                    'formatValue': format_info
                })
            
            # Event Data Variable (type 'ed')
            elif var_type == 'ed' and 'keyPath' in key_info:
                key = f"eventdata|{key_info['keyPath']}"
                variable_groups['event_data_duplicates'][key].append({
                    'name': var['name'],
                    'variableId': var['variableId'],
                    'type': var_type,
                    'keyPath': key_info['keyPath'],
                    'defaultValue': key_info.get('defaultValue', ''),
                    'formatValue': format_info
                })
            
            # Cookie Variable (type 'k')
            elif var_type == 'k' and 'name' in key_info:
                key = f"cookie|{key_info['name']}"
                variable_groups['cookie_duplicates'][key].append({
                    'name': var['name'],
                    'variableId': var['variableId'],
                    'type': var_type,
                    'cookieName': key_info['name'],
                    'formatValue': format_info
                })
            
            # JavaScript Variable (type 'j')
            elif var_type == 'j' and 'name' in key_info:
                key = f"jsvar|{key_info['name']}"
                variable_groups['js_variable_duplicates'][key].append({
                    'name': var['name'],
                    'variableId': var['variableId'],
                    'type': var_type,
                    'jsVarName': key_info['name'],
                    'formatValue': format_info
                })
            
            # URL Variable (type 'u')
            elif var_type == 'u':
                component = key_info.get('component', 'UNSPECIFIED')
                # Include queryKey in the grouping key for QUERY components,
                # so that variables extracting different query parameters
                # (e.g., gclid vs fbclid vs msclkid) are not treated as duplicates
                query_key = key_info.get('queryKey', '')
                custom_url_source = key_info.get('customUrlSource', '')
                if query_key:
                    key = f"url|{component}|{query_key}"
                elif custom_url_source:
                    key = f"url|{component}|{custom_url_source}"
                else:
                    key = f"url|{component}"
                variable_groups['url_duplicates'][key].append({
                    'name': var['name'],
                    'variableId': var['variableId'],
                    'type': var_type,
                    'component': component,
                    'queryKey': query_key,
                    'formatValue': format_info
                })
            
            # Custom Template Variables (type starts with 'cvt_')
            elif var_type and var_type.startswith('cvt_'):
                # For custom templates, create a key based on the template type and key parameters
                template_key_params = []
                for param in ['queryParamName', 'pageLocation', 'keyPath', 'name', 'key']:
                    if param in key_info:
                        template_key_params.append(f"{param}:{key_info[param]}")
                
                if template_key_params:
                    key = f"custom|{var_type}|{'|'.join(sorted(template_key_params))}"
                    variable_groups['custom_template_duplicates'][key].append({
                        'name': var['name'],
                        'variableId': var['variableId'],
                        'type': var_type,
                        'parameters': key_info,
                        'formatValue': format_info
                    })
        
        # Collect duplicate groups
        for duplicate_type, groups in variable_groups.items():
            for key, variables in groups.items():
                if len(variables) > 1:
                    duplicates[duplicate_type].append(variables)
        
        return duplicates
    
    def analyze_builtin_variables(self) -> Dict:
        """Analyze built-in variables and their types"""
        builtin_analysis = {
            'total_builtin_variables': len(self.built_in_variables),
            'builtin_by_type': {},
            'builtin_details': []
        }
        
        # Process each built-in variable
        for builtin in self.built_in_variables:
            var_type = builtin.get('type', 'Unknown')
            human_name = self.get_builtin_variable_type_name(var_type)
            
            # Count by type
            if human_name not in builtin_analysis['builtin_by_type']:
                builtin_analysis['builtin_by_type'][human_name] = 0
            builtin_analysis['builtin_by_type'][human_name] += 1
            
            # Add to details
            builtin_analysis['builtin_details'].append({
                'type': var_type,
                'human_name': human_name,
                'enabled': builtin.get('enabled', False)
            })
        
        return builtin_analysis
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive report"""
        unused_vars = self.find_unused_variables()
        all_duplicates = self.find_duplicate_variables()
        unused_templates = self.find_unused_custom_templates()
        builtin_analysis = self.analyze_builtin_variables()
        
        # Detect container type
        is_server_side = len(self.transformations) > 0 or len(self.clients) > 0
        
        # Count total duplicates across all types
        total_duplicate_groups = sum(len(dups) for dups in all_duplicates.values())
        total_duplicate_vars = sum(sum(len(group) for group in dups) for dups in all_duplicates.values())
        
        # Count paused tags
        paused_tags = sum(1 for tag in self.tags if tag.get('paused', False))
        
        report = {
            'summary': {
                'container_type': 'Server-side' if is_server_side else 'Web',
                'total_variables': len(self.variables),
                'total_tags': len(self.tags),
                'paused_tags': paused_tags,
                'include_paused_tags': self.include_paused_tags,
                'total_triggers': len(self.triggers),
                'total_transformations': len(self.transformations),
                'total_clients': len(self.clients),
                'total_custom_templates': len(self.custom_templates),
                'total_builtin_variables': builtin_analysis['total_builtin_variables'],
                'unused_variables': len(unused_vars),
                'unused_custom_templates': len(unused_templates),
                'duplicate_groups': total_duplicate_groups,
                'total_duplicates': total_duplicate_vars
            },
            'unused_variables': unused_vars,
            'unused_custom_templates': unused_templates,
            'duplicate_variables': all_duplicates,
            'builtin_variables': builtin_analysis
        }
        
        return report
    
    def get_custom_template_usage_details(self) -> Dict[str, Dict]:
        """Get detailed usage information for each custom template"""
        template_details = {}
        
        # Initialize details for all custom templates
        for template in self.custom_templates:
            container_id = template.get('containerId', '')
            template_id = template.get('templateId', '')
            
            # Always use the standard constructed ID for custom templates
            standard_template_type = f"cvt_{container_id}_{template_id}"

            # Check if it's a gallery template
            gallery_ref = template.get('galleryReference', {})
            gallery_id = gallery_ref.get('galleryTemplateId', '')
            is_gallery_template = bool(gallery_id)

            # Parse templateData to determine template type
            template_data = template.get('templateData', '')
            template_category = 'UNKNOWN'

            if isinstance(template_data, str):
                import re

                # Look for type field
                type_match = re.search(r'"type"\s*:\s*"(TAG|MACRO|CLIENT)"', template_data)
                if type_match:
                    template_category = type_match.group(1)
            
            # Create detail entries for both IDs if it's a gallery template
            if is_gallery_template and gallery_id:
                # Create a shared detail object
                detail_obj = {
                    'name': template.get('name', 'Unnamed Template'),
                    'templateId': template_id,
                    'containerId': container_id,
                    'category': template_category,
                    'is_gallery': True,
                    'gallery_id': gallery_id,
                    'standard_id': standard_template_type,
                    'used_by_variables': [],
                    'used_by_tags': [],
                    'used_by_clients': [],
                    'total_usage': 0
                }
                # Track under both IDs
                template_details[gallery_id] = detail_obj
                template_details[standard_template_type] = detail_obj
            else:
                # For custom templates, only use standard ID
                template_details[standard_template_type] = {
                    'name': template.get('name', 'Unnamed Template'),
                    'templateId': template_id,
                    'containerId': container_id,
                    'category': template_category,
                    'is_gallery': False,
                    'standard_id': standard_template_type,
                    'used_by_variables': [],
                    'used_by_tags': [],
                    'used_by_clients': [],
                    'total_usage': 0
                }
        
        # Check usage in variables (for MACRO templates)
        for var in self.variables:
            var_type = var.get('type', '')
            if var_type in template_details:
                # Avoid duplicate entries for shared detail objects
                var_entry = {
                    'name': var['name'],
                    'variableId': var['variableId']
                }
                if var_entry not in template_details[var_type]['used_by_variables']:
                    template_details[var_type]['used_by_variables'].append(var_entry)
                    template_details[var_type]['total_usage'] += 1
        
        # Check usage in tags (for TAG templates)
        for tag in self.tags:
            tag_type = tag.get('type', '')
            if tag_type in template_details:
                tag_entry = {
                    'name': tag['name'],
                    'tagId': tag['tagId'],
                    'paused': tag.get('paused', False)
                }
                if tag_entry not in template_details[tag_type]['used_by_tags']:
                    template_details[tag_type]['used_by_tags'].append(tag_entry)
                    template_details[tag_type]['total_usage'] += 1
        
        # Check usage in clients (for CLIENT templates)
        for client in self.clients:
            client_type = client.get('type', '')
            if client_type in template_details:
                client_entry = {
                    'name': client['name'],
                    'clientId': client.get('clientId', 'Unknown')
                }
                if client_entry not in template_details[client_type]['used_by_clients']:
                    template_details[client_type]['used_by_clients'].append(client_entry)
                    template_details[client_type]['total_usage'] += 1
        
        # Remove duplicate entries (keep only standard IDs for custom templates)
        unique_details = {}
        seen_templates = set()
        for template_id, details in template_details.items():
            template_key = (details['templateId'], details['containerId'])
            if template_key not in seen_templates:
                seen_templates.add(template_key)
                unique_details[details['standard_id']] = details
        
        return unique_details
    
    def get_variable_usage_details(self) -> Dict[str, Dict]:
        """Get detailed usage information for each variable"""
        usage_details = {}
        
        # Initialize usage details for all variables
        for var in self.variables:
            usage_details[var['name']] = {
                'used_in_tags': [],
                'used_in_triggers': [],
                'used_in_transformations': [],
                'used_in_variables': [],
                'used_in_clients': [],
                'used_in_custom_templates': [],
                'total_usage': 0
            }
        
        # Define components to check
        components_to_check = [
            ('tags', self.tags, 'used_in_tags'),
            ('triggers', self.triggers, 'used_in_triggers'),
            ('transformations', self.transformations, 'used_in_transformations'),
            ('variables', self.variables, 'used_in_variables'),
            ('clients', self.clients, 'used_in_clients'),
            ('customTemplate', self.custom_templates, 'used_in_custom_templates')
        ]
        
        for component_type, components, usage_key in components_to_check:
            for component in components:
                # Skip paused tags based on configuration
                if component_type == 'tags' and component.get('paused', False):
                    if not self.include_paused_tags:
                        continue
                
                # Get all variable references in this component
                component_refs = self.get_variable_references_in_object(component)
                
                # Special handling for custom templates - also check templateData
                if component_type == 'customTemplate':
                    template_data = component.get('templateData', '')
                    if isinstance(template_data, str):
                        template_refs = self.get_variable_references_in_value(template_data)
                        component_refs.update(template_refs)
                
                # For variables, don't count self-references
                if component_type == 'variables' and component.get('name') in component_refs:
                    component_refs.discard(component['name'])
                
                # Update usage details
                for var_name in component_refs:
                    if var_name in usage_details:
                        usage_details[var_name][usage_key].append(component.get('name', f'Unnamed {component_type}'))
                        usage_details[var_name]['total_usage'] += 1
        
        return usage_details
    
    def get_variable_usage_counts(self) -> Dict[str, Dict]:
        """Get usage count by component type for each variable"""
        usage_counts = {}
        
        # Initialize counts for all variables
        for var in self.variables:
            usage_counts[var['name']] = {
                'variable': var,
                'usage_locations': {
                    'tags': 0,
                    'triggers': 0,
                    'variables': 0,
                    'transformations': 0,
                    'clients': 0,
                    'custom_templates': 0
                },
                'usage_components': {
                    'tags': [],
                    'triggers': [],
                    'variables': [],
                    'transformations': [],
                    'clients': [],
                    'custom_templates': []
                },
                'total_references': 0,
                'evaluation_contexts': 0  # Future: count of unique evaluation contexts
            }
        
        # Define components to check with their friendly names
        components_to_check = [
            ('tags', self.tags, 'tags'),
            ('triggers', self.triggers, 'triggers'),
            ('variables', self.variables, 'variables'),
            ('transformations', self.transformations, 'transformations'),
            ('clients', self.clients, 'clients'),
            ('customTemplate', self.custom_templates, 'custom_templates')
        ]
        
        for component_type, components, count_key in components_to_check:
            for component in components:
                # Skip paused tags based on configuration
                if component_type == 'tags' and component.get('paused', False):
                    if not self.include_paused_tags:
                        continue
                
                # Get all variable references in this component
                component_refs = self.get_variable_references_in_object(component)
                
                # Special handling for custom templates - also check templateData
                if component_type == 'customTemplate':
                    template_data = component.get('templateData', '')
                    if isinstance(template_data, str):
                        template_refs = self.get_variable_references_in_value(template_data)
                        component_refs.update(template_refs)
                
                # For variables, don't count self-references
                if component_type == 'variables' and component.get('name') in component_refs:
                    component_refs.discard(component['name'])
                
                # Count occurrences - a variable might be referenced multiple times in one component
                for var_name in component_refs:
                    if var_name in usage_counts:
                        # Count how many times the variable appears in this component
                        occurrences = 0
                        if isinstance(component, dict):
                            occurrences = self.count_variable_occurrences_in_object(component, var_name)
                        
                        if occurrences > 0:
                            # For variables, check if it's a custom template variable
                            actual_count_key = count_key
                            if component_type == 'variables' and component.get('type', '').startswith('cvt_'):
                                # This is a custom template variable, so count it under custom_templates
                                actual_count_key = 'custom_templates'
                            
                            usage_counts[var_name]['usage_locations'][actual_count_key] += 1
                            usage_counts[var_name]['total_references'] += occurrences
                            
                            # Add component name to the list
                            component_name = component.get('name', f'Unnamed {component_type}')
                            if component_type == 'tags' and component.get('paused', False):
                                component_name += ' (PAUSED)'
                            usage_counts[var_name]['usage_components'][actual_count_key].append(component_name)
        
        # Calculate evaluation contexts and potential re-evaluations
        for var_name, counts in usage_counts.items():
            locations = counts['usage_locations']
            # Count of different component types where variable is used
            counts['evaluation_contexts'] = sum(1 for loc, count in locations.items() if count > 0)
            
            # Calculate potential re-evaluations
            # This represents maximum times a variable might be evaluated in a single page/event cycle
            potential_reevals = 0
            
            # Tags: Each tag execution evaluates the variable
            potential_reevals += locations['tags']
            
            # Triggers: Variables in triggers are evaluated when trigger conditions are checked
            # Multiple triggers might fire in same event, each evaluating the variable
            potential_reevals += locations['triggers']
            
            # Variables: If used in other variables, add cascading evaluations
            # Note: This is conservative as GTM has some caching
            potential_reevals += locations['variables']
            
            # Custom Templates: Similar to variables, can cause cascading evaluations
            potential_reevals += locations['custom_templates']
            
            # Transformations: Each transformation execution evaluates the variable
            potential_reevals += locations['transformations']
            
            # Clients: Each client request evaluates the variable
            potential_reevals += locations['clients']
            
            counts['potential_reevaluations'] = potential_reevals
            
            # Minimum re-evaluations (at least once per unique component)
            counts['minimum_reevaluations'] = sum(1 for count in locations.values() if count > 0)
        
        return usage_counts
    
    def get_variable_type_name(self, var_type: str) -> str:
        """Get human-readable name for variable type"""
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
            'rh': 'Request Header',
            'sgtmk': 'Request - Cookie Value'
        }
        
        # Handle custom template variables
        if var_type.startswith('cvt_'):
            return 'Custom Template Variable'
        
        if var_type not in type_names and var_type:
            self.unknown_variable_types.add(var_type)
        
        return type_names.get(var_type, f'Unknown ({var_type})')
    
    def get_tag_type_name(self, tag_type: str) -> str:
        """Get human-readable name for tag type"""
        type_names = {
            'html': 'Custom HTML',
            'img': 'Custom Image',
            'ua': 'Universal Analytics',
            'ga': 'Google Analytics',
            'gaawe': 'GA4 Event',
            'googtag': 'Google Tag',
            'gaawc': 'GA4 Configuration',
            'flc': 'Floodlight Counter',
            'fls': 'Floodlight Sales',
            'awct': 'Google Ads Conversion',
            'sp': 'Google Ads Remarketing',
            'gclidw': 'Conversion Linker',
            'opt': 'Optimize',
            'cegg': 'Criteo',
            'crto': 'Criteo OneTag',
            'pntr': 'Pinterest',
            'twitter_website_tag': 'Twitter',
            'baut': 'Bing Ads',
            'mpm': 'Mouseflow',
            'hjtc': 'Hotjar',
            'zone': 'Zone',
            'veip': 'Ve Interactive',
            'awj': 'ActiveCampaign Site Tracking',
            'lcl': 'Leadfeeder',
            'sdl': 'Data Layer Declaration',
            'awud': 'Adwords User Data',
            'll': 'LinkedIN Insight',
            'ta': 'TikTok Analytics',
            # Server-side tag types
            'sgtmadsct': 'Google Ads Conversion Tracking',
            'sgtmgaaw': 'Google Analytics: GA4'
        }
        
        # Handle custom template tags
        if tag_type.startswith('cvt_'):
            return 'Custom Template Tag'
        
        if tag_type not in type_names and tag_type:
            self.unknown_tag_types.add(tag_type)
        
        return type_names.get(tag_type, f'Unknown Tag ({tag_type})')
    
    def get_trigger_type_name(self, trigger_type: str) -> str:
        """Get human-readable name for trigger type"""
        type_names = {
            'pageview': 'Page View',
            'domReady': 'DOM Ready',
            'windowLoaded': 'Window Loaded',
            'customEvent': 'Custom Event',
            'trigger': 'Always Fire',
            'historyChange': 'History Change',
            'js': 'JavaScript Error',
            'linkClick': 'Click - Just Links',
            'click': 'Click - All Elements',
            'formSubmit': 'Form Submission',
            'elementVisibility': 'Element Visibility',
            'scrollDepth': 'Scroll Depth',
            'timer': 'Timer',
            'youTubeVideo': 'YouTube Video',
            'file': 'File Download',
            'amp': 'AMP',
            'consent': 'Consent',
            'adConversion': 'Ad Conversion',
            'floodlight': 'Floodlight',
            'googleAds': 'Google Ads',
            'googleAdsRemarketing': 'Google Ads Remarketing',
            'http': 'HTTP Request',
            'sdl': 'Server Data Layer',
            'pageError': 'Page Error'
        }
        
        if trigger_type not in type_names and trigger_type:
            self.unknown_trigger_types.add(trigger_type)
        
        return type_names.get(trigger_type, f'Unknown Trigger ({trigger_type})')
    
    def get_client_type_name(self, client_type: str) -> str:
        """Get human-readable name for client type (Server-side GTM)"""
        type_names = {
            'gtm': 'Google Tag Manager',
            'ga4': 'Google Analytics 4',
            'http': 'HTTP Client',
            'universal_analytics': 'Universal Analytics',
            'measurement_protocol': 'Measurement Protocol',
            'firebase': 'Firebase',
            'bigquery': 'BigQuery',
            'firestore': 'Firestore'
        }
        
        # Handle custom client templates
        if client_type.startswith('cvt_'):
            return 'Custom Client Template'
        
        if client_type not in type_names and client_type:
            self.unknown_client_types.add(client_type)
        
        return type_names.get(client_type, f'Unknown Client ({client_type})')
    
    def get_variable_type_for_name(self, var_name: str) -> str:
        """Get the variable type display name for a given variable name"""
        # First check if it's a regular variable
        var = next((v for v in self.variables if v['name'] == var_name), None)
        if var:
            return self.get_variable_type_name(var.get('type', 'Unknown'))
        
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
    
    def get_builtin_variable_type_name(self, builtin_type: str) -> str:
        """Get human-readable name for built-in variable type"""
        # Web container built-in variables
        web_types = {
            'PAGE_URL': 'Page URL',
            'PAGE_HOSTNAME': 'Page Hostname',
            'PAGE_PATH': 'Page Path', 
            'REFERRER': 'Referrer',
            'EVENT': 'Event',
            'CLICK_ELEMENT': 'Click Element',
            'CLICK_CLASSES': 'Click Classes',
            'CLICK_ID': 'Click ID',
            'CLICK_TARGET': 'Click Target',
            'CLICK_URL': 'Click URL',
            'CLICK_TEXT': 'Click Text',
            'FORM_ELEMENT': 'Form Element',
            'FORM_CLASSES': 'Form Classes',
            'FORM_ID': 'Form ID',
            'FORM_TARGET': 'Form Target',
            'FORM_URL': 'Form URL',
            'FORM_TEXT': 'Form Text',
            'ERROR_MESSAGE': 'Error Message',
            'ERROR_URL': 'Error URL',
            'ERROR_LINE': 'Error Line',
            'NEW_HISTORY_URL': 'New History URL',
            'OLD_HISTORY_URL': 'Old History URL',
            'NEW_HISTORY_FRAGMENT': 'New History Fragment',
            'OLD_HISTORY_FRAGMENT': 'Old History Fragment',
            'NEW_HISTORY_STATE': 'New History State',
            'OLD_HISTORY_STATE': 'Old History State',
            'HISTORY_SOURCE': 'History Source',
            'CONTAINER_ID': 'Container ID',
            'CONTAINER_VERSION': 'Container Version',
            'DEBUG_MODE': 'Debug Mode',
            'RANDOM_NUMBER': 'Random Number',
            'HTML_ID': 'HTML ID',
            'ENVIRONMENT_NAME': 'Environment Name',
            'APP_ID': 'App ID',
            'APP_NAME': 'App Name',
            'APP_VERSION_CODE': 'App Version Code',
            'APP_VERSION_NAME': 'App Version Name',
            'CAMPAIGN_CONTENT': 'Campaign Content',
            'CAMPAIGN_MEDIUM': 'Campaign Medium',
            'CAMPAIGN_NAME': 'Campaign Name',
            'CAMPAIGN_SOURCE': 'Campaign Source',
            'CAMPAIGN_TERM': 'Campaign Term',
            'CAMPAIGN_ID': 'Campaign ID',
            'DEVICE_NAME': 'Device Name',
            'EVENT_NAME': 'Event Name',
            'FIRE_BASE_EVENT_PARAMETER_CAMPAIGN': 'Firebase Event Parameter Campaign',
            'FIRE_BASE_EVENT_PARAMETER_CAMPAIGN_ACLID': 'Firebase Event Parameter Campaign ACLID',
            'FIRE_BASE_EVENT_PARAMETER_CAMPAIGN_ANID': 'Firebase Event Parameter Campaign ANID',
            'FIRE_BASE_EVENT_PARAMETER_CAMPAIGN_CLICK_TIMESTAMP': 'Firebase Event Parameter Campaign Click Timestamp',
            'FIRE_BASE_EVENT_PARAMETER_CAMPAIGN_CONTENT': 'Firebase Event Parameter Campaign Content',
            'FIRE_BASE_EVENT_PARAMETER_CAMPAIGN_CP1': 'Firebase Event Parameter Campaign CP1',
            'FIRE_BASE_EVENT_PARAMETER_CAMPAIGN_GCLID': 'Firebase Event Parameter Campaign GCLID',
            'FIRE_BASE_EVENT_PARAMETER_CAMPAIGN_SOURCE': 'Firebase Event Parameter Campaign Source',
            'FIRE_BASE_EVENT_PARAMETER_CAMPAIGN_TERM': 'Firebase Event Parameter Campaign Term',
            'LANGUAGE': 'Language',
            'OS_VERSION': 'OS Version',
            'PLATFORM': 'Platform',
            'SDK_VERSION': 'SDK Version',
            'DEVICE_MARKETING_NAME': 'Device Marketing Name',
            'DEVICE_MODEL': 'Device Model',
            'RESOLUTION': 'Resolution',
            'ADVERTISER_ID': 'Advertiser ID',
            'ADVERTISING_TRACKING_ENABLED': 'Advertising Tracking Enabled',
            'SCREEN_NAME': 'Screen Name',
            'SCREEN_RESOLUTION': 'Screen Resolution',
            'CLIENT_SCREEEN_HEIGHT': 'Client Screen Height',
            'CLIENT_SCREEEN_WIDTH': 'Client Screen Width',
            'CLIENT_VIEWPORT_HEIGHT': 'Client Viewport Height',
            'CLIENT_VIEWPORT_WIDTH': 'Client Viewport Width',
            'CLIENT_NAME': 'Client Name',
            'CLIENT_ID': 'Client ID',
            'CLIENT_VERSION': 'Client Version',
            'VIDEO_PROVIDER': 'Video Provider',
            'VIDEO_URL': 'Video URL', 
            'VIDEO_TITLE': 'Video Title',
            'VIDEO_DURATION': 'Video Duration',
            'VIDEO_PERCENT': 'Video Percent',
            'VIDEO_VISIBLE': 'Video Visible',
            'VIDEO_STATUS': 'Video Status',
            'VIDEO_CURRENT_TIME': 'Video Current Time',
            'PERCENT_VISIBLE': 'Percent Visible',
            'ON_SCREEN_DURATION': 'On Screen Duration',
            'ELEMENT_VISIBILITY_RATIO': 'Element Visibility Ratio',
            'ELEMENT_VISIBILITY_TIME': 'Element Visibility Time',
            'ELEMENT_VISIBILITY_FIRST_TIME': 'Element Visibility First Time',
            'ELEMENT_VISIBILITY_RECENT_TIME': 'Element Visibility Recent Time',
            'REQUEST_PATH': 'Request Path',
            'REQUEST_METHOD': 'Request Method',
            'CLIENT_NAME_VERSION': 'Client Name and Version'
        }
        
        # Server-side container built-in variables  
        server_types = {
            'CLIENT_ID': 'Client ID',
            'CLIENT_NAME': 'Client Name',
            'CONTAINER_ID': 'Container ID',
            'CONTAINER_VERSION': 'Container Version',
            'DEBUG_MODE': 'Debug Mode',
            'ENVIRONMENT_NAME': 'Environment Name',
            'EVENT_NAME': 'Event Name',
            'IP_ADDRESS': 'IP Address',
            'LANGUAGE': 'Language',
            'PAGE_ENCODING': 'Page Encoding',
            'PAGE_LOCATION': 'Page Location',
            'PAGE_REFERRER': 'Page Referrer',
            'PAGE_TITLE': 'Page Title',
            'PROTOCOL_VERSION': 'Protocol Version',
            'REQUEST_METHOD': 'Request Method',
            'REQUEST_PATH': 'Request Path',
            'REQUEST_QUERY': 'Request Query',
            'SCREEN_RESOLUTION': 'Screen Resolution',
            'SERVER_NAME': 'Server Name',
            'TIME': 'Timestamp',
            'USER_AGENT': 'User Agent',
            'USER_IP': 'User IP',
            'VIEWPORT_SIZE': 'Viewport Size',
            'VISITOR_REGION': 'Visitor Region'
        }
        
        # Check if it's in web types first, then server types
        if builtin_type in web_types:
            return web_types[builtin_type]
        elif builtin_type in server_types:
            return server_types[builtin_type]
        else:
            # Track unknown built-in types
            if not hasattr(self, 'unknown_builtin_types'):
                self.unknown_builtin_types = set()
            if builtin_type:
                self.unknown_builtin_types.add(builtin_type)
            return f'Unknown Built-in ({builtin_type})'
    
    def get_all_variable_references_recursive(self, var_name: str, visited: Set[str] = None) -> Dict[str, int]:
        """Get all variables referenced by a variable, including nested references"""
        if visited is None:
            visited = set()
        
        if var_name in visited:
            return {}  # Avoid infinite recursion
        
        visited.add(var_name)
        all_refs = {}
        
        # Find the variable
        var = None
        for v in self.variables:
            if v['name'] == var_name:
                var = v
                break
        
        if not var:
            return {}
        
        # Get direct references
        direct_refs = self.get_variable_references_in_object(var)
        
        # Add each direct reference
        for ref in direct_refs:
            if ref not in all_refs:
                all_refs[ref] = 0
            all_refs[ref] += 1
            
            # Get nested references
            nested_refs = self.get_all_variable_references_recursive(ref, visited.copy())
            for nested_ref, count in nested_refs.items():
                if nested_ref not in all_refs:
                    all_refs[nested_ref] = 0
                all_refs[nested_ref] += count
        
        return all_refs
    
    def analyze_trigger_evaluation_impact(self) -> Dict:
        """Analyze how many times variables need to be evaluated for triggers"""
        trigger_impact = {
            'total_evaluations': 0,
            'evaluations_by_type': {},
            'evaluations_by_variable': {},
            'triggers_analyzed': 0,
            'tag_type_breakdown': {},
            'trigger_details': []
        }
        
        # Get tags that use each trigger (non-paused only)
        trigger_to_tags = {}
        for tag in self.tags:
            if tag.get('paused', False):
                continue
            
            # Get firing triggers
            firing_triggers = tag.get('firingTriggerId', [])
            for trigger_id in firing_triggers:
                if trigger_id not in trigger_to_tags:
                    trigger_to_tags[trigger_id] = []
                trigger_to_tags[trigger_id].append(tag)
        
        # Analyze each trigger that's attached to non-paused tags
        for trigger in self.triggers:
            trigger_id = trigger.get('triggerId')
            
            # Skip if not attached to any non-paused tags
            if trigger_id not in trigger_to_tags:
                continue
            
            trigger_impact['triggers_analyzed'] += 1
            
            # Get all variables referenced in this trigger
            direct_vars = self.get_variable_references_in_object(trigger)
            
            trigger_detail = {
                'name': trigger.get('name', 'Unnamed Trigger'),
                'type': trigger.get('type', 'Unknown'),
                'direct_variables': list(direct_vars),
                'all_variables': {},
                'attached_tags': []
            }
            
            # Get attached tag info
            for tag in trigger_to_tags[trigger_id]:
                tag_type = self.get_tag_type_name(tag.get('type', 'Unknown'))
                trigger_detail['attached_tags'].append({
                    'name': tag.get('name', 'Unnamed Tag'),
                    'type': tag_type
                })
                
                # Track tag type breakdown
                if tag_type not in trigger_impact['tag_type_breakdown']:
                    trigger_impact['tag_type_breakdown'][tag_type] = 0
                trigger_impact['tag_type_breakdown'][tag_type] += 1
            
            # For each directly referenced variable, get all nested references
            for var_name in direct_vars:
                # Add the direct reference
                if var_name not in trigger_detail['all_variables']:
                    trigger_detail['all_variables'][var_name] = 0
                trigger_detail['all_variables'][var_name] += 1
                
                # Get nested references
                nested_refs = self.get_all_variable_references_recursive(var_name)
                for nested_var, count in nested_refs.items():
                    if nested_var not in trigger_detail['all_variables']:
                        trigger_detail['all_variables'][nested_var] = 0
                    trigger_detail['all_variables'][nested_var] += count
            
            # Update global counts
            for var_name, count in trigger_detail['all_variables'].items():
                trigger_impact['total_evaluations'] += count
                
                # Track by variable
                if var_name not in trigger_impact['evaluations_by_variable']:
                    trigger_impact['evaluations_by_variable'][var_name] = 0
                trigger_impact['evaluations_by_variable'][var_name] += count
                
                # Track by variable type
                var_type = self.get_variable_type_for_name(var_name)
                if var_type not in trigger_impact['evaluations_by_type']:
                    trigger_impact['evaluations_by_type'][var_type] = 0
                trigger_impact['evaluations_by_type'][var_type] += count
            
            trigger_impact['trigger_details'].append(trigger_detail)
        
        return trigger_impact
    
    def analyze_tag_evaluation_impact(self) -> Dict:
        """Analyze how many times variables need to be evaluated for each tag"""
        tag_impact = {
            'total_evaluations': 0,
            'evaluations_by_type': {},
            'evaluations_by_variable': {},
            'tags_analyzed': 0,
            'tag_type_statistics': {},
            'tag_details': [],
            'transformations_processed': 0,
            'custom_templates_processed': 0
        }
        
        # Process each non-paused tag
        for tag in self.tags:
            if tag.get('paused', False):
                continue
            
            tag_impact['tags_analyzed'] += 1
            tag_type = self.get_tag_type_name(tag.get('type', 'Unknown'))
            
            # Initialize tag type statistics
            if tag_type not in tag_impact['tag_type_statistics']:
                tag_impact['tag_type_statistics'][tag_type] = {
                    'count': 0,
                    'total_evaluations': 0,
                    'variables_used': set()
                }
            
            tag_impact['tag_type_statistics'][tag_type]['count'] += 1
            
            tag_detail = {
                'name': tag.get('name', 'Unnamed Tag'),
                'type': tag_type,
                'direct_variables': set(),
                'all_variables': {},
                'transformations': [],
                'custom_template_info': None
            }
            
            # Check if it's a custom template tag
            if tag.get('type', '').startswith('cvt_'):
                tag_impact['custom_templates_processed'] += 1
                # Find the custom template definition
                template_id = tag.get('type', '').split('_')[-1]
                template = next((t for t in self.custom_templates if t.get('templateId') == template_id), None)
                if template:
                    tag_detail['custom_template_info'] = {
                        'name': template.get('name', 'Unknown Template'),
                        'template_id': template_id
                    }
                    # Check templateData for variable references
                    template_data = template.get('templateData', '')
                    if isinstance(template_data, str):
                        template_refs = self.get_variable_references_in_value(template_data)
                        tag_detail['direct_variables'].update(template_refs)
            
            # Get variables from tag parameters
            tag_refs = self.get_variable_references_in_object(tag)
            tag_detail['direct_variables'].update(tag_refs)
            
            # Check for transformations (both 'transformation' and 'transformations')
            transformations = tag.get('transformation', tag.get('transformations', []))
            if isinstance(transformations, list):
                for trans in transformations:
                    tag_impact['transformations_processed'] += 1
                    trans_vars = self.get_variable_references_in_object(trans)
                    tag_detail['transformations'].append({
                        'type': trans.get('type', 'Unknown'),
                        'variables': list(trans_vars)
                    })
                    tag_detail['direct_variables'].update(trans_vars)
            
            # Get all nested variable references
            for var_name in tag_detail['direct_variables']:
                # Add the direct reference
                if var_name not in tag_detail['all_variables']:
                    tag_detail['all_variables'][var_name] = 0
                tag_detail['all_variables'][var_name] += 1
                
                # Get nested references
                nested_refs = self.get_all_variable_references_recursive(var_name)
                for nested_var, count in nested_refs.items():
                    if nested_var not in tag_detail['all_variables']:
                        tag_detail['all_variables'][nested_var] = 0
                    tag_detail['all_variables'][nested_var] += count
            
            # Update global counts
            for var_name, count in tag_detail['all_variables'].items():
                tag_impact['total_evaluations'] += count
                
                # Track by variable
                if var_name not in tag_impact['evaluations_by_variable']:
                    tag_impact['evaluations_by_variable'][var_name] = 0
                tag_impact['evaluations_by_variable'][var_name] += count
                
                # Track by variable type
                var_type = self.get_variable_type_for_name(var_name)
                if var_type not in tag_impact['evaluations_by_type']:
                    tag_impact['evaluations_by_type'][var_type] = 0
                tag_impact['evaluations_by_type'][var_type] += count
                
                # Add to tag type statistics
                tag_impact['tag_type_statistics'][tag_type]['total_evaluations'] += count
                tag_impact['tag_type_statistics'][tag_type]['variables_used'].add(var_name)
            
            # Convert direct_variables set to list for JSON serialization
            tag_detail['direct_variables'] = list(tag_detail['direct_variables'])
            tag_impact['tag_details'].append(tag_detail)
        
        # Convert sets to counts in tag_type_statistics
        for tag_type, stats in tag_impact['tag_type_statistics'].items():
            stats['unique_variables'] = len(stats['variables_used'])
            stats['variables_used'] = list(stats['variables_used'])  # Convert set to list
        
        return tag_impact
    
    def count_variable_occurrences_in_object(self, obj, var_name: str) -> int:
        """Count how many times a variable is referenced in an object"""
        count = 0
        pattern = f'{{{{{var_name}}}}}'
        
        if isinstance(obj, str):
            count += obj.count(pattern)
        elif isinstance(obj, dict):
            for value in obj.values():
                count += self.count_variable_occurrences_in_object(value, var_name)
        elif isinstance(obj, list):
            for item in obj:
                count += self.count_variable_occurrences_in_object(item, var_name)
        
        return count
    
    def generate_detailed_report(self) -> Dict:
        """Generate a comprehensive report with usage details"""
        report = self.generate_report()
        usage_details = self.get_variable_usage_details()
        usage_counts = self.get_variable_usage_counts()
        
        # Add usage details and counts to the report
        report['variable_usage_details'] = usage_details
        report['variable_usage_counts'] = usage_counts
        
        # Add detailed info for unused variables
        for unused_var in report['unused_variables']:
            var_name = unused_var['name']
            if var_name in usage_details:
                unused_var['usage_details'] = usage_details[var_name]
        
        # Add unknown types that need translation
        report['unknown_types'] = {
            'tag_types': sorted(list(self.unknown_tag_types)),
            'variable_types': sorted(list(self.unknown_variable_types)),
            'trigger_types': sorted(list(self.unknown_trigger_types)),
            'client_types': sorted(list(self.unknown_client_types)),
            'builtin_types': sorted(list(self.unknown_builtin_types))
        }
        
        return report
    
    def print_report(self, report: Dict):
        """Print a formatted report"""
        print("=" * 80)
        print("GTM VARIABLE ANALYSIS REPORT")
        print("=" * 80)
        print()
        
        # Summary
        print("SUMMARY:")
        print(f"  Container Type: {report['summary']['container_type']}")
        print(f"  Total Variables: {report['summary']['total_variables']}")
        print(f"  Total Tags: {report['summary']['total_tags']} ({report['summary']['paused_tags']} paused)")
        print(f"  Paused Tags Included: {'Yes' if report['summary']['include_paused_tags'] else 'No'}")
        print(f"  Total Triggers: {report['summary']['total_triggers']}")
        if report['summary']['total_transformations'] > 0:
            print(f"  Total Transformations: {report['summary']['total_transformations']}")
        if report['summary']['total_clients'] > 0:
            print(f"  Total Clients: {report['summary']['total_clients']}")
        if report['summary']['total_custom_templates'] > 0:
            print(f"  Total Custom Templates: {report['summary']['total_custom_templates']}")
        if report['summary']['total_builtin_variables'] > 0:
            print(f"  Built-in Variables Enabled: {report['summary']['total_builtin_variables']}")
        print()
        print(f"  Unused Variables: {report['summary']['unused_variables']}")
        print(f"  Unused Custom Templates: {report['summary']['unused_custom_templates']}")
        print(f"  Duplicate Groups: {report['summary']['duplicate_groups']}")
        print(f"  Total Duplicate Variables: {report['summary']['total_duplicates']}")
        print()
        
        # Unused Variables
        print("-" * 80)
        print("UNUSED VARIABLES:")
        print("-" * 80)
        if report['unused_variables']:
            # Group by variable type for better organization
            standard_vars = []
            template_vars = []
            
            for var in report['unused_variables']:
                if var['type'].startswith('cvt_'):
                    template_vars.append(var)
                else:
                    standard_vars.append(var)
            
            # Print standard variables first
            if standard_vars:
                print("\n  STANDARD VARIABLES:")
                for var in standard_vars:
                    print(f"    - {var['name']} (ID: {var['variableId']}, Type: {var['type']})")
            
            # Print custom template variables with their template names
            if template_vars:
                print("\n  CUSTOM TEMPLATE VARIABLES:")
                for var in template_vars:
                    template_info = f" [Template: {var.get('template_name', 'Unknown Template')}]" if 'template_name' in var else ""
                    print(f"    - {var['name']} (ID: {var['variableId']}, Type: {var['type']}){template_info}")
        else:
            print("  No unused variables found!")
        print()
        
        # Unused Custom Templates
        print("-" * 80)
        print("UNUSED CUSTOM TEMPLATES:")
        print("-" * 80)
        if report.get('unused_custom_templates'):
            for template in report['unused_custom_templates']:
                print(f"  - {template['name']} (Template ID: {template['templateId']}, Type: {template['type']})")
        else:
            print("  No unused custom templates found!")
        print()
        
        # Duplicate Variables by Type
        print("-" * 80)
        print("DUPLICATE VARIABLES:")
        print("-" * 80)
        
        duplicates = report.get('duplicate_variables', {})
        
        # Helper function to print formatValue info
        def print_format_value(format_info, indent="      "):
            if format_info:
                print(f"{indent}Format Value Options:")
                for key, value in format_info.items():
                    print(f"{indent}  - {key}: {value}")
        
        # Data Layer Duplicates
        if duplicates.get('data_layer_duplicates'):
            print("\nDATA LAYER VARIABLE DUPLICATES:")
            for i, group in enumerate(duplicates['data_layer_duplicates'], 1):
                print(f"\n  Duplicate Group {i} (Data Layer Path: '{group[0]['path']}'):")
                for var in group:
                    print(f"    - {var['name']} (ID: {var['variableId']})")
                    if var.get('defaultValue'):
                        print(f"      Default: {var['defaultValue']}")
                    print_format_value(var.get('formatValue'))
        
        # Event Data Duplicates
        if duplicates.get('event_data_duplicates'):
            print("\nEVENT DATA VARIABLE DUPLICATES:")
            for i, group in enumerate(duplicates['event_data_duplicates'], 1):
                print(f"\n  Duplicate Group {i} (Key Path: '{group[0]['keyPath']}'):")
                for var in group:
                    print(f"    - {var['name']} (ID: {var['variableId']})")
                    if var.get('defaultValue'):
                        print(f"      Default: {var['defaultValue']}")
                    print_format_value(var.get('formatValue'))
        
        # Cookie Duplicates
        if duplicates.get('cookie_duplicates'):
            print("\nCOOKIE VARIABLE DUPLICATES:")
            for i, group in enumerate(duplicates['cookie_duplicates'], 1):
                print(f"\n  Duplicate Group {i} (Cookie Name: '{group[0]['cookieName']}'):")
                for var in group:
                    print(f"    - {var['name']} (ID: {var['variableId']})")
                    print_format_value(var.get('formatValue'))
        
        # JavaScript Variable Duplicates
        if duplicates.get('js_variable_duplicates'):
            print("\nJAVASCRIPT VARIABLE DUPLICATES:")
            for i, group in enumerate(duplicates['js_variable_duplicates'], 1):
                print(f"\n  Duplicate Group {i} (JS Variable: '{group[0]['jsVarName']}'):")
                for var in group:
                    print(f"    - {var['name']} (ID: {var['variableId']})")
                    print_format_value(var.get('formatValue'))
        
        # URL Variable Duplicates
        if duplicates.get('url_duplicates'):
            print("\nURL VARIABLE DUPLICATES:")
            for i, group in enumerate(duplicates['url_duplicates'], 1):
                component = group[0].get('component', group[0].get('parameter', 'Unknown'))
                query_key = group[0].get('queryKey', '')
                if query_key:
                    print(f"\n  Duplicate Group {i} (Component: '{component}', Query Key: '{query_key}'):")
                else:
                    print(f"\n  Duplicate Group {i} (Component: '{component}'):")
                for var in group:
                    print(f"    - {var['name']} (ID: {var['variableId']})")
                    if var.get('queryKey'):
                        print(f"      Query Key: {var['queryKey']}")
                    print_format_value(var.get('formatValue'))
        
        # Custom Template Duplicates
        if duplicates.get('custom_template_duplicates'):
            print("\nCUSTOM TEMPLATE VARIABLE DUPLICATES:")
            for i, group in enumerate(duplicates['custom_template_duplicates'], 1):
                print(f"\n  Duplicate Group {i} (Template Type: '{group[0]['type']}'):")
                print(f"    Parameters: {group[0]['parameters']}")
                for var in group:
                    print(f"    - {var['name']} (ID: {var['variableId']})")
                    print_format_value(var.get('formatValue'))
        
        # Check if no duplicates found
        if not any(duplicates.values()):
            print("  No duplicate variables found!")
        
        print()
        
        # Variable Usage Location Counts
        if 'variable_usage_counts' in report:
            print("-" * 80)
            print("VARIABLE USAGE LOCATION COUNTS:")
            print("-" * 80)
            
            usage_counts = report['variable_usage_counts']
            
            # Filter out variables with no usage
            used_variables = {name: data for name, data in usage_counts.items() 
                            if data['total_references'] > 0}
            
            if used_variables:
                # Sort by total references (descending) for most used variables first
                sorted_vars = sorted(used_variables.items(), 
                                  key=lambda x: x[1]['total_references'], 
                                  reverse=True)
                
                # Show top 20 most used variables (or all if less than 20)
                vars_to_show = sorted_vars[:20] if len(sorted_vars) > 20 else sorted_vars
                
                for var_name, data in vars_to_show:
                    var_info = data['variable']
                    locations = data['usage_locations']
                    components = data.get('usage_components', {})
                    
                    # Get human-readable type
                    var_type_display = self.get_variable_type_name(var_info['type'])
                    print(f"\n  Variable: {var_name} ({var_type_display})")
                    
                    # Show locations with counts and component names
                    if locations['tags'] > 0:
                        component_list = components.get('tags', [])
                        # Limit display to 3 names to avoid clutter
                        if len(component_list) > 3:
                            display_names = ', '.join(component_list[:3]) + f', ... and {len(component_list) - 3} more'
                        else:
                            display_names = ', '.join(component_list)
                        print(f"    - Tags: {locations['tags']} [{display_names}]")
                    
                    if locations['triggers'] > 0:
                        component_list = components.get('triggers', [])
                        if len(component_list) > 3:
                            display_names = ', '.join(component_list[:3]) + f', ... and {len(component_list) - 3} more'
                        else:
                            display_names = ', '.join(component_list)
                        print(f"    - Triggers: {locations['triggers']} [{display_names}]")
                    
                    if locations['variables'] > 0:
                        component_list = components.get('variables', [])
                        if len(component_list) > 3:
                            display_names = ', '.join(component_list[:3]) + f', ... and {len(component_list) - 3} more'
                        else:
                            display_names = ', '.join(component_list)
                        print(f"    - Variables: {locations['variables']} [{display_names}]")
                    
                    if locations['clients'] > 0:
                        component_list = components.get('clients', [])
                        if len(component_list) > 3:
                            display_names = ', '.join(component_list[:3]) + f', ... and {len(component_list) - 3} more'
                        else:
                            display_names = ', '.join(component_list)
                        print(f"    - Clients: {locations['clients']} [{display_names}]")
                    
                    if locations['transformations'] > 0:
                        component_list = components.get('transformations', [])
                        if len(component_list) > 3:
                            display_names = ', '.join(component_list[:3]) + f', ... and {len(component_list) - 3} more'
                        else:
                            display_names = ', '.join(component_list)
                        print(f"    - Transformations: {locations['transformations']} [{display_names}]")
                    
                    if locations['custom_templates'] > 0:
                        component_list = components.get('custom_templates', [])
                        if len(component_list) > 3:
                            display_names = ', '.join(component_list[:3]) + f', ... and {len(component_list) - 3} more'
                        else:
                            display_names = ', '.join(component_list)
                        print(f"    - Custom Template Variables: {locations['custom_templates']} [{display_names}]")
                    
                    print(f"    Total References: {data['total_references']}")
                    
                    # Show re-evaluation metrics
                    potential_reevals = data.get('potential_reevaluations', 0)
                    min_reevals = data.get('minimum_reevaluations', 0)
                    
                    if potential_reevals > 1:
                        if potential_reevals == min_reevals:
                            print(f"    Re-evaluations per event: {potential_reevals}")
                        else:
                            print(f"    Re-evaluations per event: {min_reevals}-{potential_reevals} (depending on execution flow)")
                        
                        # Add warning for high re-evaluation counts
                        if potential_reevals >= 10:
                            print(f"    WARNING: HIGH RE-EVALUATION - This variable may impact performance")
                
                if len(sorted_vars) > 20:
                    print(f"\n  ... and {len(sorted_vars) - 20} more variables with usage")
            else:
                print("  No variables are being used in the container!")
            
            print()
        
        # Built-in Variables Analysis
        if 'builtin_variables' in report and report['builtin_variables']['total_builtin_variables'] > 0:
            print("-" * 80)
            print("BUILT-IN VARIABLES:")
            print("-" * 80)
            
            builtin = report['builtin_variables']
            print(f"\n  Total Built-in Variables Enabled: {builtin['total_builtin_variables']}")
            
            if builtin['builtin_by_type']:
                print("\n  Built-in Variables by Type:")
                # Sort by count descending
                sorted_types = sorted(builtin['builtin_by_type'].items(), 
                                    key=lambda x: x[1], reverse=True)
                
                for var_type, count in sorted_types[:10]:
                    print(f"    - {var_type}: {count}")
                
                if len(sorted_types) > 10:
                    print(f"    ... and {len(sorted_types) - 10} more types")
            
            print()
    
    def print_trigger_evaluation_impact_report(self, trigger_impact: Dict):
        """Print the trigger evaluation impact report"""
        print("\n" + "=" * 80)
        print("TRIGGER EVALUATION IMPACT")
        print("=" * 80)
        print()
        
        # Summary
        print("SUMMARY:")
        print(f"  Triggers Analyzed: {trigger_impact['triggers_analyzed']} (attached to non-paused tags)")
        print(f"  Total Variable Evaluations: {trigger_impact['total_evaluations']}")
        print()
        
        # Variable Type Breakdown
        if trigger_impact['evaluations_by_type']:
            print("VARIABLE TYPE BREAKDOWN:")
            sorted_types = sorted(trigger_impact['evaluations_by_type'].items(), 
                                key=lambda x: x[1], reverse=True)
            for var_type, count in sorted_types:
                print(f"  {var_type}: {count} evaluations")
            print()
        
        # Tag Type Breakdown
        if trigger_impact['tag_type_breakdown']:
            print("TAG TYPE BREAKDOWN (tags using these triggers):")
            sorted_tags = sorted(trigger_impact['tag_type_breakdown'].items(), 
                               key=lambda x: x[1], reverse=True)
            for tag_type, count in sorted_tags:
                print(f"  {tag_type}: {count} tags")
            print()
        
        # Variable Re-evaluation List
        if trigger_impact['evaluations_by_variable']:
            print("VARIABLE RE-EVALUATION COUNTS:")
            sorted_vars = sorted(trigger_impact['evaluations_by_variable'].items(), 
                               key=lambda x: x[1], reverse=True)
            
            # Show top 20 most evaluated variables
            vars_to_show = sorted_vars[:20] if len(sorted_vars) > 20 else sorted_vars
            
            for var_name, count in vars_to_show:
                # Find variable type
                var_type = self.get_variable_type_for_name(var_name)
                print(f"  {var_name} ({var_type}): {count} evaluations")
            
            if len(sorted_vars) > 20:
                print(f"\n  ... and {len(sorted_vars) - 20} more variables")
            print()
        
        # Detailed trigger information (optional - can be verbose)
        if trigger_impact.get('show_details', False) and trigger_impact['trigger_details']:
            print("\nTRIGGER DETAILS:")
            print("-" * 80)
            for detail in trigger_impact['trigger_details'][:10]:  # Limit to first 10
                print(f"\nTrigger: {detail['name']}")
                print(f"Type: {self.get_trigger_type_name(detail['type'])}")
                print(f"Attached to {len(detail['attached_tags'])} tag(s)")
                if detail['all_variables']:
                    print(f"Variables evaluated: {len(detail['all_variables'])}")
                    # Show first 5 variables
                    var_list = list(detail['all_variables'].items())[:5]
                    for var_name, count in var_list:
                        print(f"  - {var_name}: {count} time(s)")
                    if len(detail['all_variables']) > 5:
                        print(f"  ... and {len(detail['all_variables']) - 5} more variables")
            
            if len(trigger_impact['trigger_details']) > 10:
                print(f"\n... and {len(trigger_impact['trigger_details']) - 10} more triggers")
    
    def print_tag_evaluation_impact_report(self, tag_impact: Dict):
        """Print the tag evaluation impact report"""
        print("\n" + "=" * 80)
        print("TAG EVALUATION IMPACT")
        print("=" * 80)
        print()
        
        # Summary
        print("SUMMARY:")
        print(f"  Tags Analyzed: {tag_impact['tags_analyzed']} (non-paused tags)")
        print(f"  Total Variable Evaluations: {tag_impact['total_evaluations']}")
        print(f"  Custom Template Tags Processed: {tag_impact['custom_templates_processed']}")
        print(f"  Transformations Processed: {tag_impact['transformations_processed']}")
        print()
        
        # Tag Type Statistics
        if tag_impact['tag_type_statistics']:
            print("TAG TYPE STATISTICS:")
            sorted_tag_types = sorted(tag_impact['tag_type_statistics'].items(), 
                                    key=lambda x: x[1]['total_evaluations'], reverse=True)
            
            for tag_type, stats in sorted_tag_types:
                print(f"\n  {tag_type}:")
                print(f"    Count: {stats['count']} tags")
                print(f"    Total Evaluations: {stats['total_evaluations']}")
                print(f"    Unique Variables Used: {stats['unique_variables']}")
                avg_eval = stats['total_evaluations'] / stats['count'] if stats['count'] > 0 else 0
                print(f"    Average Evaluations per Tag: {avg_eval:.1f}")
            print()
        
        # Variable Type Breakdown
        if tag_impact['evaluations_by_type']:
            print("VARIABLE TYPE BREAKDOWN:")
            sorted_types = sorted(tag_impact['evaluations_by_type'].items(), 
                                key=lambda x: x[1], reverse=True)
            for var_type, count in sorted_types:
                print(f"  {var_type}: {count} evaluations")
            print()
        
        # Variable Re-evaluation List
        if tag_impact['evaluations_by_variable']:
            print("VARIABLE RE-EVALUATION COUNTS:")
            sorted_vars = sorted(tag_impact['evaluations_by_variable'].items(), 
                               key=lambda x: x[1], reverse=True)
            
            # Show top 20 most evaluated variables
            vars_to_show = sorted_vars[:20] if len(sorted_vars) > 20 else sorted_vars
            
            for var_name, count in vars_to_show:
                # Find variable type
                var_type = self.get_variable_type_for_name(var_name)
                print(f"  {var_name} ({var_type}): {count} evaluations")
            
            if len(sorted_vars) > 20:
                print(f"\n  ... and {len(sorted_vars) - 20} more variables")
            print()
        
        # High-impact tags (optional - show tags with most variable evaluations)
        if tag_impact.get('show_details', False) and tag_impact['tag_details']:
            print("\nHIGH-IMPACT TAGS (Top 10 by variable evaluations):")
            print("-" * 80)
            
            # Sort tags by total evaluations
            sorted_tags = sorted(tag_impact['tag_details'], 
                               key=lambda x: sum(x['all_variables'].values()), 
                               reverse=True)[:10]
            
            for detail in sorted_tags:
                total_evals = sum(detail['all_variables'].values())
                print(f"\nTag: {detail['name']}")
                print(f"Type: {detail['type']}")
                if detail['custom_template_info']:
                    print(f"Custom Template: {detail['custom_template_info']['name']}")
                if detail['transformations']:
                    print(f"Transformations: {len(detail['transformations'])}")
                print(f"Total Variable Evaluations: {total_evals}")
                if detail['all_variables']:
                    print("Top Variables:")
                    var_list = sorted(detail['all_variables'].items(), 
                                    key=lambda x: x[1], reverse=True)[:5]
                    for var_name, count in var_list:
                        print(f"  - {var_name}: {count} time(s)")
                    if len(detail['all_variables']) > 5:
                        print(f"  ... and {len(detail['all_variables']) - 5} more variables")
    
    def print_combined_reevaluation_report(self, trigger_impact: Dict, tag_impact: Dict):
        """Print combined re-evaluation report"""
        print("\n" + "=" * 80)
        print("COMBINED RE-EVALUATION ANALYSIS REPORT")
        print("=" * 80)
        print()
        
        # Section 1: Trigger Evaluation Summary
        print("SECTION 1: TRIGGER EVALUATIONS")
        print("-" * 40)
        print(f"Total Variable Evaluations for Triggers: {trigger_impact['total_evaluations']}")
        print(f"Triggers Analyzed: {trigger_impact['triggers_analyzed']}")
        print()
        
        print("Variable Re-evaluation Counts (from triggers):")
        sorted_trigger_vars = sorted(trigger_impact['evaluations_by_variable'].items(), 
                                   key=lambda x: x[1], reverse=True)[:10]
        for var_name, count in sorted_trigger_vars:
            var_type = self.get_variable_type_for_name(var_name)
            print(f"  {var_name} ({var_type}): {count} evaluations")
        if len(trigger_impact['evaluations_by_variable']) > 10:
            print(f"  ... and {len(trigger_impact['evaluations_by_variable']) - 10} more variables")
        print()
        
        # Section 2: Tag Evaluation Summary
        print("\nSECTION 2: TAG EVALUATIONS")
        print("-" * 40)
        print(f"Total Variable Evaluations for Tags: {tag_impact['total_evaluations']}")
        print(f"Tags Analyzed: {tag_impact['tags_analyzed']}")
        print()
        
        print("Tag Type Statistics (sorted by evaluation count):")
        sorted_tag_types = sorted(tag_impact['tag_type_statistics'].items(), 
                                key=lambda x: x[1]['total_evaluations'], reverse=True)
        for tag_type, stats in sorted_tag_types[:5]:
            print(f"  {tag_type}: {stats['count']} tags, {stats['total_evaluations']} evaluations")
        if len(tag_impact['tag_type_statistics']) > 5:
            print(f"  ... and {len(tag_impact['tag_type_statistics']) - 5} more tag types")
        print()
        
        print("Variable Re-evaluation Counts (from tags):")
        sorted_tag_vars = sorted(tag_impact['evaluations_by_variable'].items(), 
                               key=lambda x: x[1], reverse=True)[:10]
        for var_name, count in sorted_tag_vars:
            var_type = self.get_variable_type_for_name(var_name)
            print(f"  {var_name} ({var_type}): {count} evaluations")
        if len(tag_impact['evaluations_by_variable']) > 10:
            print(f"  ... and {len(tag_impact['evaluations_by_variable']) - 10} more variables")
        print()
        
        # Combined totals
        print("\nCOMBINED TOTALS:")
        print("-" * 40)
        total_combined = trigger_impact['total_evaluations'] + tag_impact['total_evaluations']
        print(f"Grand Total Variable Evaluations: {total_combined}")
        print(f"  From Triggers: {trigger_impact['total_evaluations']} ({trigger_impact['total_evaluations']/total_combined*100:.1f}%)")
        print(f"  From Tags: {tag_impact['total_evaluations']} ({tag_impact['total_evaluations']/total_combined*100:.1f}%)")
    
    def print_unknown_types_report(self):
        """Print report of unknown component types that need translation"""
        has_unknown = False
        
        if self.unknown_tag_types:
            has_unknown = True
            print("\n🔍 UNKNOWN TAG TYPES FOUND (Add to translations):")
            print("-" * 50)
            for tag_type in sorted(self.unknown_tag_types):
                print(f"  '{tag_type}': 'Description Here',")
        
        if self.unknown_variable_types:
            has_unknown = True
            print("\n🔍 UNKNOWN VARIABLE TYPES FOUND (Add to translations):")
            print("-" * 50)
            for var_type in sorted(self.unknown_variable_types):
                print(f"  '{var_type}': 'Description Here',")
        
        if self.unknown_trigger_types:
            has_unknown = True
            print("\n🔍 UNKNOWN TRIGGER TYPES FOUND (Add to translations):")
            print("-" * 50)
            for trigger_type in sorted(self.unknown_trigger_types):
                print(f"  '{trigger_type}': 'Description Here',")
        
        if self.unknown_client_types:
            has_unknown = True
            print("\n🔍 UNKNOWN CLIENT TYPES FOUND (Add to translations):")
            print("-" * 50)
            for client_type in sorted(self.unknown_client_types):
                print(f"  '{client_type}': 'Description Here',")
        
        if self.unknown_builtin_types:
            has_unknown = True
            print("\n🔍 UNKNOWN BUILT-IN VARIABLE TYPES FOUND (Add to translations):")
            print("-" * 50)
            for builtin_type in sorted(self.unknown_builtin_types):
                print(f"  '{builtin_type}': 'Description Here',")
        
        if not has_unknown:
            print("\n✅ All component types have translations!")


def main():
    """Main function to run the analyzer"""
    # Check if file path is provided
    if len(sys.argv) < 2:
        print("Usage: python gtm_analyzer.py <path_to_gtm_export.json> [options]")
        print("Options:")
        print("  --debug              Show debug information")
        print("  --exclude-paused     Exclude paused tags from analysis")
        sys.exit(1)
    
    file_path = sys.argv[1]
    debug_mode = '--debug' in sys.argv
    include_paused = '--exclude-paused' not in sys.argv
    
    try:
        # Load the GTM export file
        with open(file_path, 'r', encoding='utf-8') as f:
            gtm_data = json.load(f)
        
        # Create analyzer instance
        analyzer = GTMAnalyzer(gtm_data, include_paused_tags=include_paused)
        
        # Generate report with debug mode if requested
        if debug_mode:
            print("Running in DEBUG mode...\n")
            analyzer.test_variable_detection()
            analyzer.find_unused_variables(debug=True)
            print("\n" + "="*80 + "\n")
        
        # Generate detailed report with usage counts
        report = analyzer.generate_detailed_report()
        
        # Print report to console
        analyzer.print_report(report)
        
        # Generate and print trigger evaluation impact
        trigger_impact = analyzer.analyze_trigger_evaluation_impact()
        analyzer.print_trigger_evaluation_impact_report(trigger_impact)
        
        # Generate and print tag evaluation impact
        tag_impact = analyzer.analyze_tag_evaluation_impact()
        analyzer.print_tag_evaluation_impact_report(tag_impact)
        
        # Print combined re-evaluation report
        analyzer.print_combined_reevaluation_report(trigger_impact, tag_impact)
        
        # Add evaluation impacts to report
        report['trigger_evaluation_impact'] = trigger_impact
        report['tag_evaluation_impact'] = tag_impact
        
        # Optionally save report to JSON file
        output_file = file_path.replace('.json', '_analysis_report.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        print(f"Report saved to: {output_file}")
        
        # Print unknown types report
        analyzer.print_unknown_types_report()
        
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file. {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
