import sqlite3 # Use the built-in SQLite library
import sys

def connect_to_db(P6_PRO_DB_PATH):
    """Establishes a connection to the P6 SQLite database."""
    try:
        conn = sqlite3.connect(P6_PRO_DB_PATH)
        print("Successfully connected to the P6 SQLite database.")
        return conn
    except sqlite3.Error as e:
        print(f"ERROR: Database connection failed: {e}")
        sys.exit(1)

