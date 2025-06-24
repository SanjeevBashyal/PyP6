# --- START OF FILE activities.py ---

import sqlite3
import sys
import pandas as pd
from datetime import datetime
import time
import re

# Import shared settings and functions
# from pyp6 import config as cfg
from pyp6.access_db import connect_to_db
from pyp6.access_p6 import get_project_defaults, generate_guid, get_next_id
from pyp6.utils import load_config

# --- Helper Functions ---


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


def build_task_code_map(cursor, proj_id):
    """
    Queries ALL existing activities in the project and returns a dictionary
    mapping their task_code to their internal task_id. This allows linking to
    pre-existing activities not in the current CSV.
    """
    print("Building cache of existing activities from the database...")
    task_map = {}
    query = "SELECT task_code, task_id FROM TASK WHERE proj_id = ?"
    cursor.execute(query, (proj_id,))
    results = cursor.fetchall()
    for task_code, task_id in results:
        task_map[task_code] = task_id
    print(f"  -> Activity cache built successfully with {len(task_map)} entries.")
    return task_map


def parse_relationship(relationship_str, cfg):
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


# --- Main Execution ---


def main():
    cfg = load_config()
    """Main function to read CSV and add activities under specific WBS with relationships."""
    try:
        df = pd.read_csv(cfg.ACT_FILE_PATH).fillna("")
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
        print(f"Read {len(df)} records from '{cfg.ACT_FILE_PATH}'.")
    except FileNotFoundError:
        print(f"ERROR: The file '{cfg.ACT_FILE_PATH}' was not found.")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: CSV format is incorrect. {e}")
        sys.exit(1)

    conn = connect_to_db(cfg.P6_PRO_DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Get project defaults and build caches
        proj_id, root_wbs_id, clndr_id, _ = get_project_defaults(
            cursor, cfg.TARGET_PROJECT_ID
        )
        wbs_name_cache = build_wbs_cache(cursor, proj_id)

        # --- KEY CHANGE: PRE-LOAD ALL EXISTING ACTIVITIES ---
        activity_id_to_task_id = build_task_code_map(cursor, proj_id)

        # 2. Get next available IDs
        next_task_id = get_next_id(cursor, "TASK", "task_id")
        next_task_pred_id = get_next_id(cursor, "TASKPRED", "task_pred_id")

        # --- PASS 1: INSERT NEW ACTIVITIES ---
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
            wbs_name = str(row["WBS_Name"]).strip()

            wbs_id = root_wbs_id
            if wbs_name:
                wbs_id = wbs_name_cache.get(wbs_name)
                if not wbs_id:
                    raise ValueError(
                        f"WBS Name '{wbs_name}' for Activity '{task_code}' not found in the project's WBS structure."
                    )

            # The check now works against the pre-loaded map of ALL activities.
            if task_code in activity_id_to_task_id:
                print(
                    f"  -> INFO: Activity code '{task_code}' already exists in DB or is a duplicate in the CSV. Skipping creation."
                )
                continue

            print(
                f"Processing Activity: {task_code} (under WBS: '{wbs_name or 'Project Root'}')"
            )

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

            # Add the NEWLY created activity to our map for Pass 2.
            activity_id_to_task_id[task_code] = next_task_id
            print(f"  -> Queued for insertion with Task ID: {next_task_id}")
            next_task_id += 1

        # --- PASS 2: INSERT RELATIONSHIPS ---
        # No changes are needed here. The activity_id_to_task_id map is now comprehensive.
        print("\n--- Pass 2: Inserting Relationships ---")
        sql_insert_pred = """
            INSERT INTO TASKPRED (task_pred_id, task_id, pred_task_id, proj_id, pred_proj_id,
                                  pred_type, lag_hr_cnt, create_date, create_user, update_date, update_user)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for index, row in df.iterrows():
            successor_code = row["Activity_ID"]
            predecessors_str = str(row["Predecessors"]).strip()
            if not predecessors_str:
                continue

            successor_task_id = activity_id_to_task_id.get(successor_code)
            if not successor_task_id:
                # This can happen if the successor was a duplicate and skipped in Pass 1.
                continue

            print(f"Processing relationships for: {successor_code}")
            predecessor_list = [p.strip() for p in predecessors_str.split(",")]
            for pred_str in predecessor_list:
                try:
                    pred_code, pred_type, lag_hours = parse_relationship(pred_str, cfg)

                    # This lookup now works for pre-existing AND newly created activities.
                    predecessor_task_id = activity_id_to_task_id.get(pred_code)
                    if not predecessor_task_id:
                        print(
                            f"  -> ERROR: Predecessor activity '{pred_code}' for '{successor_code}' not found in the DB or CSV. Skipping this link."
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
