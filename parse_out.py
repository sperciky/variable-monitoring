import sys
import json
import os

def get_nested(data, path):
    """Retrieve nested JSON value based on dot-separated path."""
    keys = path.split(".")
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            raise KeyError(f"Path '{path}' not found in JSON")
    return data

def main():
    if len(sys.argv) < 3:
        print("Usage: python script.py <input_file.json> <json_path>")
        sys.exit(1)

    input_file = sys.argv[1]
    json_path = sys.argv[2]
    output_file = "output.json"

    # Read input file
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    try:
        extracted = get_nested(data, json_path)
    except KeyError as e:
        print(e)
        sys.exit(1)

    # Write output file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)

    print(f"Extracted JSON saved to {output_file}")

if __name__ == "__main__":
    main()