#!/usr/bin/env python3
"""
Script to update imports in test files after moving them to the tests directory.
"""

import os
import re
import glob

# Path to the tests directory
TESTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests')

def update_imports(file_path):
    """Update imports in a test file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if the file already has the correct import path
    if "parent_dir = os.path.dirname(os.path.dirname(current_dir))" in content:
        print(f"Skipping {file_path} - already updated")
        return
    
    # Add the correct import path
    import_path_code = """
# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels
sys.path.insert(0, parent_dir)
"""
    
    # Check if the file has import statements
    if "import" in content:
        # Replace existing sys.path manipulation
        content = re.sub(
            r"# Add .*?\n.*?sys\.path\.insert\(0, .*?\)\n",
            import_path_code,
            content,
            flags=re.DOTALL
        )
        
        # If no existing sys.path manipulation, add after imports
        if "sys.path.insert" not in content:
            # Find the last import statement
            import_match = re.search(r"^import .*$|^from .*$", content, re.MULTILINE)
            if import_match:
                last_import_pos = content.rfind(import_match.group(0))
                last_import_end = content.find('\n', last_import_pos) + 1
                
                # Insert the import path code after the last import
                content = content[:last_import_end] + import_path_code + content[last_import_end:]
    
    # Write the updated content back to the file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Updated {file_path}")

def main():
    """Main function."""
    # Find all test files
    test_files = glob.glob(os.path.join(TESTS_DIR, 'unit', 'test_*.py'))
    test_files += glob.glob(os.path.join(TESTS_DIR, 'integration', 'test_*.py'))
    
    # Update imports in each file
    for file_path in test_files:
        update_imports(file_path)
    
    print(f"Updated {len(test_files)} test files")

if __name__ == "__main__":
    main() 