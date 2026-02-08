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
        """Find custom templates that are not used by any variable"""
        unused_templates = []
        
        # Get all custom template IDs
        template_usage = {}
        for template in self.custom_templates:
            container_id = template.get('containerId', '')
            template_id = template.get('templateId', '')
            template_type = f"cvt_{container_id}_{template_id}"
            
            template_usage[template_type] = {
                'template': template,
                'used': False,
                'used_by': []
            }
        
        # Check all variables for custom template usage
        for var in self.variables:
            var_type = var.get('type', '')
            
            # Check if it's a custom template type (cvt_<containerId>_<templateId>)
            if var_type.startswith('cvt_'):
                if var_type in template_usage:
                    template_usage[var_type]['used'] = True
                    template_usage[var_type]['used_by'].append({
                        'name': var['name'],
                        'variableId': var['variableId']
                    })
                # Also handle public templates (cvt_<code>)
                elif '_' not in var_type[4:]:  # Public template like cvt_WVXBK
                    # These are public templates, not custom ones from this container
                    pass
        
        # Collect unused templates
        for template_type, usage_info in template_usage.items():
            if not usage_info['used']:
                template = usage_info['template']
                unused_templates.append({
                    'name': template.get('name', 'Unnamed Template'),
                    'templateId': template.get('templateId', ''),
                    'type': template_type,
                    'fingerprint': template.get('fingerprint', '')
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
                key = f"url|{component}"
                variable_groups['url_duplicates'][key].append({
                    'name': var['name'],
                    'variableId': var['variableId'],
                    'type': var_type,
                    'component': component,
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
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive report"""
        unused_vars = self.find_unused_variables()
        all_duplicates = self.find_duplicate_variables()
        unused_templates = self.find_unused_custom_templates()
        
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
                'unused_variables': len(unused_vars),
                'unused_custom_templates': len(unused_templates),
                'duplicate_groups': total_duplicate_groups,
                'total_duplicates': total_duplicate_vars
            },
            'unused_variables': unused_vars,
            'unused_custom_templates': unused_templates,
            'duplicate_variables': all_duplicates
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
            
            # Parse templateData to determine template type and check for gallery ID
            template_data = template.get('templateData', '')
            template_category = 'UNKNOWN'
            gallery_id = None
            is_gallery_template = False
            
            if isinstance(template_data, str):
                import re
                
                # Look for type field
                type_match = re.search(r'"type"\s*:\s*"(TAG|MACRO|CLIENT)"', template_data)
                if type_match:
                    template_category = type_match.group(1)
                
                # Look for ID field (check if it's a real gallery ID)
                id_match = re.search(r'"id"\s*:\s*"([^"]+)"', template_data)
                if id_match:
                    potential_id = id_match.group(1)
                    # Check if it's a valid gallery ID
                    if (potential_id.startswith('cvt_') and 
                        not potential_id.startswith('cvt_temp_') and
                        '_' not in potential_id[4:]):
                        gallery_id = potential_id
                        is_gallery_template = True
            
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
                print(f"\n  Duplicate Group {i} (Component: '{group[0].get('component', group[0].get('parameter', 'Unknown'))}'):")
                for var in group:
                    print(f"    - {var['name']} (ID: {var['variableId']})")
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
                    
                    print(f"\n  Variable: {var_name} ({var_info['type']})")
                    
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
                            print(f"    ⚠️  HIGH RE-EVALUATION: This variable may impact performance")
                
                if len(sorted_vars) > 20:
                    print(f"\n  ... and {len(sorted_vars) - 20} more variables with usage")
            else:
                print("  No variables are being used in the container!")
            
            print()


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
        
        # Optionally save report to JSON file
        output_file = file_path.replace('.json', '_analysis_report.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        print(f"Report saved to: {output_file}")
        
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
