# --- START OF FILE add_activities.py ---

import sqlite3
import sys
import pandas as pd
from datetime import datetime
import time  # Used for generating a simple unique ID

# Import the connection function from your existing file
from access_db import connect_to_db
from access_p6 import get_project_defaults, get_next_task_id, generate_guid

import config as cfg


def main():
    """Main function to read CSV and add activities to the TASK table."""

    # 1. Read data from CSV file
    try:
        df = pd.read_csv(cfg.ACT_FILE_PATH)
        # Validate that the necessary columns exist in the CSV
        if not all(
            col in df.columns
            for col in ["Activity_ID", "Activity_Name", "Duration_Days"]
        ):
            raise ValueError(
                "CSV file must contain 'Activity_ID', 'Activity_Name', and 'Duration_Days' columns."
            )
        print(f"Read {len(df)} activity records from '{cfg.ACT_FILE_PATH}'.")
    except FileNotFoundError:
        print(f"ERROR: The file '{cfg.ACT_FILE_PATH}' was not found.")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: CSV format is incorrect. {e}")
        sys.exit(1)

    # 2. Connect to the database
    conn = connect_to_db(cfg.P6_PRO_DB_PATH)
    cursor = conn.cursor()

    try:
        # 3. Get project defaults and starting task_id
        proj_id, wbs_id, clndr_id = get_project_defaults(cursor, cfg.TARGET_PROJECT_ID)
        next_task_id = get_next_task_id(cursor)
        print(f"New activities will start with internal Task ID: {next_task_id}")

        # 4. Prepare the SQL INSERT statement for the TASK table
        # We only insert the minimum required fields. P6 calculates the rest.
        sql_insert = """
            INSERT INTO TASK (
                task_id, proj_id, wbs_id, clndr_id, task_code, task_name,
                status_code, task_type, duration_type, complete_pct_type,
                target_drtn_hr_cnt, remain_drtn_hr_cnt, 
                auto_compute_act_flag, guid,
                create_date, create_user, update_date, update_user
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # 5. Iterate over the DataFrame and insert activities
        print("\n--- Inserting Activities into Database ---")
        current_time = datetime.now()

        for index, row in df.iterrows():
            task_code = row["Activity_ID"]
            task_name = row["Activity_Name"]
            duration_days = row["Duration_Days"]
            duration_hours = duration_days * cfg.HOURS_PER_DAY

            print(f"Processing: {task_code} - {task_name}")

            # Check if an activity with the same code already exists in this project
            cursor.execute(
                "SELECT task_id FROM TASK WHERE proj_id = ? AND task_code = ?",
                (proj_id, task_code),
            )
            if cursor.fetchone():
                print(
                    f"  -> WARNING: Activity with code '{task_code}' already exists. Skipping."
                )
                continue

            # This tuple holds all the data for the new activity record
            task_data = (
                next_task_id,
                proj_id,
                wbs_id,  # Assign to the project's root WBS
                clndr_id,  # Assign to the project's default calendar
                task_code,
                task_name,
                "TK_NotStart",  # Status Code: Not Started
                "TT_Task",  # Task Type: Task Dependent
                "DT_FixedDur",  # Duration Type: Fixed Duration & Units
                "CP_Drtn",  # Percent Complete Type: Duration
                duration_hours,  # Target Duration (in hours)
                duration_hours,  # Remaining Duration (in hours)
                "Y",  # Auto Compute Actuals Flag
                generate_guid(),  # A unique identifier
                current_time,  # Create Date
                cfg.USER_NAME,  # Create User
                current_time,  # Update Date
                cfg.USER_NAME,  # Update User
            )

            cursor.execute(sql_insert, task_data)
            print(f"  -> Queued for insertion with Task ID: {next_task_id}")
            next_task_id += 1  # Increment ID for the next activity

        # 6. If all inserts are successful, commit the transaction to save changes
        conn.commit()
        print("\nSUCCESS: All new activities have been committed to the database.")
        print(
            "IMPORTANT: Open the project in P6 and press F9 (or go to Tools -> Schedule) to calculate dates."
        )

    except (ValueError, sqlite3.Error) as e:
        # 7. If any error occurred, roll back the entire transaction to prevent partial updates
        print(f"\nERROR: An error occurred: {e}. Rolling back all changes.")
        conn.rollback()
        print("Rollback complete. No changes were made to the database.")

    finally:
        # 8. Always close the connection
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    main()

# --- END OF FILE add_activities.py ---
