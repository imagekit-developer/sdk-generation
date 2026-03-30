#!/usr/bin/env python3
"""
Sync operationId values in the OpenAPI spec with method names from the Stainless config.

Reads method_name → endpoint mappings from main.yaml, finds the matching
operationId in v1.0.0.yaml by HTTP method + path, then replaces ALL occurrences
of the old operationId with the new method name throughout the spec.
"""

import re
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
STAINLESS_CONFIG = os.path.join(ROOT, "stainless-config", "main.yaml")
OPENAPI_SPEC = os.path.join(ROOT, "openapi", "v1.0.0.yaml")


def parse_stainless_methods(config_path: str) -> list[dict]:
    """Parse method_name → (http_method, path) from the Stainless config."""
    with open(config_path) as f:
        lines = f.readlines()

    methods = []
    in_methods = False
    current_method_name = None
    
    for line in lines:
        stripped = line.rstrip("\n")

        # Detect start of methods: section (exactly 2-space indent)
        if re.match(r'^  methods:', stripped):
            in_methods = True
            continue

        # Exit methods section when we hit another top-level key or non-indented line
        if in_methods and stripped.strip() and not stripped.startswith("    "):
            if not stripped.startswith("  methods"):
                in_methods = False
                continue

        if not in_methods:
            continue

        # Skip comments and blank lines
        if not stripped.strip() or stripped.strip().startswith("#"):
            continue

        # Simple method: "method_name: verb /path"
        simple = re.match(r'^\s{4,6}(\w+):\s+(get|post|put|patch|delete)\s+(/\S+)', stripped)
        if simple:
            method_name = simple.group(1)
            http_method = simple.group(2).lower()
            path = simple.group(3)
            methods.append({
                "method_name": method_name,
                "http_method": http_method,
                "path": path,
            })
            current_method_name = None
            continue

        # Multi-line method: "method_name:" (value on next lines)
        multi_start = re.match(r'^\s{4,6}(\w+):\s*$', stripped)
        if multi_start:
            current_method_name = multi_start.group(1)
            continue

        # Endpoint line under multi-line method
        if current_method_name:
            endpoint_match = re.match(r'^\s+endpoint:\s+(get|post|put|patch|delete)\s+(/\S+)', stripped)
            if endpoint_match:
                http_method = endpoint_match.group(1).lower()
                path = endpoint_match.group(2)
                methods.append({
                    "method_name": current_method_name,
                    "http_method": http_method,
                    "path": path,
                })
            # If we hit skip: true or another key, just keep current_method_name
            # until the next method definition

    return methods


def find_operation_id_for_endpoint(spec_content: str, http_method: str, path: str) -> str | None:
    """Find the current operationId for a given HTTP method + path in the OpenAPI spec."""
    lines = spec_content.split("\n")
    
    # Find the path block
    path_pattern = re.compile(r'^  ' + re.escape(path) + r':$')
    method_pattern = re.compile(r'^    ' + re.escape(http_method) + r':$')
    
    in_target_path = False
    
    for i, line in enumerate(lines):
        # Match path (2-space indent)
        if path_pattern.match(line):
            in_target_path = True
            continue

        # If we hit another path, stop
        if in_target_path and re.match(r'^  /\S+:', line):
            in_target_path = False
            continue

        # Match HTTP method under the target path (4-space indent)
        if in_target_path and method_pattern.match(line):
            # Search forward for operationId within this method block
            for j in range(i + 1, min(i + 20, len(lines))):
                op_match = re.match(r'^\s+operationId:\s+(\S+)', lines[j])
                if op_match:
                    return op_match.group(1)
                # Stop if we hit another method or path
                if re.match(r'^    (get|post|put|patch|delete):', lines[j]):
                    break
                if re.match(r'^  /\S+:', lines[j]):
                    break

    return None


def main():
    methods = parse_stainless_methods(STAINLESS_CONFIG)
    print(f"Found {len(methods)} methods in Stainless config\n")

    with open(OPENAPI_SPEC) as f:
        spec_content = f.read()

    replacements = []  # (old_id, new_id)

    for m in methods:
        old_id = find_operation_id_for_endpoint(spec_content, m["http_method"], m["path"])
        new_id = m["method_name"]

        if old_id is None:
            print(f"  WARNING: No operationId found for {m['http_method'].upper()} {m['path']} (method: {new_id})")
            continue

        if old_id == new_id:
            print(f"  OK (unchanged): {old_id}")
            continue

        replacements.append((old_id, new_id))
        print(f"  {old_id} → {new_id}")

    if not replacements:
        print("\nNo changes needed.")
        return

    # Sort longest-first to avoid substring collisions
    # e.g. "delete-file-version" must be replaced before "delete-file"
    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    print(f"\n--- Applying {len(replacements)} replacements (longest-first) ---\n")

    for old_id, new_id in replacements:
        count = spec_content.count(old_id)
        spec_content = spec_content.replace(old_id, new_id)
        print(f"  Replaced '{old_id}' → '{new_id}' ({count} occurrences)")

    with open(OPENAPI_SPEC, "w") as f:
        f.write(spec_content)

    print(f"\nDone. Updated {OPENAPI_SPEC}")


if __name__ == "__main__":
    main()
