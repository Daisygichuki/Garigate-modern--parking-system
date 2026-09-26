# Algorithms & Data Structures — GariGate

This document explains the data structures and algorithms used in the
GariGate parking system, and why each one was chosen.

## 1. Data structures used

| Data structure | Where it's used | Why this one |
|---|---|---|
| **Relational tables (SQLite)** | `spots` and `sessions` tables in `database.py` | A real database, not just variables in memory, so data survives a restart. Each row is a fixed-size record — exactly what a relational table is built for. |
| **Dictionary (hash map)** | `ZONE_LAYOUT = {"A": 4, "B": 4, "C": 4}` in `database.py`; `sqlite3.Row` objects (accessed like `spot["status"]`) | O(1) average lookup by key — instantly get a zone's bay count or a row's column value without scanning anything. |
| **List of tuples (a lookup table)** | `FEE_TIERS = [(30, 0), (120, 50), (240, 100), (360, 300), (inf, 500)]` in `fee_calculator.py` | An ordered sequence of (threshold, price) pairs. Storing the pricing rules as data (not as a long chain of `if/elif`) means the business rule can change without touching the algorithm around it. |
| **String** | License plates, driver names, ISO timestamps (`"2026-09-26T14:05:00"`) | Plates and names are naturally text; ISO-format timestamps are used because they sort and compare correctly as plain strings. |

## 2. Algorithms used

### 2.1 Linear search — finding an available bay
**Where:** `database.get_available_spot()`

```python
SELECT * FROM spots WHERE status = 'available' ORDER BY spot_id LIMIT 1
```

Conceptually this is a **linear search**: scan the bays in order and
stop at the first one whose status is `available`.

- **Time complexity:** O(n), where n = number of bays.
- **Why linear search is fine here:** a parking lot has a small,
  fixed number of bays (12 in this build). For n this small, a
  simple scan is both fast enough and far easier to read/mark than a
  more complex search structure would be.

### 2.2 Linear search — finding a vehicle's active session
**Where:** `database.find_active_session_by_plate()`

Same idea as 2.1, but scanning `sessions` for a row matching a given
plate number where `check_out_time IS NULL` (i.e. the car hasn't left
yet).
- **Time complexity:** O(m), where m = number of session records.
- **Note:** SQLite internally can use an index to speed this up as
  the table grows, but at the algorithmic level this is still a
  search for a matching key — the same concept as 2.1.

### 2.3 Tiered lookup ("bracket" algorithm) — fee calculation
**Where:** `fee_calculator.calculate_fee()`

```python
for upper_limit, price in FEE_TIERS:
    if duration_minutes <= upper_limit:
        return price
```

This walks the `FEE_TIERS` list **in ascending order** and returns
the price for the first bracket the duration fits into. This is a
classic **step function / bracket-matching algorithm** — the same
pattern used for things like income tax brackets or shipping-cost
tiers.

- **Time complexity:** O(k), where k = number of tiers (always 5,
  regardless of how many cars use the system) — effectively
  constant time in practice.
- **Worked example:** a car parked for 150 minutes:
  - 150 > 30 → not free
  - 150 > 120 → not the KSh 50 tier
  - 150 ≤ 240 → **matches this tier → returns KSh 100**

### 2.4 Date/time arithmetic — duration calculation
**Where:** `fee_calculator.calculate_duration_minutes()`

```python
delta = check_out - check_in
return delta.total_seconds() / 60
```

Two timestamps are subtracted to get a `timedelta`, which is then
converted to minutes. This is a direct arithmetic operation rather
than a search — included here because it feeds directly into the
tiered lookup above (2.3).

### 2.5 CRUD operations (Create, Read, Update)
**Where:** throughout `database.py`

The whole system is built around the four standard database
operations:
- **Create** — `create_session()` inserts a new row when a car
  arrives.
- **Read** — `get_all_spots()`, `get_recent_history()` fetch data
  for display.
- **Update** — `close_session()` and `pay_session()` modify existing
  rows (billing a session, then marking it paid and freeing the bay).
- *(Delete is not used — completed sessions are kept as permanent
  history/receipts rather than removed.)*

## 3. Why these choices fit the brief

The project asks for identified **modules, algorithms, and
databases**. Splitting the project into `database.py` (data),
`fee_calculator.py` (business logic/algorithm), and `app.py` (routes)
keeps each concern isolated, so the algorithm above can be pointed to
directly and explained/marked on its own, separate from the web
plumbing around it.
