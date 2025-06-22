# --- START OF FILE obs.py ---

import sqlite3
import sys
import pandas as pd
from datetime import datetime

# Import shared settings and functions
from pyp6 import config as cfg
from pyp6.access_db import connect_to_db
from pyp6.access_p6 import generate_guid, get_next_id

def get_or_create_obs_id(cursor, index, obs_name, parent_obs_name, cache):
    """
    Finds an OBS element by name or creates it if it doesn't exist,
    now including a programmatically generated sequence number.
    """
    if pd.isna(obs_name) or not obs_name:
        return None  # Handles empty or NaN parent names

    # 1. Check cache first to avoid DB calls
    if obs_name in cache:
        return cache[obs_name]

    # 2. Check if the OBS element already exists in the database
    cursor.execute("SELECT obs_id FROM OBS WHERE obs_name = ?", (obs_name,))
    result = cursor.fetchone()
    if result:
        obs_id = result[0]
        cache[obs_name] = obs_id
        print(f"Found existing OBS: '{obs_name}' (ID: {obs_id})")
        return obs_id

    # 3. If it doesn't exist, we must create it. First, get the parent's ID.
    print(f"OBS element '{obs_name}' not found. Attempting to create.")
    # The parent doesn't need an index since we are creating it recursively.
    # Pass a placeholder index like -1.
    parent_obs_id = get_or_create_obs_id(cursor, -1, parent_obs_name, None, cache)

    # 4. Insert the new OBS element with the sequence number
    try:
        # MODIFIED: Added seq_num to the INSERT statement
        sql_insert = """
            INSERT INTO OBS (obs_id, parent_obs_id, seq_num, obs_name, guid, 
                             create_date, create_user, update_date, update_user)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        new_obs_id = get_next_id(cursor, 'OBS', 'obs_id')
        current_time = datetime.now()
        guid = generate_guid()
        # NEW: Generate sequence number from the CSV row index
        seq_num = (index + 1) * 10

        # MODIFIED: Added seq_num to the data tuple
        obs_data = (
            new_obs_id, parent_obs_id, seq_num, obs_name, guid,
            current_time, cfg.USER_NAME, current_time, cfg.USER_NAME
        )
        cursor.execute(sql_insert, obs_data)

        cache[obs_name] = new_obs_id
        print(f"  -> Successfully created OBS: '{obs_name}' with ID: {new_obs_id} and Seq Num: {seq_num}")
        return new_obs_id

    except sqlite3.Error as e:
        print(f"ERROR: Failed to insert OBS element '{obs_name}'. {e}")
        raise  # Raise exception to trigger a transaction rollback

def main():
    """Main function to read CSV and populate the OBS table."""
    try:
        df = pd.read_csv(cfg.OBS_FILE_PATH).fillna('')
        if not all(col in df.columns for col in ['OBS_Name', 'Parent_OBS_Name']):
            raise ValueError("CSV must contain 'OBS_Name' and 'Parent_OBS_Name' columns.")
        print(f"Read {len(df)} OBS records from '{cfg.OBS_FILE_PATH}'.")
    except FileNotFoundError:
        print(f"ERROR: The file '{cfg.OBS_FILE_PATH}' was not found.")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: CSV format is incorrect. {e}")
        sys.exit(1)

    conn = connect_to_db(cfg.P6_PRO_DB_PATH)
    cursor = conn.cursor()
    obs_cache = {}  # Cache to store OBS Name -> obs_id

    try:
        print("\n--- Processing OBS Hierarchy ---")
        # The 'index' from iterrows() is now used to generate the sequence number
        for index, row in df.iterrows():
            get_or_create_obs_id(cursor, index, row['OBS_Name'], row['Parent_OBS_Name'], obs_cache)

        conn.commit()
        print("\nSUCCESS: OBS hierarchy changes have been committed to the database.")

    except Exception as e:
        print(f"\nERROR: An error occurred: {e}. Rolling back all changes.")
        conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    main()

# --- END OF FILE obs.py ---