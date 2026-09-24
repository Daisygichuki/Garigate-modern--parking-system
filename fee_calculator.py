"""
fee_calculator.py
------------------
Keeping the billing logic in its OWN small file (instead of burying it
inside app.py) is good practice: it is the single "source of truth"
for how much a driver owes, it's easy to unit-test on its own, and a
lecturer marking algorithms/logic can find it in one glance.

Fee tiers, exactly as given in the brief:
    0  - 30 minutes   -> FREE
    30 min - 2 hours   -> KSh 50
    2 hrs  - 4 hours   -> KSh 100
    4 hrs  - 6 hours   -> KSh 300
    over 6 hours        -> KSh 500
"""

from datetime import datetime

# (upper_limit_in_minutes, price) - checked in order, first match wins.
# Using a table like this (instead of a long if/elif chain) makes it
# trivial to change the pricing later without touching any logic.
FEE_TIERS = [
    (30,   0),
    (120,  50),
    (240,  100),
    (360,  300),
    (float("inf"), 500),
]


def calculate_duration_minutes(check_in_iso, check_out_iso=None):
    """
    Works out how many minutes a car has been parked.
    Both timestamps are stored as ISO strings (e.g. '2026-09-23T14:05:00')
    because that is what SQLite is happiest storing as TEXT.
    """
    check_in = datetime.fromisoformat(check_in_iso)
    check_out = datetime.fromisoformat(check_out_iso) if check_out_iso else datetime.now()
    delta = check_out - check_in
    return delta.total_seconds() / 60


def calculate_fee(duration_minutes):
    """Looks up the correct tier for a given duration and returns the price."""
    for upper_limit, price in FEE_TIERS:
        if duration_minutes <= upper_limit:
            return price
    return FEE_TIERS[-1][1]  # safety net, should never actually be reached


def format_duration(duration_minutes):
    """Turns '125.4' minutes into a friendly '2h 5m' style string for the UI."""
    total_minutes = int(duration_minutes)
    hours, minutes = divmod(total_minutes, 60)
    if hours == 0:
        return f"{minutes}m"
    return f"{hours}h {minutes}m"
