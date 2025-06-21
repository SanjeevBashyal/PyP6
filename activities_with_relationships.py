import sqlite3
import sys
import pandas as pd
from datetime import datetime
import time  # Used for generating a simple unique ID
import re

# Import the connection function from your existing file
from access_db import connect_to_db
from access_p6 import get_project_defaults, generate_guid, get_next_id

import config as cfg


def parse_relationship(relationship_str):
    """
    Parses a relationship string like 'A1000[SS+5d]' into components.
    Format: ActivityID[Type+Lag] or ActivityID[Type] or ActivityID
    Type: FS, SS, FF, SF
    Lag: e.g., +5d (days) or -10h (hours)
    """
    # Default values
    pred_type = "FS"  # Finish-to-Start is the P6 default
    lag_hours = 0.0

    # Regex to capture the Activity ID, and optionally the type and lag
    match = re.match(
        r"^\s*([a-zA-Z0-9.-]+)\s*(?:\[\s*(\w{2})\s*([+-]?\d+[dh])?\s*\])?\s*$",
        relationship_str,
    )

    if not match:
        raise ValueError(f"Invalid relationship format: '{relationship_str}'")

    pred_activity_id, p_type, lag_str = match.groups()

    if p_type:
        pred_type = p_type.upper()
        if pred_type not in ["FS", "SS", "FF", "SF"]:
            raise ValueError(
                f"Invalid relationship type '{pred_type}' in '{relationship_str}'"
            )

    if lag_str:
        lag_val = int(re.findall(r"[+-]?\d+", lag_str)[0])
        if lag_str.endswith("d"):
            lag_hours = float(lag_val * cfg.HOURS_PER_DAY)
        elif lag_str.endswith("h"):
            lag_hours = float(lag_val)

    pred_type = "PR_" + pred_type

    return pred_activity_id, pred_type, lag_hours


def main():
    """Main function to read CSV and add activities and their relationships."""

    # 1. Read and validate CSV
    try:
        # Update config to point to the new CSV file
        cfg.ACT_FILE_PATH = cfg.DATA_PATH / "activities_with_relationships.csv"
        df = pd.read_csv(cfg.ACT_FILE_PATH).fillna("")
        required_cols = [
            "Activity_ID",
            "Activity_Name",
            "Duration_Days",
            "Predecessors",
        ]
        if not all(col in df.columns for col in required_cols):
            raise ValueError(
                f"CSV must contain the columns: {', '.join(required_cols)}"
            )
        print(f"Read {len(df)} records from '{cfg.ACT_FILE_PATH}'.")
    except FileNotFoundError:
        print(f"ERROR: The file '{cfg.ACT_FILE_PATH}' was not found.")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: CSV format is incorrect. {e}")
        sys.exit(1)

    # 2. Connect to DB and set up
    conn = connect_to_db(cfg.P6_PRO_DB_PATH)
    cursor = conn.cursor()

    # This map is crucial for linking relationships later
    activity_id_to_task_id = {}

    try:
        # 3. Get project defaults and starting IDs
        proj_id, wbs_id, clndr_id = get_project_defaults(cursor, cfg.TARGET_PROJECT_ID)
        next_task_id = get_next_id(cursor, "TASK", "task_id")
        next_task_pred_id = get_next_id(cursor, "TASKPRED", "task_pred_id")

        # --- PASS 1: INSERT ACTIVITIES ---
        print("\n--- Pass 1: Inserting Activities ---")
        current_time = datetime.now()

        sql_insert_task = """
            INSERT INTO TASK (
                task_id, proj_id, wbs_id, clndr_id, task_code, task_name,
                status_code, task_type, duration_type, complete_pct_type,
                target_drtn_hr_cnt, remain_drtn_hr_cnt, 
                auto_compute_act_flag, guid,
                create_date, create_user, update_date, update_user
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        for index, row in df.iterrows():
            task_code = row["Activity_ID"]
            if task_code in activity_id_to_task_id:
                print(
                    f"  -> WARNING: Duplicate Activity ID '{task_code}' in CSV. Skipping subsequent entry."
                )
                continue

            print(f"Processing Activity: {task_code} - {row['Activity_Name']}")

            cursor.execute(
                "SELECT task_id FROM TASK WHERE proj_id = ? AND task_code = ?",
                (proj_id, task_code),
            )
            if cursor.fetchone():
                print(
                    f"  -> WARNING: Activity with code '{task_code}' already exists in DB. Skipping."
                )
                # Still, we need its ID for relationships
                # Re-query to get the ID and add to map
                cursor.execute(
                    "SELECT task_id FROM TASK WHERE proj_id = ? AND task_code = ?",
                    (proj_id, task_code),
                )
                existing_task_id = cursor.fetchone()[0]
                activity_id_to_task_id[task_code] = existing_task_id
                continue

            duration_hours = row["Duration_Days"] * cfg.HOURS_PER_DAY
            task_data = (
                next_task_id,
                proj_id,
                wbs_id,  # Assign to the project's root WBS
                clndr_id,  # Assign to the project's default calendar
                task_code,
                row["Activity_Name"],
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
            cursor.execute(sql_insert_task, task_data)

            # Map the user-friendly ID to the new database ID
            activity_id_to_task_id[task_code] = next_task_id
            print(f"  -> Queued for insertion with Task ID: {next_task_id}")
            next_task_id += 1

        # --- PASS 2: INSERT RELATIONSHIPS ---
        print("\n--- Pass 2: Inserting Relationships ---")
        sql_insert_pred = """
            INSERT INTO TASKPRED (task_pred_id, task_id, pred_task_id, proj_id, pred_proj_id,
                                  pred_type, lag_hr_cnt, create_date, create_user, update_date, update_user)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        for index, row in df.iterrows():
            successor_code = row["Activity_ID"]
            predecessors_str = str(row["Predecessors"]).strip()

            if (
                not predecessors_str
                or predecessors_str == "nan"
                or predecessors_str == ""
            ):
                continue  # Skip if no predecessors are listed

            successor_task_id = activity_id_to_task_id.get(successor_code)
            if not successor_task_id:
                print(
                    f"  -> WARNING: Could not find successor '{successor_code}' in map. Skipping its relationships."
                )
                continue

            print(f"Processing relationships for: {successor_code}")
            predecessor_list = [p.strip() for p in str(predecessors_str).split(",")]

            for pred_str in predecessor_list:
                try:
                    pred_code, pred_type, lag_hours = parse_relationship(pred_str)

                    predecessor_task_id = activity_id_to_task_id.get(pred_code)
                    if not predecessor_task_id:
                        print(
                            f"  -> ERROR: Predecessor '{pred_code}' for '{successor_code}' not found in CSV or DB. Skipping this link."
                        )
                        continue

                    pred_data = (
                        next_task_pred_id,
                        successor_task_id,
                        predecessor_task_id,
                        proj_id,
                        proj_id,
                        pred_type,
                        lag_hours,
                        current_time,
                        cfg.USER_NAME,
                        current_time,
                        cfg.USER_NAME,
                    )
                    cursor.execute(sql_insert_pred, pred_data)
                    print(
                        f"  -> Queued link: {pred_code} -> {successor_code} (Type: {pred_type}, Lag: {lag_hours}h)"
                    )
                    next_task_pred_id += 1

                except ValueError as e:
                    print(
                        f"  -> ERROR: Could not parse relationship '{pred_str}' for successor '{successor_code}'. {e}"
                    )

        # 4. Commit all changes if both passes were successful
        conn.commit()
        print("\nSUCCESS: All activities and relationships have been committed.")
        print(
            "IMPORTANT: Open the project in P6 and press F9 (or go to Tools -> Schedule) to see the changes."
        )

    except (ValueError, sqlite3.Error) as e:
        print(f"\nERROR: An error occurred: {e}. Rolling back all changes.")
        conn.rollback()

    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    main()

# --- END OF FILE add_activities_with_relationships.py ---
