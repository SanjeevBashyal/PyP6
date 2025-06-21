# --- START OF FILE wbs.py ---

import sqlite3
import sys
import pandas as pd
from datetime import datetime

# Import shared settings and functions
import config as cfg
from access_db import connect_to_db
from access_p6 import generate_guid, get_next_id, get_project_defaults

def get_or_create_wbs_id(cursor, proj_id, root_wbs_id, wbs_short_name, wbs_name, parent_wbs_name, cache):
    """
    Finds a WBS element by its short name or creates it if it doesn't exist.
    It now uses the parent's full name to find the parent_wbs_id.
    """
    if pd.isna(wbs_short_name) or not wbs_short_name:
        return None

    # Use the WBS Short Name as the unique key for the cache
    if wbs_short_name in cache:
        return cache[wbs_short_name]

    # Check if this WBS element already exists in the database
    cursor.execute("SELECT wbs_id FROM PROJWBS WHERE proj_id = ? AND wbs_name = ?", (proj_id, wbs_name))
    result = cursor.fetchone()
    if result:
        wbs_id = result[0]
        cache[wbs_short_name] = wbs_id
        print(f"Found existing WBS: '{wbs_short_name}' (ID: {wbs_id})")
        return wbs_id
        
    print(f"WBS element '{wbs_short_name}' not found. Attempting to create.")
    
    # --- Parent Lookup Logic (Modified) ---
    parent_wbs_id = root_wbs_id # Default to the project's root WBS
    if pd.notna(parent_wbs_name) and parent_wbs_name:
        # Find the parent's ID by its NAME.
        # This assumes WBS Names are unique within the project and parents are processed first.
        cursor.execute("SELECT wbs_id FROM PROJWBS WHERE proj_id = ? AND wbs_name = ?", (proj_id, parent_wbs_name))
        parent_result = cursor.fetchone()
        
        if not parent_result:
            # This error occurs if the parent row was not found in the DB.
            # It highlights the need for the CSV to be ordered correctly.
            raise ValueError(
                f"Could not find parent WBS with name '{parent_wbs_name}' for WBS '{wbs_short_name}'. "
                f"Please ensure parent rows appear before child rows in your CSV file."
            )
        parent_wbs_id = parent_result[0]
        print(f"  -> Found parent '{parent_wbs_name}' with ID: {parent_wbs_id}")

    # --- WBS Insertion Logic (Unchanged) ---
    try:
        sql_insert = """
            INSERT INTO PROJWBS (
                wbs_id, proj_id, parent_wbs_id, wbs_short_name, wbs_name,
                proj_node_flag, sum_data_flag, status_code, guid,
                create_date, create_user, update_date, update_user
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        new_wbs_id = get_next_id(cursor, 'PROJWBS', 'wbs_id')
        current_time = datetime.now()
        
        wbs_data = (
            new_wbs_id, proj_id, parent_wbs_id, wbs_short_name, wbs_name,
            'N', 'Y', 'WS_Active', generate_guid(), # Set proj_node_flag to 'N' for all new elements
            current_time, cfg.USER_NAME, current_time, cfg.USER_NAME
        )
        cursor.execute(sql_insert, wbs_data)

        # Add the newly created WBS to the cache
        cache[wbs_short_name] = new_wbs_id
        print(f"  -> Successfully created WBS: '{wbs_short_name}' - '{wbs_name}' with ID: {new_wbs_id}")
        return new_wbs_id

    except sqlite3.Error as e:
        print(f"ERROR: Failed to insert WBS '{wbs_short_name}'. {e}")
        raise

def main():
    try:
        df = pd.read_csv(cfg.WBS_FILE_PATH).fillna('')
        # Validate using the new column names
        required_cols = ['WBS Short Name', 'WBS Name', 'Parent WBS Name']
        if not all(col in df.columns for col in required_cols):
             raise ValueError(f"CSV must contain the columns: {', '.join(required_cols)}.")
        print(f"Read {len(df)} WBS records from '{cfg.WBS_FILE_PATH}'.")
        print("IMPORTANT: The script assumes that parent WBS elements are listed before their children in the CSV file.")

    except FileNotFoundError:
        print(f"ERROR: The file '{cfg.WBS_FILE_PATH}' was not found.")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: CSV format is incorrect. {e}")
        sys.exit(1)

    conn = connect_to_db(cfg.P6_PRO_DB_PATH)
    cursor = conn.cursor()
    # The cache maps WBS Short Name -> wbs_id
    wbs_cache = {}

    try:
        proj_id, root_wbs_id, _ = get_project_defaults(cursor, cfg.TARGET_PROJECT_ID)
        
        # Add the project's root WBS name and ID to the cache for lookups
        cursor.execute("SELECT wbs_name, wbs_short_name FROM PROJWBS WHERE wbs_id = ?", (root_wbs_id,))
        root_wbs_info = cursor.fetchone()
        if root_wbs_info:
            wbs_cache[root_wbs_info[1]] = root_wbs_id

        print("\n--- Processing WBS Hierarchy ---")
        for index, row in df.iterrows():
            # Call the function with the new column names from the DataFrame
            get_or_create_wbs_id(
                cursor, 
                proj_id, 
                root_wbs_id, 
                row['WBS Short Name'], 
                row['WBS Name'], 
                row['Parent WBS Name'], 
                wbs_cache
            )

        conn.commit()
        print("\nSUCCESS: WBS hierarchy changes have been committed to the database.")

    except Exception as e:
        print(f"\nERROR: An error occurred: {e}. Rolling back all changes.")
        conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    main()

# --- END OF FILE wbs.py ---