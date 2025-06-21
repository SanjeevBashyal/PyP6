# --- START OF FILE activities_wbs_relationships.py ---

import sqlite3
import sys
import pandas as pd
from datetime import datetime
import time
import re

# Import shared settings and functions
import config as cfg
from access_db import connect_to_db
from access_p6 import get_project_defaults, generate_guid, get_next_id


def build_wbs_cache(cursor, proj_id):
    """Queries all WBS elements for a given project and returns a dictionary mapping WBS Name to wbs_id."""
    print("Building WBS cache for the project...")
    wbs_cache = {}
    query = "SELECT wbs_name, wbs_id FROM PROJWBS WHERE proj_id = ?"
    cursor.execute(query, (proj_id,))
    results = cursor.fetchall()
    for wbs_name, wbs_id in results:
        wbs_cache[wbs_name] = wbs_id
    if not wbs_cache:
        raise ValueError(
            f"No WBS elements found for project with proj_id: {proj_id}. Please add WBS first."
        )
    print(f"  -> WBS cache built successfully with {len(wbs_cache)} entries.")
    return wbs_cache


def parse_relationship(relationship_str):
    """Parses a relationship string like 'A1000[SS+5d]' into components."""
    pred_type = "FS"
    lag_hours = 0.0
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
        lag_hours = (
            float(lag_val * cfg.HOURS_PER_DAY)
            if lag_str.endswith("d")
            else float(lag_val)
        )
    return pred_activity_id, "PR_" + pred_type, lag_hours


def main():
    """Main function to read CSV and add activities under specific WBS with relationships."""

    # 1. Read and validate CSV
    try:
        df = pd.read_csv(cfg.ACTIVITIES_WBS_REL_FILE_PATH).fillna("")
        required_cols = [
            "Activity_ID",
            "Activity_Name",
            "Duration_Days",
            "WBS_Name",
            "Predecessors",
        ]
        if not all(col in df.columns for col in required_cols):
            raise ValueError(
                f"CSV must contain the columns: {', '.join(required_cols)}"
            )
        print(f"Read {len(df)} records from '{cfg.ACTIVITIES_WBS_REL_FILE_PATH}'.")
    except FileNotFoundError:
        print(f"ERROR: The file '{cfg.ACTIVITIES_WBS_REL_FILE_PATH}' was not found.")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: CSV format is incorrect. {e}")
        sys.exit(1)

    # 2. Connect to DB and set up
    conn = connect_to_db(cfg.P6_PRO_DB_PATH)
    cursor = conn.cursor()
    activity_id_to_task_id = {}

    try:
        # 3. Get project defaults and build WBS cache
        proj_id, root_wbs_id, clndr_id, _ = get_project_defaults(
            cursor, cfg.TARGET_PROJECT_ID
        )
        wbs_name_cache = build_wbs_cache(cursor, proj_id)

        next_task_id = get_next_id(cursor, "TASK", "task_id")
        next_task_pred_id = get_next_id(cursor, "TASKPRED", "task_pred_id")

        # --- PASS 1: INSERT ACTIVITIES ---
        print("\n--- Pass 1: Inserting Activities ---")
        current_time = datetime.now()
        sql_insert_task = """
            INSERT INTO TASK (task_id, proj_id, wbs_id, clndr_id, task_code, task_name, status_code, task_type, duration_type,
                              complete_pct_type, target_drtn_hr_cnt, remain_drtn_hr_cnt, auto_compute_act_flag, guid,
                              create_date, create_user, update_date, update_user)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        for index, row in df.iterrows():
            task_code = row["Activity_ID"]
            wbs_name = str(
                row["WBS_Name"]
            ).strip()  # Ensure it's a string and remove whitespace

            # --- LOGIC FOR OPTIONAL WBS_NAME ---
            # Default to the project's root WBS ID
            wbs_id = root_wbs_id

            if wbs_name:  # If a WBS Name is provided...
                wbs_id = wbs_name_cache.get(
                    wbs_name
                )  # ...try to get its ID from the cache.
                if not wbs_id:
                    # If it's not found in the cache, raise an error.
                    raise ValueError(
                        f"WBS Name '{wbs_name}' for Activity '{task_code}' not found in the project's WBS structure. Please check your CSV or run the WBS import script."
                    )
                print(f"Processing Activity: {task_code} (under WBS: '{wbs_name}')")
            else:  # If WBS Name is empty...
                # ...the wbs_id remains the root_wbs_id.
                print(f"Processing Activity: {task_code} (under project root WBS)")
            # --- END OF OPTIONAL WBS_NAME LOGIC ---

            if task_code in activity_id_to_task_id:
                print(
                    f"  -> WARNING: Duplicate Activity ID '{task_code}' in CSV. Skipping."
                )
                continue

            cursor.execute(
                "SELECT task_id FROM TASK WHERE proj_id = ? AND task_code = ?",
                (proj_id, task_code),
            )
            if cursor.fetchone():
                print(
                    f"  -> WARNING: Activity code '{task_code}' already exists in DB. Skipping insertion, but mapping for relationships."
                )
                cursor.execute(
                    "SELECT task_id FROM TASK WHERE proj_id = ? AND task_code = ?",
                    (proj_id, task_code),
                )
                activity_id_to_task_id[task_code] = cursor.fetchone()[0]
                continue

            duration_hours = row["Duration_Days"] * cfg.HOURS_PER_DAY
            task_data = (
                next_task_id,
                proj_id,
                wbs_id,
                clndr_id,
                task_code,
                row["Activity_Name"],
                "TK_NotStart",
                "TT_Task",
                "DT_FixedDur",
                "CP_Drtn",
                duration_hours,
                duration_hours,
                "Y",
                generate_guid(),
                current_time,
                cfg.USER_NAME,
                current_time,
                cfg.USER_NAME,
            )
            cursor.execute(sql_insert_task, task_data)
            activity_id_to_task_id[task_code] = next_task_id
            print(f"  -> Queued for insertion with Task ID: {next_task_id}")
            next_task_id += 1

        # --- PASS 2: INSERT RELATIONSHIPS ---
        # The logic to handle empty predecessors was already robust, but I've added comments to clarify.
        print("\n--- Pass 2: Inserting Relationships ---")
        sql_insert_pred = """
            INSERT INTO TASKPRED (task_pred_id, task_id, pred_task_id, proj_id, pred_proj_id,
                                  pred_type, lag_hr_cnt, create_date, create_user, update_date, update_user)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for index, row in df.iterrows():
            successor_code = row["Activity_ID"]
            # This check correctly handles empty strings, NaN, etc.
            predecessors_str = str(row["Predecessors"]).strip()
            if not predecessors_str:
                continue  # If the predecessor string is empty, skip this row entirely for Pass 2.

            successor_task_id = activity_id_to_task_id.get(successor_code)
            if not successor_task_id:
                continue

            print(f"Processing relationships for: {successor_code}")
            predecessor_list = [p.strip() for p in predecessors_str.split(",")]
            for pred_str in predecessor_list:
                try:
                    pred_code, pred_type, lag_hours = parse_relationship(pred_str)
                    predecessor_task_id = activity_id_to_task_id.get(pred_code)
                    if not predecessor_task_id:
                        print(
                            f"  -> ERROR: Predecessor '{pred_code}' for '{successor_code}' not found. Skipping link."
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
                        f"  -> Queued link: {pred_code} -> {successor_code} (Type: {pred_type.replace('PR_','')}, Lag: {lag_hours}h)"
                    )
                    next_task_pred_id += 1
                except ValueError as e:
                    print(
                        f"  -> ERROR: Could not parse relationship '{pred_str}' for '{successor_code}'. {e}"
                    )

        conn.commit()
        print("\nSUCCESS: All activities and relationships have been committed.")
        print("IMPORTANT: Open P6 and press F9 (Schedule) to see the changes.")

    except (ValueError, sqlite3.Error) as e:
        print(f"\nERROR: An error occurred: {e}. Rolling back all changes.")
        conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    main()

# --- END OF FILE activities_wbs_relationships.py ---
