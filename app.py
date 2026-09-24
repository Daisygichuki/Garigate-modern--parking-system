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
    4. Barrier opens once payment is confirmed        -> /pay/<id>
"""

from flask import Flask, render_template, request, redirect, url_for, flash

import database
import fee_calculator

app = Flask(__name__)
app.secret_key = "garigate-dev-secret"  # only used to show flash messages

# Make sure the database + tables exist as soon as the app boots.
database.init_db()


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
    calculates (but does not yet charge) the amount due.
    """
    if request.method == "POST":
        plate = request.form.get("plate_number", "").strip().upper()
        session_row = database.find_active_session_by_plate(plate)

        if session_row is None:
            flash(f"No active parking session found for {plate}.", "error")
            return redirect(url_for("checkout"))

        duration = fee_calculator.calculate_duration_minutes(session_row["check_in_time"])
        amount = fee_calculator.calculate_fee(duration)

        # Save the calculated bill against the session (but the bay stays
        # occupied and the barrier stays shut until payment is confirmed).
        database.close_session(session_row["session_id"], amount)

        return render_template(
            "receipt.html",
            session=session_row,
            duration_text=fee_calculator.format_duration(duration),
            amount=amount,
        )

    return render_template("checkout.html")


@app.route("/pay/<int:session_id>/<spot_id>/<float:amount>")
def pay(session_id, spot_id, amount):
    """
    Step 2 of leaving: confirms payment. This is the ONE moment in the
    whole system where the barrier is allowed to lift - modelling the
    brief's 'barrier opens on payment of parking fees' requirement.
    """
    database.pay_session(session_id, spot_id)
    return render_template("receipt.html", paid=True, spot_id=spot_id, amount=amount)


if __name__ == "__main__":
    # debug=True gives helpful error pages while you're building/marking this.
    app.run(debug=True)
