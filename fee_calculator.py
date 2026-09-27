"""
fee_calculator.py
------------------
Keeping the billing logic in its OWN small file (instead of burying it
inside app.py) is good practice: it is the single "source of truth"
for how much a driver owes, it's easy to unit-test on its own, and a
lecturer marking algorithms/logic can find it in one glance.

The fee TIERS themselves now live in the database (see database.py's
fee_tiers table), so management can change rates without a software
change. This file only holds the ALGORITHM that applies whatever
tiers it's given - it no longer hardcodes the prices itself.
"""

from datetime import datetime


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


def calculate_fee(duration_minutes, tiers):
    """
    Looks up the correct tier for a given duration and returns the price.

    tiers: a list of (upper_minutes, price) tuples, in ascending order,
    as returned by database.get_fee_tiers(). The final tier's
    upper_minutes is None, meaning "everything above the previous tier".
    """
    for upper_minutes, price in tiers:
        if upper_minutes is None or duration_minutes <= upper_minutes:
            return price
    # Should never be reached if the tiers list ends with a None tier,
    # but kept as a safety net.
    return tiers[-1][1]


def format_duration(duration_minutes):
    """Turns '125.4' minutes into a friendly '2h 5m' style string for the UI."""
    total_minutes = int(duration_minutes)
    hours, minutes = divmod(total_minutes, 60)
    if hours == 0:
        return f"{minutes}m"
    return f"{hours}h {minutes}m"
