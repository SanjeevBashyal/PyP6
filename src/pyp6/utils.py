# --- START OF FILE src/pyp6/utils.py ---

import json
from pathlib import Path
import sys
import types # Import the types module

# Define the standard location for the config directory and file
CONFIG_DIR = Path.home() / ".pyp6"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Define the package's hardcoded defaults in one place.
DEFAULTS = {
    "TARGET_PROJECT_ID": "UTHP",
    "HOURS_PER_DAY": 8.0,
    "USER_NAME": "PyP6_Script"
}

def load_config():
    """
    Loads configuration and returns it as a namespace object (like a module).
    This allows accessing settings with dot notation (e.g., cfg.database_path).
    """
    if not CONFIG_FILE.is_file():
        print("ERROR: pyp6 configuration not found.", file=sys.stderr)
        print("Please run the initialization command first:", file=sys.stderr)
        print(f"  pyp6-init \"/path/to/your/database.db\" \"/path/to/your/Data\"", file=sys.stderr)
        sys.exit(1)
    
    # Start with the hardcoded defaults.
    final_config_dict = DEFAULTS.copy()
    
    # Load and merge the user's config file.
    with open(CONFIG_FILE, 'r') as f:
        user_config = json.load(f)
    final_config_dict.update(user_config)
    
    # Ensure mandatory path keys exist.
    if "database_path" not in final_config_dict or "data_folder_path" not in final_config_dict:
        print("ERROR: Your config.json is corrupted or missing path information.", file=sys.stderr)
        print("Please re-run the init command: pyp6-init", file=sys.stderr)
        sys.exit(1)

    # --- KEY CHANGE: Convert dictionary to a SimpleNamespace object ---
    cfg = types.SimpleNamespace(**final_config_dict)

    # Convert string paths to Path objects for easier use.
    cfg.P6_PRO_DB_PATH = Path(cfg.database_path)
    cfg.DATA_PATH = Path(cfg.data_folder_path)

    # Add the specific CSV file paths for convenience, just like the old config.py
    cfg.ACT_FILE_PATH = cfg.DATA_PATH / "activities.csv"
    cfg.OBS_FILE_PATH = cfg.DATA_PATH / "obs.csv"
    cfg.WBS_FILE_PATH = cfg.DATA_PATH / "wbs.csv"
    cfg.ROLES_FILE_PATH = cfg.DATA_PATH / "roles.csv"
    
    return cfg

# --- END OF FILE src/pyp6/utils.py ---