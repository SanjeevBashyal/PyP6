# --- START OF FILE config.py ---

from pathlib import Path

# --- Paths ---
# BASE_DIR allows for creating paths relative to this config file's location.
BASE_DIR = Path(__file__).resolve().parent

# Full path to the P6 SQLite database file.
P6_PRO_DB_PATH = r"C:\Users\Ripple\OneDrive - Tribhuvan University\1 UTHP\1 PMC\2 Construction Programme\Database\uthp.db"

# Directory for input data files.
DATA_PATH = BASE_DIR / 'Data'

# Paths to individual CSV files
ACT_FILE_PATH = DATA_PATH / 'activities.csv'
OBS_FILE_PATH = DATA_PATH / 'obs.csv'
WBS_FILE_PATH = DATA_PATH / 'wbs.csv'
ROLES_FILE_PATH = DATA_PATH / 'roles.csv'
ACTIVITIES_WBS_REL_FILE_PATH = DATA_PATH / 'activities_wbs_relationships.csv'


# --- P6 Project ---
# The Project Short Name in P6 where new data will be added.
TARGET_PROJECT_ID = 'UTHP'


# --- Defaults & Metadata ---
# Default conversion rate from days to hours for activity durations.
HOURS_PER_DAY = 8

# User name to log in the database for any created or updated records.
USER_NAME = 'PyScript'

# --- END OF FILE config.py ---