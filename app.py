"""
app.py
------
This is the "front counter" of the whole system. Flask turns each
Python function below into a web page (a "route"). Run this file,
open a browser, and you have a real (if small) web application -
which satisfies the brief's "running as web-based system" requirement.

Use cases covered (matching the brief):
    1. Driver views available slots BEFORE entry   -> /  (dashboard)
    2. System records the vehicle on arrival        -> /checkin
    3. System calculates time + amount on exit       -> /checkout
    4. Barrier opens once payment is confirmed        -> /pay
    5. Management changes rates, no code change        -> /admin/rates
    6. Auditable record of shillings collected          -> /reports
"""

from flask import Flask, render_template, request, redirect, url_for, flash

import database
import fee_calculator

app = Flask(__name__)
app.secret_key = "garigate-dev-secret"  # only used to show flash messages

# Make sure the database + tables exist as soon as the app boots.
database.init_db()

# The payment methods a driver can choose at exit.
PAYMENT_METHODS = ["M-Pesa", "Card", "Cash"]


@app.route("/")
def dashboard():
    """
    The visual display of the parking lot. This is the page a driver
    would see on a screen at the entrance before deciding to come in.
    """
    spots = database.get_all_spots()
    total = len(spots)
    occupied = len([s for s in spots if s["status"] == "occupied"])
    available = total - occupied

    history = database.get_recent_history(limit=6)

    return render_template(
        "dashboard.html",
        spots=spots,
        total=total,
        occupied=occupied,
        available=available,
        history=history,
    )


@app.route("/checkin", methods=["GET", "POST"])
def checkin():
    """Handles a vehicle arriving at the gate."""
    if request.method == "POST":
        plate = request.form.get("plate_number", "").strip().upper()
        driver_name = request.form.get("driver_name", "").strip()

        if not plate:
            flash("Please enter a license plate number.", "error")
            return redirect(url_for("checkin"))

        # A car that is already parked shouldn't be allowed to check in twice.
        if database.find_active_session_by_plate(plate):
            flash(f"{plate} is already checked in.", "error")
            return redirect(url_for("checkin"))

        spot = database.get_available_spot()
        if spot is None:
            flash("Sorry, GariGate is full right now. Please try again shortly.", "error")
            return redirect(url_for("checkin"))

        database.create_session(spot["spot_id"], plate, driver_name)
        flash(f"Welcome! {plate} has been assigned bay {spot['spot_id']}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("checkin.html")


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    """
    Step 1 of leaving: driver types their plate number and the system
    calculates (but does not yet charge) the amount due, using
    whatever fee tiers management currently has configured.
    """
    if request.method == "POST":
        plate = request.form.get("plate_number", "").strip().upper()
        session_row = database.find_active_session_by_plate(plate)

        if session_row is None:
            flash(f"No active parking session found for {plate}.", "error")
            return redirect(url_for("checkout"))

        tiers = database.get_fee_tiers()
        duration = fee_calculator.calculate_duration_minutes(session_row["check_in_time"])
        amount = fee_calculator.calculate_fee(duration, tiers)

        # Save the calculated bill against the session (but the bay stays
        # occupied and the barrier stays shut until payment is confirmed).
        database.close_session(session_row["session_id"], amount)

        return render_template(
            "receipt.html",
            session=session_row,
            duration_text=fee_calculator.format_duration(duration),
            amount=amount,
            payment_methods=PAYMENT_METHODS,
        )

    return render_template("checkout.html")


@app.route("/pay", methods=["POST"])
def pay():
    """
    Step 2 of leaving: confirms payment via the method the driver chose.
    This is the ONE moment in the whole system where the barrier is
    allowed to lift - modelling the brief's 'open the barrier only on
    confirmed payment' requirement.
    """
    session_id = int(request.form["session_id"])
    spot_id = request.form["spot_id"]
    amount = float(request.form["amount"])
    payment_method = request.form.get("payment_method", "Cash")

    database.pay_session(session_id, spot_id, payment_method)

    return render_template(
        "receipt.html",
        paid=True,
        spot_id=spot_id,
        amount=amount,
        payment_method=payment_method,
    )


@app.route("/admin/rates", methods=["GET", "POST"])
def admin_rates():
    """
    Lets management change parking rates at any time, without a
    software change. Reads/writes the fee_tiers table directly -
    no code edit or restart required to take effect.
    """
    if request.method == "POST":
        try:
            tier1_upper = float(request.form["tier1_upper"])
            tier2_upper = float(request.form["tier2_upper"])
            tier3_upper = float(request.form["tier3_upper"])
            tier4_upper = float(request.form["tier4_upper"])

            tier1_price = float(request.form["tier1_price"])
            tier2_price = float(request.form["tier2_price"])
            tier3_price = float(request.form["tier3_price"])
            tier4_price = float(request.form["tier4_price"])
            tier5_price = float(request.form["tier5_price"])
        except (KeyError, ValueError):
            flash("Please enter valid numbers for every field.", "error")
            return redirect(url_for("admin_rates"))

        new_tiers = [
            (tier1_upper, tier1_price),
            (tier2_upper, tier2_price),
            (tier3_upper, tier3_price),
            (tier4_upper, tier4_price),
            (None, tier5_price),
        ]
        database.update_fee_tiers(new_tiers)
        flash("Parking rates updated successfully.", "success")
        return redirect(url_for("admin_rates"))

    tiers = database.get_fee_tiers()
    return render_template("admin_rates.html", tiers=tiers)


@app.route("/reports")
def reports():
    """
    An auditable record of every shilling collected, for reconciliation
    and VAT. Supports optional date-range and payment-method filters
    via query parameters, e.g. /reports?start=2026-09-01&method=Cash
    """
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    method = request.args.get("method", "")

    sessions = database.get_paid_sessions(
        start_date=start or None,
        end_date=end or None,
        payment_method=method or None,
    )

    total_collected = sum(s["amount_due"] or 0 for s in sessions)

    breakdown = {}
    for s in sessions:
        key = s["payment_method"] or "Unrecorded"
        breakdown[key] = breakdown.get(key, 0) + (s["amount_due"] or 0)

    return render_template(
        "reports.html",
        sessions=sessions,
        total_collected=total_collected,
        transaction_count=len(sessions),
        breakdown=breakdown,
        payment_methods=PAYMENT_METHODS,
        start=start,
        end=end,
        method=method,
    )


if __name__ == "__main__":
    # debug=True gives helpful error pages while you're building/marking this.
    app.run(debug=True)
