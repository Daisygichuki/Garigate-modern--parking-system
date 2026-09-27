# GariGate — Automated Parking System

A modern, web-based parking management system . "Gari" is Swahili for car.

## Use cases implemented

1. **View available slots before entry** — the home page (`/`) is a
   live visual map of every bay, colour-coded available/occupied.
2. **Record a vehicle on arrival** — `/checkin` assigns the next free
   bay and timestamps the arrival.
3. **Calculate time and amount on exit** — `/checkout` looks up the
   vehicle, works out how long it was parked, and applies the current
   fee tiers (see below).
4. **Collect payment and open barrier only on confirmation** — the
   checkout ticket asks for a payment method (M-Pesa, Card, or Cash);
   `/pay` is the only route that marks a ticket as paid, frees the
   bay, and animates the barrier open.
5. **Management can change rates without a software change** —
   `/admin/rates` reads and writes the fee tiers directly in the
   database. No code edit or restart is needed for a new rate to
   apply to the next vehicle checked out.
6. **Auditable record of every shilling collected** — `/reports`
   lists every paid transaction with plate, bay, amount and payment
   method, filterable by date range and payment method, with running
   totals for reconciliation and VAT purposes.

## Fee structure

The default rates, editable at any time via `/admin/rates`:

| Duration            | Fee        |
|----------------------|-----------|
| Up to 30 minutes      | Free      |
| Up to 2 hours          | KSh 50   |
| Up to 4 hours          | KSh 100  |
| Up to 6 hours          | KSh 300  |
| Over 6 hours            | KSh 500  |

## Project structure

```
garigate/
├── app.py              # Flask routes (the web pages)
├── database.py          # All SQLite reads/writes
├── fee_calculator.py     # Billing logic, kept separate & testable
├── requirements.txt
├── templates/            # HTML pages (Jinja2)
│   ├── base.html
│   ├── dashboard.html
│   ├── checkin.html
│   ├── checkout.html
│   └── receipt.html
└── static/
    └── style.css         # Custom visual design
```

`garigate.db` (the SQLite database file) is created automatically the
first time you run the app.

## How to run it

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## How to demo it 

1. Open the home page — show the empty lot (all bays "available").
2. Go to **Check In**, enter a plate number (e.g. `KDA 456J`) — a bay
   gets assigned and turns "occupied" on the dashboard.
3. Go to **Check Out**, enter the same plate — you get a ticket
   showing time parked and the fee.
4. Click **Pay & Open Barrier** — the barrier animation opens and the
   bay becomes available again on the dashboard.

## Publishing to GitHub

```bash
cd garigate
git init
git add .
git commit -m "GariGate parking system"
git branch -M main
git remote add origin <your-empty-github-repo-url>
git push -u origin main
```
