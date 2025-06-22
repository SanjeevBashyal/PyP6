# --- START OF FILE add_roles.py ---

import sqlite3
import sys
import pandas as pd
from datetime import datetime
import time

# Import shared settings and functions
from pyp6 import config as cfg
from pyp6.access_db import connect_to_db

def generate_guid():
    """Generates a simple, unique-enough string for the GUID field."""
    return str(int(time.time() * 1000000))[:22]

def get_next_id(cursor, table_name, id_column):
    """Generic function to get the next available primary key ID."""
    cursor.execute(f"SELECT MAX({id_column}) FROM {table_name}")
    max_id = cursor.fetchone()[0]
    return (max_id or 0) + 1

def get_or_create_role_id(cursor, role_name, short_name, parent_role_name, cache):
    """
    Finds a Role by name or creates it if it doesn't exist.
    """
    if pd.isna(role_name) or not role_name:
        return None

    if role_name in cache:
        return cache[role_name]

    cursor.execute("SELECT role_id FROM ROLES WHERE role_name = ?", (role_name,))
    result = cursor.fetchone()
    if result:
        role_id = result[0]
        cache[role_name] = role_id
        print(f"Found existing Role: '{role_name}' (ID: {role_id})")
        return role_id

    print(f"Role '{role_name}' not found. Attempting to create.")
    parent_role_id = get_or_create_role_id(cursor, parent_role_name, "", "", cache)

    try:
        sql_insert = """
            INSERT INTO ROLES (
                role_id, parent_role_id, role_name, role_short_name,
                create_date, create_user, update_date, update_user
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        new_role_id = get_next_id(cursor, 'ROLES', 'role_id')
        current_time = datetime.now()
        
        cursor.execute(sql_insert, (new_role_id, parent_role_id, role_name, short_name, current_time, cfg.USER_NAME, current_time, cfg.USER_NAME))

        cache[role_name] = new_role_id
        print(f"  -> Successfully created Role: '{role_name}' with ID: {new_role_id}")
        return new_role_id

    except sqlite3.Error as e:
        print(f"ERROR: Failed to insert Role '{role_name}'. {e}")
        raise

def main():
    try:
        df = pd.read_csv(cfg.ROLES_FILE_PATH).fillna('')
        if not all(col in df.columns for col in ['Role_Name', 'Role_Short_Name', 'Parent_Role_Name']):
             raise ValueError("CSV must contain 'Role_Name', 'Role_Short_Name', and 'Parent_Role_Name' columns.")
        print(f"Read {len(df)} Role records from '{cfg.ROLES_FILE_PATH}'.")
    except FileNotFoundError:
        print(f"ERROR: The file '{cfg.ROLES_FILE_PATH}' was not found.")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: CSV format is incorrect. {e}")
        sys.exit(1)

    conn = connect_to_db(cfg.P6_PRO_DB_PATH)
    cursor = conn.cursor()
    role_cache = {}

    try:
        print("\n--- Processing Roles Hierarchy ---")
        for index, row in df.iterrows():
            get_or_create_role_id(cursor, row['Role_Name'], row['Role_Short_Name'], row['Parent_Role_Name'], role_cache)

        conn.commit()
        print("\nSUCCESS: Roles hierarchy changes have been committed to the database.")

    except Exception as e:
        print(f"\nERROR: An error occurred: {e}. Rolling back all changes.")
        conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    main()

# --- END OF FILE add_roles.py ---