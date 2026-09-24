"""
database.py
------------
This file is our "database module". Its only job is to talk to the
SQLite database file (garigate.db) so that the rest of the app never
has to write raw SQL directly. Think of it as the "librarian" -
other files ask it for information, and it goes and fetches/stores it.

We use SQLite because it needs NO separate server install (unlike
MySQL/Postgres) - it's just a single file on disk. Perfect for a
student project that still needs a REAL database (not just a Python
dictionary that disappears when the program stops).
"""

import sqlite3
from datetime import datetime

DB_NAME = "garigate.db"

# Zones and how many bays are in each zone. Feel free to change this
# to resize the parking lot - the rest of the app reads from here.
ZONE_LAYOUT = {
    "A": 4,   # A1, A2, A3, A4
    "B": 4,   # B1, B2, B3, B4
    "C": 4,   # C1, C2, C3, C4
}


def get_connection():
    """
    Opens a connection to the database file.
    row_factory = sqlite3.Row lets us access columns by NAME
    (e.g. row["status"]) instead of only by position (row[2]),
    which makes the rest of the code much easier to read.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Creates the tables if they do not already exist, and fills the
    'spots' table with empty bays the first time the app runs.
    This is safe to call every time the app starts - it won't wipe
    existing data because of "IF NOT EXISTS".
    """
    conn = get_connection()
    cur = conn.cursor()

    # One row per physical parking bay (A1, A2, B1, ...)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS spots (
            spot_id TEXT PRIMARY KEY,
            zone TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available'
        )
    """)

    # One row PER VISIT. A finished visit stays in the table forever
    # as a receipt/history record - this doubles as our "database"
    # of past transactions, which examiners like to see.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            spot_id TEXT NOT NULL,
            plate_number TEXT NOT NULL,
            driver_name TEXT,
            check_in_time TEXT NOT NULL,
            check_out_time TEXT,
            amount_due REAL,
            payment_status TEXT DEFAULT 'unpaid'
        )
    """)
    conn.commit()

    # Only seed the spots table if it is empty (first run ever)
    cur.execute("SELECT COUNT(*) FROM spots")
    if cur.fetchone()[0] == 0:
        for zone, bay_count in ZONE_LAYOUT.items():
            for n in range(1, bay_count + 1):
                spot_id = f"{zone}{n}"
                cur.execute(
                    "INSERT INTO spots (spot_id, zone, status) VALUES (?, ?, 'available')",
                    (spot_id, zone)
                )
        conn.commit()

    conn.close()


def get_all_spots():
    """Returns every bay, grouped in the order needed for the visual grid."""
    conn = get_connection()
    spots = conn.execute("SELECT * FROM spots ORDER BY zone, spot_id").fetchall()
    conn.close()
    return spots


def get_available_spot():
    """
    Finds the FIRST free bay (a simple 'first available' allocation
    strategy - nearest-to-the-entrance style, like a real barrier gate).
    Returns None if the lot is full.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM spots WHERE status = 'available' ORDER BY spot_id LIMIT 1"
    ).fetchone()
    conn.close()
    return row


def find_active_session_by_plate(plate_number):
    """Finds a vehicle that is currently parked (no check_out_time yet)."""
    conn = get_connection()
    row = conn.execute(
        """SELECT * FROM sessions
           WHERE plate_number = ? AND check_out_time IS NULL
           ORDER BY session_id DESC LIMIT 1""",
        (plate_number,)
    ).fetchone()
    conn.close()
    return row


def create_session(spot_id, plate_number, driver_name):
    """Records a new arrival: occupies the bay and opens a new session row."""
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE spots SET status = 'occupied' WHERE spot_id = ?",
        (spot_id,)
    )
    conn.execute(
        """INSERT INTO sessions (spot_id, plate_number, driver_name, check_in_time)
           VALUES (?, ?, ?, ?)""",
        (spot_id, plate_number, driver_name, now)
    )
    conn.commit()
    conn.close()


def close_session(session_id, amount_due):
    """Marks a session as billed (still 'unpaid' until pay_session() runs)."""
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """UPDATE sessions SET check_out_time = ?, amount_due = ?
           WHERE session_id = ?""",
        (now, amount_due, session_id)
    )
    conn.commit()
    conn.close()


def pay_session(session_id, spot_id):
    """
    Confirms payment, frees the physical bay again, and this is the
    exact moment the barrier is allowed to open (see app.py /pay route).
    """
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET payment_status = 'paid' WHERE session_id = ?",
        (session_id,)
    )
    conn.execute(
        "UPDATE spots SET status = 'available' WHERE spot_id = ?",
        (spot_id,)
    )
    conn.commit()
    conn.close()


def get_recent_history(limit=8):
    """Last few completed visits, shown on the dashboard as an activity feed."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM sessions WHERE check_out_time IS NOT NULL
           ORDER BY session_id DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return rows
