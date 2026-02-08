#!/usr/bin/env python3
"""
GTM Container Analysis Pipeline
Runs the GTM analyzer and generates a static HTML dashboard in one step.

Usage:
    python run_gtm_analysis.py <path_to_gtm_export.json> [options]

Options:
    --debug              Show debug information during analysis
    --exclude-paused     Exclude paused tags from analysis
    --skip-dashboard     Only run the analyzer, skip dashboard generation
    --output-dir DIR     Output directory for generated files (default: same as input)
"""

import sys
import os
import re
import json


def validate_filename(file_path):
    """
    Validate that the filename doesn't contain copy indicators like (1), (2), etc.
    These appear when files are duplicated by the OS (e.g., downloaded twice)
    and often cause issues with shell parsing and indicate stale data.
    """
    basename = os.path.basename(file_path)

    # Match patterns like (1), (2), (10), etc. — typical OS copy suffixes
    copy_pattern = re.compile(r'\(\d+\)')
    match = copy_pattern.search(basename)

    if match:
        # Build a suggested clean name by removing the copy indicator
        clean_name = copy_pattern.sub('', basename)
        # Collapse any resulting double spaces or leading/trailing spaces
        clean_name = re.sub(r'  +', ' ', clean_name).strip()
        # Handle case where (1) was right before the extension: "file (1).json" -> "file.json"
        clean_name = re.sub(r' \.', '.', clean_name)

        print(f"ERROR: The filename '{basename}' contains a copy indicator '{match.group()}'.")
        print(f"  This usually means the file is a duplicate created by your OS")
        print(f"  (e.g., a second download of the same file).")
        print()
        print(f"  Suggested actions:")
        print(f"    1. Rename the file to: {clean_name}")
        print(f"    2. Or verify you are using the correct (original) export file.")
        print()

        clean_path = os.path.join(os.path.dirname(file_path), clean_name)
        if os.path.exists(clean_path):
            print(f"  NOTE: The clean-named file '{clean_name}' already exists in the same directory.")
            print(f"  You may want to use that one instead:")
            print(f"    python {os.path.basename(__file__)} \"{clean_path}\"")
        else:
            print(f"  To rename, run:")
            print(f"    mv \"{file_path}\" \"{clean_path}\"")

        sys.exit(1)


def run_analyzer(file_path, debug_mode=False, include_paused=True):
    """Run the GTM analyzer and return the report + output file path"""
    # Import the analyzer module
    # Handle the hyphen in the filename by using importlib
    import importlib.util
    analyzer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gtm-analyzer.py')

    if not os.path.exists(analyzer_path):
        print(f"ERROR: Analyzer script not found at: {analyzer_path}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("gtm_analyzer", analyzer_path)
    gtm_analyzer_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gtm_analyzer_module)

    # Load the GTM export file
    with open(file_path, 'r', encoding='utf-8') as f:
        gtm_data = json.load(f)

    # Create analyzer instance
    analyzer = gtm_analyzer_module.GTMAnalyzer(gtm_data, include_paused_tags=include_paused)

    # Run debug output if requested
    if debug_mode:
        print("Running in DEBUG mode...\n")
        analyzer.test_variable_detection()
        analyzer.find_unused_variables(debug=True)
        print("\n" + "=" * 80 + "\n")

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

    # Save report to JSON file
    output_file = file_path.replace('.json', '_analysis_report.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print(f"\nAnalysis report saved to: {output_file}")

    # Print unknown types report
    analyzer.print_unknown_types_report()

    return report, output_file


def run_dashboard(analysis_data, analysis_file_path):
    """Run the static dashboard generator"""
    # Import the dashboard module
    import importlib.util
    dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gtm_dashboard_static.py')

    if not os.path.exists(dashboard_path):
        print(f"ERROR: Dashboard script not found at: {dashboard_path}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("gtm_dashboard_static", dashboard_path)
    dashboard_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dashboard_module)

    # Generate output filename based on analysis file
    base_name = os.path.basename(analysis_file_path)
    if base_name.endswith('_analysis_report.json'):
        base_name = base_name[:-21]
    elif base_name.endswith('.json'):
        base_name = base_name[:-5]

    output_dir = os.path.dirname(analysis_file_path) or '.'
    output_filename = os.path.join(output_dir, f'gtm_dashboard_{base_name}.html')

    # Generate dashboard
    dashboard_module.generate_static_dashboard(analysis_data, output_filename)

    return output_filename


def main():
    if len(sys.argv) < 2:
        print("GTM Container Analysis Pipeline")
        print("=" * 40)
        print()
        print(f"Usage: python {os.path.basename(__file__)} <path_to_gtm_export.json> [options]")
        print()
        print("Options:")
        print("  --debug              Show debug information during analysis")
        print("  --exclude-paused     Exclude paused tags from analysis")
        print("  --skip-dashboard     Only run the analyzer, skip dashboard generation")
        print()
        print("Example:")
        print(f"  python {os.path.basename(__file__)} GTM-MHKFW34_workspace473.json")
        print(f"  python {os.path.basename(__file__)} GTM-MHKFW34_workspace473.json --exclude-paused")
        sys.exit(1)

    file_path = sys.argv[1]
    debug_mode = '--debug' in sys.argv
    include_paused = '--exclude-paused' not in sys.argv
    skip_dashboard = '--skip-dashboard' in sys.argv

    # --- Step 0: Validate the input file ---
    if not os.path.exists(file_path):
        print(f"ERROR: File '{file_path}' not found.")
        sys.exit(1)

    if not file_path.endswith('.json'):
        print(f"ERROR: Input file must be a .json GTM export file.")
        sys.exit(1)

    # Check for copy indicators in filename
    validate_filename(file_path)

    # --- Step 1: Run the GTM Analyzer ---
    print("=" * 80)
    print("STEP 1: Running GTM Variable Analyzer")
    print("=" * 80)
    print()

    try:
        report, analysis_file = run_analyzer(file_path, debug_mode, include_paused)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON file. {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if skip_dashboard:
        print("\nDashboard generation skipped (--skip-dashboard flag).")
        return

    # --- Step 2: Generate the Static Dashboard ---
    print()
    print("=" * 80)
    print("STEP 2: Generating Static HTML Dashboard")
    print("=" * 80)
    print()

    try:
        dashboard_file = run_dashboard(report, analysis_file)
    except ImportError as e:
        print(f"ERROR: Missing dependency for dashboard generation: {e}")
        print("  Install required packages: pip install plotly pandas")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR during dashboard generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # --- Summary ---
    print()
    print("=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)
    print(f"  Input file:      {file_path}")
    print(f"  Analysis report:  {analysis_file}")
    print(f"  Dashboard:        {dashboard_file}")
    print()


if __name__ == '__main__':
    main()
