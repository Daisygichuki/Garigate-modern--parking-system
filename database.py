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

# The starting fee tiers, used ONLY to seed the fee_tiers table the very
# first time the app runs. After that, management edits rates through
# the /admin/rates page - never by touching this code again.
# Each tuple is (upper_minutes, price). The final tier's upper_minutes
# is None, meaning "everything above the previous tier".
DEFAULT_FEE_TIERS = [
    (30, 0),
    (120, 50),
    (240, 100),
    (360, 300),
    (None, 500),
]


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
    Creates the tables if they do not already exist, and seeds default
    data the first time the app runs. Safe to call every time the app
    starts - "IF NOT EXISTS" means it never wipes existing data.
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

    # One row PER VISIT. A finished, paid visit stays in the table
    # forever as a receipt/history record - this is what makes the
    # "auditable record of every shilling collected" objective possible.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            spot_id TEXT NOT NULL,
            plate_number TEXT NOT NULL,
            driver_name TEXT,
            check_in_time TEXT NOT NULL,
            check_out_time TEXT,
            amount_due REAL,
            payment_status TEXT DEFAULT 'unpaid',
            payment_method TEXT
        )
    """)

    # The pricing rulebook, as DATA instead of code. This is what lets
    # management change rates without a software change: editing a row
    # here needs no code edit and no restart.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fee_tiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sort_order INTEGER NOT NULL,
            upper_minutes REAL,
            price REAL NOT NULL
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

    # Only seed fee_tiers if it is empty (first run ever)
    cur.execute("SELECT COUNT(*) FROM fee_tiers")
    if cur.fetchone()[0] == 0:
        for order, (upper_minutes, price) in enumerate(DEFAULT_FEE_TIERS):
            cur.execute(
                "INSERT INTO fee_tiers (sort_order, upper_minutes, price) VALUES (?, ?, ?)",
                (order, upper_minutes, price)
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


def pay_session(session_id, spot_id, payment_method):
    """
    Confirms payment, records HOW it was paid, frees the physical bay
    again, and this is the exact moment the barrier is allowed to open
    (see app.py /pay route).
    """
    conn = get_connection()
    conn.execute(
        """UPDATE sessions SET payment_status = 'paid', payment_method = ?
           WHERE session_id = ?""",
        (payment_method, session_id)
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


# ---------------------------------------------------------------------
# Fee tiers - lets management change rates without a software change
# ---------------------------------------------------------------------

def get_fee_tiers():
    """
    Returns the current pricing rules as a list of (upper_minutes, price)
    tuples, ordered cheapest/shortest first. upper_minutes is None for
    the final, uncapped tier.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT upper_minutes, price FROM fee_tiers ORDER BY sort_order"
    ).fetchall()
    conn.close()
    return [(row["upper_minutes"], row["price"]) for row in rows]


def update_fee_tiers(tiers):
    """
    Replaces the whole pricing table with a new set of tiers.
    tiers: a list of (upper_minutes, price) tuples, in order.
    This is a "delete everything, insert the new set" approach -
    simple and safe because there are only ever 5 tiers.
    """
    conn = get_connection()
    conn.execute("DELETE FROM fee_tiers")
    for order, (upper_minutes, price) in enumerate(tiers):
        conn.execute(
            "INSERT INTO fee_tiers (sort_order, upper_minutes, price) VALUES (?, ?, ?)",
            (order, upper_minutes, price)
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# Reporting - the auditable record of every shilling collected
# ---------------------------------------------------------------------

def get_paid_sessions(start_date=None, end_date=None, payment_method=None):
    """
    Returns completed, PAID sessions, optionally filtered by a date
    range (inclusive, 'YYYY-MM-DD' strings compared against the date
    part of check_out_time) and/or a specific payment method.
    Used by the /reports page for reconciliation.
    """
    conn = get_connection()
    query = "SELECT * FROM sessions WHERE payment_status = 'paid'"
    params = []

    if start_date:
        query += " AND date(check_out_time) >= date(?)"
        params.append(start_date)
    if end_date:
        query += " AND date(check_out_time) <= date(?)"
        params.append(end_date)
    if payment_method:
        query += " AND payment_method = ?"
        params.append(payment_method)

    query += " ORDER BY check_out_time DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows
