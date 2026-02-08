#!/usr/bin/env python3
"""
Simple launcher for GTM Dashboard without debug mode
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gtm_dashboard import create_dashboard, load_analysis_data

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_dashboard.py <path_to_analysis_report.json>")
        sys.exit(1)
    
    print("Loading analysis data...")
    data = load_analysis_data(sys.argv[1])
    
    print("Creating dashboard...")
    app = create_dashboard(data)
    
    print("\n" + "="*50)
    print("GTM Dashboard is starting...")
    print("="*50)
    print("\nOpen your browser and go to:")
    print("  → http://localhost:8050")
    print("\nPress CTRL+C to stop the server\n")
    
    # Run without debug mode
    app.run(host='0.0.0.0', port=8050, debug=False)

if __name__ == '__main__':
    main()