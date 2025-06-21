import sqlite3
import time


def get_project_defaults(cursor, project_short_name):
    """
    Retrieves the proj_id, root wbs_id, and default clndr_id for the target project.
    This requires a two-step lookup:
    1. Get proj_id and clndr_id from the PROJECT table.
    2. Get the root wbs_id from the PROJWBS table where the proj_node_flag is 'Y' for that project.
    """
    print(f"Fetching project defaults for '{project_short_name}'...")

    # Step 1: Get the project's internal ID and default calendar from the PROJECT table.
    project_query = "SELECT proj_id, clndr_id FROM PROJECT WHERE proj_short_name = ?"
    cursor.execute(project_query, (project_short_name,))
    project_result = cursor.fetchone()

    if not project_result:
        raise ValueError(f"Project with short name '{project_short_name}' not found in the PROJECT table.")
    
    proj_id, clndr_id = project_result

    if not clndr_id:
        raise ValueError(f"Project '{project_short_name}' does not have a default calendar assigned in the database.")

    print(f"Found Project ID: {proj_id}, Default Calendar ID: {clndr_id}")

    # Step 2: Find the root WBS for this project in the PROJWBS table.
    # The root WBS node is identified by having proj_node_flag = 'Y'.
    # Its wbs_short_name will also match the project_short_name.
    wbs_query = "SELECT wbs_id FROM PROJWBS WHERE proj_id = ? AND proj_node_flag = 'Y'"
    cursor.execute(wbs_query, (proj_id,))
    wbs_result = cursor.fetchone()

    if not wbs_result:
        raise ValueError(f"Could not find the root WBS node for project '{project_short_name}' (proj_id: {proj_id}). The database may be inconsistent or the project setup is incomplete.")
        
    root_wbs_id = wbs_result[0]
    print(f"Found Root WBS ID: {root_wbs_id}")
    
    return proj_id, root_wbs_id, clndr_id


def generate_guid():
    """Generates a simple, unique-enough string for the GUID field."""
    # P6 GUIDs are 22 chars. This is a simple way to create a unique string.
    return str(int(time.time() * 1000000))[:22]


def get_next_id(cursor, table_name, id_column):
    """Generic function to get the next available primary key ID."""
    cursor.execute(f"SELECT MAX({id_column}) FROM {table_name}")
    max_id = cursor.fetchone()[0]
    return (max_id or 0) + 1


def get_next_task_id(cursor):
    """
    Finds the maximum existing task_id in the database to ensure new IDs are unique.
    """
    cursor.execute("SELECT MAX(task_id) FROM TASK")
    max_id = cursor.fetchone()[0]
    return (max_id or 0) + 1  # Start from 1 if the table is empty
