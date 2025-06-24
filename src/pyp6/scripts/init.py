# --- START OF FILE src/pyp6/scripts/init.py ---

import json
from pathlib import Path
import sys

# Import DEFAULTS and path constants from the utils module
from pyp6.utils import DEFAULTS, CONFIG_DIR, CONFIG_FILE

def main():
    """
    Initializes the pyp6 configuration.

    If a config file already exists, it displays the path and does nothing.
    If no config file exists, it creates a template `config.json` with
    default values and placeholders for the user to edit.
    """
    # Create the ~/.pyp6 directory if it doesn't exist
    CONFIG_DIR.mkdir(exist_ok=True)

    if CONFIG_FILE.is_file():
        print("Configuration file already exists.")
        print(f"  -> You can edit it here: {CONFIG_FILE}")
        return
    
    # --- Create a new configuration file ---
    print(f"No configuration file found. Creating a new template at: {CONFIG_FILE}")

    # Start with the package defaults
    config_data = DEFAULTS.copy()
    
    # Add placeholder paths that the user must change.
    # Using platform-specific examples for user-friendliness.
    if sys.platform == "win32":
        placeholder_db_path = "C:\\path\\to\\your\\database.db"
        placeholder_data_folder = "C:\\path\\to\\your\\Data"
    else: # macOS, Linux, etc.
        placeholder_db_path = "/path/to/your/database.db"
        placeholder_data_folder = "/path/to/your/Data"
        
    config_data["database_path"] = placeholder_db_path
    config_data["data_folder_path"] = placeholder_data_folder

    # --- Write the template configuration to the JSON file ---
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        print(f"ERROR: Could not write configuration file to {CONFIG_FILE}. Please check permissions.", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nSUCCESS: A new configuration file has been created.")
    print("\nIMPORTANT: You must now edit this file with your actual paths.")
    print(f"  -> Edit file: {CONFIG_FILE}")
    
    print("\nFile contents:")
    print("-------------")
    with open(CONFIG_FILE, 'r') as f:
        print(f.read())
    print("-------------")

if __name__ == '__main__':
    main()

# --- END OF FILE src/pyp6/scripts/init.py ---